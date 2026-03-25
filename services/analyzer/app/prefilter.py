from __future__ import annotations

from dataclasses import dataclass
from hashlib import md5
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess

from .domain import Asset


@dataclass(slots=True)
class FrameSignal:
    timestamp_sec: float
    sharpness: float
    contrast: float
    brightness: float
    motion_energy: float
    distinctiveness: float
    center_focus: float
    score: float
    source: str


@dataclass(slots=True)
class AudioSignal:
    timestamp_sec: float
    rms_energy: float
    peak_loudness: float
    is_silent: bool
    source: str


def sample_asset_signals(
    asset: Asset,
    *,
    target_count: int | None = None,
    timestamps: list[float] | None = None,
    frame_width: int = 64,
) -> list[FrameSignal]:
    if timestamps is None:
        timestamps = sample_timestamps(asset.duration_sec, target_count=target_count)
    signals: list[FrameSignal] = []
    previous_pixels: bytes | None = None

    for timestamp in timestamps:
        extracted = extract_gray_frame(asset.proxy_path, timestamp, width=frame_width)
        if extracted is None:
            signal = deterministic_signal(asset, timestamp)
        else:
            width, height, pixels = extracted
            signal = measure_frame_signal(timestamp, width, height, pixels, previous_pixels)
            previous_pixels = pixels
        signals.append(signal)

    return signals


def sample_timestamps(duration_sec: float, *, target_count: int | None = None) -> list[float]:
    usable_duration = max(duration_sec, 1.0)
    if target_count is None:
        target_count = max(4, min(10, int(math.ceil(usable_duration / 8.0)) + 2))
    target_count = max(1, target_count)
    step = usable_duration / (target_count + 1)
    return [round(step * index, 3) for index in range(1, target_count + 1)]


def build_prefilter_segments(
    *,
    asset: Asset,
    base_ranges: list[tuple[float, float]],
    signals: list[FrameSignal],
    audio_signals: list[AudioSignal] | None = None,
    top_windows: int = 2,
) -> list[tuple[float, float]]:
    ranges = normalized_ranges(base_ranges, asset.duration_sec)
    if not signals:
        return ranges

    peak_windows = windows_from_peak_signals(
        asset=asset,
        signals=signals,
        limit=top_windows,
    )

    audio_peak_windows: list[tuple[float, float]] = []
    if audio_signals:
        audio_peak_windows = windows_from_peak_audio_signals(
            asset=asset,
            audio_signals=audio_signals,
            limit=top_windows,
        )

    combined = ranges + peak_windows + audio_peak_windows
    if not combined:
        return ranges
    return dedupe_ranges(combined, asset.duration_sec)


def aggregate_segment_prefilter(
    *,
    signals: list[FrameSignal],
    start_sec: float,
    end_sec: float,
    audio_signals: list[AudioSignal] | None = None,
) -> dict[str, object]:
    matching = [
        signal
        for signal in signals
        if start_sec <= signal.timestamp_sec <= end_sec
    ]
    if not matching and signals:
        center = (start_sec + end_sec) / 2.0
        nearest = min(signals, key=lambda signal: abs(signal.timestamp_sec - center))
        matching = [nearest]

    if not matching:
        return {
            "score": 0.0,
            "sampled_frame_count": 0,
            "sampled_frame_timestamps_sec": [],
            "top_frame_timestamps_sec": [],
            "metrics_snapshot": {},
        }

    motion_values = [signal.motion_energy for signal in matching]
    stability = clamp(1.0 - statistics.pstdev(motion_values) * 1.6) if len(motion_values) > 1 else 0.72
    score = average(signal.score for signal in matching)

    matching_audio = _matching_audio_signals(audio_signals, start_sec, end_sec)
    audio_energy = average(sig.rms_energy for sig in matching_audio) if matching_audio else 0.0
    speech_ratio = (
        sum(1 for sig in matching_audio if not sig.is_silent) / len(matching_audio)
        if matching_audio else 0.0
    )

    metrics_snapshot = {
        "sharpness": round(average(signal.sharpness for signal in matching), 4),
        "stability": round(stability, 4),
        "visual_novelty": round(average(signal.distinctiveness for signal in matching), 4),
        "subject_clarity": round(
            average((signal.center_focus * 0.65) + (signal.contrast * 0.35) for signal in matching),
            4,
        ),
        "motion_energy": round(average(signal.motion_energy for signal in matching), 4),
        "prefilter_brightness": round(average(signal.brightness for signal in matching), 4),
        "prefilter_contrast": round(average(signal.contrast for signal in matching), 4),
        "prefilter_score": round(score, 4),
        "audio_energy": round(clamp(audio_energy), 4),
        "speech_ratio": round(clamp(speech_ratio), 4),
    }
    top_timestamps = [
        round(signal.timestamp_sec, 3)
        for signal in sorted(matching, key=lambda signal: signal.score, reverse=True)[:2]
    ]

    return {
        "score": round(score, 4),
        "sampled_frame_count": len(matching),
        "sampled_frame_timestamps_sec": [round(signal.timestamp_sec, 3) for signal in matching],
        "top_frame_timestamps_sec": top_timestamps,
        "metrics_snapshot": metrics_snapshot,
    }


def average(values) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def normalized_ranges(ranges: list[tuple[float, float]], duration_sec: float) -> list[tuple[float, float]]:
    normalized: list[tuple[float, float]] = []
    for start_sec, end_sec in ranges:
        start = clamp(start_sec, 0.0, duration_sec)
        end = clamp(end_sec, start + 0.01, duration_sec)
        if end - start >= 1.0:
            normalized.append((round(start, 3), round(end, 3)))
    return dedupe_ranges(normalized, duration_sec)


def windows_from_peak_signals(
    *,
    asset: Asset,
    signals: list[FrameSignal],
    limit: int,
) -> list[tuple[float, float]]:
    if not signals:
        return []

    sorted_signals = sorted(signals, key=lambda signal: (signal.score, signal.distinctiveness), reverse=True)
    window_size = clamp(asset.duration_sec / 8.0, 2.5, 5.5)
    windows: list[tuple[float, float]] = []

    for signal in sorted_signals:
        start = max(0.0, signal.timestamp_sec - (window_size / 2.0))
        end = min(asset.duration_sec, start + window_size)
        if end - start < 1.5:
            continue
        candidate = (round(start, 3), round(end, 3))
        if any(overlap_ratio(candidate, existing) >= 0.7 for existing in windows):
            continue
        windows.append(candidate)
        if len(windows) >= limit:
            break

    return windows


def merge_ranges(ranges: list[tuple[float, float]], duration_sec: float) -> list[tuple[float, float]]:
    if not ranges:
        return []

    ordered = sorted((max(0.0, start), min(duration_sec, end)) for start, end in ranges if end > start)
    merged: list[list[float]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        current = merged[-1]
        if start <= current[1] + 0.75:
            current[1] = max(current[1], end)
        else:
            merged.append([start, end])
    return [(round(start, 3), round(end, 3)) for start, end in merged]


def dedupe_ranges(ranges: list[tuple[float, float]], duration_sec: float) -> list[tuple[float, float]]:
    if not ranges:
        return []

    ordered = sorted(
        (
            (max(0.0, start), min(duration_sec, end))
            for start, end in ranges
            if end > start
        ),
        key=lambda item: ((item[1] - item[0]), item[0]),
    )
    kept: list[tuple[float, float]] = []
    for candidate in ordered:
        if any(overlap_ratio(candidate, existing) >= 0.9 for existing in kept):
            continue
        kept.append((round(candidate[0], 3), round(candidate[1], 3)))
    return sorted(kept, key=lambda item: item[0])


def overlap_ratio(a: tuple[float, float], b: tuple[float, float]) -> float:
    start = max(a[0], b[0])
    end = min(a[1], b[1])
    if end <= start:
        return 0.0
    overlap = end - start
    shorter = min(a[1] - a[0], b[1] - b[0])
    return overlap / shorter if shorter > 0 else 0.0


def deterministic_signal(asset: Asset, timestamp_sec: float) -> FrameSignal:
    seed = deterministic_value(asset.id, timestamp_sec, "sharpness")
    contrast = clamp(0.42 + deterministic_value(asset.name, timestamp_sec, "contrast") * 0.42)
    sharpness = clamp(0.48 + seed * 0.42)
    brightness = clamp(0.38 + deterministic_value(asset.source_path, timestamp_sec, "brightness") * 0.36)
    motion = clamp(0.25 + deterministic_value(asset.proxy_path, timestamp_sec, "motion") * 0.55)
    distinctiveness = clamp(0.28 + deterministic_value(asset.interchange_reel_name, timestamp_sec, "distinctive") * 0.58)
    center_focus = clamp(0.4 + deterministic_value(asset.id, timestamp_sec, "center") * 0.42)
    score = combine_signal_score(
        sharpness=sharpness,
        contrast=contrast,
        motion_energy=motion,
        distinctiveness=distinctiveness,
        center_focus=center_focus,
    )
    return FrameSignal(
        timestamp_sec=round(timestamp_sec, 3),
        sharpness=round(sharpness, 4),
        contrast=round(contrast, 4),
        brightness=round(brightness, 4),
        motion_energy=round(motion, 4),
        distinctiveness=round(distinctiveness, 4),
        center_focus=round(center_focus, 4),
        score=round(score, 4),
        source="deterministic",
    )


def deterministic_value(asset_key: str, timestamp_sec: float, label: str) -> float:
    token = f"{asset_key}:{timestamp_sec:.3f}:{label}".encode("utf-8")
    digest = md5(token).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def extract_gray_frame(path: str, timestamp_sec: float, *, width: int) -> tuple[int, int, bytes] | None:
    if shutil.which("ffmpeg") is None:
        return None
    if not Path(path).exists():
        return None

    process = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{timestamp_sec:.3f}",
            "-i",
            path,
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:-1,format=gray",
            "-f",
            "image2pipe",
            "-vcodec",
            "pgm",
            "-",
        ],
        check=False,
        capture_output=True,
    )
    if process.returncode != 0 or not process.stdout:
        return None

    return decode_pgm(process.stdout)


def decode_pgm(raw: bytes) -> tuple[int, int, bytes] | None:
    if not raw.startswith(b"P5"):
        return None

    index = 2
    tokens: list[bytes] = []
    length = len(raw)
    while len(tokens) < 3 and index < length:
        while index < length and raw[index] in b" \t\r\n":
            index += 1
        if index < length and raw[index] == ord("#"):
            while index < length and raw[index] != ord("\n"):
                index += 1
            continue
        start = index
        while index < length and raw[index] not in b" \t\r\n":
            index += 1
        if start < index:
            tokens.append(raw[start:index])

    if len(tokens) != 3:
        return None

    try:
        width = int(tokens[0])
        height = int(tokens[1])
        max_value = int(tokens[2])
    except ValueError:
        return None
    if max_value <= 0 or width <= 0 or height <= 0:
        return None

    while index < length and raw[index] in b" \t\r\n":
        index += 1
    expected = width * height
    pixels = raw[index:index + expected]
    if len(pixels) != expected:
        return None
    return width, height, pixels


def measure_frame_signal(
    timestamp_sec: float,
    width: int,
    height: int,
    pixels: bytes,
    previous_pixels: bytes | None,
) -> FrameSignal:
    total = width * height
    mean_value = sum(pixels) / (255.0 * total)
    variance = sum(((value / 255.0) - mean_value) ** 2 for value in pixels) / total
    contrast = clamp(math.sqrt(variance) * 2.4)

    horizontal = 0.0
    vertical = 0.0
    for row in range(height):
        row_offset = row * width
        for col in range(width - 1):
            horizontal += abs(pixels[row_offset + col] - pixels[row_offset + col + 1])
    for row in range(height - 1):
        row_offset = row * width
        next_offset = (row + 1) * width
        for col in range(width):
            vertical += abs(pixels[row_offset + col] - pixels[next_offset + col])
    gradient_denominator = max(1.0, ((height * (width - 1)) + ((height - 1) * width)) * 255.0)
    sharpness = clamp((horizontal + vertical) / gradient_denominator * 3.2)

    if previous_pixels is None or len(previous_pixels) != len(pixels):
        motion_energy = 0.32
        distinctiveness = 0.32
    else:
        difference = sum(abs(current - previous) for current, previous in zip(pixels, previous_pixels))
        normalized_difference = difference / (len(pixels) * 255.0)
        motion_energy = clamp(normalized_difference * 3.4)
        distinctiveness = clamp(normalized_difference * 3.0)

    center_focus = clamp(center_region_contrast(width, height, pixels) * 2.0)
    score = combine_signal_score(
        sharpness=sharpness,
        contrast=contrast,
        motion_energy=motion_energy,
        distinctiveness=distinctiveness,
        center_focus=center_focus,
    )
    return FrameSignal(
        timestamp_sec=round(timestamp_sec, 3),
        sharpness=round(sharpness, 4),
        contrast=round(contrast, 4),
        brightness=round(clamp(mean_value), 4),
        motion_energy=round(motion_energy, 4),
        distinctiveness=round(distinctiveness, 4),
        center_focus=round(center_focus, 4),
        score=round(score, 4),
        source="ffmpeg",
    )


def center_region_contrast(width: int, height: int, pixels: bytes) -> float:
    x0 = max(0, width // 4)
    x1 = min(width, width - x0)
    y0 = max(0, height // 4)
    y1 = min(height, height - y0)
    values: list[float] = []
    for row in range(y0, y1):
        row_offset = row * width
        for col in range(x0, x1):
            values.append(pixels[row_offset + col] / 255.0)
    if not values:
        return 0.0
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def combine_signal_score(
    *,
    sharpness: float,
    contrast: float,
    motion_energy: float,
    distinctiveness: float,
    center_focus: float,
) -> float:
    return clamp(
        (sharpness * 0.26)
        + (contrast * 0.16)
        + (motion_energy * 0.22)
        + (distinctiveness * 0.2)
        + (center_focus * 0.16)
    )


def sample_audio_signals(
    asset: Asset,
    timestamps: list[float],
) -> list[AudioSignal]:
    if not timestamps:
        return []
    if os.environ.get("TIMELINE_AI_AUDIO_ENABLED", "true").lower() == "false":
        return _fallback_audio_signals(timestamps)
    if not asset.has_speech:
        return _fallback_audio_signals(timestamps)
    if shutil.which("ffmpeg") is None or not Path(asset.proxy_path).exists():
        return _fallback_audio_signals(timestamps)

    try:
        silence_intervals = _detect_silence_intervals(asset.proxy_path)
        rms_by_time = _extract_rms_by_time(asset.proxy_path, asset.duration_sec, len(timestamps))
    except Exception:
        return _fallback_audio_signals(timestamps)

    if not rms_by_time:
        return _fallback_audio_signals(timestamps)

    half_window = (asset.duration_sec / (len(timestamps) + 1)) / 2.0
    signals: list[AudioSignal] = []
    for ts in timestamps:
        window_start = max(0.0, ts - half_window)
        window_end = min(asset.duration_sec, ts + half_window)
        matching_rms = [rms for time, rms in rms_by_time if window_start <= time <= window_end]
        rms_energy = sum(matching_rms) / len(matching_rms) if matching_rms else 0.0
        peak_loudness = max(matching_rms) if matching_rms else 0.0
        is_silent = _is_window_silent(silence_intervals, window_start, window_end)
        signals.append(
            AudioSignal(
                timestamp_sec=round(ts, 3),
                rms_energy=round(clamp(rms_energy), 4),
                peak_loudness=round(clamp(peak_loudness), 4),
                is_silent=is_silent,
                source="ffmpeg",
            )
        )
    return signals


def windows_from_peak_audio_signals(
    *,
    asset: Asset,
    audio_signals: list[AudioSignal],
    limit: int,
    min_energy_threshold: float = 0.05,
) -> list[tuple[float, float]]:
    energetic = [sig for sig in audio_signals if sig.rms_energy >= min_energy_threshold and not sig.is_silent]
    if not energetic:
        return []

    sorted_signals = sorted(energetic, key=lambda sig: sig.rms_energy, reverse=True)
    window_size = clamp(asset.duration_sec / 8.0, 2.5, 5.5)
    windows: list[tuple[float, float]] = []

    for signal in sorted_signals:
        start = max(0.0, signal.timestamp_sec - (window_size / 2.0))
        end = min(asset.duration_sec, start + window_size)
        if end - start < 1.5:
            continue
        candidate = (round(start, 3), round(end, 3))
        if any(overlap_ratio(candidate, existing) >= 0.7 for existing in windows):
            continue
        windows.append(candidate)
        if len(windows) >= limit:
            break

    return windows


def _matching_audio_signals(
    audio_signals: list[AudioSignal] | None,
    start_sec: float,
    end_sec: float,
) -> list[AudioSignal]:
    if not audio_signals:
        return []
    matching = [sig for sig in audio_signals if start_sec <= sig.timestamp_sec <= end_sec]
    if not matching:
        center = (start_sec + end_sec) / 2.0
        nearest = min(audio_signals, key=lambda sig: abs(sig.timestamp_sec - center))
        matching = [nearest]
    return matching


def _fallback_audio_signals(timestamps: list[float]) -> list[AudioSignal]:
    return [
        AudioSignal(
            timestamp_sec=round(ts, 3),
            rms_energy=0.0,
            peak_loudness=0.0,
            is_silent=True,
            source="fallback",
        )
        for ts in timestamps
    ]


def _detect_silence_intervals(path: str) -> list[tuple[float, float]]:
    # -v info is required: silencedetect writes at info level, not warning
    process = subprocess.run(
        [
            "ffmpeg", "-v", "info",
            "-i", path,
            "-map", "0:a:0",
            "-af", "silencedetect=noise=-35dB:duration=0.3",
            "-f", "null", "-",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    intervals: list[tuple[float, float]] = []
    silence_start: float | None = None
    for line in process.stderr.splitlines():
        if "silence_start:" in line:
            match = re.search(r"silence_start:\s*([-\d.eE+]+)", line)
            if match:
                silence_start = float(match.group(1))
        elif "silence_end:" in line and silence_start is not None:
            match = re.search(r"silence_end:\s*([-\d.eE+]+)", line)
            if match:
                intervals.append((silence_start, float(match.group(1))))
                silence_start = None
    if silence_start is not None:
        intervals.append((silence_start, float("inf")))
    return intervals


def _extract_rms_by_time(
    path: str,
    duration_sec: float,
    target_count: int,
) -> list[tuple[float, float]]:
    import tempfile

    chunk_len = max(0.1, min(2.0, duration_sec / max(1, target_count * 2)))
    tmp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()

    try:
        subprocess.run(
            [
                "ffmpeg", "-v", "warning",
                "-i", path,
                "-map", "0:a:0",
                "-af", f"astats=length={chunk_len:.3f}:metadata=1:reset=1,ametadata=mode=print:file={tmp_path}",
                "-f", "null", "-",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        output = Path(tmp_path).read_text(errors="replace") if Path(tmp_path).exists() else ""
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass

    if not output:
        return []

    results: list[tuple[float, float]] = []
    current_time: float | None = None
    for line in output.splitlines():
        time_match = re.search(r"pts_time:([\d.eE+-]+)", line)
        if time_match:
            current_time = float(time_match.group(1))
        if current_time is not None:
            rms_match = re.search(r"lavfi\.astats\.Overall\.RMS_level=([-\d.eEinf+]+)", line)
            if rms_match:
                try:
                    rms_str = rms_match.group(1).strip()
                    if "inf" in rms_str or "nan" in rms_str:
                        rms_linear = 0.0
                    else:
                        rms_dbfs = float(rms_str)
                        rms_linear = clamp(10.0 ** (rms_dbfs / 20.0))
                    results.append((current_time, rms_linear))
                    current_time = None
                except ValueError:
                    pass
    return results


def _is_window_silent(
    intervals: list[tuple[float, float]],
    start: float,
    end: float,
) -> bool:
    window_dur = end - start
    if window_dur <= 0:
        return True
    silent_overlap = 0.0
    for s, e in intervals:
        overlap_start = max(s, start)
        overlap_end = min(e, end)
        if overlap_end > overlap_start:
            silent_overlap += overlap_end - overlap_start
    return (silent_overlap / window_dur) >= 0.5
