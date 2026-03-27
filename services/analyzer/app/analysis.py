from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import md5
import importlib
import importlib.util
import json
import logging
from pathlib import Path
import re
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
    SegmentReviewState,
    TakeRecommendation,
    Timeline,
    TimelineItem,
)
from .media import FFprobeRunner, build_assets_from_matches, discover_media_files, match_media_files
from .prefilter import (
    AudioSignal,
    FrameSignal,
    SeedRegion,
    aggregate_segment_prefilter,
    build_prefilter_seed_regions,
    build_prefilter_segments,
    sample_asset_signals,
    sample_audio_signals,
    sample_timestamps,
)
from .scoring import infer_analysis_mode, limiting_factor_labels, score_segment, top_score_driver_labels


class SceneDetector(Protocol):
    def detect(self, asset: Asset) -> list[tuple[float, float]]:
        ...


class TranscriptProvider(Protocol):
    def excerpt(self, asset: Asset, start_sec: float, end_sec: float) -> str:
        ...

    def spans(self, asset: Asset, start_sec: float, end_sec: float) -> list["TranscriptSpan"]:
        ...

    def runtime_status(self) -> "TranscriptRuntimeStatus":
        ...

    def has_cached_asset(self, asset: Asset) -> bool:
        ...


StatusCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int, Asset], None]

TAKE_SELECTION_MIN_SCORE = 0.68
TAKE_SELECTION_ALT_GAP = 0.08
AUDIO_SNAP_MAX_CENTER_DRIFT_SEC = 2.0
TRANSCRIPT_SELECTIVE_MAX_RMS = 0.02
TRANSCRIPT_SELECTIVE_MIN_AVG_RMS = 0.0075
TRANSCRIPT_SELECTIVE_MIN_PEAK_RMS = 0.012
TRANSCRIPT_SELECTIVE_MIN_NON_SILENT_WINDOWS = 3
TRANSCRIPT_DIRECT_FULL_PASS_MAX_RMS = 0.05
TRANSCRIPT_DIRECT_FULL_PASS_MIN_AVG_RMS = 0.02
TRANSCRIPT_PROBE_DURATION_SEC = 4.0
TRANSCRIPT_PROBE_MAX_WINDOWS = 2
TRANSCRIPT_PROBE_MIN_ALPHA_CHARS = 8
TRANSCRIPT_TURN_MAX_INTERNAL_GAP_SEC = 0.9
TRANSCRIPT_TURN_BREAK_GAP_SEC = 1.35
TRANSCRIPT_TURN_BOUNDARY_TOLERANCE_SEC = 0.45
TRANSCRIPT_TURN_REFINE_MARGIN_SEC = 0.75
TRANSCRIPT_TURN_CONTINUITY_GAP_SEC = 0.55
SPOKEN_STRUCTURE_MONOLOGUE_GAP_SEC = 0.95
SPOKEN_STRUCTURE_QUESTION_ANSWER_GAP_SEC = 1.6
TIMELINE_VISUAL_BASE_MAX_DURATION_SEC = 5.0
TIMELINE_VISUAL_REFINED_MAX_DURATION_SEC = 6.5
TIMELINE_VISUAL_MERGED_MAX_DURATION_SEC = 7.0
ASSEMBLY_MERGE_MAX_GAP_SEC = 1.25
ASSEMBLY_MERGE_STRUCTURAL_GAP_SEC = 0.4
ASSEMBLY_MERGE_STRUCTURAL_MAX_DURATION_SEC = 7.5
ASSEMBLY_TRANSCRIPT_CONTINUITY_GAP_SEC = 0.9
ASSEMBLY_SPLIT_MIN_DURATION_SEC = 6.5
ASSEMBLY_SPLIT_MIN_PART_SEC = 2.0
ASSEMBLY_SPLIT_TRANSCRIPT_GAP_SEC = 1.25
ASSEMBLY_SPLIT_SCENE_EDGE_BUFFER_SEC = 1.5


@dataclass(slots=True)
class TranscriptSpan:
    start_sec: float
    end_sec: float
    text: str


@dataclass(slots=True)
class TranscriptTurn:
    id: str
    start_sec: float
    end_sec: float
    text: str
    span_count: int


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


@dataclass(slots=True)
class SpokenStructureEvidence:
    label: str
    cues: list[str]
    confidence: float
    question_answer_flow: float
    monologue_continuity: float
    spoken_beat_completeness: float


@dataclass(slots=True)
class TranscriptRuntimeStatus:
    configured_provider: str
    effective_provider: str
    model_size: str
    enabled: bool
    available: bool
    status: str
    detail: str
    transcribed_asset_count: int = 0
    failed_asset_count: int = 0
    cached_asset_count: int = 0
    probed_asset_count: int = 0
    probe_rejected_asset_count: int = 0


@dataclass(slots=True)
class RefinedSegmentCandidate:
    start_sec: float
    end_sec: float
    boundary_strategy: str
    boundary_confidence: float
    seed_region_ids: list[str]
    seed_region_sources: list[str]
    seed_region_ranges_sec: list[list[float]]
    transcript_turn_ids: list[str] | None = None
    transcript_turn_ranges_sec: list[list[float]] | None = None
    transcript_turn_alignment: str = ""


@dataclass(slots=True)
class AssemblyContinuitySignals:
    gap_sec: float
    transcript_span_count: int
    transcript_internal_gap_sec: float
    transcript_turn_count: int
    transcript_turn_gap_sec: float
    same_analysis_mode: bool
    shared_seed_source: bool
    scene_divider_between: bool
    shared_turn: bool
    consecutive_turns: bool
    strong_turn_break_between: bool
    question_answer_flow: bool
    monologue_continuity: bool


@dataclass(slots=True)
class StoryAssemblyChoice:
    take: TakeRecommendation
    sequence_score: float
    sequence_group: str
    sequence_role: str
    sequence_rationale: list[str]
    sequence_driver_labels: list[str]
    sequence_tradeoff_labels: list[str]


@dataclass(slots=True)
class StoryAssemblyEvaluation:
    score: float
    driver_labels: list[str]
    tradeoff_labels: list[str]
    matched_prompt_terms: list[str]


class NoOpTranscriptProvider:
    def __init__(
        self,
        *,
        configured_provider: str = "disabled",
        effective_provider: str = "none",
        model_size: str = "",
        enabled: bool = False,
        available: bool = False,
        status: str = "disabled",
        detail: str = "Transcript extraction is disabled.",
    ) -> None:
        self._status = TranscriptRuntimeStatus(
            configured_provider=configured_provider,
            effective_provider=effective_provider,
            model_size=model_size,
            enabled=enabled,
            available=available,
            status=status,
            detail=detail,
        )

    def excerpt(self, asset: Asset, start_sec: float, end_sec: float) -> str:
        return ""

    def spans(self, asset: Asset, start_sec: float, end_sec: float) -> list[TranscriptSpan]:
        return []

    def runtime_status(self) -> TranscriptRuntimeStatus:
        return self._status

    def has_cached_asset(self, asset: Asset) -> bool:
        return False


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
    def __init__(
        self,
        model_size: str = "small",
        *,
        configured_provider: str = "faster-whisper",
        cache_root: str | Path | None = None,
    ) -> None:
        self.configured_provider = configured_provider
        self.model_size = model_size
        self.cache_root = Path(cache_root) if cache_root is not None else None
        self._model = None
        self._cache: dict[str, list[TranscriptSpan]] = {}
        self._transcribed_assets: set[str] = set()
        self._failed_assets: set[str] = set()
        self._cached_assets: set[str] = set()
        self._probed_assets: set[str] = set()
        self._probe_rejected_assets: set[str] = set()
        self._probe_cache: dict[str, bool] = {}
        self._last_error: str = ""
        self._model_load_failed = False
        self._device = "cpu"
        self._compute_type = "float32"

    def excerpt(self, asset: Asset, start_sec: float, end_sec: float) -> str:
        spec = importlib.util.find_spec("faster_whisper")
        if spec is None:
            return ""

        lines = [
            span.text
            for span in self.spans(asset, start_sec, end_sec)
            if span.text
        ]
        return " ".join(lines).strip()

    def spans(self, asset: Asset, start_sec: float, end_sec: float) -> list[TranscriptSpan]:
        if importlib.util.find_spec("faster_whisper") is None:
            return []
        self._ensure_cached(asset)
        return [
            TranscriptSpan(
                start_sec=span.start_sec,
                end_sec=span.end_sec,
                text=span.text,
            )
            for span in self._cache.get(asset.proxy_path, [])
            if span.end_sec >= start_sec and span.start_sec <= end_sec and span.text
        ]

    def _ensure_cached(self, asset: Asset) -> None:
        if asset.proxy_path in self._failed_assets:
            return

        if asset.proxy_path in self._cache:
            return

        if self._load_cached_spans(asset):
            return

        if not self._ensure_model_loaded():
            return

        try:
            segments, _info = self._model.transcribe(asset.proxy_path, vad_filter=True)
            self._cache[asset.proxy_path] = [
                TranscriptSpan(
                    start_sec=float(segment.start),
                    end_sec=float(segment.end),
                    text=segment.text.strip(),
                )
                for segment in segments
                if segment.text.strip()
            ]
            self._transcribed_assets.add(asset.proxy_path)
            self._write_cached_spans(asset, self._cache[asset.proxy_path])
        except Exception as exc:
            self._failed_assets.add(asset.proxy_path)
            self._cache[asset.proxy_path] = []
            self._last_error = str(exc)
            logger.warning("Transcript extraction failed for %s: %s", asset.proxy_path, exc)

    def _ensure_model_loaded(self) -> bool:
        if self._model is not None:
            return True
        try:
            module = importlib.import_module("faster_whisper")
            self._device, self._compute_type = resolve_faster_whisper_runtime()
            self._model = module.WhisperModel(
                self.model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            return True
        except Exception as exc:
            self._model_load_failed = True
            self._last_error = str(exc)
            logger.warning("faster-whisper model load failed: %s", exc)
            return False

    def probe(self, asset: Asset, clip_ranges: list[tuple[float, float]]) -> bool:
        if not clip_ranges:
            return True
        if asset.proxy_path in self._cache or self._load_cached_spans(asset):
            return True
        if asset.proxy_path in self._probe_cache:
            return self._probe_cache[asset.proxy_path]
        if not self._ensure_model_loaded():
            return True

        normalized = _normalize_transcript_probe_ranges(asset, clip_ranges)
        if not normalized:
            return True
        clip_timestamps = ",".join(
            f"{start_sec:.3f},{end_sec:.3f}"
            for start_sec, end_sec in normalized
        )
        try:
            segments, _info = self._model.transcribe(
                asset.proxy_path,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=False,
                clip_timestamps=clip_timestamps,
            )
            probe_text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning("Transcript probe failed for %s: %s", asset.proxy_path, exc)
            return True

        accepted = transcript_probe_detects_text(probe_text)
        self._probed_assets.add(asset.proxy_path)
        self._probe_cache[asset.proxy_path] = accepted
        if not accepted:
            self._probe_rejected_assets.add(asset.proxy_path)
        return accepted

    def _asset_cache_path(self, asset: Asset) -> Path | None:
        if self.cache_root is None:
            return None
        try:
            stat = Path(asset.proxy_path).stat()
        except OSError:
            return None
        key = md5(
            f"{asset.proxy_path}|{stat.st_mtime_ns}|{stat.st_size}|{self.model_size}".encode("utf-8")
        ).hexdigest()
        return self.cache_root / f"{key}.json"

    def has_cached_asset(self, asset: Asset) -> bool:
        cache_path = self._asset_cache_path(asset)
        return cache_path is not None and cache_path.is_file()

    def _load_cached_spans(self, asset: Asset) -> bool:
        cache_path = self._asset_cache_path(asset)
        if cache_path is None or not cache_path.is_file():
            return False
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            spans = [
                TranscriptSpan(
                    start_sec=float(item["start_sec"]),
                    end_sec=float(item["end_sec"]),
                    text=str(item["text"]).strip(),
                )
                for item in payload.get("spans", [])
                if str(item.get("text", "")).strip()
            ]
        except Exception as exc:
            logger.warning("Transcript cache read failed for %s: %s", asset.proxy_path, exc)
            return False
        self._cache[asset.proxy_path] = spans
        self._cached_assets.add(asset.proxy_path)
        return True

    def _write_cached_spans(self, asset: Asset, spans: list[TranscriptSpan]) -> None:
        cache_path = self._asset_cache_path(asset)
        if cache_path is None:
            return
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "proxy_path": asset.proxy_path,
                        "model_size": self.model_size,
                        "spans": [
                            {
                                "start_sec": round(span.start_sec, 3),
                                "end_sec": round(span.end_sec, 3),
                                "text": span.text,
                            }
                            for span in spans
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Transcript cache write failed for %s: %s", asset.proxy_path, exc)

    def runtime_status(self) -> TranscriptRuntimeStatus:
        detail = (
            "faster-whisper transcription is active "
            f"with model size '{self.model_size}' on {self._device} using {self._compute_type}."
            if not self._last_error
            else (
                "faster-whisper transcription is active "
                f"with model size '{self.model_size}' on {self._device} using {self._compute_type}, "
                f"but encountered errors: {self._last_error}"
            )
        )
        status = "active" if not (self._failed_assets or self._model_load_failed) else "partial-fallback"
        return TranscriptRuntimeStatus(
            configured_provider=self.configured_provider,
            effective_provider="faster-whisper",
            model_size=self.model_size,
            enabled=True,
            available=True,
            status=status,
            detail=detail,
            transcribed_asset_count=len(self._transcribed_assets),
            failed_asset_count=len(self._failed_assets) + (1 if self._model_load_failed else 0),
            cached_asset_count=len(self._cached_assets),
            probed_asset_count=len(self._probed_assets),
            probe_rejected_asset_count=len(self._probe_rejected_assets),
        )


def resolve_faster_whisper_runtime() -> tuple[str, str]:
    device = "cpu"
    compute_type = "float32"
    try:
        ctranslate2 = importlib.import_module("ctranslate2")
        supported = set(ctranslate2.get_supported_compute_types(device))
        if "int8_float32" in supported:
            compute_type = "int8_float32"
        elif "int8" in supported:
            compute_type = "int8"
        elif "float32" in supported:
            compute_type = "float32"
    except Exception:
        pass
    return device, compute_type


def build_transcript_provider(
    config: AIAnalysisConfig,
    *,
    cache_root: str | Path | None = None,
) -> TranscriptProvider:
    provider = config.transcript_provider
    model_size = config.transcript_model_size

    if provider == "disabled":
        return NoOpTranscriptProvider(
            configured_provider="disabled",
            effective_provider="none",
            model_size=model_size,
            enabled=False,
            available=False,
            status="disabled",
            detail="Transcript extraction is disabled by configuration.",
        )

    if importlib.util.find_spec("faster_whisper") is None:
        return NoOpTranscriptProvider(
            configured_provider=provider,
            effective_provider="none",
            model_size=model_size,
            enabled=True,
            available=False,
            status="unavailable",
            detail=(
                "Transcript extraction is enabled but `faster_whisper` is not installed. "
                "Speech-aware fallback will be used when speech signals are strong."
            ),
        )

    return FasterWhisperAdapter(
        model_size=model_size,
        configured_provider=provider,
        cache_root=cache_root,
    )


def transcript_runtime_status(transcriber: TranscriptProvider) -> TranscriptRuntimeStatus:
    status_getter = getattr(transcriber, "runtime_status", None)
    if callable(status_getter):
        return status_getter()
    return TranscriptRuntimeStatus(
        configured_provider="unknown",
        effective_provider="none",
        model_size="",
        enabled=False,
        available=False,
        status="unknown",
        detail="Transcript runtime status is unavailable.",
    )


def transcript_cache_available(transcriber: TranscriptProvider, asset: Asset) -> bool:
    cache_checker = getattr(transcriber, "has_cached_asset", None)
    if callable(cache_checker):
        return bool(cache_checker(asset))
    return False


def transcript_probe_allows_full_pass(
    transcriber: TranscriptProvider,
    *,
    asset: Asset,
    probe_ranges: list[tuple[float, float]],
) -> bool:
    probe_fn = getattr(transcriber, "probe", None)
    if callable(probe_fn):
        return bool(probe_fn(asset, probe_ranges))
    return True


def should_request_transcript_for_asset(
    *,
    asset: Asset,
    audio_signals,
    transcriber: TranscriptProvider,
    runtime_status: TranscriptRuntimeStatus,
) -> bool:
    if not asset.has_speech or not runtime_status.enabled or not runtime_status.available:
        return False
    if transcript_cache_available(transcriber, asset):
        return True
    relevant = [signal for signal in audio_signals if signal.source == "ffmpeg"]
    if not relevant:
        return False
    non_silent = [signal for signal in relevant if not signal.is_silent]
    avg_rms = sum(signal.rms_energy for signal in relevant) / len(relevant)
    max_rms = max(signal.rms_energy for signal in relevant)
    if max_rms >= TRANSCRIPT_SELECTIVE_MAX_RMS:
        return True
    if len(non_silent) >= TRANSCRIPT_SELECTIVE_MIN_NON_SILENT_WINDOWS and avg_rms >= TRANSCRIPT_SELECTIVE_MIN_AVG_RMS:
        return True
    if len(non_silent) >= 2 and max_rms >= TRANSCRIPT_SELECTIVE_MIN_PEAK_RMS and avg_rms >= 0.0065:
        return True
    return False


def should_probe_before_full_transcript(audio_signals) -> bool:
    relevant = [signal for signal in audio_signals if signal.source == "ffmpeg"]
    if not relevant:
        return False
    non_silent = [signal for signal in relevant if not signal.is_silent]
    if not non_silent:
        return False
    avg_rms = sum(signal.rms_energy for signal in relevant) / len(relevant)
    max_rms = max(signal.rms_energy for signal in relevant)
    if max_rms >= TRANSCRIPT_DIRECT_FULL_PASS_MAX_RMS:
        return False
    if len(non_silent) >= 4 and avg_rms >= TRANSCRIPT_DIRECT_FULL_PASS_MIN_AVG_RMS:
        return False
    return True


def should_probe_after_selective_skip(audio_signals) -> bool:
    relevant = [signal for signal in audio_signals if signal.source == "ffmpeg"]
    if not relevant:
        return False
    non_silent = [signal for signal in relevant if not signal.is_silent]
    if not non_silent:
        return False
    avg_rms = sum(signal.rms_energy for signal in relevant) / len(relevant)
    max_rms = max(signal.rms_energy for signal in relevant)
    return avg_rms >= 0.003 or max_rms >= 0.005


def build_transcript_probe_ranges(asset: Asset, audio_signals) -> list[tuple[float, float]]:
    relevant = [signal for signal in audio_signals if signal.source == "ffmpeg" and not signal.is_silent]
    if not relevant:
        return []
    ordered = sorted(relevant, key=lambda signal: signal.rms_energy, reverse=True)
    selected = ordered[:TRANSCRIPT_PROBE_MAX_WINDOWS]
    ranges: list[tuple[float, float]] = []
    for signal in selected:
        half = TRANSCRIPT_PROBE_DURATION_SEC / 2.0
        start_sec = max(0.0, signal.timestamp_sec - half)
        end_sec = min(asset.duration_sec, start_sec + TRANSCRIPT_PROBE_DURATION_SEC)
        start_sec = max(0.0, end_sec - TRANSCRIPT_PROBE_DURATION_SEC)
        ranges.append((round(start_sec, 3), round(end_sec, 3)))
    return _normalize_transcript_probe_ranges(asset, ranges)


def _normalize_transcript_probe_ranges(
    asset: Asset,
    ranges: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    if not ranges:
        return []
    ordered = sorted(ranges, key=lambda item: (item[0], item[1]))
    merged: list[tuple[float, float]] = []
    for start_sec, end_sec in ordered:
        start_sec = max(0.0, min(asset.duration_sec, start_sec))
        end_sec = max(start_sec, min(asset.duration_sec, end_sec))
        if end_sec - start_sec < 0.5:
            continue
        if not merged:
            merged.append((start_sec, end_sec))
            continue
        previous_start, previous_end = merged[-1]
        if start_sec <= previous_end + 0.25:
            merged[-1] = (previous_start, max(previous_end, end_sec))
        else:
            merged.append((start_sec, end_sec))
    return [(round(start_sec, 3), round(end_sec, 3)) for start_sec, end_sec in merged]


def transcript_probe_detects_text(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    alpha_chars = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]", normalized)
    if len(alpha_chars) < TRANSCRIPT_PROBE_MIN_ALPHA_CHARS:
        return False
    words = [word for word in re.split(r"\s+", normalized) if word]
    return len(words) >= 2


def segment_transcript_status(
    *,
    asset: Asset,
    segment: CandidateSegment,
    runtime_status: TranscriptRuntimeStatus,
    transcript_lookup_attempted: bool = True,
) -> str:
    if not asset.has_speech:
        return "not-applicable"
    if segment.transcript_excerpt.strip():
        return "excerpt-available"
    if not transcript_lookup_attempted and runtime_status.available:
        return "selective-skip"
    if segment.analysis_mode == "speech":
        return "fallback-no-transcript"
    if runtime_status.status == "disabled":
        return "provider-disabled"
    if runtime_status.status == "unavailable":
        return "provider-unavailable"
    if runtime_status.status == "partial-fallback":
        return "provider-partial"
    return "no-transcript-match"


def segment_speech_mode_source(
    *,
    asset: Asset,
    segment: CandidateSegment,
) -> str:
    _analysis_mode, source = infer_analysis_mode(asset, segment.transcript_excerpt, segment.quality_metrics)
    return source


def transcript_spans_for_range(
    transcriber: TranscriptProvider,
    asset: Asset,
    start_sec: float,
    end_sec: float,
) -> list[TranscriptSpan]:
    spans_getter = getattr(transcriber, "spans", None)
    if callable(spans_getter):
        spans = spans_getter(asset, start_sec, end_sec)
        return [
            TranscriptSpan(
                start_sec=float(getattr(span, "start_sec", 0.0)),
                end_sec=float(getattr(span, "end_sec", 0.0)),
                text=str(getattr(span, "text", "")),
            )
            for span in spans
            if float(getattr(span, "end_sec", 0.0)) > float(getattr(span, "start_sec", 0.0))
        ]
    return []


def derive_transcript_turns(transcript_spans: list[TranscriptSpan]) -> list[TranscriptTurn]:
    if not transcript_spans:
        return []

    ordered = sorted(transcript_spans, key=lambda span: (span.start_sec, span.end_sec))
    turns: list[TranscriptTurn] = []
    current: list[TranscriptSpan] = [ordered[0]]

    for span in ordered[1:]:
        previous = current[-1]
        if span.start_sec - previous.end_sec <= TRANSCRIPT_TURN_MAX_INTERNAL_GAP_SEC:
            current.append(span)
            continue
        turns.append(_transcript_turn_from_spans(len(turns) + 1, current))
        current = [span]

    turns.append(_transcript_turn_from_spans(len(turns) + 1, current))
    return turns


def _transcript_turn_from_spans(index: int, spans: list[TranscriptSpan]) -> TranscriptTurn:
    return TranscriptTurn(
        id=f"turn-{index:02d}",
        start_sec=round(min(span.start_sec for span in spans), 3),
        end_sec=round(max(span.end_sec for span in spans), 3),
        text=" ".join(span.text.strip() for span in spans if span.text.strip()).strip(),
        span_count=len(spans),
    )


def transcript_turns_for_range(
    transcript_turns: list[TranscriptTurn],
    start_sec: float,
    end_sec: float,
) -> list[TranscriptTurn]:
    return [
        turn
        for turn in transcript_turns
        if turn.end_sec >= start_sec and turn.start_sec <= end_sec
    ]


def transcript_turn_alignment(
    transcript_turns: list[TranscriptTurn],
    start_sec: float,
    end_sec: float,
) -> tuple[list[TranscriptTurn], str, float]:
    matched = transcript_turns_for_range(transcript_turns, start_sec, end_sec)
    if not matched:
        return [], "", 0.0

    first_turn = matched[0]
    last_turn = matched[-1]
    turn_window_start = first_turn.start_sec
    turn_window_end = last_turn.end_sec
    covered_duration = max(0.0, min(end_sec, turn_window_end) - max(start_sec, turn_window_start))
    turn_window_duration = max(0.1, turn_window_end - turn_window_start)
    coverage = clamp(covered_duration / turn_window_duration)
    start_edge = clamp(1.0 - abs(start_sec - turn_window_start) / TRANSCRIPT_TURN_BOUNDARY_TOLERANCE_SEC)
    end_edge = clamp(1.0 - abs(end_sec - turn_window_end) / TRANSCRIPT_TURN_BOUNDARY_TOLERANCE_SEC)
    completeness = round(clamp((coverage * 0.55) + (((start_edge + end_edge) / 2.0) * 0.45)), 4)

    if start_edge >= 0.85 and end_edge >= 0.85:
        alignment = "turn-aligned"
    elif coverage >= 0.8:
        alignment = "mostly-complete"
    else:
        alignment = "partial-turn"
    return matched, alignment, completeness


QUESTION_WORDS = {
    "how",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "can",
    "could",
    "did",
    "do",
    "does",
    "is",
    "are",
    "should",
    "will",
    "would",
}


def is_question_like_text(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    if "?" in normalized:
        return True
    words = re.findall(r"[a-z0-9']+", normalized)
    return bool(words) and words[0] in QUESTION_WORDS


def derive_spoken_structure(
    transcript_spans: list[TranscriptSpan],
    *,
    start_sec: float,
    end_sec: float,
    turn_completeness: float,
) -> SpokenStructureEvidence:
    matching_spans = [
        span
        for span in transcript_spans
        if span.end_sec >= start_sec and span.start_sec <= end_sec and span.text.strip()
    ]
    if not matching_spans:
        return SpokenStructureEvidence("", [], 0.0, 0.0, 0.0, round(turn_completeness, 4))

    ordered = sorted(matching_spans, key=lambda span: (span.start_sec, span.end_sec))
    question_answer_flow = 0.0
    monologue_continuity = 0.0
    cues: list[str] = []

    for earlier, later in zip(ordered, ordered[1:]):
        gap_sec = max(0.0, later.start_sec - earlier.end_sec)
        if (
            is_question_like_text(earlier.text)
            and not is_question_like_text(later.text)
            and gap_sec <= SPOKEN_STRUCTURE_QUESTION_ANSWER_GAP_SEC
        ):
            question_answer_flow = 0.9
            cues.extend(["question_prompt", "answer_followthrough"])
            break

    if len(ordered) >= 2 and question_answer_flow == 0.0:
        max_gap = max(
            (max(0.0, later.start_sec - earlier.end_sec) for earlier, later in zip(ordered, ordered[1:])),
            default=0.0,
        )
        question_count = sum(1 for span in ordered if is_question_like_text(span.text))
        if max_gap <= SPOKEN_STRUCTURE_MONOLOGUE_GAP_SEC and question_count == 0:
            monologue_continuity = 0.82
            cues.extend(["monologue_continuity", "multi_span_flow"])
        elif max_gap <= SPOKEN_STRUCTURE_MONOLOGUE_GAP_SEC and question_count == 1 and not is_question_like_text(ordered[-1].text):
            monologue_continuity = 0.68
            cues.extend(["answer_continuation"])

    edge_start = clamp(1.0 - abs(start_sec - ordered[0].start_sec) / TRANSCRIPT_TURN_BOUNDARY_TOLERANCE_SEC)
    edge_end = clamp(1.0 - abs(end_sec - ordered[-1].end_sec) / TRANSCRIPT_TURN_BOUNDARY_TOLERANCE_SEC)
    spoken_beat_completeness = clamp(
        (turn_completeness * 0.6)
        + (((edge_start + edge_end) / 2.0) * 0.25)
        + (question_answer_flow * 0.1)
        + (monologue_continuity * 0.05)
    )

    label = ""
    confidence = 0.0
    if question_answer_flow >= 0.85:
        label = "question-answer-flow"
        confidence = clamp((question_answer_flow * 0.75) + (spoken_beat_completeness * 0.25))
    elif monologue_continuity >= 0.75:
        label = "monologue-continuity"
        confidence = clamp((monologue_continuity * 0.7) + (spoken_beat_completeness * 0.3))
    elif spoken_beat_completeness >= 0.82 and len(ordered) >= 2:
        label = "spoken-beat-complete"
        confidence = spoken_beat_completeness

    return SpokenStructureEvidence(
        label=label,
        cues=dedupe_labels(cues),
        confidence=round(confidence, 4),
        question_answer_flow=round(question_answer_flow, 4),
        monologue_continuity=round(monologue_continuity, 4),
        spoken_beat_completeness=round(spoken_beat_completeness, 4),
    )


def transcript_excerpt_for_range(
    transcriber: TranscriptProvider,
    asset: Asset,
    transcript_spans: list[TranscriptSpan],
    start_sec: float,
    end_sec: float,
    *,
    allow_provider_lookup: bool = True,
) -> str:
    matching = [
        span.text.strip()
        for span in transcript_spans
        if span.end_sec >= start_sec and span.start_sec <= end_sec and span.text.strip()
    ]
    if matching:
        return " ".join(matching).strip()
    if not allow_provider_lookup:
        return ""
    return transcriber.excerpt(asset, start_sec, end_sec).strip()


def make_candidate_segment(
    *,
    asset: Asset,
    segment_id: str,
    start_sec: float,
    end_sec: float,
    transcriber: TranscriptProvider,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    prefilter_signals,
    audio_signals,
    boundary_strategy: str,
    boundary_confidence: float,
    seed_region_ids: list[str],
    seed_region_sources: list[str],
    seed_region_ranges_sec: list[list[float]],
    transcript_lookup_enabled: bool = True,
    assembly_operation: str = "none",
    assembly_rule_family: str = "",
    assembly_source_segment_ids: list[str] | None = None,
    assembly_source_ranges_sec: list[list[float]] | None = None,
) -> CandidateSegment:
    matching_spans = (
        [
            span
            for span in transcript_spans
            if span.end_sec >= start_sec and span.start_sec <= end_sec and span.text.strip()
        ]
        if asset.has_speech
        else []
    )
    excerpt = (
        transcript_excerpt_for_range(
            transcriber,
            asset,
            matching_spans,
            start_sec,
            end_sec,
            allow_provider_lookup=transcript_lookup_enabled,
        )
        if asset.has_speech
        else ""
    )
    matched_turns, turn_alignment, turn_completeness = transcript_turn_alignment(
        transcript_turns,
        start_sec,
        end_sec,
    )
    spoken_structure = derive_spoken_structure(
        matching_spans,
        start_sec=start_sec,
        end_sec=end_sec,
        turn_completeness=turn_completeness,
    )
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
        "visual",
        prefilter_snapshot=prefilter_snapshot["metrics_snapshot"],
    )
    metrics["turn_completeness"] = turn_completeness
    metrics["transcript_turn_count"] = float(len(matched_turns))
    metrics["question_answer_flow"] = spoken_structure.question_answer_flow
    metrics["monologue_continuity"] = spoken_structure.monologue_continuity
    metrics["spoken_beat_completeness"] = spoken_structure.spoken_beat_completeness
    analysis_mode, _analysis_mode_source = infer_analysis_mode(asset, excerpt, metrics)
    return CandidateSegment(
        id=segment_id,
        asset_id=asset.id,
        start_sec=round(start_sec, 3),
        end_sec=round(end_sec, 3),
        analysis_mode=analysis_mode,
        transcript_excerpt=excerpt,
        description=describe_segment(asset, start_sec, end_sec, excerpt, metrics, analysis_mode=analysis_mode),
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
            boundary_strategy=boundary_strategy,
            boundary_confidence=boundary_confidence,
            seed_region_ids=list(seed_region_ids),
            seed_region_sources=list(seed_region_sources),
            seed_region_ranges_sec=[list(item) for item in seed_region_ranges_sec],
            assembly_operation=assembly_operation,
            assembly_rule_family=assembly_rule_family,
            assembly_source_segment_ids=list(assembly_source_segment_ids or []),
            assembly_source_ranges_sec=[list(item) for item in (assembly_source_ranges_sec or [])],
            transcript_turn_ids=[turn.id for turn in matched_turns],
            transcript_turn_ranges_sec=[[turn.start_sec, turn.end_sec] for turn in matched_turns],
            transcript_turn_alignment=turn_alignment,
            speech_structure_label=spoken_structure.label,
            speech_structure_cues=list(spoken_structure.cues),
            speech_structure_confidence=spoken_structure.confidence,
        ),
    )


def refine_seed_regions(
    *,
    asset: Asset,
    seed_regions: list[SeedRegion],
    base_ranges: list[tuple[float, float]],
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    audio_signals,
) -> list[RefinedSegmentCandidate]:
    if not seed_regions:
        return []

    refined: list[RefinedSegmentCandidate] = []
    for seed in seed_regions:
        candidate = (
            _refine_seed_with_transcript(asset, seed, transcript_spans, transcript_turns)
            or _refine_seed_with_audio(asset, seed, audio_signals)
            or _refine_seed_with_scene(asset, seed, base_ranges)
            or _refine_seed_with_duration(asset, seed)
        )
        refined.append(candidate)
    return _dedupe_refined_candidates(refined)


def _refine_seed_with_transcript(
    asset: Asset,
    seed: SeedRegion,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
) -> RefinedSegmentCandidate | None:
    expanded_start = max(0.0, seed.start_sec - TRANSCRIPT_TURN_REFINE_MARGIN_SEC)
    expanded_end = min(asset.duration_sec, seed.end_sec + TRANSCRIPT_TURN_REFINE_MARGIN_SEC)
    if transcript_turns:
        matching_turns = transcript_turns_for_range(transcript_turns, expanded_start, expanded_end)
        if matching_turns:
            matching_turns = extend_transcript_turn_window(matching_turns, transcript_turns)
            start_sec = max(0.0, min(turn.start_sec for turn in matching_turns))
            end_sec = min(asset.duration_sec, max(turn.end_sec for turn in matching_turns))
            if end_sec - start_sec >= 1.0:
                return RefinedSegmentCandidate(
                    start_sec=round(start_sec, 3),
                    end_sec=round(end_sec, 3),
                    boundary_strategy="turn-snap",
                    boundary_confidence=0.93,
                    seed_region_ids=[seed.id],
                    seed_region_sources=[seed.source],
                    seed_region_ranges_sec=[[round(seed.start_sec, 3), round(seed.end_sec, 3)]],
                    transcript_turn_ids=[turn.id for turn in matching_turns],
                    transcript_turn_ranges_sec=[[turn.start_sec, turn.end_sec] for turn in matching_turns],
                    transcript_turn_alignment="turn-aligned",
                )
    if not transcript_spans:
        return None
    matching = [
        span
        for span in transcript_spans
        if span.end_sec >= expanded_start and span.start_sec <= expanded_end
    ]
    if not matching:
        return None
    start_sec = max(0.0, min(span.start_sec for span in matching))
    end_sec = min(asset.duration_sec, max(span.end_sec for span in matching))
    if end_sec - start_sec < 1.0:
        return None
    return RefinedSegmentCandidate(
        start_sec=round(start_sec, 3),
        end_sec=round(end_sec, 3),
        boundary_strategy="transcript-snap",
        boundary_confidence=0.9,
        seed_region_ids=[seed.id],
        seed_region_sources=[seed.source],
        seed_region_ranges_sec=[[round(seed.start_sec, 3), round(seed.end_sec, 3)]],
        transcript_turn_ids=[],
        transcript_turn_ranges_sec=[],
        transcript_turn_alignment="span-aligned",
    )


def extend_transcript_turn_window(
    matching_turns: list[TranscriptTurn],
    transcript_turns: list[TranscriptTurn],
) -> list[TranscriptTurn]:
    if not matching_turns or not transcript_turns:
        return matching_turns
    ordered_all = {turn.id: index for index, turn in enumerate(transcript_turns)}
    extended = list(matching_turns)
    last_turn = extended[-1]
    last_index = ordered_all.get(last_turn.id, -1)
    if last_index < 0 or last_index >= len(transcript_turns) - 1:
        return extended
    next_turn = transcript_turns[last_index + 1]
    gap_sec = max(0.0, next_turn.start_sec - last_turn.end_sec)
    if is_question_like_text(last_turn.text) and gap_sec <= SPOKEN_STRUCTURE_QUESTION_ANSWER_GAP_SEC:
        extended.append(next_turn)
        return extended
    if (
        not is_question_like_text(last_turn.text)
        and not is_question_like_text(next_turn.text)
        and gap_sec <= SPOKEN_STRUCTURE_MONOLOGUE_GAP_SEC
        and len(extended) == 1
    ):
        extended.append(next_turn)
    return extended


def _refine_seed_with_audio(
    asset: Asset,
    seed: SeedRegion,
    audio_signals,
) -> RefinedSegmentCandidate | None:
    if not audio_signals:
        return None
    energetic = [sig for sig in audio_signals if not sig.is_silent and sig.rms_energy >= 0.05]
    if not energetic:
        return None
    center = (seed.start_sec + seed.end_sec) / 2.0
    nearest_idx = min(range(len(audio_signals)), key=lambda idx: abs(audio_signals[idx].timestamp_sec - center))
    if audio_signals[nearest_idx].is_silent or audio_signals[nearest_idx].rms_energy < 0.05:
        nearest_idx = min(range(len(energetic)), key=lambda idx: abs(energetic[idx].timestamp_sec - center))
        center_signal = energetic[nearest_idx]
        nearest_idx = next(
            idx for idx, signal in enumerate(audio_signals)
            if signal.timestamp_sec == center_signal.timestamp_sec and signal.rms_energy == center_signal.rms_energy
        )

    left_idx = nearest_idx
    while left_idx > 0 and not audio_signals[left_idx - 1].is_silent and audio_signals[left_idx - 1].rms_energy >= 0.05:
        left_idx -= 1
    right_idx = nearest_idx
    while right_idx < len(audio_signals) - 1 and not audio_signals[right_idx + 1].is_silent and audio_signals[right_idx + 1].rms_energy >= 0.05:
        right_idx += 1

    step = _average_signal_step(audio_signals)
    start_sec = max(0.0, audio_signals[left_idx].timestamp_sec - step / 2.0)
    end_sec = min(asset.duration_sec, audio_signals[right_idx].timestamp_sec + step / 2.0)
    snapped_center = (start_sec + end_sec) / 2.0
    if abs(snapped_center - center) > AUDIO_SNAP_MAX_CENTER_DRIFT_SEC:
        return None
    if end_sec - start_sec < 1.0:
        return None
    return RefinedSegmentCandidate(
        start_sec=round(start_sec, 3),
        end_sec=round(end_sec, 3),
        boundary_strategy="audio-snap",
        boundary_confidence=0.74,
        seed_region_ids=[seed.id],
        seed_region_sources=[seed.source],
        seed_region_ranges_sec=[[round(seed.start_sec, 3), round(seed.end_sec, 3)]],
    )


def _refine_seed_with_scene(
    asset: Asset,
    seed: SeedRegion,
    base_ranges: list[tuple[float, float]],
) -> RefinedSegmentCandidate | None:
    if not base_ranges:
        return None
    center = (seed.start_sec + seed.end_sec) / 2.0
    containing = [item for item in base_ranges if item[0] <= center <= item[1]]
    if containing:
        scene_start, scene_end = containing[0]
    else:
        scene_start, scene_end = max(
            base_ranges,
            key=lambda item: min(item[1], seed.end_sec) - max(item[0], seed.start_sec),
        )
    if scene_end - scene_start > 8.0:
        return _refine_seed_with_duration(asset, seed, strategy="scene-duration")
    return RefinedSegmentCandidate(
        start_sec=round(max(0.0, scene_start), 3),
        end_sec=round(min(asset.duration_sec, scene_end), 3),
        boundary_strategy="scene-snap",
        boundary_confidence=0.62,
        seed_region_ids=[seed.id],
        seed_region_sources=[seed.source],
        seed_region_ranges_sec=[[round(seed.start_sec, 3), round(seed.end_sec, 3)]],
    )


def _refine_seed_with_duration(
    asset: Asset,
    seed: SeedRegion,
    *,
    strategy: str = "duration-rule",
) -> RefinedSegmentCandidate:
    center = (seed.start_sec + seed.end_sec) / 2.0
    duration = max(1.5, min(6.0, seed.end_sec - seed.start_sec))
    half = duration / 2.0
    start_sec = max(0.0, center - half)
    end_sec = min(asset.duration_sec, center + half)
    return RefinedSegmentCandidate(
        start_sec=round(start_sec, 3),
        end_sec=round(end_sec, 3),
        boundary_strategy=strategy,
        boundary_confidence=0.48,
        seed_region_ids=[seed.id],
        seed_region_sources=[seed.source],
        seed_region_ranges_sec=[[round(seed.start_sec, 3), round(seed.end_sec, 3)]],
    )


def _average_signal_step(signals) -> float:
    if len(signals) < 2:
        return 1.0
    deltas = [
        later.timestamp_sec - earlier.timestamp_sec
        for earlier, later in zip(signals, signals[1:])
        if later.timestamp_sec > earlier.timestamp_sec
    ]
    if not deltas:
        return 1.0
    return sum(deltas) / len(deltas)


def _dedupe_refined_candidates(candidates: list[RefinedSegmentCandidate]) -> list[RefinedSegmentCandidate]:
    if not candidates:
        return []
    ordered = sorted(
        candidates,
        key=lambda item: (item.boundary_confidence, -(item.end_sec - item.start_sec)),
        reverse=True,
    )
    kept: list[RefinedSegmentCandidate] = []
    for candidate in ordered:
        if any(_range_overlap_ratio((candidate.start_sec, candidate.end_sec), (existing.start_sec, existing.end_sec)) >= 0.9 for existing in kept):
            continue
        kept.append(candidate)
    return sorted(kept, key=lambda item: item.start_sec)


def _range_overlap_ratio(a: tuple[float, float], b: tuple[float, float]) -> float:
    start = max(a[0], b[0])
    end = min(a[1], b[1])
    if end <= start:
        return 0.0
    overlap = end - start
    shorter = min(a[1] - a[0], b[1] - b[0])
    return overlap / shorter if shorter > 0 else 0.0


def assemble_narrative_units(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    base_ranges: list[tuple[float, float]],
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    transcriber: TranscriptProvider,
    prefilter_signals,
    audio_signals,
) -> list[CandidateSegment]:
    if not segments:
        return []

    split_segments: list[CandidateSegment] = []
    for segment in sorted(segments, key=lambda item: item.start_sec):
        split_segments.extend(
            split_candidate_segment(
                asset=asset,
                segment=segment,
                base_ranges=base_ranges,
                transcript_spans=transcript_spans,
                transcript_turns=transcript_turns,
                transcriber=transcriber,
                prefilter_signals=prefilter_signals,
                audio_signals=audio_signals,
            )
        )

    merged_segments = merge_adjacent_segments(
        asset=asset,
        segments=split_segments,
        base_ranges=base_ranges,
        transcript_spans=transcript_spans,
        transcript_turns=transcript_turns,
        transcriber=transcriber,
        prefilter_signals=prefilter_signals,
        audio_signals=audio_signals,
    )

    return [
        replace(segment, id=f"{asset.id}-segment-{index:02d}")
        for index, segment in enumerate(merged_segments, start=1)
    ]


def split_candidate_segment(
    *,
    asset: Asset,
    segment: CandidateSegment,
    base_ranges: list[tuple[float, float]],
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    transcriber: TranscriptProvider,
    prefilter_signals,
    audio_signals,
) -> list[CandidateSegment]:
    divider, rule_family = _find_segment_split_divider(segment, base_ranges, transcript_spans, transcript_turns)
    if divider is None or not rule_family:
        return [segment]

    prefilter = segment.prefilter
    if prefilter is None:
        return [segment]

    boundary_confidence = round(clamp(max(prefilter.boundary_confidence, 0.45) * 0.92), 4)
    source_segment_ids = assembly_source_segment_ids(segment)
    source_ranges = assembly_source_ranges_sec(segment)
    split_ranges = [(segment.start_sec, divider), (divider, segment.end_sec)]
    parts: list[CandidateSegment] = []
    for part_index, (start_sec, end_sec) in enumerate(split_ranges, start=1):
        if end_sec - start_sec < ASSEMBLY_SPLIT_MIN_PART_SEC:
            return [segment]
        parts.append(
            make_candidate_segment(
                asset=asset,
                segment_id=f"{segment.id}-split-{part_index}",
                start_sec=start_sec,
                end_sec=end_sec,
                transcriber=transcriber,
                transcript_spans=transcript_spans,
                transcript_turns=transcript_turns,
                prefilter_signals=prefilter_signals,
                audio_signals=audio_signals,
                boundary_strategy=f"assembly-split:{rule_family}",
                boundary_confidence=boundary_confidence,
                seed_region_ids=prefilter.seed_region_ids,
                seed_region_sources=prefilter.seed_region_sources,
                seed_region_ranges_sec=prefilter.seed_region_ranges_sec,
                transcript_lookup_enabled=bool(transcript_spans),
                assembly_operation="split",
                assembly_rule_family=rule_family,
                assembly_source_segment_ids=source_segment_ids,
                assembly_source_ranges_sec=source_ranges,
            )
        )
    return parts


def merge_adjacent_segments(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    base_ranges: list[tuple[float, float]],
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    transcriber: TranscriptProvider,
    prefilter_signals,
    audio_signals,
) -> list[CandidateSegment]:
    if not segments:
        return []

    ordered = sorted(segments, key=lambda item: (item.start_sec, item.end_sec))
    merged: list[CandidateSegment] = []
    buffer: list[CandidateSegment] = [ordered[0]]
    buffer_rules: list[str] = []

    for candidate in ordered[1:]:
        signals = collect_assembly_continuity_signals(buffer[-1], candidate, transcript_spans, transcript_turns, base_ranges)
        rule_family = merge_rule_family(buffer[-1], candidate, signals)
        if rule_family:
            buffer.append(candidate)
            buffer_rules.append(rule_family)
            continue
        merged.append(
            materialize_merged_segment(
                asset=asset,
                segments=buffer,
                rule_families=buffer_rules,
                transcriber=transcriber,
                transcript_spans=transcript_spans,
                transcript_turns=transcript_turns,
                prefilter_signals=prefilter_signals,
                audio_signals=audio_signals,
            )
        )
        buffer = [candidate]
        buffer_rules = []

    merged.append(
        materialize_merged_segment(
            asset=asset,
            segments=buffer,
            rule_families=buffer_rules,
            transcriber=transcriber,
            transcript_spans=transcript_spans,
            transcript_turns=transcript_turns,
            prefilter_signals=prefilter_signals,
            audio_signals=audio_signals,
        )
    )
    return merged


def collect_assembly_continuity_signals(
    left: CandidateSegment,
    right: CandidateSegment,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    base_ranges: list[tuple[float, float]],
) -> AssemblyContinuitySignals:
    gap_sec = round(max(0.0, right.start_sec - left.end_sec), 3)
    matching_spans = sorted(
        [
            span
            for span in transcript_spans
            if span.end_sec >= left.start_sec and span.start_sec <= right.end_sec
        ],
        key=lambda span: (span.start_sec, span.end_sec),
    )
    transcript_gap = largest_transcript_gap(matching_spans)
    matching_turns = transcript_turns_for_range(transcript_turns, left.start_sec, right.end_sec)
    transcript_turn_gap = largest_transcript_turn_gap(matching_turns)
    scene_boundaries = scene_boundaries_from_ranges(base_ranges)
    scene_divider_between = any(left.end_sec <= boundary <= right.start_sec for boundary in scene_boundaries)
    left_sources = set(left.prefilter.seed_region_sources if left.prefilter is not None else [])
    right_sources = set(right.prefilter.seed_region_sources if right.prefilter is not None else [])
    left_turn_ids = set(left.prefilter.transcript_turn_ids if left.prefilter is not None else [])
    right_turn_ids = set(right.prefilter.transcript_turn_ids if right.prefilter is not None else [])
    shared_turn = bool(left_turn_ids.intersection(right_turn_ids))
    consecutive_turns = False
    strong_turn_break_between = False
    question_answer_flow = False
    monologue_continuity = False
    if left_turn_ids and right_turn_ids and transcript_turns:
        order_by_id = {turn.id: index for index, turn in enumerate(transcript_turns)}
        left_last = max((order_by_id[turn_id] for turn_id in left_turn_ids if turn_id in order_by_id), default=-1)
        right_first = min((order_by_id[turn_id] for turn_id in right_turn_ids if turn_id in order_by_id), default=-1)
        if left_last >= 0 and right_first >= 0 and right_first - left_last == 1:
            consecutive_turns = True
            turn_gap = transcript_turns[right_first].start_sec - transcript_turns[left_last].end_sec
            strong_turn_break_between = turn_gap >= TRANSCRIPT_TURN_BREAK_GAP_SEC
    left_is_question = bool(left.transcript_excerpt.strip()) and is_question_like_text(left.transcript_excerpt)
    right_is_question = bool(right.transcript_excerpt.strip()) and is_question_like_text(right.transcript_excerpt)
    if (
        left.analysis_mode == "speech"
        and right.analysis_mode == "speech"
        and left_is_question
        and not right_is_question
        and gap_sec <= SPOKEN_STRUCTURE_QUESTION_ANSWER_GAP_SEC
    ):
        question_answer_flow = True
    if (
        left.analysis_mode == "speech"
        and right.analysis_mode == "speech"
        and not left_is_question
        and not right_is_question
        and gap_sec <= SPOKEN_STRUCTURE_MONOLOGUE_GAP_SEC
        and not scene_divider_between
    ):
        monologue_continuity = True
    return AssemblyContinuitySignals(
        gap_sec=gap_sec,
        transcript_span_count=len(matching_spans),
        transcript_internal_gap_sec=transcript_gap,
        transcript_turn_count=len(matching_turns),
        transcript_turn_gap_sec=transcript_turn_gap,
        same_analysis_mode=left.analysis_mode == right.analysis_mode,
        shared_seed_source=bool(left_sources.intersection(right_sources)),
        scene_divider_between=scene_divider_between,
        shared_turn=shared_turn,
        consecutive_turns=consecutive_turns,
        strong_turn_break_between=strong_turn_break_between,
        question_answer_flow=question_answer_flow,
        monologue_continuity=monologue_continuity,
    )


def merge_rule_family(
    left: CandidateSegment,
    right: CandidateSegment,
    signals: AssemblyContinuitySignals,
) -> str:
    left_source_ids = assembly_source_segment_ids(left)
    right_source_ids = assembly_source_segment_ids(right)
    if (
        left.prefilter is not None
        and right.prefilter is not None
        and left.prefilter.assembly_operation == "split"
        and right.prefilter.assembly_operation == "split"
        and left_source_ids == right_source_ids
    ):
        return ""
    if signals.gap_sec > ASSEMBLY_MERGE_MAX_GAP_SEC:
        return ""
    if (
        signals.question_answer_flow
        and not signals.scene_divider_between
        and not signals.strong_turn_break_between
    ):
        return "question-answer-flow"
    if (
        signals.monologue_continuity
        and not signals.scene_divider_between
        and signals.gap_sec <= SPOKEN_STRUCTURE_MONOLOGUE_GAP_SEC
    ):
        return "monologue-continuity"
    if (
        (signals.shared_turn or signals.consecutive_turns)
        and not signals.strong_turn_break_between
        and signals.transcript_turn_gap_sec <= TRANSCRIPT_TURN_CONTINUITY_GAP_SEC
        and not signals.scene_divider_between
    ):
        return "turn-continuity"
    if (
        signals.transcript_span_count >= 2
        and signals.transcript_internal_gap_sec <= ASSEMBLY_TRANSCRIPT_CONTINUITY_GAP_SEC
        and not signals.scene_divider_between
    ):
        return "transcript-continuity"
    if (
        signals.gap_sec <= ASSEMBLY_MERGE_STRUCTURAL_GAP_SEC
        and max(left.end_sec, right.end_sec) - min(left.start_sec, right.start_sec) <= ASSEMBLY_MERGE_STRUCTURAL_MAX_DURATION_SEC
        and not signals.scene_divider_between
        and (
            signals.same_analysis_mode
            or signals.shared_seed_source
            or left.analysis_mode == "speech"
            or right.analysis_mode == "speech"
        )
    ):
        return "structural-continuity"
    return ""


def materialize_merged_segment(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    rule_families: list[str],
    transcriber: TranscriptProvider,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    prefilter_signals,
    audio_signals,
) -> CandidateSegment:
    if len(segments) == 1:
        return segments[0]

    unique_rule_families = list(dict.fromkeys(rule_families))
    rule_family = unique_rule_families[0] if len(unique_rule_families) == 1 else "continuity-chain"
    prefilters = [segment.prefilter for segment in segments if segment.prefilter is not None]
    boundary_confidence = round(
        clamp(sum(prefilter.boundary_confidence for prefilter in prefilters) / max(1, len(prefilters))),
        4,
    )

    return make_candidate_segment(
        asset=asset,
        segment_id=f"{asset.id}-merged-{segments[0].id}-{segments[-1].id}",
        start_sec=segments[0].start_sec,
        end_sec=segments[-1].end_sec,
        transcriber=transcriber,
        transcript_spans=transcript_spans,
        transcript_turns=transcript_turns,
        prefilter_signals=prefilter_signals,
        audio_signals=audio_signals,
        boundary_strategy=f"assembly-merge:{rule_family}",
        boundary_confidence=boundary_confidence,
        seed_region_ids=flatten_prefilter_lists(segments, "seed_region_ids"),
        seed_region_sources=flatten_prefilter_lists(segments, "seed_region_sources"),
        seed_region_ranges_sec=flatten_prefilter_range_lists(segments, "seed_region_ranges_sec"),
        transcript_lookup_enabled=bool(transcript_spans),
        assembly_operation="merge",
        assembly_rule_family=rule_family,
        assembly_source_segment_ids=flatten_source_segment_ids(segments),
        assembly_source_ranges_sec=flatten_source_ranges(segments),
    )


def _find_segment_split_divider(
    segment: CandidateSegment,
    base_ranges: list[tuple[float, float]],
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
) -> tuple[float | None, str]:
    if segment.end_sec - segment.start_sec < ASSEMBLY_SPLIT_MIN_DURATION_SEC:
        return None, ""

    matching_turns = transcript_turns_for_range(transcript_turns, segment.start_sec, segment.end_sec)
    if len(matching_turns) >= 2:
        for earlier, later in zip(matching_turns, matching_turns[1:]):
            gap_sec = later.start_sec - earlier.end_sec
            divider = round((earlier.end_sec + later.start_sec) / 2.0, 3)
            if (
                gap_sec >= TRANSCRIPT_TURN_BREAK_GAP_SEC
                and divider - segment.start_sec >= ASSEMBLY_SPLIT_MIN_PART_SEC
                and segment.end_sec - divider >= ASSEMBLY_SPLIT_MIN_PART_SEC
            ):
                return divider, "turn-break"

    matching_spans = sorted(
        [
            span
            for span in transcript_spans
            if span.end_sec >= segment.start_sec and span.start_sec <= segment.end_sec
        ],
        key=lambda span: (span.start_sec, span.end_sec),
    )
    gap_candidates: list[tuple[float, float]] = []
    for earlier, later in zip(matching_spans, matching_spans[1:]):
        gap_sec = later.start_sec - earlier.end_sec
        divider = round((earlier.end_sec + later.start_sec) / 2.0, 3)
        if (
            gap_sec >= ASSEMBLY_SPLIT_TRANSCRIPT_GAP_SEC
            and divider - segment.start_sec >= ASSEMBLY_SPLIT_MIN_PART_SEC
            and segment.end_sec - divider >= ASSEMBLY_SPLIT_MIN_PART_SEC
        ):
            gap_candidates.append((gap_sec, divider))
    if len(matching_spans) >= 3 and gap_candidates:
        _gap_sec, divider = max(gap_candidates, key=lambda item: item[0])
        return divider, "transcript-gap"

    scene_boundaries = scene_boundaries_from_ranges(base_ranges)
    eligible_boundaries = [
        boundary
        for boundary in scene_boundaries
        if segment.start_sec + ASSEMBLY_SPLIT_SCENE_EDGE_BUFFER_SEC
        <= boundary
        <= segment.end_sec - ASSEMBLY_SPLIT_SCENE_EDGE_BUFFER_SEC
    ]
    if not eligible_boundaries:
        return None, ""
    if matching_spans:
        for boundary in eligible_boundaries:
            has_left = any(span.start_sec < boundary for span in matching_spans)
            has_right = any(span.end_sec > boundary for span in matching_spans)
            if has_left and has_right:
                return round(boundary, 3), "scene-divider"
        return None, ""

    boundary = min(
        eligible_boundaries,
        key=lambda item: abs(item - ((segment.start_sec + segment.end_sec) / 2.0)),
    )
    return round(boundary, 3), "scene-divider"


def largest_transcript_gap(spans: list[TranscriptSpan]) -> float:
    largest_gap = 0.0
    for earlier, later in zip(spans, spans[1:]):
        largest_gap = max(largest_gap, later.start_sec - earlier.end_sec)
    return round(max(0.0, largest_gap), 3)


def largest_transcript_turn_gap(turns: list[TranscriptTurn]) -> float:
    largest_gap = 0.0
    for earlier, later in zip(turns, turns[1:]):
        largest_gap = max(largest_gap, later.start_sec - earlier.end_sec)
    return round(max(0.0, largest_gap), 3)


def scene_boundaries_from_ranges(base_ranges: list[tuple[float, float]]) -> list[float]:
    return [round(end_sec, 3) for _start_sec, end_sec in base_ranges[:-1]]


def flatten_prefilter_lists(segments: list[CandidateSegment], attribute: str) -> list[str]:
    values: list[str] = []
    for segment in segments:
        prefilter = segment.prefilter
        if prefilter is None:
            continue
        for value in getattr(prefilter, attribute):
            if value not in values:
                values.append(value)
    return values


def flatten_prefilter_range_lists(segments: list[CandidateSegment], attribute: str) -> list[list[float]]:
    values: list[list[float]] = []
    seen: set[tuple[float, float]] = set()
    for segment in segments:
        prefilter = segment.prefilter
        if prefilter is None:
            continue
        for item in getattr(prefilter, attribute):
            normalized = (round(float(item[0]), 3), round(float(item[1]), 3))
            if normalized in seen:
                continue
            seen.add(normalized)
            values.append([normalized[0], normalized[1]])
    return values


def assembly_source_segment_ids(segment: CandidateSegment) -> list[str]:
    prefilter = segment.prefilter
    if prefilter is not None and prefilter.assembly_source_segment_ids:
        return list(prefilter.assembly_source_segment_ids)
    return [segment.id]


def assembly_source_ranges_sec(segment: CandidateSegment) -> list[list[float]]:
    prefilter = segment.prefilter
    if prefilter is not None and prefilter.assembly_source_ranges_sec:
        return [list(item) for item in prefilter.assembly_source_ranges_sec]
    return [[round(segment.start_sec, 3), round(segment.end_sec, 3)]]


def flatten_source_segment_ids(segments: list[CandidateSegment]) -> list[str]:
    values: list[str] = []
    for segment in segments:
        for value in assembly_source_segment_ids(segment):
            if value not in values:
                values.append(value)
    return values


def flatten_source_ranges(segments: list[CandidateSegment]) -> list[list[float]]:
    values: list[list[float]] = []
    seen: set[tuple[float, float]] = set()
    for segment in segments:
        for item in assembly_source_ranges_sec(segment):
            normalized = (round(float(item[0]), 3), round(float(item[1]), 3))
            if normalized in seen:
                continue
            seen.add(normalized)
            values.append([normalized[0], normalized[1]])
    return values


def semantic_boundary_ambiguity_score(segment: CandidateSegment) -> float:
    prefilter = segment.prefilter
    if prefilter is None:
        return 0.0

    score = 1.0 - clamp(prefilter.boundary_confidence)
    if prefilter.boundary_strategy in {"legacy", "duration-rule", "scene-duration"}:
        score += 0.18
    if prefilter.boundary_strategy.startswith("assembly-merge:structural"):
        score += 0.16
    if prefilter.assembly_operation == "split":
        score += 0.2
    if prefilter.assembly_operation == "merge" and prefilter.assembly_rule_family == "structural-continuity":
        score += 0.12

    duration = segment.end_sec - segment.start_sec
    seed_drift_sec = boundary_seed_center_drift(segment)
    if prefilter.boundary_strategy in {"audio-snap", "scene-snap"} and seed_drift_sec >= 1.0:
        score += 0.08
    if prefilter.boundary_strategy == "transcript-snap" and seed_drift_sec >= 0.75:
        score += 0.04
    if prefilter.boundary_strategy == "turn-snap" and seed_drift_sec >= 0.5:
        score += 0.03
    if segment.analysis_mode == "speech" and prefilter.transcript_turn_alignment == "partial-turn":
        score += 0.08
    if segment.analysis_mode == "speech" and prefilter.transcript_turn_alignment == "mostly-complete":
        score += 0.03
    if segment.analysis_mode == "speech" and prefilter.assembly_rule_family == "turn-break":
        score += 0.14
    if segment.analysis_mode == "speech" and prefilter.assembly_rule_family == "turn-continuity":
        score += 0.04
    if segment.analysis_mode == "speech" and len(prefilter.transcript_turn_ids) >= 2:
        score += 0.05
    if segment.analysis_mode == "speech" and segment.quality_metrics.get("turn_completeness", 0.0) < 0.7:
        score += 0.06
    if segment.analysis_mode == "speech" and segment.quality_metrics.get("turn_completeness", 0.0) < 0.5:
        score += 0.08
    if segment.analysis_mode == "speech" and 2.0 <= duration <= 7.0:
        score += 0.08
    if segment.analysis_mode == "visual" and segment.quality_metrics.get("motion_energy", 0.0) >= 0.65:
        score += 0.06

    return round(clamp(score), 4)


def boundary_seed_center_drift(segment: CandidateSegment) -> float:
    prefilter = segment.prefilter
    if prefilter is None or not prefilter.seed_region_ranges_sec:
        return 0.0

    seed_centers = [
        (item[0] + item[1]) / 2.0
        for item in prefilter.seed_region_ranges_sec
        if len(item) == 2 and item[1] > item[0]
    ]
    if not seed_centers:
        return 0.0

    segment_center = (segment.start_sec + segment.end_sec) / 2.0
    seed_center = sum(seed_centers) / len(seed_centers)
    return abs(segment_center - seed_center)


def semantic_validation_is_available(analyzer: VisionLanguageAnalyzer) -> bool:
    return analyzer.requires_keyframes and not isinstance(analyzer, DeterministicVisionLanguageAnalyzer)


def select_semantic_boundary_validation_targets(
    *,
    segments: list[CandidateSegment],
    enabled: bool,
    analyzer_available: bool,
    ambiguity_threshold: float,
    floor_threshold: float,
    min_targets: int,
) -> tuple[dict[str, float], list[str], dict[str, str]]:
    ambiguity_by_id = {
        segment.id: semantic_boundary_ambiguity_score(segment)
        for segment in segments
    }
    target_reasons: dict[str, str] = {}
    if not enabled or not analyzer_available:
        return ambiguity_by_id, [], target_reasons

    eligible = [
        segment
        for segment in segments
        if ambiguity_by_id.get(segment.id, 0.0) >= ambiguity_threshold
    ]
    ordered = sorted(
        eligible,
        key=lambda segment: (
            ambiguity_by_id.get(segment.id, 0.0),
            segment.prefilter.score if segment.prefilter is not None else 0.0,
        ),
        reverse=True,
    )
    if not ordered and min_targets > 0:
        floor_candidates = [
            segment
            for segment in segments
            if ambiguity_by_id.get(segment.id, 0.0) >= floor_threshold
        ]
        ordered = sorted(
            floor_candidates,
            key=lambda segment: (
                ambiguity_by_id.get(segment.id, 0.0),
                segment.prefilter.score if segment.prefilter is not None else 0.0,
            ),
            reverse=True,
        )
        if ordered:
            ordered = ordered[:min_targets]
            target_reasons = {segment.id: "floor" for segment in ordered}
    else:
        target_reasons = {segment.id: "threshold" for segment in ordered}

    return ambiguity_by_id, [segment.id for segment in ordered], target_reasons


def run_scoped_semantic_validation_budget(
    *,
    target_orders: list[list[str]],
    budget_pct: int,
    max_segments: int,
) -> int:
    if max_segments <= 0 or budget_pct <= 0:
        return 0

    total_candidates = sum(len(order) for order in target_orders)
    if total_candidates <= 0:
        return 0

    pct_limit = max(1, int(total_candidates * budget_pct / 100.0))
    return min(total_candidates, max_segments, pct_limit)


def initial_boundary_validation_result(
    *,
    segment: CandidateSegment,
    enabled: bool,
    analyzer_available: bool,
    ambiguity_score: float,
    ambiguity_threshold: float,
    targeted: bool,
    target_reason: str = "",
) -> BoundaryValidationResult:
    if ambiguity_score < ambiguity_threshold and not targeted:
        return BoundaryValidationResult(
            status="not_eligible",
            decision="keep",
            reason="Deterministic boundaries were not ambiguous enough for semantic validation.",
            confidence=0.0,
            ambiguity_score=ambiguity_score,
            target_reason=target_reason,
            original_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
            suggested_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
        )
    if not enabled:
        skip_reason = "disabled"
        reason = "Semantic boundary validation is disabled."
    elif not analyzer_available:
        skip_reason = "ai_unavailable"
        reason = "Semantic boundary validation is unavailable for the active analyzer."
    elif not targeted:
        skip_reason = "over_budget"
        reason = "Semantic boundary validation was skipped because the runtime budget was exhausted."
    else:
        skip_reason = ""
        if target_reason == "floor":
            reason = "Semantic boundary validation was activated by the minimum-target floor."
        else:
            reason = "Semantic boundary validation is pending."

    status = "pending" if targeted else "skipped"
    return BoundaryValidationResult(
        status=status,
        decision="keep",
        reason=reason,
        confidence=0.0,
        ambiguity_score=ambiguity_score,
        target_reason=target_reason,
        provider="deterministic" if not targeted else "",
        provider_model="fallback-v1" if not targeted else "",
        skip_reason=skip_reason,
        applied=False,
        original_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
        suggested_range_sec=[round(segment.start_sec, 3), round(segment.end_sec, 3)],
    )


def apply_semantic_boundary_validation(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    validation_results: dict[str, BoundaryValidationResult],
    transcriber: TranscriptProvider,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    prefilter_signals,
    audio_signals,
    max_adjustment_sec: float,
) -> list[CandidateSegment]:
    updated: list[CandidateSegment] = []

    for segment in segments:
        result = validation_results.get(segment.id)
        if result is None or result.status in {"not_eligible", "skipped"}:
            if result is not None:
                segment.boundary_validation = result
            updated.append(segment)
            continue

        transformed = apply_single_boundary_validation(
            asset=asset,
            segment=segment,
            result=result,
            transcriber=transcriber,
            transcript_spans=transcript_spans,
            transcript_turns=transcript_turns,
            prefilter_signals=prefilter_signals,
            audio_signals=audio_signals,
            max_adjustment_sec=max_adjustment_sec,
        )
        updated.extend(transformed)

    return [
        replace(segment, id=f"{asset.id}-segment-{index:02d}")
        for index, segment in enumerate(updated, start=1)
    ]


def semantic_split_is_supported(
    *,
    segment: CandidateSegment,
    result: BoundaryValidationResult,
    transcript_turns: list[TranscriptTurn],
) -> bool:
    if result.decision != "split":
        return True
    prefilter = segment.prefilter
    if prefilter is None:
        return False
    if prefilter.boundary_strategy.startswith("assembly-split:"):
        return True
    if prefilter.assembly_operation == "merge":
        return True
    if len(prefilter.transcript_turn_ids) >= 2:
        return True
    matched_turns = transcript_turns_for_range(transcript_turns, segment.start_sec, segment.end_sec)
    if len(matched_turns) >= 2:
        return True
    if (
        segment.analysis_mode == "speech"
        and result.confidence >= 0.85
        and (prefilter.boundary_strategy.startswith("transcript-") or prefilter.boundary_strategy == "turn-snap")
    ):
        return True
    return False


def apply_single_boundary_validation(
    *,
    asset: Asset,
    segment: CandidateSegment,
    result: BoundaryValidationResult,
    transcriber: TranscriptProvider,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    prefilter_signals,
    audio_signals,
    max_adjustment_sec: float,
) -> list[CandidateSegment]:
    prefilter = segment.prefilter
    if prefilter is None:
        segment.boundary_validation = result
        return [segment]

    original_start = segment.start_sec
    original_end = segment.end_sec
    bounded_start = clamp_range_value(
        value=result.suggested_range_sec[0] if result.suggested_range_sec else original_start,
        current=original_start,
        minimum=0.0,
        maximum=min(asset.duration_sec, original_end - 1.5),
        max_adjustment_sec=max_adjustment_sec,
    )
    bounded_end = clamp_range_value(
        value=result.suggested_range_sec[1] if result.suggested_range_sec else original_end,
        current=original_end,
        minimum=max(0.0, bounded_start + 1.5),
        maximum=asset.duration_sec,
        max_adjustment_sec=max_adjustment_sec,
    )
    if bounded_end - bounded_start < 1.5:
        bounded_start, bounded_end = original_start, original_end

    if result.decision == "split" and result.split_ranges_sec:
        if not semantic_split_is_supported(
            segment=segment,
            result=result,
            transcript_turns=transcript_turns,
        ):
            result.decision = "keep"
            result.applied = False
            result.suggested_range_sec = [round(original_start, 3), round(original_end, 3)]
            segment.boundary_validation = result
            return [segment]
        split_point = clamp_range_value(
            value=result.split_ranges_sec[0][1],
            current=(original_start + original_end) / 2.0,
            minimum=original_start + 1.5,
            maximum=original_end - 1.5,
            max_adjustment_sec=max_adjustment_sec,
        )
        if split_point > original_start + 1.5 and original_end - split_point > 1.5:
            children: list[CandidateSegment] = []
            for part_index, (start_sec, end_sec) in enumerate(
                ((original_start, split_point), (split_point, original_end)),
                start=1,
            ):
                child_result = BoundaryValidationResult(
                    status=result.status,
                    decision="split",
                    reason=result.reason,
                    confidence=result.confidence,
                    ambiguity_score=result.ambiguity_score,
                    target_reason=result.target_reason,
                    provider=result.provider,
                    provider_model=result.provider_model,
                    skip_reason=result.skip_reason,
                    applied=True,
                    original_range_sec=list(result.original_range_sec),
                    suggested_range_sec=[round(start_sec, 3), round(end_sec, 3)],
                    split_ranges_sec=[list(item) for item in result.split_ranges_sec],
                )
                children.append(
                    rebuild_segment_with_validation(
                        asset=asset,
                        segment=segment,
                        new_id=f"{segment.id}-semantic-{part_index}",
                        start_sec=start_sec,
                        end_sec=end_sec,
                        transcriber=transcriber,
                        transcript_spans=transcript_spans,
                        transcript_turns=transcript_turns,
                        prefilter_signals=prefilter_signals,
                        audio_signals=audio_signals,
                        boundary_validation=child_result,
                    )
                )
            return children

    applied = result.decision in {"extend", "trim"} and (
        abs(bounded_start - original_start) > 0.01 or abs(bounded_end - original_end) > 0.01
    )
    result.applied = applied
    result.suggested_range_sec = [round(bounded_start, 3), round(bounded_end, 3)]
    if not applied:
        segment.boundary_validation = result
        return [segment]

    return [
        rebuild_segment_with_validation(
            asset=asset,
            segment=segment,
            new_id=segment.id,
            start_sec=bounded_start,
            end_sec=bounded_end,
            transcriber=transcriber,
            transcript_spans=transcript_spans,
            transcript_turns=transcript_turns,
            prefilter_signals=prefilter_signals,
            audio_signals=audio_signals,
            boundary_validation=result,
        )
    ]


def rebuild_segment_with_validation(
    *,
    asset: Asset,
    segment: CandidateSegment,
    new_id: str,
    start_sec: float,
    end_sec: float,
    transcriber: TranscriptProvider,
    transcript_spans: list[TranscriptSpan],
    transcript_turns: list[TranscriptTurn],
    prefilter_signals,
    audio_signals,
    boundary_validation: BoundaryValidationResult,
) -> CandidateSegment:
    prefilter = segment.prefilter
    if prefilter is None:
        segment.boundary_validation = boundary_validation
        return segment

    rebuilt = make_candidate_segment(
        asset=asset,
        segment_id=new_id,
        start_sec=start_sec,
        end_sec=end_sec,
        transcriber=transcriber,
        transcript_spans=transcript_spans,
        transcript_turns=transcript_turns,
        prefilter_signals=prefilter_signals,
        audio_signals=audio_signals,
        boundary_strategy=prefilter.boundary_strategy,
        boundary_confidence=max(prefilter.boundary_confidence, boundary_validation.confidence),
        seed_region_ids=prefilter.seed_region_ids,
        seed_region_sources=prefilter.seed_region_sources,
        seed_region_ranges_sec=prefilter.seed_region_ranges_sec,
        assembly_operation=prefilter.assembly_operation,
        assembly_rule_family=prefilter.assembly_rule_family,
        assembly_source_segment_ids=prefilter.assembly_source_segment_ids,
        assembly_source_ranges_sec=prefilter.assembly_source_ranges_sec,
        transcript_lookup_enabled=bool(transcript_spans),
    )
    rebuilt.boundary_validation = boundary_validation
    return rebuilt


def clamp_range_value(
    *,
    value: float,
    current: float,
    minimum: float,
    maximum: float,
    max_adjustment_sec: float,
) -> float:
    bounded = max(minimum, min(maximum, value))
    delta_bounded = max(current - max_adjustment_sec, min(current + max_adjustment_sec, bounded))
    return round(max(minimum, min(maximum, delta_bounded)), 3)


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

        base_ranges = detector.detect(asset) if asset.duration_sec > 0 else [(0.0, 4.0)]
        if not base_ranges:
            base_ranges = fallback_segments(asset.duration_sec)
        timestamps = sample_timestamps(asset.duration_sec)
        prefilter_signals = sample_asset_signals(asset, timestamps=timestamps)

        # Audio signal sampling
        audio_signals = sample_audio_signals(asset, timestamps)
        total_prefilter_samples += len(prefilter_signals)
        has_audio = any(sig.source == "ffmpeg" for sig in audio_signals)
        if has_audio:
            total_audio_signal_assets += 1
        if status_callback is not None:
            audio_status = f"audio detected" if has_audio else "silent/no audio"
            status_callback(f"  ✓ Sampled {len(prefilter_signals)} frames ({audio_status})")
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
                    extract_keyframes=analyzer.requires_keyframes,
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
                        extract_keyframes=analyzer.requires_keyframes,
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


def build_take_recommendations(
    assets: list[Asset],
    candidate_segments: list[CandidateSegment],
) -> list[TakeRecommendation]:
    takes: list[TakeRecommendation] = []

    for asset in assets:
        asset_segments = [segment for segment in candidate_segments if segment.asset_id == asset.id]
        if not asset_segments:
            continue
        ranked_segment_data = sorted(
            ((segment, score_segment(asset, segment)) for segment in asset_segments),
            key=lambda item: item[1].total,
            reverse=True,
        )
        ranked_segments = [segment for segment, _breakdown in ranked_segment_data]
        breakdown_by_segment_id = {segment.id: breakdown for segment, breakdown in ranked_segment_data}
        selected_segments = select_segments_for_asset(asset, ranked_segments)
        selected_ids = {selected.id for selected in selected_segments}
        winner_segment = ranked_segments[0]
        winner_score = breakdown_by_segment_id[winner_segment.id].total
        rank_by_segment_id = {segment.id: index for index, segment in enumerate(ranked_segments, start=1)}

        for index, segment in enumerate(asset_segments, start=1):
            breakdown = breakdown_by_segment_id[segment.id]
            is_best_take = segment.id in selected_ids
            outcome = recommendation_outcome(segment, winner_segment, selected_ids)
            drivers = top_score_driver_labels(asset, segment)
            limiting_factors = (
                []
                if segment.id == winner_segment.id
                else limiting_factor_labels(asset, segment, winner_segment)
            )
            takes.append(
                TakeRecommendation(
                    id=f"{asset.id}-take-{index:02d}",
                    candidate_segment_id=segment.id,
                    title=make_take_title(asset, segment, breakdown.analysis_mode, outcome),
                    is_best_take=is_best_take,
                    selection_reason=make_selection_reason(
                        asset=asset,
                        segment=segment,
                        total_score=breakdown.total,
                        outcome=outcome,
                        winner_score=winner_score,
                        within_asset_rank=rank_by_segment_id[segment.id],
                        driver_labels=drivers,
                        limiting_labels=limiting_factors,
                    ),
                    score_technical=breakdown.technical,
                    score_semantic=breakdown.semantic,
                    score_story=breakdown.story,
                    score_total=breakdown.total,
                    outcome=outcome,
                    within_asset_rank=rank_by_segment_id[segment.id],
                    score_gap_to_winner=round(max(0.0, winner_score - breakdown.total), 4),
                    score_driver_labels=drivers,
                    limiting_factor_labels=limiting_factors,
                )
            )

    return takes


def build_timeline(
    take_recommendations: list[TakeRecommendation],
    candidate_segments: list[CandidateSegment],
    assets: list[Asset],
    story_prompt: str = "",
) -> Timeline:
    best_takes = [take for take in take_recommendations if take.is_best_take]
    segment_by_id = {segment.id: segment for segment in candidate_segments}
    asset_by_id = {asset.id: asset for asset in assets}
    assembled_choices = assemble_story_sequence(best_takes, segment_by_id, asset_by_id, story_prompt=story_prompt)

    items: list[TimelineItem] = []
    for index, choice in enumerate(assembled_choices):
        take = choice.take
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
                sequence_group=choice.sequence_group,
                sequence_role=choice.sequence_role,
                sequence_score=round(choice.sequence_score, 4),
                sequence_rationale=list(choice.sequence_rationale),
                sequence_driver_labels=list(choice.sequence_driver_labels),
                sequence_tradeoff_labels=list(choice.sequence_tradeoff_labels),
            )
        )

    ordered_takes = [choice.take for choice in assembled_choices]
    summary = summarize_story(ordered_takes, segment_by_id)
    return Timeline(
        id="timeline-main",
        version=1,
        story_summary=summary,
        items=items,
    )


def assemble_story_sequence(
    best_takes: list[TakeRecommendation],
    segment_by_id: dict[str, CandidateSegment],
    asset_by_id: dict[str, Asset],
    *,
    story_prompt: str = "",
) -> list[StoryAssemblyChoice]:
    if not best_takes:
        return []
    prompt_keywords = extract_story_prompt_keywords(story_prompt)

    if len(best_takes) == 1:
        take = best_takes[0]
        segment = segment_by_id[take.candidate_segment_id]
        return [
            StoryAssemblyChoice(
                take=take,
                sequence_score=round(take.score_total, 4),
                sequence_group="setup",
                sequence_role=sequence_role_for_item(0, 1, segment),
                sequence_rationale=["Only selected beat in the current rough timeline."],
                sequence_driver_labels=["local_strength"],
                sequence_tradeoff_labels=[],
            )
        ]

    remaining = list(best_takes)
    opener_evaluations = {
        take.id: evaluate_opener_candidate(
            take,
            segment_by_id[take.candidate_segment_id],
            prompt_keywords=prompt_keywords,
        )
        for take in remaining
    }
    opener = max(
        remaining,
        key=lambda take: opener_evaluations[take.id].score,
    )
    remaining.remove(opener)

    release_take: TakeRecommendation | None = None
    release_evaluations: dict[str, StoryAssemblyEvaluation] = {}
    if len(best_takes) >= 3 and remaining:
        release_evaluations = {
            take.id: evaluate_release_candidate(
                take,
                segment_by_id[take.candidate_segment_id],
                prompt_keywords=prompt_keywords,
            )
            for take in remaining
        }
        release_candidates = [
            take for take in remaining if segment_by_id[take.candidate_segment_id].analysis_mode == "visual"
        ]
        if not release_candidates:
            release_candidates = list(remaining)
        release_take = max(release_candidates, key=lambda take: release_evaluations[take.id].score)
        remaining.remove(release_take)

    ordered_takes = [opener]
    while remaining:
        previous = ordered_takes[-1]
        seen_segments = [segment_by_id[take.candidate_segment_id] for take in ordered_takes]
        transition_evaluations = {
            take.id: evaluate_transition_candidate(
                previous,
                take,
                segment_by_id[previous.candidate_segment_id],
                segment_by_id[take.candidate_segment_id],
                seen_segments=seen_segments,
                prompt_keywords=prompt_keywords,
            )
            for take in remaining
        }
        next_take = max(
            remaining,
            key=lambda take: transition_evaluations[take.id].score,
        )
        ordered_takes.append(next_take)
        remaining.remove(next_take)

    if release_take is not None:
        ordered_takes.append(release_take)

    choices: list[StoryAssemblyChoice] = []
    total = len(ordered_takes)
    for index, take in enumerate(ordered_takes):
        segment = segment_by_id[take.candidate_segment_id]
        previous_segment = (
            segment_by_id[ordered_takes[index - 1].candidate_segment_id]
            if index > 0
            else None
        )
        if index == 0:
            evaluation = opener_evaluations.get(
                take.id,
                StoryAssemblyEvaluation(
                    score=take.score_total,
                    driver_labels=["local_strength"],
                    tradeoff_labels=[],
                    matched_prompt_terms=[],
                ),
            )
        elif release_take is not None and take.id == release_take.id:
            evaluation = release_evaluations.get(
                take.id,
                StoryAssemblyEvaluation(
                    score=take.score_total,
                    driver_labels=["local_strength"],
                    tradeoff_labels=[],
                    matched_prompt_terms=[],
                ),
            )
        else:
            evaluation = evaluate_transition_candidate(
                ordered_takes[index - 1],
                take,
                previous_segment if previous_segment is not None else segment,
                segment,
                seen_segments=[segment_by_id[item.candidate_segment_id] for item in ordered_takes[:index]],
                prompt_keywords=prompt_keywords,
            )
        choices.append(
            StoryAssemblyChoice(
                take=take,
                sequence_score=round(evaluation.score, 4),
                sequence_group=sequence_group_for_item(index, total),
                sequence_role=sequence_role_for_item(index, total, segment),
                sequence_rationale=sequence_rationale_for_item(
                    index=index,
                    total=total,
                    current_take=take,
                    current_segment=segment,
                    previous_segment=previous_segment,
                    release_reserved=release_take is not None and take.id == release_take.id,
                    asset_by_id=asset_by_id,
                    driver_labels=evaluation.driver_labels,
                    tradeoff_labels=evaluation.tradeoff_labels,
                    prompt_terms=evaluation.matched_prompt_terms,
                ),
                sequence_driver_labels=list(evaluation.driver_labels),
                sequence_tradeoff_labels=list(evaluation.tradeoff_labels),
            )
        )
    return choices


def has_mixed_sequence_modes(
    takes: list[TakeRecommendation],
    segment_by_id: dict[str, CandidateSegment],
) -> bool:
    modes = {segment_by_id[take.candidate_segment_id].analysis_mode for take in takes}
    return len(modes) > 1


def evaluate_opener_candidate(
    take: TakeRecommendation,
    segment: CandidateSegment,
    *,
    prompt_keywords: set[str],
) -> StoryAssemblyEvaluation:
    score = take.score_total
    driver_labels = ["local_strength"]
    tradeoff_labels: list[str] = []
    if segment.analysis_mode == "visual":
        score += 0.09
        driver_labels.append("opener_fit")
        if segment.quality_metrics.get("visual_novelty", 0.0) >= 0.7:
            score += 0.04
            driver_labels.append("visual_novelty")
    else:
        score += 0.03
        if not segment.transcript_excerpt.strip():
            score -= 0.03
    if segment.quality_metrics.get("hook_strength", 0.0) >= 0.7:
        score += 0.03
        driver_labels.append("hook_strength")
    prompt_fit, matched_terms = segment_prompt_fit(segment, prompt_keywords)
    if prompt_fit > 0.0:
        score += prompt_fit
        driver_labels.append("prompt_fit")
        if segment.analysis_mode == "visual":
            score += 0.02
            driver_labels.append("prompt_led_opener")
        if take.score_total < 0.78:
            tradeoff_labels.append("preferred_for_prompt_fit")
    return StoryAssemblyEvaluation(
        score=round(score, 4),
        driver_labels=dedupe_labels(driver_labels),
        tradeoff_labels=dedupe_labels(tradeoff_labels),
        matched_prompt_terms=matched_terms,
    )


def evaluate_release_candidate(
    take: TakeRecommendation,
    segment: CandidateSegment,
    *,
    prompt_keywords: set[str],
) -> StoryAssemblyEvaluation:
    score = take.score_total
    driver_labels = ["local_strength", "release_fit"]
    tradeoff_labels: list[str] = []
    if segment.analysis_mode == "visual":
        score += 0.08
        if segment.quality_metrics.get("motion_energy", 0.0) <= 0.55:
            score += 0.04
            driver_labels.append("calm_release")
    elif segment.quality_metrics.get("turn_completeness", 0.0) >= 0.85:
        score += 0.03
        driver_labels.append("complete_turn")
    if segment.quality_metrics.get("story_alignment", 0.0) >= 0.7:
        score += 0.03
        driver_labels.append("story_alignment")
    prompt_fit, matched_terms = segment_prompt_fit(segment, prompt_keywords)
    if prompt_fit > 0.0:
        score += min(0.05, prompt_fit)
        driver_labels.append("prompt_fit")
    return StoryAssemblyEvaluation(
        score=round(score, 4),
        driver_labels=dedupe_labels(driver_labels),
        tradeoff_labels=dedupe_labels(tradeoff_labels),
        matched_prompt_terms=matched_terms,
    )


def evaluate_transition_candidate(
    previous_take: TakeRecommendation,
    current_take: TakeRecommendation,
    previous_segment: CandidateSegment,
    current_segment: CandidateSegment,
    *,
    seen_segments: list[CandidateSegment],
    prompt_keywords: set[str],
) -> StoryAssemblyEvaluation:
    score = current_take.score_total
    driver_labels = ["local_strength"]
    tradeoff_labels: list[str] = []
    if current_segment.analysis_mode != previous_segment.analysis_mode:
        score += 0.08
        driver_labels.extend(["mode_variety", "repetition_control"])
        if previous_segment.analysis_mode == "visual" and current_segment.analysis_mode == "speech":
            score += 0.04
            driver_labels.append("spoken_progression")
        if previous_segment.analysis_mode == "speech" and current_segment.analysis_mode == "visual":
            score += 0.05
            driver_labels.append("release_transition")
    else:
        score -= 0.04
        tradeoff_labels.append("same_mode_repeat")

    if segment_story_role(previous_segment) != segment_story_role(current_segment):
        score += 0.04
        driver_labels.extend(["role_variety", "repetition_control"])
    else:
        score -= 0.03
        tradeoff_labels.append("same_role_repeat")

    if (
        current_segment.analysis_mode == "speech"
        and current_segment.quality_metrics.get("turn_completeness", 0.0) >= 0.85
    ):
        score += 0.02
        driver_labels.append("complete_turn")

    if previous_take.score_total >= 0.75 and current_take.score_total >= 0.75:
        score += 0.01
        driver_labels.append("paired_strength")

    prompt_fit, matched_terms = segment_prompt_fit(current_segment, prompt_keywords)
    if prompt_fit > 0.0:
        score += min(0.06, prompt_fit)
        driver_labels.append("prompt_fit")

    if seen_segments:
        recent_modes = [segment.analysis_mode for segment in seen_segments[-2:]]
        if recent_modes and all(mode == current_segment.analysis_mode for mode in recent_modes):
            score -= 0.05
            tradeoff_labels.append("third_same_mode_avoided")
        recent_roles = [segment_story_role(segment) for segment in seen_segments[-2:]]
        current_role = segment_story_role(current_segment)
        if recent_roles and all(role == current_role for role in recent_roles):
            score -= 0.04
            tradeoff_labels.append("third_same_role_avoided")

    return StoryAssemblyEvaluation(
        score=round(score, 4),
        driver_labels=dedupe_labels(driver_labels),
        tradeoff_labels=dedupe_labels(tradeoff_labels),
        matched_prompt_terms=matched_terms,
    )


def segment_story_role(segment: CandidateSegment) -> str:
    if segment.ai_understanding and segment.ai_understanding.story_roles:
        return segment.ai_understanding.story_roles[0]
    if segment.analysis_mode == "speech":
        return "spoken beat"
    metrics = segment.quality_metrics
    if metrics.get("visual_novelty", 0.0) >= 0.8 and metrics.get("motion_energy", 0.0) >= 0.7:
        return "dynamic establishing"
    if metrics.get("motion_energy", 0.0) < 0.45:
        return "calm texture"
    if metrics.get("subject_clarity", 0.0) >= 0.8:
        return "clear detail"
    return "transition-ready"


def sequence_group_for_item(index: int, count: int) -> str:
    if count <= 1 or index == 0:
        return "setup"
    if index == count - 1:
        return "release"
    return "development"


def sequence_role_for_item(index: int, count: int, segment: CandidateSegment) -> str:
    if index == 0:
        return "opener"
    if index == count - 1:
        return "release"
    if segment.analysis_mode == "speech":
        return "spoken beat"
    return "visual bridge"


def sequence_rationale_for_item(
    *,
    index: int,
    total: int,
    current_take: TakeRecommendation,
    current_segment: CandidateSegment,
    previous_segment: CandidateSegment | None,
    release_reserved: bool,
    asset_by_id: dict[str, Asset],
    driver_labels: list[str],
    tradeoff_labels: list[str],
    prompt_terms: list[str],
) -> list[str]:
    asset = asset_by_id[current_segment.asset_id]
    reasons: list[str] = []
    if index == 0:
        if current_segment.analysis_mode == "visual":
            reasons.append("Starts on a visual anchor to establish the cut cleanly.")
        else:
            reasons.append("Starts on the strongest spoken beat available.")
        if current_segment.quality_metrics.get("hook_strength", 0.0) >= 0.7:
            reasons.append("Its hook strength makes it a stable opener.")
    else:
        if previous_segment is not None and previous_segment.analysis_mode != current_segment.analysis_mode:
            reasons.append(
                f"Alternates from {previous_segment.analysis_mode} to {current_segment.analysis_mode} to keep sequence contrast."
            )
        if previous_segment is not None and segment_story_role(previous_segment) != segment_story_role(current_segment):
            reasons.append("Adds role variety instead of repeating the same beat type.")
        if current_segment.analysis_mode == "speech" and current_segment.transcript_excerpt.strip():
            reasons.append("Moves the sequence forward with readable spoken information.")
        elif current_segment.analysis_mode == "visual":
            reasons.append("Provides visual pacing between stronger information beats.")

    if release_reserved:
        reasons.append("Held for the end because it reads as a cleaner release beat.")
    if index == total - 1 and not release_reserved:
        reasons.append("Closes the current rough cut without needing another transition.")
    if "prompt_fit" in driver_labels and prompt_terms:
        reasons.append(f"Matches story prompt cues: {', '.join(prompt_terms[:2])}.")
    if "repetition_control" in driver_labels:
        reasons.append("Avoids repeating the same beat pattern too closely.")
    if tradeoff_labels and current_take.score_total < 0.8:
        reasons.append("Accepts a bounded local-score tradeoff for stronger sequence fit.")
    if current_take.score_total >= 0.78:
        reasons.append(f"Carries strong local quality at {round(current_take.score_total * 100):d}/100.")
    reasons.append(f"Source {asset.interchange_reel_name}.")
    return reasons[:4]


def extract_story_prompt_keywords(story_prompt: str) -> set[str]:
    if not story_prompt.strip():
        return set()
    stopwords = {
        "about",
        "after",
        "before",
        "build",
        "from",
        "into",
        "make",
        "moment",
        "move",
        "rough",
        "short",
        "story",
        "that",
        "then",
        "this",
        "through",
        "with",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", story_prompt.lower())
        if len(token) >= 4 and token not in stopwords
    }


def segment_prompt_fit(segment: CandidateSegment, prompt_keywords: set[str]) -> tuple[float, list[str]]:
    if not prompt_keywords:
        return 0.0, []
    searchable_parts = [
        segment.transcript_excerpt,
        segment.description,
        " ".join(segment.ai_understanding.story_roles) if segment.ai_understanding else "",
        " ".join(segment.ai_understanding.subjects) if segment.ai_understanding else "",
        " ".join(segment.ai_understanding.actions) if segment.ai_understanding else "",
        segment.ai_understanding.summary if segment.ai_understanding else "",
    ]
    searchable = " ".join(part for part in searchable_parts if part).lower()
    matched_terms = sorted(term for term in prompt_keywords if term in searchable)
    if not matched_terms:
        return 0.0, []
    return min(0.08, 0.02 * len(matched_terms)), matched_terms[:3]


def dedupe_labels(labels: list[str]) -> list[str]:
    ordered: list[str] = []
    for label in labels:
        if label and label not in ordered:
            ordered.append(label)
    return ordered


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
    *,
    analysis_mode: str,
) -> str:
    duration = round(end_sec - start_sec, 2)

    if transcript_excerpt:
        return (
            f"{asset.name} yields a spoken beat around {start_sec:.2f}s to {end_sec:.2f}s. "
            f"The excerpt carries usable narrative value, and the {duration:.2f}s duration is well suited for a rough cut."
        )

    if analysis_mode == "speech":
        return (
            f"{asset.name} reads as a spoken beat from {start_sec:.2f}s to {end_sec:.2f}s, "
            f"but transcript text is unavailable. Speech activity is still strong enough to keep the {duration:.2f}s range in speech-aware scoring."
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


def make_take_title(asset: Asset, segment: CandidateSegment, analysis_mode: str, outcome: str) -> str:
    title_prefix = "Best" if outcome == "best" else "Alternate" if outcome == "alternate" else "Candidate"
    role = "Dialogue" if analysis_mode == "speech" else "Visual"
    return f"{title_prefix} {role}: {asset.name}"


def recommendation_outcome(
    segment: CandidateSegment,
    winner_segment: CandidateSegment,
    selected_ids: set[str],
) -> str:
    if segment.id == winner_segment.id:
        return "best"
    if segment.id in selected_ids:
        return "alternate"
    return "backup"


def make_selection_reason(
    *,
    asset: Asset,
    segment: CandidateSegment,
    total_score: float,
    outcome: str,
    winner_score: float,
    within_asset_rank: int,
    driver_labels: list[str],
    limiting_labels: list[str],
) -> str:
    score = round(total_score * 100)
    score_gap = round(max(0.0, (winner_score - total_score) * 100))
    drivers = human_join(driver_labels[:3])
    limiting = human_join(limiting_labels[:2])

    if outcome == "best":
        return f"Won this clip at {score}/100 on {drivers}."

    if outcome == "alternate":
        return (
            f"Kept as an alternate {score_gap} point{'s' if score_gap != 1 else ''} behind the winner "
            f"because it still cleared the selection gap on {drivers}."
        )

    if total_score < TAKE_SELECTION_MIN_SCORE:
        return (
            f"Usable, but below the {round(TAKE_SELECTION_MIN_SCORE * 100):d}/100 selection threshold. "
            f"Strongest factors were {drivers}."
        )

    if asset.duration_sec >= 18 and total_score < winner_score - TAKE_SELECTION_ALT_GAP:
        return (
            f"Usable, but {score_gap} points behind the winner and outside the alternate gap, "
            f"mainly on {limiting or drivers}."
        )

    return (
        f"Usable, but ranked #{within_asset_rank} behind the selected take for this clip, "
        f"mainly on {limiting or drivers}."
    )


def build_segment_review_state(segment: CandidateSegment) -> SegmentReviewState:
    prefilter = segment.prefilter
    evidence = segment.evidence_bundle
    understanding = segment.ai_understanding
    boundary_validation = segment.boundary_validation
    clip_score = None
    if prefilter is not None:
        clip_score = prefilter.metrics_snapshot.get("clip_score")

    model_analyzed = bool(understanding and understanding.provider != "deterministic")
    deterministic_fallback = bool(understanding and understanding.provider == "deterministic")
    evidence_keyframe_count = len(evidence.keyframe_timestamps_sec) if evidence is not None else 0
    blocked_reason = review_blocked_reason(segment)
    transcript_status = evidence.transcript_status if evidence is not None else default_segment_transcript_status(segment)
    speech_mode_source = evidence.speech_mode_source if evidence is not None else default_segment_speech_mode_source(segment)

    return SegmentReviewState(
        shortlisted=bool(prefilter and prefilter.shortlisted),
        filtered_before_vlm=bool(prefilter and prefilter.filtered_before_vlm),
        clip_scored=clip_score is not None,
        clip_score=round(clip_score, 4) if clip_score is not None else None,
        clip_gated=bool(prefilter and prefilter.clip_gated),
        deduplicated=bool(prefilter and prefilter.deduplicated),
        dedup_group_id=prefilter.dedup_group_id if prefilter is not None else None,
        vlm_budget_capped=bool(prefilter and prefilter.vlm_budget_capped),
        model_analyzed=model_analyzed,
        deterministic_fallback=deterministic_fallback,
        evidence_keyframe_count=evidence_keyframe_count,
        analysis_path_summary=describe_analysis_path(segment, evidence_keyframe_count),
        blocked_reason=blocked_reason,
        boundary_strategy_label=boundary_strategy_label(segment),
        boundary_confidence=round(prefilter.boundary_confidence, 4) if prefilter is not None else None,
        lineage_summary=lineage_summary(segment),
        semantic_validation_status=boundary_validation.status if boundary_validation is not None else "",
        semantic_validation_summary=semantic_validation_summary(segment),
        transcript_status=transcript_status,
        transcript_summary=transcript_summary(segment, transcript_status, speech_mode_source),
        speech_mode_source=speech_mode_source,
        turn_summary=turn_summary(segment),
        speech_structure_summary=speech_structure_summary(segment),
    )


def describe_analysis_path(segment: CandidateSegment, evidence_keyframe_count: int) -> str:
    prefilter = segment.prefilter
    understanding = segment.ai_understanding
    boundary_validation = segment.boundary_validation
    steps: list[str] = []

    if prefilter and prefilter.shortlisted:
        steps.append("shortlisted")
    else:
        steps.append("screened locally only")

    clip_score = prefilter.metrics_snapshot.get("clip_score") if prefilter is not None else None
    if clip_score is not None:
        steps.append(f"CLIP {round(clip_score * 100):d}")
    if prefilter and prefilter.deduplicated:
        steps.append(f"deduped in group {prefilter.dedup_group_id}")
    if prefilter and prefilter.assembly_operation != "none":
        rule_label = prefilter.assembly_rule_family or prefilter.assembly_operation
        steps.append(f"{prefilter.assembly_operation} via {rule_label}")
    if prefilter and prefilter.clip_gated:
        steps.append("CLIP gated")
    if prefilter and prefilter.vlm_budget_capped:
        steps.append("budget capped")
    if boundary_validation is not None:
        if boundary_validation.status == "validated":
            steps.append(f"boundary {boundary_validation.decision}")
        elif boundary_validation.status == "fallback":
            steps.append("boundary fallback")
        elif boundary_validation.status == "skipped":
            steps.append(f"boundary skipped ({boundary_validation.skip_reason})")
    if evidence_keyframe_count > 0:
        steps.append(f"{evidence_keyframe_count} keyframe{'s' if evidence_keyframe_count != 1 else ''}")
    elif segment.analysis_mode == "speech" and not segment.transcript_excerpt.strip():
        steps.append("speech fallback")

    if understanding is not None:
        if understanding.provider == "deterministic":
            steps.append("deterministic fallback")
        else:
            steps.append(f"VLM {understanding.provider}")

    return " -> ".join(steps)


def default_segment_transcript_status(segment: CandidateSegment) -> str:
    if segment.transcript_excerpt.strip():
        return "excerpt-available"
    if segment.analysis_mode == "speech":
        return "fallback-no-transcript"
    return "not-applicable"


def default_segment_speech_mode_source(segment: CandidateSegment) -> str:
    if segment.transcript_excerpt.strip():
        return "transcript"
    if segment.analysis_mode == "speech":
        return "speech-signal-fallback"
    return "visual"


def transcript_summary(segment: CandidateSegment, transcript_status: str, speech_mode_source: str) -> str:
    if transcript_status == "excerpt-available":
        prefilter = segment.prefilter
        if prefilter is not None and prefilter.transcript_turn_ids:
            return (
                f"Transcript excerpt available with {len(prefilter.transcript_turn_ids)} aligned "
                f"turn{'s' if len(prefilter.transcript_turn_ids) != 1 else ''}."
            )
        return "Transcript excerpt available for this segment."
    if transcript_status == "selective-skip":
        return "Transcript extraction was skipped for this asset because cheap speech signals stayed below the selective-transcription threshold."
    if transcript_status == "fallback-no-transcript":
        source_label = speech_mode_source or "speech-signal-fallback"
        return f"Speech-aware fallback is active because transcript text is unavailable ({source_label})."
    if transcript_status in {"provider-disabled", "provider-unavailable", "provider-partial"}:
        return f"Transcript support did not provide excerpt text ({transcript_status})."
    if segment.analysis_mode == "speech":
        return "Speech scoring is active without transcript text."
    return "No transcript evidence was needed for this segment."


def review_blocked_reason(segment: CandidateSegment) -> str:
    prefilter = segment.prefilter
    if prefilter is None:
        return ""
    if prefilter.deduplicated:
        return "duplicate"
    if prefilter.clip_gated:
        return "clip_gate"
    if prefilter.vlm_budget_capped:
        return "budget_cap"
    if prefilter.filtered_before_vlm:
        return "shortlist_filter"
    return ""


def boundary_strategy_label(segment: CandidateSegment) -> str:
    prefilter = segment.prefilter
    if prefilter is None:
        return ""
    strategy = prefilter.boundary_strategy
    labels = {
        "legacy": "Legacy window",
        "turn-snap": "Turn snapped",
        "transcript-snap": "Transcript snapped",
        "audio-snap": "Audio snapped",
        "scene-snap": "Scene snapped",
        "scene-duration": "Scene duration rule",
        "duration-rule": "Duration rule",
    }
    if strategy in labels:
        return labels[strategy]
    if strategy.startswith("assembly-merge:"):
        rule = strategy.split(":", 1)[1].replace("-", " ")
        return f"Assembly merged ({rule})"
    if strategy.startswith("assembly-split:"):
        rule = strategy.split(":", 1)[1].replace("-", " ")
        return f"Assembly split ({rule})"
    return strategy.replace("-", " ").title()


def lineage_summary(segment: CandidateSegment) -> str:
    prefilter = segment.prefilter
    if prefilter is None:
        return ""
    if prefilter.assembly_operation == "merge" and prefilter.assembly_source_segment_ids:
        count = len(prefilter.assembly_source_segment_ids)
        rule = prefilter.assembly_rule_family.replace("-", " ") if prefilter.assembly_rule_family else "continuity"
        return f"Merged {count} refined regions via {rule}."
    if prefilter.assembly_operation == "split" and prefilter.assembly_source_segment_ids:
        source_id = prefilter.assembly_source_segment_ids[0]
        rule = prefilter.assembly_rule_family.replace("-", " ") if prefilter.assembly_rule_family else "internal divider"
        return f"Split from {source_id} via {rule}."
    if prefilter.seed_region_ids:
        count = len(prefilter.seed_region_ids)
        sources = human_join([value.replace("-", " ") for value in prefilter.seed_region_sources[:3]])
        return f"Built from {count} seed region{'s' if count != 1 else ''} ({sources})."
    return ""


def turn_summary(segment: CandidateSegment) -> str:
    prefilter = segment.prefilter
    if prefilter is None or not prefilter.transcript_turn_ids:
        return ""
    count = len(prefilter.transcript_turn_ids)
    if prefilter.assembly_rule_family == "turn-continuity":
        return f"Merged {count} transcript turns via turn continuity."
    if prefilter.assembly_rule_family == "question-answer-flow":
        return "Merged across a question/answer flow."
    if prefilter.assembly_rule_family == "monologue-continuity":
        return "Merged across continuous monologue flow."
    if prefilter.assembly_rule_family == "turn-break":
        return "Split at a strong transcript turn break."
    alignment = prefilter.transcript_turn_alignment or "turn-aware"
    if alignment == "turn-aligned":
        return f"Aligned to {count} transcript turn{'s' if count != 1 else ''}."
    if alignment == "mostly-complete":
        return f"Mostly covers {count} transcript turn{'s' if count != 1 else ''}."
    return f"Partially overlaps {count} transcript turn{'s' if count != 1 else ''}."


def speech_structure_summary(segment: CandidateSegment) -> str:
    prefilter = segment.prefilter
    if prefilter is None or not prefilter.speech_structure_label:
        return ""
    label = prefilter.speech_structure_label.replace("-", " ")
    if prefilter.speech_structure_cues:
        cues = human_join([cue.replace("_", " ") for cue in prefilter.speech_structure_cues[:3]])
        return f"Speech structure reads as {label} ({cues})."
    return f"Speech structure reads as {label}."


def semantic_validation_summary(segment: CandidateSegment) -> str:
    validation = segment.boundary_validation
    if validation is None:
        return ""
    target_prefix = ""
    if validation.target_reason == "floor":
        target_prefix = "Floor-targeted semantic validation "
    if validation.status == "validated":
        if validation.decision == "keep":
            return f"{target_prefix or 'Semantic validation '}kept the deterministic boundary at {round(validation.confidence * 100):d}% confidence."
        if validation.decision == "split":
            return f"{target_prefix or 'Semantic validation '}split the segment because {validation.reason.lower()}"
        return f"{target_prefix or 'Semantic validation '}suggested {validation.decision} because {validation.reason.lower()}"
    if validation.status == "fallback":
        return "Semantic validation fell back to deterministic output."
    if validation.status == "skipped":
        reason = validation.skip_reason.replace("_", " ") if validation.skip_reason else "not run"
        return f"Semantic validation skipped: {reason}."
    if validation.status == "not_eligible":
        return validation.reason
    return ""


def human_join(items: list[str]) -> str:
    values = [item for item in items if item]
    if not values:
        return "overall balance"
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def select_segments_for_asset(asset: Asset, segments: list[CandidateSegment]) -> list[CandidateSegment]:
    if not segments:
        return []

    selected: list[CandidateSegment] = []
    primary_score = score_segment(asset, segments[0]).total
    for segment in segments:
        breakdown = score_segment(asset, segment)
        if breakdown.total < TAKE_SELECTION_MIN_SCORE:
            continue
        if selected and breakdown.total < primary_score - TAKE_SELECTION_ALT_GAP:
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


def select_vlm_targets_three_stage(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    analyzer: VisionLanguageAnalyzer,
    prefilter_shortlist_ids: set[str],
    max_segments_per_asset: int,
    vlm_budget_pct: int,
    clip_enabled: bool = False,
) -> set[str]:
    """
    Select VLM targets using three-stage gating:
    1. Filter out CLIP-gated and deduplicated segments
    2. Apply per-asset limit
    3. Apply global budget cap (placeholder for global logic)
    """
    if not analyzer.requires_keyframes:
        return set()

    # Start with shortlisted segments
    eligible = [s for s in segments if s.id in prefilter_shortlist_ids]

    # Stage 1: Filter out CLIP-gated and deduplicated segments
    eligible = [s for s in eligible if not (s.prefilter and (s.prefilter.clip_gated or s.prefilter.deduplicated))]

    # Stage 2: Apply per-asset limit
    ranked = sorted(
        eligible,
        key=lambda s: (s.prefilter.metrics_snapshot.get("clip_score", 0.0) + s.prefilter.score) / 2.0
        if s.prefilter else 0.0,
        reverse=True,
    )
    per_asset_limit = max(1, min(max_segments_per_asset, len(ranked)))
    stage2_targets = ranked[:per_asset_limit]

    # Stage 3: Apply global VLM budget cap (within this asset's portion)
    # Note: This is simplified - full implementation would coordinate across all assets
    if vlm_budget_pct < 100 and stage2_targets:
        budget_count = max(1, int(len(stage2_targets) * vlm_budget_pct / 100.0))
        for i, segment in enumerate(stage2_targets):
            if i >= budget_count and segment.prefilter is not None:
                segment.prefilter.vlm_budget_capped = True

    return {s.id for s in stage2_targets if not (s.prefilter and s.prefilter.vlm_budget_capped)}


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


def describe_prefilter_selection(
    *,
    score: float,
    shortlisted: bool,
    filtered_before_vlm: bool,
    clip_gated: bool = False,
    vlm_budget_capped: bool = False,
) -> str:
    score_label = f"{round(score * 100):d}/100"
    if filtered_before_vlm:
        if clip_gated:
            return f"Gated by CLIP semantic scoring at {score_label}."
        if vlm_budget_capped:
            return f"Excluded by global VLM budget cap at {score_label}."
        return f"Filtered before VLM analysis during vision prefiltering at {score_label}."
    if shortlisted:
        return f"Shortlisted by vision prefiltering at {score_label}."
    return f"Scored {score_label} during vision prefiltering."


def suggested_timeline_duration(segment: CandidateSegment) -> float:
    duration = max(0.0, segment.end_sec - segment.start_sec)
    if segment.analysis_mode == "speech":
        return min(duration, 7.5)
    prefilter = segment.prefilter
    if prefilter is None:
        return min(duration, TIMELINE_VISUAL_BASE_MAX_DURATION_SEC)
    if prefilter.assembly_operation == "merge" or prefilter.boundary_strategy.startswith("assembly-merge:"):
        return min(duration, TIMELINE_VISUAL_MERGED_MAX_DURATION_SEC)
    if (
        prefilter.boundary_strategy in {"scene-snap", "audio-snap", "transcript-snap"}
        or prefilter.boundary_confidence >= 0.6
    ):
        return min(duration, TIMELINE_VISUAL_REFINED_MAX_DURATION_SEC)
    return min(duration, TIMELINE_VISUAL_BASE_MAX_DURATION_SEC)


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
