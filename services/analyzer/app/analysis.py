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
    analyze_segments_bounded,
    build_segment_evidence,
    default_vision_language_analyzer,
    load_ai_analysis_config,
)
from .domain import Asset, CandidateSegment, ProjectData, ProjectMeta, TakeRecommendation, Timeline, TimelineItem
from .media import FFprobeRunner, build_assets_from_matches, discover_media_files, match_media_files
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

    total_assets = len(assets)
    for asset_index, asset in enumerate(assets, start=1):
        segment_ranges = detector.detect(asset) if asset.duration_sec > 0 else [(0.0, 4.0)]
        if not segment_ranges:
            segment_ranges = fallback_segments(asset.duration_sec)

        asset_segments: list[CandidateSegment] = []
        for index, (start_sec, end_sec) in enumerate(segment_ranges, start=1):
            excerpt = transcriber.excerpt(asset, start_sec, end_sec).strip() if asset.has_speech else ""
            analysis_mode = "speech" if excerpt else "visual"
            metrics = synthesize_quality_metrics(asset, start_sec, end_sec, analysis_mode)
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
                )
            )

        ai_target_ids = select_ai_target_segment_ids(
            asset=asset,
            segments=asset_segments,
            analyzer=analyzer,
            max_segments_per_asset=ai_config.max_segments_per_asset,
            mode=ai_config.mode,
        )
        ai_tasks: list[tuple[Asset, CandidateSegment, object, str]] = []

        for index, segment in enumerate(asset_segments):
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
                ai_tasks.append((asset, segment, evidence, project.story_prompt))
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

        ai_results = analyze_segments_bounded(
            analyzer=analyzer,
            tasks=ai_tasks,
            concurrency=ai_config.concurrency,
        )
        for segment in asset_segments:
            if segment.id in ai_results:
                segment.ai_understanding = ai_results[segment.id]
        candidate_segments.extend(asset_segments)
        if progress_callback is not None:
            progress_callback(asset_index, total_assets, asset)

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
) -> dict[str, float]:
    duration = max(0.1, end_sec - start_sec)
    seed = seeded_value(asset.id, start_sec, end_sec)
    variation = seeded_value(asset.name, end_sec, start_sec)
    duration_fit = clamp(1.0 - abs(duration - 5.5) / 7.0)
    motion_energy = clamp(0.45 + seed * 0.45)
    visual_novelty = clamp(0.4 + variation * 0.5)
    subject_clarity = clamp(0.58 + seeded_value(asset.proxy_path, duration, start_sec) * 0.32)
    hook_strength = clamp(0.52 + seeded_value(asset.interchange_reel_name, end_sec, duration) * 0.38)
    story_alignment = clamp(0.55 + seeded_value(asset.source_path, start_sec, duration) * 0.35)
    speech_presence = 0.92 if analysis_mode == "speech" else 0.0

    return {
        "sharpness": round(clamp(0.62 + seed * 0.28), 4),
        "stability": round(clamp(0.56 + variation * 0.26), 4),
        "visual_novelty": round(visual_novelty, 4),
        "subject_clarity": round(subject_clarity, 4),
        "motion_energy": round(motion_energy, 4),
        "duration_fit": round(duration_fit, 4),
        "speech_presence": round(speech_presence, 4),
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
        return {segment.id for segment in segments}
    if mode != "fast":
        return {segment.id for segment in segments}

    ranked = sorted(
        segments,
        key=lambda segment: score_segment(asset, segment).total,
        reverse=True,
    )
    limit = max(1, min(max_segments_per_asset, len(ranked)))
    return {segment.id for segment in ranked[:limit]}


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
