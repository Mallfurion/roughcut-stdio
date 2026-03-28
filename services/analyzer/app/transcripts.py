from __future__ import annotations

from dataclasses import dataclass
from hashlib import md5
import importlib
import importlib.util
import json
import logging
from pathlib import Path
import re
from typing import Protocol

from .ai import AIAnalysisConfig
from .domain import Asset, CandidateSegment
from .scoring import infer_analysis_mode
from .shared.numbers import clamp
from .shared.strings import dedupe_labels

logger = logging.getLogger(__name__)

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
ASSEMBLY_TRANSCRIPT_CONTINUITY_GAP_SEC = 0.9


class TranscriptProvider(Protocol):
    def excerpt(self, asset: Asset, start_sec: float, end_sec: float) -> str:
        ...

    def spans(self, asset: Asset, start_sec: float, end_sec: float) -> list["TranscriptSpan"]:
        ...

    def runtime_status(self) -> "TranscriptRuntimeStatus":
        ...

    def has_cached_asset(self, asset: Asset) -> bool:
        ...


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
        if importlib.util.find_spec("faster_whisper") is None:
            return ""
        lines = [span.text for span in self.spans(asset, start_sec, end_sec) if span.text]
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
        if asset.proxy_path in self._failed_assets or asset.proxy_path in self._cache:
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
        clip_timestamps = ",".join(f"{start_sec:.3f},{end_sec:.3f}" for start_sec, end_sec in normalized)
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
