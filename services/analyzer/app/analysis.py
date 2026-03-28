from __future__ import annotations

from dataclasses import dataclass, replace
import importlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Callable, Protocol

logger = logging.getLogger(__name__)

from .ai import (
    AIAnalysisConfig,
    DeterministicVisionLanguageAnalyzer,
    VisionLanguageAnalyzer,
    analyze_asset_segments,
    build_segment_evidence,
    default_vision_language_analyzer,
    get_ai_runtime_stats,
    load_ai_analysis_config,
    segment_evidence_matches,
    validate_segment_boundaries,
)

# Lazy imports for optional CLIP dependencies
CLIPScorer = None
CLIPDeduplicator = None
is_clip_available = lambda: False

try:
    from .clip import CLIPScorer, is_available as is_clip_available
    from .clip_dedup import CLIPDeduplicator
except ImportError:
    pass
from .deduplication import (
    HistogramDeduplicator,
    apply_deduplication_results,
    deduplicate_segments,
    get_dedup_threshold,
    is_deduplication_enabled,
)
from .domain import (
    Asset,
    BoundaryValidationResult,
    CandidateSegment,
    PrefilterDecision,
    ProjectData,
    ProjectMeta,
)
from .media import FFprobeRunner, build_assets_from_matches, discover_media_files, match_media_files
from .prefilter import (
    DeterministicPreprocessingArtifact,
    AudioSignal,
    FrameSignal,
    build_prefilter_seed_regions,
    build_prefilter_segments,
    deterministic_preprocessing_cache_path,
    deterministic_preprocessing_compatibility_key,
    load_deterministic_preprocessing_artifact,
    sample_asset_signals,
    sample_audio_signals,
    sample_timestamps,
    write_deterministic_preprocessing_artifact,
)
from .selection import (
    StoryAssemblyChoice as SelectionStoryAssemblyChoice,
    StoryAssemblyEvaluation as SelectionStoryAssemblyEvaluation,
    assemble_story_sequence as selection_assemble_story_sequence,
    boundary_strategy_label as selection_boundary_strategy_label,
    build_segment_review_state as selection_build_segment_review_state,
    build_take_recommendations as selection_build_take_recommendations,
    build_timeline as selection_build_timeline,
    default_segment_speech_mode_source as selection_default_segment_speech_mode_source,
    default_segment_transcript_status as selection_default_segment_transcript_status,
    describe_analysis_path as selection_describe_analysis_path,
    describe_prefilter_selection as selection_describe_prefilter_selection,
    evaluate_opener_candidate as selection_evaluate_opener_candidate,
    evaluate_release_candidate as selection_evaluate_release_candidate,
    evaluate_transition_candidate as selection_evaluate_transition_candidate,
    extract_story_prompt_keywords as selection_extract_story_prompt_keywords,
    has_mixed_sequence_modes as selection_has_mixed_sequence_modes,
    lineage_summary as selection_lineage_summary,
    make_selection_reason as selection_make_selection_reason,
    make_take_title as selection_make_take_title,
    recommendation_outcome as selection_recommendation_outcome,
    review_blocked_reason as selection_review_blocked_reason,
    segment_prompt_fit as selection_segment_prompt_fit,
    segment_story_role as selection_segment_story_role,
    select_ai_target_segment_ids as selection_select_ai_target_segment_ids,
    select_prefilter_shortlist_ids as selection_select_prefilter_shortlist_ids,
    select_segments_for_asset as selection_select_segments_for_asset,
    select_vlm_targets_three_stage as selection_select_vlm_targets_three_stage,
    semantic_validation_summary as selection_semantic_validation_summary,
    sequence_group_for_item as selection_sequence_group_for_item,
    sequence_rationale_for_item as selection_sequence_rationale_for_item,
    sequence_role_for_item as selection_sequence_role_for_item,
    speech_structure_summary as selection_speech_structure_summary,
    suggested_timeline_duration as selection_suggested_timeline_duration,
    summarize_story as selection_summarize_story,
    timeline_label as selection_timeline_label,
    timeline_note as selection_timeline_note,
    transcript_summary as selection_transcript_summary,
    turn_summary as selection_turn_summary,
)
from .semantic_validation import (
    apply_semantic_boundary_validation,
    initial_boundary_validation_result,
    run_scoped_semantic_validation_budget,
    select_semantic_boundary_validation_targets,
    semantic_boundary_ambiguity_score,
    semantic_validation_is_available,
)
from .segmentation import (
    AUDIO_SNAP_MAX_CENTER_DRIFT_SEC,
    ASSEMBLY_MERGE_MAX_GAP_SEC,
    ASSEMBLY_MERGE_STRUCTURAL_GAP_SEC,
    ASSEMBLY_MERGE_STRUCTURAL_MAX_DURATION_SEC,
    ASSEMBLY_SPLIT_MIN_DURATION_SEC,
    ASSEMBLY_SPLIT_MIN_PART_SEC,
    ASSEMBLY_SPLIT_SCENE_EDGE_BUFFER_SEC,
    ASSEMBLY_SPLIT_TRANSCRIPT_GAP_SEC,
    AssemblyContinuitySignals,
    RefinedSegmentCandidate,
    assemble_narrative_units,
    collect_assembly_continuity_signals,
    make_candidate_segment,
    merge_adjacent_segments,
    merge_rule_family,
    refine_seed_regions,
    scene_boundaries_from_ranges,
    split_candidate_segment,
)
from .shared.numbers import clamp
from .shared.strings import dedupe_labels, human_join, slugify
from .transcripts import (
    FasterWhisperAdapter,
    NoOpTranscriptProvider,
    TranscriptProvider,
    TranscriptRuntimeStatus,
    TranscriptSpan,
    TranscriptTurn,
    build_transcript_probe_ranges,
    build_transcript_provider,
    derive_transcript_turns,
    segment_speech_mode_source,
    segment_transcript_status,
    should_probe_after_selective_skip,
    should_probe_before_full_transcript,
    should_request_transcript_for_asset,
    transcript_cache_available,
    transcript_probe_allows_full_pass,
    transcript_runtime_status,
    transcript_spans_for_range,
    transcript_turns_for_range,
)


class SceneDetector(Protocol):
    def detect(self, asset: Asset) -> list[tuple[float, float]]:
        ...


StatusCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int, Asset], None]


@dataclass(slots=True)
class AssetAnalysisContext:
    asset: Asset
    asset_segments: list[CandidateSegment]
    base_ranges: list[tuple[float, float]]
    prefilter_signals: list[FrameSignal]
    audio_signals: list[AudioSignal]
    transcript_spans: list[TranscriptSpan]
    transcript_turns: list[TranscriptTurn]
    transcript_lookup_enabled: bool
    ambiguity_by_id: dict[str, float]
    semantic_target_order: list[str]
    semantic_target_reasons: dict[str, str]


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


def inspect_runtime_capabilities() -> dict[str, bool]:
    return {
        "ffprobe": shutil.which("ffprobe") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "scenedetect": importlib.util.find_spec("scenedetect") is not None,
        "faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
        "fastapi": importlib.util.find_spec("fastapi") is not None,
    }


def runtime_status_label(*, active: bool, unavailable: bool, fallback_count: int, skipped_count: int) -> str:
    if unavailable:
        return "unavailable"
    if fallback_count > 0:
        return "degraded"
    if skipped_count > 0 and active:
        return "partial"
    if active:
        return "active"
    return "inactive"


def combined_runtime_status_label(*modes: str) -> str:
    normalized = [mode.strip() for mode in modes if mode and mode.strip()]
    if any(mode == "unavailable" for mode in normalized):
        return "unavailable"
    if any(mode == "degraded" for mode in normalized):
        return "degraded"
    if any(mode == "partial" for mode in normalized):
        return "partial"
    if any(mode == "active" for mode in normalized):
        return "active"
    return "inactive"


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
    media_discovery_started_at = time.monotonic()
    ai_config = load_ai_analysis_config()
    transcript_cache_root = (
        Path(artifacts_root) / "transcript-cache"
        if artifacts_root is not None and ai_config.cache_enabled
        else None
    )
    discovered = discover_media_files(media_roots, probe_runner=probe_runner)
    if status_callback is not None:
        status_callback(f"Discovered {len(discovered)} video files.")
    matches = match_media_files(discovered)
    assets = build_assets_from_matches(matches)
    media_discovery_duration = time.monotonic() - media_discovery_started_at
    if status_callback is not None:
        status_callback(f"Matched {len(assets)} source assets to process.")
    project_data = analyze_assets(
        project=ProjectMeta(
            id=slugify(project_name),
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
    phase_timings = dict(project_data.project.analysis_summary.get("phase_timings_sec", {}))
    phase_timings["media_discovery"] = round(media_discovery_duration, 3)
    project_data.project.analysis_summary["phase_timings_sec"] = phase_timings
    return project_data


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
    ai_config = load_ai_analysis_config()
    transcript_provider_injected = transcript_provider is not None
    transcript_cache_root = (
        Path(artifacts_root) / "transcript-cache"
        if artifacts_root is not None and ai_config.cache_enabled
        else None
    )
    transcriber = transcript_provider or build_transcript_provider(ai_config, cache_root=transcript_cache_root)
    transcript_status = transcript_runtime_status(transcriber)
    analyzer = segment_analyzer or default_vision_language_analyzer(
        artifacts_root=artifacts_root,
        analysis_config=ai_config,
    )
    deterministic_analyzer = DeterministicVisionLanguageAnalyzer()
    semantic_available = semantic_validation_is_available(analyzer)
    candidate_segments: list[CandidateSegment] = []
    total_prefilter_samples = 0
    total_prefilter_shortlisted = 0
    total_vlm_targets = 0
    total_filtered_before_vlm = 0
    total_audio_signal_assets = 0
    total_transcript_target_assets = 0
    total_transcript_skipped_assets = 0
    total_transcript_probed_assets = 0
    total_transcript_probe_rejected_assets = 0
    total_transcript_excerpt_segments = 0
    total_speech_fallback_segments = 0
    total_deduplicated_segments = 0
    total_clip_scored = 0
    total_clip_gated = 0
    total_semantic_boundary_eligible = 0
    total_semantic_boundary_request_count = 0
    total_semantic_boundary_validated = 0
    total_semantic_boundary_skipped = 0
    total_semantic_boundary_fallback = 0
    total_semantic_boundary_threshold_targeted = 0
    total_semantic_boundary_floor_targeted = 0
    total_semantic_boundary_applied = 0
    total_semantic_boundary_noop = 0
    total_preprocessing_cache_hits = 0
    total_preprocessing_cache_rebuilds = 0
    deduplication_enabled = is_deduplication_enabled()
    dedup_threshold = get_dedup_threshold()
    total_dedup_group_count = 0  # Accumulate dedup group count across all dedup passes
    total_dedup_eliminated_count = 0  # Accumulate deduplicated segment count

    total_assets = len(assets)
    analysis_contexts: list[AssetAnalysisContext] = []
    all_frame_signals_by_id: dict[str, list] = {}  # Accumulate frame signals for histogram dedup fallback
    per_asset_analysis_started_at = time.monotonic()

    if status_callback is not None:
        transcript_label = transcript_status.effective_provider or "none"
        status_callback(
            "Transcript support: "
            f"{transcript_status.status} via {transcript_label}"
            + (f" ({transcript_status.model_size})" if transcript_status.model_size else "")
        )
        status_callback(transcript_status.detail)

    for asset in assets:
        if status_callback is not None:
            status_callback(f"[{len(analysis_contexts) + 1}/{total_assets}] Analyzing: {asset.name}")

        timestamps = sample_timestamps(asset.duration_sec)
        preprocessing_cache_hit = False
        cache_path: Path | None = None
        compatibility_key = ""
        if artifacts_root is not None:
            cache_path = deterministic_preprocessing_cache_path(
                artifacts_root=artifacts_root,
                asset=asset,
            )
            compatibility_key = deterministic_preprocessing_compatibility_key(
                asset=asset,
                timestamps=timestamps,
                frame_width=64,
                audio_enabled=os.environ.get("TIMELINE_AI_AUDIO_ENABLED", "true").lower() != "false",
            )
            cached_artifact = load_deterministic_preprocessing_artifact(
                cache_path=cache_path,
                compatibility_key=compatibility_key,
            )
        else:
            cached_artifact = None

        if cached_artifact is not None:
            preprocessing_cache_hit = True
            base_ranges = cached_artifact.base_ranges
            prefilter_signals = cached_artifact.frame_signals
            audio_signals = cached_artifact.audio_signals
            total_preprocessing_cache_hits += 1
        else:
            base_ranges = detector.detect(asset) if asset.duration_sec > 0 else [(0.0, 4.0)]
            if not base_ranges:
                base_ranges = fallback_segments(asset.duration_sec)
            prefilter_signals = sample_asset_signals(asset, timestamps=timestamps)
            audio_signals = sample_audio_signals(asset, timestamps)
            if cache_path is not None:
                write_deterministic_preprocessing_artifact(
                    cache_path=cache_path,
                    artifact=DeterministicPreprocessingArtifact(
                        compatibility_key=compatibility_key,
                        base_ranges=base_ranges,
                        frame_signals=prefilter_signals,
                        audio_signals=audio_signals,
                    ),
                )
                total_preprocessing_cache_rebuilds += 1

        total_prefilter_samples += len(prefilter_signals)
        has_audio = any(sig.source == "ffmpeg" for sig in audio_signals)
        if has_audio:
            total_audio_signal_assets += 1
        if status_callback is not None:
            audio_status = f"audio detected" if has_audio else "silent/no audio"
            status_callback(
                f"  ✓ Sampled {len(prefilter_signals)} frames ({audio_status})"
                + (" from preprocessing cache" if preprocessing_cache_hit else "")
            )
        if transcript_provider_injected:
            transcript_lookup_enabled = asset.has_speech
        else:
            transcript_lookup_enabled = should_request_transcript_for_asset(
                asset=asset,
                audio_signals=audio_signals,
                transcriber=transcriber,
                runtime_status=transcript_status,
            )
        transcript_probe_ran = False
        transcript_probe_detected_text = False
        if (
            not transcript_provider_injected
            and asset.has_speech
            and transcript_status.available
            and not transcript_cache_available(transcriber, asset)
        ):
            should_probe = (
                transcript_lookup_enabled and should_probe_before_full_transcript(audio_signals)
            ) or (
                not transcript_lookup_enabled and should_probe_after_selective_skip(audio_signals)
            )
            if should_probe:
                transcript_probe_ran = True
                total_transcript_probed_assets += 1
                probe_ranges = build_transcript_probe_ranges(asset, audio_signals)
                transcript_probe_detected_text = transcript_probe_allows_full_pass(
                    transcriber,
                    asset=asset,
                    probe_ranges=probe_ranges,
                )
                transcript_lookup_enabled = transcript_probe_detected_text
                if not transcript_lookup_enabled:
                    total_transcript_probe_rejected_assets += 1

        if transcript_lookup_enabled:
            total_transcript_target_assets += 1
        elif asset.has_speech and transcript_status.available:
            total_transcript_skipped_assets += 1
        transcript_spans = (
            transcript_spans_for_range(transcriber, asset, 0.0, asset.duration_sec)
            if transcript_lookup_enabled
            else []
        )
        transcript_turns = derive_transcript_turns(transcript_spans)
        if status_callback is not None and asset.has_speech and transcript_status.available:
            transcript_note = "selected for transcript pass" if transcript_lookup_enabled else "skipped transcript pass"
            status_callback(f"  ✓ Speech gate: {transcript_note}")
            if transcript_probe_ran:
                probe_note = "text detected" if transcript_probe_detected_text else "no text detected"
                status_callback(f"  ✓ Speech probe: {probe_note}")
        top_windows = 2 if ai_config.mode == "fast" else 3
        refined_candidates: list[RefinedSegmentCandidate] = []
        if ai_config.boundary_refinement_enabled:
            seed_regions = build_prefilter_seed_regions(
                asset=asset,
                base_ranges=base_ranges,
                signals=prefilter_signals,
                audio_signals=audio_signals,
                top_windows=top_windows,
            )
            refined_candidates = refine_seed_regions(
                asset=asset,
                seed_regions=seed_regions,
                base_ranges=base_ranges,
                transcript_spans=transcript_spans,
                transcript_turns=transcript_turns,
                audio_signals=audio_signals,
            )

        if refined_candidates:
            segment_inputs = [
                (
                    candidate.start_sec,
                    candidate.end_sec,
                    candidate.boundary_strategy,
                    candidate.boundary_confidence,
                    candidate.seed_region_ids,
                    candidate.seed_region_sources,
                    candidate.seed_region_ranges_sec,
                )
                for candidate in refined_candidates
            ]
        else:
            segment_ranges = build_prefilter_segments(
                asset=asset,
                base_ranges=base_ranges,
                signals=prefilter_signals,
                audio_signals=audio_signals,
                top_windows=top_windows,
            )
            if not segment_ranges and ai_config.boundary_refinement_enabled and not ai_config.boundary_refinement_legacy_fallback:
                segment_ranges = []
            if not segment_ranges:
                segment_ranges = fallback_segments(asset.duration_sec)
            segment_inputs = [
                (start_sec, end_sec, "legacy", 0.0, [], [], [])
                for start_sec, end_sec in segment_ranges
            ]

        asset_segments: list[CandidateSegment] = []
        for index, (
            start_sec,
            end_sec,
            boundary_strategy,
            boundary_confidence,
            seed_region_ids,
            seed_region_sources,
            seed_region_ranges_sec,
        ) in enumerate(segment_inputs, start=1):
            asset_segments.append(
                make_candidate_segment(
                    asset=asset,
                    segment_id=(
                        f"{asset.id}-region-{index:02d}"
                        if ai_config.boundary_refinement_enabled
                        else f"{asset.id}-segment-{index:02d}"
                    ),
                    start_sec=start_sec,
                    end_sec=end_sec,
                    transcriber=transcriber,
                    transcript_spans=transcript_spans,
                    transcript_turns=transcript_turns,
                    prefilter_signals=prefilter_signals,
                    audio_signals=audio_signals,
                    boundary_strategy=boundary_strategy,
                    boundary_confidence=boundary_confidence,
                    seed_region_ids=seed_region_ids,
                    seed_region_sources=seed_region_sources,
                    seed_region_ranges_sec=seed_region_ranges_sec,
                    transcript_lookup_enabled=transcript_lookup_enabled,
                )
            )

        if ai_config.boundary_refinement_enabled and asset_segments:
            asset_segments = assemble_narrative_units(
                asset=asset,
                segments=asset_segments,
                base_ranges=base_ranges,
                transcript_spans=transcript_spans,
                transcript_turns=transcript_turns,
                transcriber=transcriber,
                prefilter_signals=prefilter_signals,
                audio_signals=audio_signals,
            )

        total_transcript_excerpt_segments += sum(1 for segment in asset_segments if segment.transcript_excerpt.strip())
        total_speech_fallback_segments += sum(
            1
            for segment in asset_segments
            if segment.analysis_mode == "speech" and not segment.transcript_excerpt.strip()
        )

        ambiguity_by_id, semantic_target_order, semantic_target_reasons = select_semantic_boundary_validation_targets(
            segments=asset_segments,
            enabled=ai_config.semantic_boundary_validation_enabled and ai_config.boundary_refinement_enabled,
            analyzer_available=semantic_available,
            ambiguity_threshold=ai_config.semantic_boundary_ambiguity_threshold,
            floor_threshold=ai_config.semantic_boundary_floor_threshold,
            min_targets=ai_config.semantic_boundary_min_targets,
        )
        total_semantic_boundary_eligible += sum(
            1
            for segment in asset_segments
            if ambiguity_by_id.get(segment.id, 0.0) >= ai_config.semantic_boundary_ambiguity_threshold
        )

        analysis_contexts.append(
            AssetAnalysisContext(
                asset=asset,
                asset_segments=asset_segments,
                base_ranges=base_ranges,
                prefilter_signals=prefilter_signals,
                audio_signals=audio_signals,
                transcript_spans=transcript_spans,
                transcript_turns=transcript_turns,
                transcript_lookup_enabled=transcript_lookup_enabled,
                ambiguity_by_id=ambiguity_by_id,
                semantic_target_order=semantic_target_order,
                semantic_target_reasons=semantic_target_reasons,
            )
        )

    remaining_semantic_budget = run_scoped_semantic_validation_budget(
        target_orders=[context.semantic_target_order for context in analysis_contexts],
        budget_pct=ai_config.semantic_boundary_validation_budget_pct,
        max_segments=ai_config.semantic_boundary_validation_max_segments,
    )

    for asset_index, context in enumerate(analysis_contexts, start=1):
        asset = context.asset
        asset_segments = context.asset_segments
        base_ranges = context.base_ranges
        prefilter_signals = context.prefilter_signals
        audio_signals = context.audio_signals
        transcript_spans = context.transcript_spans
        transcript_turns = context.transcript_turns
        transcript_lookup_enabled = context.transcript_lookup_enabled
        ambiguity_by_id = context.ambiguity_by_id
        semantic_target_ids = set(context.semantic_target_order[:remaining_semantic_budget])
        semantic_target_reasons = {
            segment_id: context.semantic_target_reasons.get(segment_id, "threshold")
            for segment_id in semantic_target_ids
        }
        remaining_semantic_budget = max(0, remaining_semantic_budget - len(semantic_target_ids))

        for segment in asset_segments:
            segment.boundary_validation = initial_boundary_validation_result(
                segment=segment,
                enabled=ai_config.semantic_boundary_validation_enabled and ai_config.boundary_refinement_enabled,
                analyzer_available=semantic_available,
                ambiguity_score=ambiguity_by_id.get(segment.id, 0.0),
                ambiguity_threshold=ai_config.semantic_boundary_ambiguity_threshold,
                targeted=segment.id in semantic_target_ids,
                target_reason=semantic_target_reasons.get(segment.id, ""),
            )

        total_semantic_boundary_threshold_targeted += sum(
            1 for reason in semantic_target_reasons.values() if reason == "threshold"
        )
        total_semantic_boundary_floor_targeted += sum(
            1 for reason in semantic_target_reasons.values() if reason == "floor"
        )

        if semantic_target_ids:
            semantic_tasks: list[tuple[CandidateSegment, object, str]] = []
            for index, segment in enumerate(asset_segments):
                if segment.id not in semantic_target_ids:
                    continue
                evidence = build_segment_evidence(
                    asset=asset,
                    segment=segment,
                    asset_segments=asset_segments,
                    segment_index=index,
                    story_prompt=project.story_prompt,
                    artifacts_root=artifacts_root,
                    extract_keyframes=analyzer.requires_keyframes,
                    transcript_status=segment_transcript_status(
                        asset=asset,
                        segment=segment,
                        runtime_status=transcript_status,
                        transcript_lookup_attempted=transcript_lookup_enabled,
                    ),
                    speech_mode_source=segment_speech_mode_source(asset=asset, segment=segment),
                    max_keyframes_per_segment=ai_config.max_keyframes_per_segment,
                    keyframe_max_width=ai_config.keyframe_max_width,
                )
                segment.evidence_bundle = evidence
                semantic_tasks.append((segment, evidence, project.story_prompt))

            total_semantic_boundary_request_count += len(semantic_tasks)
            semantic_results = validate_segment_boundaries(
                analyzer=analyzer,
                asset=asset,
                tasks=semantic_tasks,
                concurrency=ai_config.concurrency,
            )
            for segment in asset_segments:
                if segment.id not in semantic_target_ids:
                    continue
                result = semantic_results.get(segment.id)
                pending_result = segment.boundary_validation
                if result is None:
                    result = BoundaryValidationResult(
                        status="fallback",
                        decision="keep",
                        reason="Semantic boundary validation returned no result, so deterministic output was preserved.",
                        confidence=0.0,
                        provider="deterministic",
                        provider_model="fallback-v1",
                        skip_reason="request_failed",
                        original_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
                        suggested_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
                    )
                if pending_result is not None and not result.target_reason:
                    result.target_reason = pending_result.target_reason
                result.ambiguity_score = ambiguity_by_id.get(segment.id, 0.0)
                segment.boundary_validation = result
                if result.status == "validated":
                    total_semantic_boundary_validated += 1
                elif result.status == "fallback":
                    total_semantic_boundary_fallback += 1

            asset_segments = apply_semantic_boundary_validation(
                asset=asset,
                segments=asset_segments,
                validation_results={segment.id: segment.boundary_validation for segment in asset_segments if segment.boundary_validation is not None},
                transcriber=transcriber,
                transcript_spans=transcript_spans,
                transcript_turns=transcript_turns,
                prefilter_signals=prefilter_signals,
                audio_signals=audio_signals,
                max_adjustment_sec=ai_config.semantic_boundary_max_adjustment_sec,
            )
            total_semantic_boundary_applied += sum(
                1
                for segment in asset_segments
                if segment.boundary_validation is not None
                and segment.boundary_validation.status == "validated"
                and segment.boundary_validation.applied
            )
            total_semantic_boundary_noop += sum(
                1
                for segment in asset_segments
                if segment.boundary_validation is not None
                and segment.boundary_validation.status == "validated"
                and not segment.boundary_validation.applied
            )

        total_semantic_boundary_skipped += sum(
            1
            for segment in asset_segments
            if segment.boundary_validation is not None and segment.boundary_validation.status == "skipped"
        )

        # Deduplication pass: runs after prefilter scoring and before shortlist selection
        if deduplication_enabled and len(asset_segments) > 1:
            if status_callback is not None:
                status_callback(f"  ✓ Deduplicating {len(asset_segments)} prefilter segments...")

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
                all_frame_signals_by_id[segment.id] = matching_signals  # Accumulate for histogram dedup fallback

            dedup_results = deduplicate_segments(
                segments=asset_segments,
                frame_signals_by_id=frame_signals_by_id,
                similarity_threshold=dedup_threshold,
            )
            apply_deduplication_results(asset_segments, dedup_results)
            asset_dedup_count = sum(1 for deduplicated, _ in dedup_results.values() if deduplicated)
            total_deduplicated_segments += asset_dedup_count
            if asset_dedup_count > 0 and status_callback is not None:
                status_callback(f"    → Eliminated {asset_dedup_count} near-duplicate(s)")

        # Filter out deduplicated segments from further processing
        active_segments = [s for s in asset_segments if not (s.prefilter and s.prefilter.deduplicated)]

        prefilter_shortlist_ids = select_prefilter_shortlist_ids(
            asset=asset,
            segments=active_segments,
            max_segments_per_asset=ai_config.max_segments_per_asset,
            mode=ai_config.mode,
        )
        total_prefilter_shortlisted += len(prefilter_shortlist_ids)
        ai_tasks: list[tuple[CandidateSegment, object, str]] = []
        requires_image_evidence = analyzer.requires_keyframes or (
            ai_config.clip_enabled and is_clip_available() and CLIPScorer is not None
        )

        # Build evidence for all shortlisted segments
        for index, segment in enumerate(asset_segments):
            if segment.prefilter is not None:
                segment.prefilter.shortlisted = segment.id in prefilter_shortlist_ids

            evidence = None
            if segment.id in prefilter_shortlist_ids:
                segment_transcript_state = segment_transcript_status(
                    asset=asset,
                    segment=segment,
                    runtime_status=transcript_status,
                    transcript_lookup_attempted=transcript_lookup_enabled,
                )
                segment_speech_source = segment_speech_mode_source(asset=asset, segment=segment)
                if segment_evidence_matches(
                    evidence=segment.evidence_bundle,
                    asset=asset,
                    segment=segment,
                    asset_segments=asset_segments,
                    segment_index=index,
                    story_prompt=project.story_prompt,
                    extract_keyframes=requires_image_evidence,
                    transcript_status=segment_transcript_state,
                    speech_mode_source=segment_speech_source,
                    max_keyframes_per_segment=ai_config.max_keyframes_per_segment,
                    keyframe_max_width=ai_config.keyframe_max_width,
                ):
                    evidence = segment.evidence_bundle
                else:
                    evidence = build_segment_evidence(
                        asset=asset,
                        segment=segment,
                        asset_segments=asset_segments,
                        segment_index=index,
                        story_prompt=project.story_prompt,
                        artifacts_root=artifacts_root,
                        extract_keyframes=requires_image_evidence,
                        transcript_status=segment_transcript_state,
                        speech_mode_source=segment_speech_source,
                        max_keyframes_per_segment=ai_config.max_keyframes_per_segment,
                        keyframe_max_width=ai_config.keyframe_max_width,
                    )
                segment.evidence_bundle = evidence

        # CLIP scoring pass (if enabled and available)
        clip_scorer = None
        if ai_config.clip_enabled and is_clip_available() and CLIPScorer is not None:
            if status_callback is not None:
                status_callback(f"  ✓ CLIP semantic scoring {len(prefilter_shortlist_ids)} shortlisted segments...")

            try:
                clip_scorer = CLIPScorer(
                    model_name=ai_config.clip_model,
                    pretrained=ai_config.clip_model_pretrained,
                )
                asset_clip_scored = 0
                asset_clip_gated = 0

                for segment in asset_segments:
                    if segment.id in prefilter_shortlist_ids and segment.evidence_bundle is not None:
                        # Score using contact sheet if available, otherwise first keyframe
                        image_path = segment.evidence_bundle.contact_sheet_path
                        if not image_path or not Path(image_path).exists():
                            if segment.evidence_bundle.keyframe_paths:
                                image_path = segment.evidence_bundle.keyframe_paths[0]

                        if image_path and Path(image_path).exists():
                            clip_score = clip_scorer.score(image_path)
                            segment.prefilter.metrics_snapshot["clip_score"] = clip_score
                            total_clip_scored += 1
                            asset_clip_scored += 1

                            if clip_score < ai_config.clip_min_score:
                                segment.prefilter.clip_gated = True
                                total_clip_gated += 1
                                asset_clip_gated += 1

                if asset_clip_gated > 0 and status_callback is not None:
                    status_callback(f"    → Gated {asset_clip_gated}/{asset_clip_scored} by semantic threshold")
            except Exception as e:
                logger.error(f"CLIP scoring failed: {e}, disabling CLIP")
                clip_scorer = None
                if status_callback is not None:
                    status_callback(f"    ⚠ CLIP scoring unavailable (disabling for this run)")

        # Deduplication pass (after evidence building and CLIP scoring, before VLM targeting)
        if is_deduplication_enabled():
            shortlisted_segments = [s for s in active_segments if s.prefilter and s.prefilter.shortlisted]
            if shortlisted_segments:
                if status_callback is not None:
                    status_callback(f"  ✓ Deduplicating {len(shortlisted_segments)} shortlisted segments...")

                try:
                    if clip_scorer is not None and CLIPDeduplicator is not None:
                        # Use CLIP-based dedup
                        deduplicator = CLIPDeduplicator(clip_scorer)
                        deduplicator.deduplicate(shortlisted_segments)
                    else:
                        # Use histogram fallback (use frame signals accumulated from prefilter dedup pass)
                        frame_signals_by_id = {
                            segment_id: signals
                            for segment_id, signals in all_frame_signals_by_id.items()
                            if any(s.id == segment_id for s in active_segments)
                        }
                        deduplicator = HistogramDeduplicator(frame_signals_by_id, threshold=get_dedup_threshold())
                        deduplicator.deduplicate(shortlisted_segments)

                    # Count dedup results for summary
                    dedup_groups = set(s.prefilter.dedup_group_id for s in shortlisted_segments if s.prefilter.dedup_group_id is not None)
                    dedup_eliminated = sum(1 for s in shortlisted_segments if s.prefilter and s.prefilter.deduplicated)
                    total_dedup_group_count += len(dedup_groups)
                    total_dedup_eliminated_count += dedup_eliminated

                    if dedup_eliminated > 0 and status_callback is not None:
                        status_callback(f"    → Eliminated {dedup_eliminated} near-duplicate(s)")
                except Exception as e:
                    logger.error(f"Deduplication failed: {e}")
                    if status_callback is not None:
                        status_callback(f"    ⚠ Deduplication unavailable: {e}")

        # Three-stage VLM target selection
        # Stage 1: Filter out clip_gated segments
        # Stage 2: Apply per-asset limit
        # Stage 3: Apply global budget cap
        ai_target_ids = select_vlm_targets_three_stage(
            asset=asset,
            segments=active_segments,
            analyzer=analyzer,
            prefilter_shortlist_ids=prefilter_shortlist_ids,
            max_segments_per_asset=ai_config.max_segments_per_asset,
            vlm_budget_pct=ai_config.vlm_budget_pct,
            clip_enabled=ai_config.clip_enabled and clip_scorer is not None,
        )
        total_vlm_targets += len(ai_target_ids)

        # Log VLM targeting decision
        if status_callback is not None:
            deterministic_count = len(prefilter_shortlist_ids) - len(ai_target_ids)
            status_callback(f"  ✓ VLM targets: {len(ai_target_ids)} | Deterministic: {deterministic_count}")

        # Build prefilter selection reasons and apply analysis
        for segment in asset_segments:
            if segment.prefilter is not None:
                # Skip deduplicated segments — preserve their dedup-specific selection_reason
                if segment.prefilter.deduplicated:
                    continue
                segment.prefilter.filtered_before_vlm = analyzer.requires_keyframes and segment.id not in ai_target_ids
                segment.prefilter.selection_reason = describe_prefilter_selection(
                    score=segment.prefilter.score,
                    shortlisted=segment.prefilter.shortlisted,
                    filtered_before_vlm=segment.prefilter.filtered_before_vlm,
                    clip_gated=segment.prefilter.clip_gated,
                    vlm_budget_capped=segment.prefilter.vlm_budget_capped,
                )
                if segment.prefilter.filtered_before_vlm:
                    total_filtered_before_vlm += 1

        # Build ai_tasks for VLM targets and apply deterministic understanding for others
        for segment in asset_segments:
            if segment.id not in prefilter_shortlist_ids:
                continue

            if segment.id in ai_target_ids:
                if segment.evidence_bundle is not None:
                    ai_tasks.append((segment, segment.evidence_bundle, project.story_prompt))
            else:
                # Segment is shortlisted but not selected for VLM (CLIP gated or budget capped)
                if segment.evidence_bundle is not None:
                    understanding = deterministic_analyzer.analyze(
                        asset=asset,
                        segment=segment,
                        evidence=segment.evidence_bundle,
                        story_prompt=project.story_prompt,
                    )
                    if segment.prefilter.clip_gated:
                        understanding.risk_flags = sorted(set([*understanding.risk_flags, "gated_by_clip"]))
                    if segment.prefilter.vlm_budget_capped:
                        understanding.risk_flags = sorted(set([*understanding.risk_flags, "excluded_by_budget_cap"]))
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
    per_asset_analysis_duration = time.monotonic() - per_asset_analysis_started_at

    for segment in candidate_segments:
        segment.review_state = build_segment_review_state(segment)

    take_selection_started_at = time.monotonic()
    take_recommendations = build_take_recommendations(assets, candidate_segments)
    take_selection_duration = time.monotonic() - take_selection_started_at

    timeline_assembly_started_at = time.monotonic()
    timeline = build_timeline(
        take_recommendations,
        candidate_segments,
        assets,
        story_prompt=project.story_prompt,
    )
    timeline_assembly_duration = time.monotonic() - timeline_assembly_started_at
    final_transcript_status = transcript_runtime_status(transcriber)

    project.analysis_summary = {
        "asset_count": total_assets,
        "prefilter_sample_count": total_prefilter_samples,
        "candidate_segment_count": len(candidate_segments),
        "deduplicated_segment_count": total_deduplicated_segments if deduplication_enabled else 0,
        "dedup_group_count": total_dedup_group_count if deduplication_enabled else 0,
        "dedup_eliminated_count": total_dedup_eliminated_count if deduplication_enabled else 0,
        "prefilter_shortlisted_count": total_prefilter_shortlisted,
        "vlm_target_count": total_vlm_targets,
        "filtered_before_vlm_count": total_filtered_before_vlm,
        "audio_signal_asset_count": total_audio_signal_assets,
        "audio_silent_asset_count": total_assets - total_audio_signal_assets,
        "transcript_target_asset_count": total_transcript_target_assets,
        "transcript_skipped_asset_count": total_transcript_skipped_assets,
        "transcript_probed_asset_count": total_transcript_probed_assets,
        "transcript_probe_rejected_asset_count": total_transcript_probe_rejected_assets,
        "transcript_provider_configured": final_transcript_status.configured_provider,
        "transcript_provider_effective": final_transcript_status.effective_provider,
        "transcript_status": final_transcript_status.status,
        "transcript_available": final_transcript_status.available,
        "transcript_enabled": final_transcript_status.enabled,
        "transcript_model_size": final_transcript_status.model_size,
        "transcript_detail": final_transcript_status.detail,
        "transcribed_asset_count": final_transcript_status.transcribed_asset_count,
        "transcript_failed_asset_count": final_transcript_status.failed_asset_count,
        "transcript_cached_asset_count": final_transcript_status.cached_asset_count,
        "transcript_runtime_probed_asset_count": final_transcript_status.probed_asset_count,
        "transcript_runtime_probe_rejected_asset_count": final_transcript_status.probe_rejected_asset_count,
        "transcript_excerpt_segment_count": total_transcript_excerpt_segments,
        "speech_fallback_segment_count": total_speech_fallback_segments,
        "clip_scored_count": total_clip_scored if (ai_config.clip_enabled and is_clip_available()) else 0,
        "clip_gated_count": total_clip_gated if (ai_config.clip_enabled and is_clip_available()) else 0,
        "semantic_boundary_eligible_count": total_semantic_boundary_eligible,
        "semantic_boundary_request_count": total_semantic_boundary_request_count,
        "semantic_boundary_validated_count": total_semantic_boundary_validated,
        "semantic_boundary_skipped_count": total_semantic_boundary_skipped,
        "semantic_boundary_fallback_count": total_semantic_boundary_fallback,
        "semantic_boundary_threshold_targeted_count": total_semantic_boundary_threshold_targeted,
        "semantic_boundary_floor_targeted_count": total_semantic_boundary_floor_targeted,
        "semantic_boundary_applied_count": total_semantic_boundary_applied,
        "semantic_boundary_noop_count": total_semantic_boundary_noop,
        "semantic_boundary_dormant": total_semantic_boundary_validated == 0,
        "deterministic_preprocessing_cache_hit_asset_count": total_preprocessing_cache_hits,
        "deterministic_preprocessing_cache_rebuilt_asset_count": total_preprocessing_cache_rebuilds,
        "vlm_budget_cap_pct": ai_config.vlm_budget_pct,
        "vlm_budget_was_binding": total_vlm_targets < (total_prefilter_shortlisted * ai_config.vlm_budget_pct / 100.0) if ai_config.vlm_budget_pct < 100 else False,
        "vlm_target_pct_of_candidates": (total_vlm_targets / len(candidate_segments) * 100) if candidate_segments else 0.0,
        "phase_timings_sec": {
            "per_asset_analysis": round(per_asset_analysis_duration, 3),
            "take_selection": round(take_selection_duration, 3),
            "timeline_assembly": round(timeline_assembly_duration, 3),
        },
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
    project.analysis_summary["transcript_runtime_mode"] = runtime_status_label(
        active=final_transcript_status.enabled and final_transcript_status.available,
        unavailable=final_transcript_status.enabled and not final_transcript_status.available,
        fallback_count=final_transcript_status.failed_asset_count,
        skipped_count=project.analysis_summary.get("transcript_skipped_asset_count", 0)
        + project.analysis_summary.get("transcript_runtime_probe_rejected_asset_count", 0),
    )
    timeline_mode_alternations = 0
    timeline_group_count = 0
    timeline_role_count = 0
    timeline_prompt_fit_count = 0
    timeline_tradeoff_count = 0
    timeline_repetition_control_count = 0
    speech_structure_segment_count = sum(
        1
        for segment in candidate_segments
        if segment.prefilter is not None and bool(segment.prefilter.speech_structure_label)
    )
    question_answer_segment_count = sum(
        1
        for segment in candidate_segments
        if segment.prefilter is not None and segment.prefilter.speech_structure_label == "question-answer-flow"
    )
    monologue_segment_count = sum(
        1
        for segment in candidate_segments
        if segment.prefilter is not None and segment.prefilter.speech_structure_label == "monologue-continuity"
    )
    if timeline.items:
        best_take_by_id = {take.id: take for take in take_recommendations}
        candidate_segments_by_id = {segment.id: segment for segment in candidate_segments}
        timeline_modes: list[str] = []
        for item in timeline.items:
            take = best_take_by_id.get(item.take_recommendation_id)
            if take is None:
                continue
            segment = candidate_segments_by_id.get(take.candidate_segment_id)
            if segment is None:
                continue
            timeline_modes.append(segment.analysis_mode)
        timeline_mode_alternations = sum(
            1
            for index in range(1, len(timeline_modes))
            if timeline_modes[index] != timeline_modes[index - 1]
        )
        timeline_group_count = len({item.sequence_group for item in timeline.items if item.sequence_group})
        timeline_role_count = len({item.sequence_role for item in timeline.items if item.sequence_role})
        timeline_prompt_fit_count = sum(
            1 for item in timeline.items if "prompt_fit" in item.sequence_driver_labels
        )
        timeline_tradeoff_count = sum(
            1 for item in timeline.items if item.sequence_tradeoff_labels
        )
        timeline_repetition_control_count = sum(
            1 for item in timeline.items if "repetition_control" in item.sequence_driver_labels
        )
    project.analysis_summary.update(
        {
            "story_assembly_active": len(timeline.items) > 1,
            "story_assembly_strategy": "sequence-heuristic-v2",
            "story_assembly_transition_count": max(0, len(timeline.items) - 1),
            "story_assembly_mode_alternation_count": timeline_mode_alternations,
            "story_assembly_group_count": timeline_group_count,
            "story_assembly_role_count": timeline_role_count,
            "story_assembly_prompt_fit_count": timeline_prompt_fit_count,
            "story_assembly_tradeoff_count": timeline_tradeoff_count,
            "story_assembly_repetition_control_count": timeline_repetition_control_count,
            "speech_structure_segment_count": speech_structure_segment_count,
            "speech_structure_question_answer_count": question_answer_segment_count,
            "speech_structure_monologue_count": monologue_segment_count,
        }
    )
    semantic_validated_count = int(project.analysis_summary.get("semantic_boundary_validated_count", 0))
    semantic_fallback_count = int(project.analysis_summary.get("semantic_boundary_fallback_count", 0))
    semantic_skipped_count = int(project.analysis_summary.get("semantic_boundary_skipped_count", 0))
    project.analysis_summary["semantic_boundary_runtime_mode"] = runtime_status_label(
        active=bool(ai_config.semantic_boundary_validation_enabled),
        unavailable=bool(ai_config.semantic_boundary_validation_enabled) and semantic_available is False,
        fallback_count=semantic_fallback_count,
        skipped_count=semantic_skipped_count,
    )
    project.analysis_summary["semantic_boundary_targeting_mode"] = (
        "active"
        if semantic_validated_count > 0
        else "inactive"
    )
    analyzer_available_method = getattr(analyzer, "is_available", None)
    analyzer_available = analyzer_available_method() if callable(analyzer_available_method) else True
    project.analysis_summary["ai_runtime_mode"] = runtime_status_label(
        active=bool(ai_runtime_stats.live_segment_count or ai_runtime_stats.cached_segment_count),
        unavailable=not analyzer_available,
        fallback_count=ai_runtime_stats.fallback_segment_count,
        skipped_count=project.analysis_summary.get("filtered_before_vlm_count", 0)
        + project.analysis_summary.get("ai_cached_segment_count", 0),
    )
    project.analysis_summary["cache_runtime_mode"] = runtime_status_label(
        active=bool(ai_config.cache_enabled),
        unavailable=False,
        fallback_count=0,
        skipped_count=0 if ai_runtime_stats.cached_segment_count > 0 else 1,
    )
    runtime_degraded_reasons: list[str] = []
    runtime_intentional_skip_reasons: list[str] = []

    if final_transcript_status.enabled and not final_transcript_status.available:
        runtime_degraded_reasons.append("transcript runtime unavailable")
    elif final_transcript_status.failed_asset_count > 0:
        runtime_degraded_reasons.append(
            f"transcript fallback on {final_transcript_status.failed_asset_count} asset"
            f"{'' if final_transcript_status.failed_asset_count == 1 else 's'}"
        )

    if total_semantic_boundary_fallback > 0:
        runtime_degraded_reasons.append(
            f"semantic boundary fallback on {total_semantic_boundary_fallback} segment"
            f"{'' if total_semantic_boundary_fallback == 1 else 's'}"
        )

    if ai_runtime_stats.fallback_segment_count > 0:
        runtime_degraded_reasons.append(
            f"deterministic AI fallback on {ai_runtime_stats.fallback_segment_count} segment"
            f"{'' if ai_runtime_stats.fallback_segment_count == 1 else 's'}"
        )

    if not final_transcript_status.enabled:
        runtime_intentional_skip_reasons.append("transcript provider disabled")
    elif total_transcript_skipped_assets > 0 or total_transcript_probe_rejected_assets > 0:
        parts: list[str] = []
        if total_transcript_skipped_assets > 0:
            parts.append(
                f"{total_transcript_skipped_assets} transcript-target skip"
                f"{'' if total_transcript_skipped_assets == 1 else 's'}"
            )
        if total_transcript_probe_rejected_assets > 0:
            parts.append(
                f"{total_transcript_probe_rejected_assets} probe rejection"
                f"{'' if total_transcript_probe_rejected_assets == 1 else 's'}"
            )
        runtime_intentional_skip_reasons.append("transcript targeting kept cost bounded: " + ", ".join(parts))

    if not ai_config.semantic_boundary_validation_enabled:
        runtime_intentional_skip_reasons.append("semantic boundary validation disabled")
    elif semantic_skipped_count > 0:
        runtime_intentional_skip_reasons.append(
            f"semantic boundary validation skipped {semantic_skipped_count} segment"
            f"{'' if semantic_skipped_count == 1 else 's'}"
        )

    filtered_before_vlm_count = int(project.analysis_summary.get("filtered_before_vlm_count", 0))
    if filtered_before_vlm_count > 0:
        runtime_intentional_skip_reasons.append(
            f"AI analysis skipped {filtered_before_vlm_count} segment"
            f"{'' if filtered_before_vlm_count == 1 else 's'} before live VLM"
        )

    runtime_reliability_mode = combined_runtime_status_label(
        project.analysis_summary["ai_runtime_mode"],
        project.analysis_summary["transcript_runtime_mode"],
        project.analysis_summary["semantic_boundary_runtime_mode"],
        project.analysis_summary["cache_runtime_mode"],
    )
    runtime_reliability_summary = (
        "AI "
        f"{project.analysis_summary['ai_runtime_mode']}, "
        f"transcript {project.analysis_summary['transcript_runtime_mode']}, "
        f"semantic {project.analysis_summary['semantic_boundary_runtime_mode']}, "
        f"cache {project.analysis_summary['cache_runtime_mode']}"
    )
    project.analysis_summary.update(
        {
            "runtime_reliability_mode": runtime_reliability_mode,
            "runtime_ready": runtime_reliability_mode not in {"unavailable", "inactive"},
            "runtime_reliability_summary": runtime_reliability_summary,
            "runtime_degraded_reasons": runtime_degraded_reasons,
            "runtime_intentional_skip_reasons": runtime_intentional_skip_reasons,
        }
    )
    if status_callback is not None:
        status_callback("")
        status_callback("═══════════════════════════════════════════════════")
        status_callback("Analysis Complete - Summary")
        status_callback("═══════════════════════════════════════════════════")
        status_callback(f"Assets processed: {total_assets}")
        status_callback(f"Total candidate segments: {len(candidate_segments)}")
        status_callback(f"Frames sampled: {total_prefilter_samples}")

        if deduplication_enabled:
            status_callback(f"Deduplication: {total_deduplicated_segments} near-duplicates eliminated")

        status_callback(f"Prefilter shortlisted: {total_prefilter_shortlisted}/{len(candidate_segments)} segments")

        if total_clip_scored > 0:
            status_callback(f"CLIP semantic scoring: {total_clip_scored} segments scored, {total_clip_gated} gated")

        status_callback(f"Audio coverage: {total_audio_signal_assets}/{total_assets} assets with audio")
        status_callback(
            "Transcript coverage: "
            f"{final_transcript_status.transcribed_asset_count} assets transcribed, "
            f"{final_transcript_status.cached_asset_count} loaded from cache, "
            f"{total_transcript_target_assets} targeted, "
            f"{total_transcript_skipped_assets} skipped, "
            f"{total_transcript_probed_assets} probed, "
            f"{total_transcript_probe_rejected_assets} probe-rejected, "
            f"{total_transcript_excerpt_segments} segments with transcript excerpts, "
            f"{total_speech_fallback_segments} speech-fallback segments"
        )

        status_callback(f"VLM analysis: {total_vlm_targets} segments selected for AI")
        status_callback(f"Deterministic analysis: {total_filtered_before_vlm} segments (budget/gating/fast-mode)")
        status_callback(
            f"Story assembly: {project.analysis_summary['story_assembly_transition_count']} transitions, "
            f"{project.analysis_summary['story_assembly_mode_alternation_count']} mode alternations"
        )

        status_callback(
            f"AI results: "
            f"live={ai_runtime_stats.live_segment_count}, "
            f"cached={ai_runtime_stats.cached_segment_count}, "
            f"fallback={ai_runtime_stats.fallback_segment_count}"
        )
        status_callback(
            "Runtime reliability: "
            f"{runtime_reliability_mode} "
            f"({runtime_reliability_summary})"
        )
        if runtime_degraded_reasons:
            status_callback("Runtime degraded modes: " + "; ".join(runtime_degraded_reasons))
        if runtime_intentional_skip_reasons:
            status_callback("Runtime intentional skips: " + "; ".join(runtime_intentional_skip_reasons))
        status_callback("═══════════════════════════════════════════════════")

    return ProjectData(
        project=project,
        assets=assets,
        candidate_segments=candidate_segments,
        take_recommendations=take_recommendations,
        timeline=timeline,
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

StoryAssemblyChoice = SelectionStoryAssemblyChoice
StoryAssemblyEvaluation = SelectionStoryAssemblyEvaluation
assemble_story_sequence = selection_assemble_story_sequence
boundary_strategy_label = selection_boundary_strategy_label
build_segment_review_state = selection_build_segment_review_state
build_take_recommendations = selection_build_take_recommendations
build_timeline = selection_build_timeline
default_segment_speech_mode_source = selection_default_segment_speech_mode_source
default_segment_transcript_status = selection_default_segment_transcript_status
describe_analysis_path = selection_describe_analysis_path
describe_prefilter_selection = selection_describe_prefilter_selection
evaluate_opener_candidate = selection_evaluate_opener_candidate
evaluate_release_candidate = selection_evaluate_release_candidate
evaluate_transition_candidate = selection_evaluate_transition_candidate
extract_story_prompt_keywords = selection_extract_story_prompt_keywords
has_mixed_sequence_modes = selection_has_mixed_sequence_modes
lineage_summary = selection_lineage_summary
make_selection_reason = selection_make_selection_reason
make_take_title = selection_make_take_title
recommendation_outcome = selection_recommendation_outcome
review_blocked_reason = selection_review_blocked_reason
segment_prompt_fit = selection_segment_prompt_fit
segment_story_role = selection_segment_story_role
select_ai_target_segment_ids = selection_select_ai_target_segment_ids
select_prefilter_shortlist_ids = selection_select_prefilter_shortlist_ids
select_segments_for_asset = selection_select_segments_for_asset
select_vlm_targets_three_stage = selection_select_vlm_targets_three_stage
semantic_validation_summary = selection_semantic_validation_summary
sequence_group_for_item = selection_sequence_group_for_item
sequence_rationale_for_item = selection_sequence_rationale_for_item
sequence_role_for_item = selection_sequence_role_for_item
speech_structure_summary = selection_speech_structure_summary
suggested_timeline_duration = selection_suggested_timeline_duration
summarize_story = selection_summarize_story
timeline_label = selection_timeline_label
timeline_note = selection_timeline_note
transcript_summary = selection_transcript_summary
turn_summary = selection_turn_summary
