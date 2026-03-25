from __future__ import annotations

from hashlib import md5
import importlib
import importlib.util
from pathlib import Path
import re
import shutil
from typing import Callable, Protocol

from .ai import (
    DeterministicVisionLanguageAnalyzer,
    VisionLanguageAnalyzer,
    analyze_asset_segments,
    build_segment_evidence,
    default_vision_language_analyzer,
    get_ai_runtime_stats,
    load_ai_analysis_config,
)
from .deduplication import (
    apply_deduplication_results,
    deduplicate_segments,
    get_dedup_threshold,
    is_deduplication_enabled,
)
from .domain import (
    Asset,
    CandidateSegment,
    PrefilterDecision,
    ProjectData,
    ProjectMeta,
    TakeRecommendation,
    Timeline,
    TimelineItem,
)
from .media import FFprobeRunner, build_assets_from_matches, discover_media_files, match_media_files
from .prefilter import (
    aggregate_segment_prefilter,
    build_prefilter_segments,
    sample_asset_signals,
    sample_audio_signals,
    sample_timestamps,
)
from .scoring import score_segment


class SceneDetector(Protocol):
    def detect(self, asset: Asset) -> list[tuple[float, float]]:
        ...


class TranscriptProvider(Protocol):
    def excerpt(self, asset: Asset, start_sec: float, end_sec: float) -> str:
        ...


StatusCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int, Asset], None]


class NoOpTranscriptProvider:
    def excerpt(self, asset: Asset, start_sec: float, end_sec: float) -> str:
        return ""


class PySceneDetectAdapter:
    def detect(self, asset: Asset) -> list[tuple[float, float]]:
        spec = importlib.util.find_spec("scenedetect")
        if spec is None:
            return fallback_segments(asset.duration_sec)

        scenedetect = importlib.import_module("scenedetect")
        detectors = importlib.import_module("scenedetect.detectors")

        video = scenedetect.open_video(asset.proxy_path)
        manager = scenedetect.SceneManager()
        manager.add_detector(detectors.ContentDetector())
        manager.detect_scenes(video)

        scenes = manager.get_scene_list()
        if not scenes:
            return fallback_segments(asset.duration_sec)

        return [
            (round(start.get_seconds(), 3), round(end.get_seconds(), 3))
            for start, end in scenes
        ]


class FasterWhisperAdapter:
    def __init__(self, model_size: str = "small") -> None:
        self.model_size = model_size
        self._model = None
        self._cache: dict[str, list[tuple[float, float, str]]] = {}

    def excerpt(self, asset: Asset, start_sec: float, end_sec: float) -> str:
        spec = importlib.util.find_spec("faster_whisper")
        if spec is None:
            return ""

        if self._model is None:
            module = importlib.import_module("faster_whisper")
            self._model = module.WhisperModel(self.model_size)

        if asset.proxy_path not in self._cache:
            segments, _info = self._model.transcribe(asset.proxy_path, vad_filter=True)
            self._cache[asset.proxy_path] = [
                (float(segment.start), float(segment.end), segment.text.strip()) for segment in segments
            ]

        lines = [
            text
            for segment_start, segment_end, text in self._cache[asset.proxy_path]
            if segment_end >= start_sec and segment_start <= end_sec and text
        ]
        return " ".join(lines).strip()


def inspect_runtime_capabilities() -> dict[str, bool]:
    return {
        "ffprobe": shutil.which("ffprobe") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "scenedetect": importlib.util.find_spec("scenedetect") is not None,
        "faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
        "fastapi": importlib.util.find_spec("fastapi") is not None,
    }


def build_project_from_media_roots(
    *,
    project_name: str,
    media_roots: list[str],
    story_prompt: str,
    probe_runner: FFprobeRunner | None = None,
    scene_detector: SceneDetector | None = None,
    transcript_provider: TranscriptProvider | None = None,
    segment_analyzer: VisionLanguageAnalyzer | None = None,
    artifacts_root: str | Path | None = None,
    status_callback: StatusCallback | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ProjectData:
    discovered = discover_media_files(media_roots, probe_runner=probe_runner)
    if status_callback is not None:
        status_callback(f"Discovered {len(discovered)} video files.")
    matches = match_media_files(discovered)
    assets = build_assets_from_matches(matches)
    if status_callback is not None:
        status_callback(f"Matched {len(assets)} source assets to process.")
    project_id = slugify(project_name)
    return analyze_assets(
        project=ProjectMeta(
            id=project_id,
            name=project_name,
            story_prompt=story_prompt,
            status="draft",
            media_roots=media_roots,
        ),
        assets=assets,
        scene_detector=scene_detector,
        transcript_provider=transcript_provider,
        segment_analyzer=segment_analyzer,
        artifacts_root=artifacts_root,
        status_callback=status_callback,
        progress_callback=progress_callback,
    )


def analyze_assets(
    *,
    project: ProjectMeta,
    assets: list[Asset],
    scene_detector: SceneDetector | None = None,
    transcript_provider: TranscriptProvider | None = None,
    segment_analyzer: VisionLanguageAnalyzer | None = None,
    artifacts_root: str | Path | None = None,
    status_callback: StatusCallback | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ProjectData:
    detector = scene_detector or PySceneDetectAdapter()
    transcriber = transcript_provider or NoOpTranscriptProvider()
    ai_config = load_ai_analysis_config()
    analyzer = segment_analyzer or default_vision_language_analyzer(
        artifacts_root=artifacts_root,
        analysis_config=ai_config,
    )
    deterministic_analyzer = DeterministicVisionLanguageAnalyzer()
    candidate_segments: list[CandidateSegment] = []
    total_prefilter_samples = 0
    total_prefilter_shortlisted = 0
    total_vlm_targets = 0
    total_filtered_before_vlm = 0
    total_audio_signal_assets = 0
    total_deduplicated_segments = 0
    deduplication_enabled = is_deduplication_enabled()
    dedup_threshold = get_dedup_threshold()

    total_assets = len(assets)
    for asset_index, asset in enumerate(assets, start=1):
        base_ranges = detector.detect(asset) if asset.duration_sec > 0 else [(0.0, 4.0)]
        if not base_ranges:
            base_ranges = fallback_segments(asset.duration_sec)
        timestamps = sample_timestamps(asset.duration_sec)
        prefilter_signals = sample_asset_signals(asset, timestamps=timestamps)
        audio_signals = sample_audio_signals(asset, timestamps)
        total_prefilter_samples += len(prefilter_signals)
        if any(sig.source == "ffmpeg" for sig in audio_signals):
            total_audio_signal_assets += 1
        segment_ranges = build_prefilter_segments(
            asset=asset,
            base_ranges=base_ranges,
            signals=prefilter_signals,
            audio_signals=audio_signals,
            top_windows=2 if ai_config.mode == "fast" else 3,
        )
        if not segment_ranges:
            segment_ranges = fallback_segments(asset.duration_sec)

        asset_segments: list[CandidateSegment] = []
        for index, (start_sec, end_sec) in enumerate(segment_ranges, start=1):
            excerpt = transcriber.excerpt(asset, start_sec, end_sec).strip() if asset.has_speech else ""
            analysis_mode = "speech" if excerpt else "visual"
            prefilter_snapshot = aggregate_segment_prefilter(
                signals=prefilter_signals,
                start_sec=start_sec,
                end_sec=end_sec,
                audio_signals=audio_signals,
            )
            metrics = synthesize_quality_metrics(
                asset,
                start_sec,
                end_sec,
                analysis_mode,
                prefilter_snapshot=prefilter_snapshot["metrics_snapshot"],
            )
            asset_segments.append(
                CandidateSegment(
                    id=f"{asset.id}-segment-{index:02d}",
                    asset_id=asset.id,
                    start_sec=round(start_sec, 3),
                    end_sec=round(end_sec, 3),
                    analysis_mode=analysis_mode,
                    transcript_excerpt=excerpt,
                    description=describe_segment(asset, start_sec, end_sec, excerpt, metrics),
                    quality_metrics=metrics,
                    prefilter=PrefilterDecision(
                        score=float(prefilter_snapshot["score"]),
                        shortlisted=False,
                        filtered_before_vlm=False,
                        selection_reason="Segment has not been evaluated for VLM shortlist yet.",
                        sampled_frame_count=int(prefilter_snapshot["sampled_frame_count"]),
                        sampled_frame_timestamps_sec=list(prefilter_snapshot["sampled_frame_timestamps_sec"]),
                        top_frame_timestamps_sec=list(prefilter_snapshot["top_frame_timestamps_sec"]),
                        metrics_snapshot=dict(prefilter_snapshot["metrics_snapshot"]),
                    ),
                )
            )

        # Deduplication pass: runs after prefilter scoring and before shortlist selection
        if deduplication_enabled and len(asset_segments) > 1:
            # Build frame signals per segment based on time window
            frame_signals_by_id = {}
            for segment in asset_segments:
                matching_signals = [
                    signal
                    for signal in prefilter_signals
                    if segment.start_sec <= signal.timestamp_sec <= segment.end_sec
                ]
                # If no signals fall within segment, use the nearest signal for context
                if not matching_signals and prefilter_signals:
                    center = (segment.start_sec + segment.end_sec) / 2.0
                    nearest = min(
                        prefilter_signals,
                        key=lambda signal: abs(signal.timestamp_sec - center),
                    )
                    matching_signals = [nearest]
                frame_signals_by_id[segment.id] = matching_signals

            dedup_results = deduplicate_segments(
                segments=asset_segments,
                frame_signals_by_id=frame_signals_by_id,
                similarity_threshold=dedup_threshold,
            )
            apply_deduplication_results(asset_segments, dedup_results)
            total_deduplicated_segments += sum(1 for deduplicated, _ in dedup_results.values() if deduplicated)

        # Filter out deduplicated segments from further processing
        active_segments = [s for s in asset_segments if not (s.prefilter and s.prefilter.deduplicated)]

        prefilter_shortlist_ids = select_prefilter_shortlist_ids(
            asset=asset,
            segments=active_segments,
            max_segments_per_asset=ai_config.max_segments_per_asset,
            mode=ai_config.mode,
        )
        ai_target_ids = select_ai_target_segment_ids(
            asset=asset,
            segments=active_segments,
            analyzer=analyzer,
            max_segments_per_asset=ai_config.max_segments_per_asset,
            mode=ai_config.mode,
        )
        total_prefilter_shortlisted += len(prefilter_shortlist_ids)
        total_vlm_targets += len(ai_target_ids)
        ai_tasks: list[tuple[CandidateSegment, object, str]] = []

        for index, segment in enumerate(asset_segments):
            if segment.prefilter is not None:
                segment.prefilter.shortlisted = segment.id in prefilter_shortlist_ids
                segment.prefilter.filtered_before_vlm = analyzer.requires_keyframes and segment.id not in ai_target_ids
                segment.prefilter.selection_reason = describe_prefilter_selection(
                    score=segment.prefilter.score,
                    shortlisted=segment.prefilter.shortlisted,
                    filtered_before_vlm=segment.prefilter.filtered_before_vlm,
                )
                if segment.prefilter.filtered_before_vlm:
                    total_filtered_before_vlm += 1
            evidence = build_segment_evidence(
                asset=asset,
                segment=segment,
                asset_segments=asset_segments,
                segment_index=index,
                story_prompt=project.story_prompt,
                artifacts_root=artifacts_root,
                extract_keyframes=analyzer.requires_keyframes and segment.id in ai_target_ids,
                max_keyframes_per_segment=ai_config.max_keyframes_per_segment,
                keyframe_max_width=ai_config.keyframe_max_width,
            )
            segment.evidence_bundle = evidence
            if segment.id in ai_target_ids:
                ai_tasks.append((segment, evidence, project.story_prompt))
            else:
                understanding = deterministic_analyzer.analyze(
                    asset=asset,
                    segment=segment,
                    evidence=evidence,
                    story_prompt=project.story_prompt,
                )
                if analyzer.requires_keyframes and ai_config.mode == "fast":
                    understanding.risk_flags = sorted(set([*understanding.risk_flags, "ai_skipped_fast_mode"]))
                    understanding.rationale = (
                        f"{understanding.rationale} AI was skipped for this segment in fast mode because "
                        "it was not in the per-asset shortlist."
                    )
                segment.ai_understanding = understanding

        ai_results = analyze_asset_segments(
            analyzer=analyzer,
            asset=asset,
            tasks=ai_tasks,
            concurrency=ai_config.concurrency,
        )
        for segment in asset_segments:
            if segment.id in ai_results:
                segment.ai_understanding = ai_results[segment.id]
        candidate_segments.extend(asset_segments)
        if progress_callback is not None:
            progress_callback(asset_index, total_assets, asset)

    project.analysis_summary = {
        "prefilter_sample_count": total_prefilter_samples,
        "candidate_segment_count": len(candidate_segments),
        "deduplicated_segment_count": total_deduplicated_segments if deduplication_enabled else 0,
        "prefilter_shortlisted_count": total_prefilter_shortlisted,
        "vlm_target_count": total_vlm_targets,
        "filtered_before_vlm_count": total_filtered_before_vlm,
        "audio_signal_asset_count": total_audio_signal_assets,
        "audio_silent_asset_count": total_assets - total_audio_signal_assets,
    }
    ai_runtime_stats = get_ai_runtime_stats(analyzer)
    project.analysis_summary.update(
        {
            "ai_live_segment_count": ai_runtime_stats.live_segment_count,
            "ai_cached_segment_count": ai_runtime_stats.cached_segment_count,
            "ai_fallback_segment_count": ai_runtime_stats.fallback_segment_count,
            "ai_live_request_count": ai_runtime_stats.live_request_count,
        }
    )
    if status_callback is not None:
        if deduplication_enabled and total_deduplicated_segments > 0:
            status_callback(
                f"Deduplication: {total_deduplicated_segments} near-duplicate segments eliminated."
            )
        status_callback(
            "Prefilter sampled "
            f"{total_prefilter_samples} frames and shortlisted {total_prefilter_shortlisted}/"
            f"{len(candidate_segments)} segments before VLM analysis."
        )
        status_callback(
            f"Audio signal: {total_audio_signal_assets}/{total_assets} assets had audio coverage."
        )
        status_callback(f"VLM target segments: {total_vlm_targets}.")
        status_callback(
            "AI outcomes: "
            f"live={ai_runtime_stats.live_segment_count}, "
            f"cache={ai_runtime_stats.cached_segment_count}, "
            f"fallback={ai_runtime_stats.fallback_segment_count}, "
            f"skipped={total_filtered_before_vlm}."
        )

    take_recommendations = build_take_recommendations(assets, candidate_segments)
    timeline = build_timeline(take_recommendations, candidate_segments, assets)

    return ProjectData(
        project=project,
        assets=assets,
        candidate_segments=candidate_segments,
        take_recommendations=take_recommendations,
        timeline=timeline,
    )


def build_take_recommendations(
    assets: list[Asset],
    candidate_segments: list[CandidateSegment],
) -> list[TakeRecommendation]:
    asset_by_id = {asset.id: asset for asset in assets}
    takes: list[TakeRecommendation] = []

    for asset in assets:
        asset_segments = [segment for segment in candidate_segments if segment.asset_id == asset.id]
        ranked_segments = sorted(
            asset_segments,
            key=lambda segment: score_segment(asset_by_id[segment.asset_id], segment).total,
            reverse=True,
        )
        selected_segments = select_segments_for_asset(asset, ranked_segments)

        for index, segment in enumerate(asset_segments, start=1):
            breakdown = score_segment(asset, segment)
            is_best_take = segment.id in {selected.id for selected in selected_segments}
            takes.append(
                TakeRecommendation(
                    id=f"{asset.id}-take-{index:02d}",
                    candidate_segment_id=segment.id,
                    title=make_take_title(asset, segment, breakdown.analysis_mode, is_best_take),
                    is_best_take=is_best_take,
                    selection_reason=make_selection_reason(asset, segment, breakdown.total, is_best_take),
                    score_technical=breakdown.technical,
                    score_semantic=breakdown.semantic,
                    score_story=breakdown.story,
                    score_total=breakdown.total,
                )
            )

    return takes


def build_timeline(
    take_recommendations: list[TakeRecommendation],
    candidate_segments: list[CandidateSegment],
    assets: list[Asset],
) -> Timeline:
    best_takes = [take for take in take_recommendations if take.is_best_take]
    best_takes.sort(key=lambda take: take.score_total, reverse=True)

    segment_by_id = {segment.id: segment for segment in candidate_segments}
    asset_by_id = {asset.id: asset for asset in assets}
    best_takes.sort(
        key=lambda take: (
            asset_order(asset_by_id, segment_by_id[take.candidate_segment_id].asset_id),
            segment_by_id[take.candidate_segment_id].start_sec,
            -take.score_total,
        )
    )

    items: list[TimelineItem] = []
    for index, take in enumerate(best_takes):
        segment = segment_by_id[take.candidate_segment_id]
        asset = asset_by_id[segment.asset_id]
        duration = segment.end_sec - segment.start_sec
        trimmed_duration = min(duration, suggested_timeline_duration(segment))
        items.append(
            TimelineItem(
                id=f"timeline-item-{index + 1:02d}",
                take_recommendation_id=take.id,
                order_index=index,
                trim_in_sec=0.0,
                trim_out_sec=round(trimmed_duration, 3),
                label=timeline_label(index, len(best_takes), segment.analysis_mode),
                notes=timeline_note(segment),
                source_asset_path=asset.source_path,
                source_reel=asset.interchange_reel_name,
            )
        )

    summary = summarize_story(best_takes, segment_by_id)
    return Timeline(
        id="timeline-main",
        version=1,
        story_summary=summary,
        items=items,
    )


def fallback_segments(duration_sec: float) -> list[tuple[float, float]]:
    usable_duration = max(duration_sec, 6.0)
    if usable_duration <= 8.0:
        return [(0.0, round(usable_duration, 3))]

    windows = []
    window_size = 5.5
    stride = max(2.75, min(6.0, usable_duration / 3))
    start = 0.0
    while start < usable_duration and len(windows) < 4:
        end = min(usable_duration, start + window_size)
        if end - start >= 2.5:
            windows.append((round(start, 3), round(end, 3)))
        if end >= usable_duration:
            break
        start += stride

    if not windows:
        return [(0.0, round(usable_duration, 3))]

    return windows


def synthesize_quality_metrics(
    asset: Asset,
    start_sec: float,
    end_sec: float,
    analysis_mode: str,
    prefilter_snapshot: dict[str, float] | None = None,
) -> dict[str, float]:
    if prefilter_snapshot and prefilter_snapshot.get("prefilter_score", 0.0) > 0.0:
        duration = max(0.1, end_sec - start_sec)
        duration_fit = clamp(1.0 - abs(duration - 5.5) / 7.0)
        sharpness = clamp(prefilter_snapshot.get("sharpness", 0.0))
        stability = clamp(prefilter_snapshot.get("stability", 0.0))
        subject_clarity = clamp(prefilter_snapshot.get("subject_clarity", 0.0))
        motion_energy = clamp(prefilter_snapshot.get("motion_energy", 0.0))
        visual_novelty = clamp(prefilter_snapshot.get("visual_novelty", 0.0))
        prefilter_score = clamp(prefilter_snapshot.get("prefilter_score", 0.0))
        hook_strength = clamp((prefilter_score * 0.5) + (subject_clarity * 0.25) + (motion_energy * 0.25))
        story_alignment = clamp((prefilter_score * 0.45) + (visual_novelty * 0.25) + (subject_clarity * 0.2) + (duration_fit * 0.1))
        audio_energy = clamp(prefilter_snapshot.get("audio_energy", 0.0))
        speech_ratio = clamp(prefilter_snapshot.get("speech_ratio", 0.0))
        return {
            "sharpness": round(sharpness, 4),
            "stability": round(stability, 4),
            "visual_novelty": round(visual_novelty, 4),
            "subject_clarity": round(subject_clarity, 4),
            "motion_energy": round(motion_energy, 4),
            "duration_fit": round(duration_fit, 4),
            "audio_energy": round(audio_energy, 4),
            "speech_ratio": round(speech_ratio, 4),
            "hook_strength": round(hook_strength, 4),
            "story_alignment": round(story_alignment, 4),
        }

    duration = max(0.1, end_sec - start_sec)
    seed = seeded_value(asset.id, start_sec, end_sec)
    variation = seeded_value(asset.name, end_sec, start_sec)
    duration_fit = clamp(1.0 - abs(duration - 5.5) / 7.0)
    motion_energy = clamp(0.45 + seed * 0.45)
    visual_novelty = clamp(0.4 + variation * 0.5)
    subject_clarity = clamp(0.58 + seeded_value(asset.proxy_path, duration, start_sec) * 0.32)
    hook_strength = clamp(0.52 + seeded_value(asset.interchange_reel_name, end_sec, duration) * 0.38)
    story_alignment = clamp(0.55 + seeded_value(asset.source_path, start_sec, duration) * 0.35)

    return {
        "sharpness": round(clamp(0.62 + seed * 0.28), 4),
        "stability": round(clamp(0.56 + variation * 0.26), 4),
        "visual_novelty": round(visual_novelty, 4),
        "subject_clarity": round(subject_clarity, 4),
        "motion_energy": round(motion_energy, 4),
        "duration_fit": round(duration_fit, 4),
        "audio_energy": 0.0,
        "speech_ratio": 0.0,
        "hook_strength": round(hook_strength, 4),
        "story_alignment": round(story_alignment, 4),
    }


def describe_segment(
    asset: Asset,
    start_sec: float,
    end_sec: float,
    transcript_excerpt: str,
    metrics: dict[str, float],
) -> str:
    duration = round(end_sec - start_sec, 2)

    if transcript_excerpt:
        return (
            f"{asset.name} yields a spoken beat around {start_sec:.2f}s to {end_sec:.2f}s. "
            f"The excerpt carries usable narrative value, and the {duration:.2f}s duration is well suited for a rough cut."
        )

    shot_role = visual_role(metrics)
    return (
        f"{asset.name} provides a {shot_role} moment from {start_sec:.2f}s to {end_sec:.2f}s. "
        f"It reads as strong silent coverage because the framing stays clear while the visual rhythm remains usable over {duration:.2f}s."
    )


def visual_role(metrics: dict[str, float]) -> str:
    if metrics["visual_novelty"] >= 0.8 and metrics["motion_energy"] >= 0.7:
        return "dynamic establishing"
    if metrics["motion_energy"] < 0.45:
        return "calm texture"
    if metrics["subject_clarity"] >= 0.8:
        return "clear detail"
    return "transition-ready"


def make_take_title(asset: Asset, segment: CandidateSegment, analysis_mode: str, is_best_take: bool) -> str:
    title_prefix = "Best" if is_best_take else "Candidate"
    role = "Dialogue" if analysis_mode == "speech" else "Visual"
    return f"{title_prefix} {role}: {asset.name}"


def make_selection_reason(
    asset: Asset,
    segment: CandidateSegment,
    total_score: float,
    is_best_take: bool,
) -> str:
    if is_best_take and segment.analysis_mode == "speech":
        return (
            f"Selected because {asset.name} contributes a spoken narrative beat with a {round(total_score * 100):d}/100 composite score."
        )

    if is_best_take:
        return (
            f"Selected because {asset.name} works as silent b-roll with strong visual novelty and pacing at {round(total_score * 100):d}/100."
        )

    return (
        f"Kept as a backup candidate; the segment is usable but less distinctive for the story than the higher-ranked alternative in this clip."
    )


def select_segments_for_asset(asset: Asset, segments: list[CandidateSegment]) -> list[CandidateSegment]:
    if not segments:
        return []

    selected: list[CandidateSegment] = []
    primary_score = score_segment(asset, segments[0]).total
    for segment in segments:
        breakdown = score_segment(asset, segment)
        if breakdown.total < 0.68:
            continue
        if selected and breakdown.total < primary_score - 0.08:
            continue
        selected.append(segment)
        if len(selected) >= (2 if asset.duration_sec >= 18 else 1):
            break

    return selected or segments[:1]


def select_ai_target_segment_ids(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    analyzer: VisionLanguageAnalyzer,
    max_segments_per_asset: int,
    mode: str,
) -> set[str]:
    if not segments:
        return set()
    if not analyzer.requires_keyframes:
        return set()
    if mode != "fast":
        return {segment.id for segment in segments}

    return select_prefilter_shortlist_ids(
        asset=asset,
        segments=segments,
        max_segments_per_asset=max_segments_per_asset,
        mode=mode,
    )


def select_prefilter_shortlist_ids(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    max_segments_per_asset: int,
    mode: str,
) -> set[str]:
    if not segments:
        return set()
    if mode != "fast":
        return {segment.id for segment in segments}

    ranked = sorted(
        segments,
        key=lambda segment: (
            segment.prefilter.score if segment.prefilter is not None else score_segment(asset, segment).total
        ),
        reverse=True,
    )
    limit = max(1, min(max_segments_per_asset, len(ranked)))
    return {segment.id for segment in ranked[:limit]}


def describe_prefilter_selection(*, score: float, shortlisted: bool, filtered_before_vlm: bool) -> str:
    score_label = f"{round(score * 100):d}/100"
    if filtered_before_vlm:
        return f"Filtered before VLM analysis during vision prefiltering at {score_label}."
    if shortlisted:
        return f"Shortlisted by vision prefiltering at {score_label}."
    return f"Scored {score_label} during vision prefiltering."


def suggested_timeline_duration(segment: CandidateSegment) -> float:
    duration = max(0.0, segment.end_sec - segment.start_sec)
    if segment.analysis_mode == "speech":
        return min(duration, 7.5)
    return min(duration, 5.0)


def timeline_label(index: int, count: int, analysis_mode: str) -> str:
    if index == 0:
        return "Opener"
    if index == count - 1:
        return "Outro"
    return "Narrative beat" if analysis_mode == "speech" else "Visual bridge"


def timeline_note(segment: CandidateSegment) -> str:
    if segment.analysis_mode == "speech":
        return "Protect the spoken beat and keep the line readable."
    return "Use this as visual pacing or atmospheric coverage."


def summarize_story(
    best_takes: list[TakeRecommendation],
    segment_by_id: dict[str, CandidateSegment],
) -> str:
    if not best_takes:
        return "No best takes have been selected yet."

    modes = [segment_by_id[take.candidate_segment_id].analysis_mode for take in best_takes]
    if all(mode == "visual" for mode in modes):
        return "The cut leans on visual progression, using silent coverage to move from setup to payoff."
    if all(mode == "speech" for mode in modes):
        return "The cut is dialogue-led and organized around spoken beats."
    return "The cut opens visually, turns on spoken information where available, and returns to visual release."


def asset_order(asset_by_id: dict[str, Asset], asset_id: str) -> int:
    ids = list(asset_by_id.keys())
    return ids.index(asset_id)


def seeded_value(token: str, first: float, second: float) -> float:
    payload = f"{token}:{first:.3f}:{second:.3f}".encode("utf-8")
    digest = md5(payload).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "project"
