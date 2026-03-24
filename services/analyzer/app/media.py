from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Iterable

from .domain import Asset


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mxf",
    ".m4v",
    ".avi",
    ".mkv",
    ".webm",
}

PROXY_FOLDER_MARKERS = ("proxy", "proxies", "optimized media", "optimized")
PROXY_NAME_MARKERS = ("proxy", "prox", "optimized", "opt")


@dataclass(slots=True)
class MediaProbe:
    duration_sec: float | None
    fps: float | None
    width: int | None
    height: int | None
    has_audio: bool | None
    timecode: str | None


@dataclass(slots=True)
class DiscoveredMedia:
    path: str
    role: str
    clip_key: str
    stem: str
    extension: str
    probe: MediaProbe | None = None


@dataclass(slots=True)
class MatchedMedia:
    source: DiscoveredMedia
    proxy: DiscoveredMedia | None
    confidence: float
    reason: str


class FFprobeRunner:
    def probe(self, media_path: str | Path) -> MediaProbe:
        path = Path(media_path)
        process = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(process.stdout)

        video_stream = next(
            (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"),
            None,
        )
        audio_stream = next(
            (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "audio"),
            None,
        )

        format_payload = payload.get("format", {})
        duration_sec = parse_float(format_payload.get("duration"))
        fps = parse_ratio(video_stream.get("avg_frame_rate")) if video_stream else None

        timecode = None
        if video_stream:
            timecode = (
                video_stream.get("tags", {}).get("timecode")
                or video_stream.get("timecode")
                or format_payload.get("tags", {}).get("timecode")
            )

        return MediaProbe(
            duration_sec=duration_sec,
            fps=fps,
            width=video_stream.get("width") if video_stream else None,
            height=video_stream.get("height") if video_stream else None,
            has_audio=audio_stream is not None,
            timecode=timecode,
        )


class ExifToolRunner:
    def probe(self, media_path: str | Path) -> MediaProbe:
        path = Path(media_path)
        process = subprocess.run(
            ["exiftool", "-j", "-n", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(process.stdout)[0]

        duration_sec = numeric_or_none(payload.get("Duration"))
        fps = numeric_or_none(payload.get("VideoFrameRate")) or numeric_or_none(payload.get("PlaybackFrameRate"))
        width = integer_or_none(payload.get("ImageWidth")) or integer_or_none(payload.get("SourceImageWidth"))
        height = integer_or_none(payload.get("ImageHeight")) or integer_or_none(payload.get("SourceImageHeight"))
        has_audio = bool(payload.get("AudioChannels") or payload.get("AudioFormat"))
        timecode = first_timecode_string(
            payload.get("StartTimecode"),
            payload.get("SourceTimecode"),
            payload.get("TimeCode"),
        )
        if timecode is None:
            timecode = datetime_to_timecode(
                payload.get("Blackmagic-design Camera Date Recorded")
                or payload.get("CreationDate")
                or payload.get("CreateDate")
            )

        return MediaProbe(
            duration_sec=duration_sec,
            fps=fps,
            width=width,
            height=height,
            has_audio=has_audio,
            timecode=timecode,
        )


def discover_media_files(
    roots: Iterable[str | Path],
    probe_runner: FFprobeRunner | None = None,
) -> list[DiscoveredMedia]:
    effective_probe_runner = probe_runner or default_probe_runner()
    discovered: list[DiscoveredMedia] = []

    for root in roots:
        root_path = Path(root).expanduser().resolve()
        if not root_path.exists():
            continue

        for candidate in sorted(root_path.rglob("*")):
            if not candidate.is_file() or candidate.suffix.lower() not in VIDEO_EXTENSIONS:
                continue

            role = classify_media_role(candidate)
            probe = effective_probe_runner.probe(candidate) if effective_probe_runner is not None else None
            discovered.append(
                DiscoveredMedia(
                    path=str(candidate),
                    role=role,
                    clip_key=normalized_clip_key(candidate.stem),
                    stem=candidate.stem,
                    extension=candidate.suffix.lower(),
                    probe=probe,
                )
            )

    return discovered


def match_media_files(media_files: Iterable[DiscoveredMedia]) -> list[MatchedMedia]:
    grouped: dict[str, list[DiscoveredMedia]] = {}
    for media_file in media_files:
        grouped.setdefault(media_file.clip_key, []).append(media_file)

    matches: list[MatchedMedia] = []
    for group in grouped.values():
        sources = [media for media in group if media.role == "source"]
        proxies = [media for media in group if media.role == "proxy"]

        if not sources and proxies:
            for proxy in proxies:
                matches.append(
                    MatchedMedia(
                        source=proxy,
                        proxy=proxy,
                        confidence=0.45,
                        reason="Only proxy media found; using proxy as the source placeholder.",
                    )
                )
            continue

        for source in sources:
            best_proxy, confidence, reason = select_best_proxy(source, proxies)
            matches.append(
                MatchedMedia(
                    source=source,
                    proxy=best_proxy,
                    confidence=confidence,
                    reason=reason,
                )
            )

    matches.sort(key=lambda item: item.source.path)
    return matches


def build_assets_from_matches(matches: Iterable[MatchedMedia]) -> list[Asset]:
    assets: list[Asset] = []

    for index, match in enumerate(matches, start=1):
        source_probe = match.source.probe or MediaProbe(None, None, None, None, None, None)
        proxy_path = match.proxy.path if match.proxy is not None else match.source.path
        reel_name = Path(match.source.path).stem
        assets.append(
            Asset(
                id=f"asset-{index:03d}",
                name=humanize_stem(match.source.stem),
                source_path=match.source.path,
                proxy_path=proxy_path,
                duration_sec=source_probe.duration_sec or 0.0,
                fps=source_probe.fps or 24.0,
                width=source_probe.width or 1920,
                height=source_probe.height or 1080,
                has_speech=bool(source_probe.has_audio),
                interchange_reel_name=reel_name,
                source_timecode=source_probe.timecode or "00:00:00:00",
            )
        )

    return assets


def classify_media_role(path: str | Path) -> str:
    candidate = Path(path)
    parts = [part.lower() for part in candidate.parts]
    stem = candidate.stem.lower()

    if any(marker in part for part in parts for marker in PROXY_FOLDER_MARKERS):
        return "proxy"

    if any(re.search(rf"(?:^|[_\-. ]){marker}(?:$|[_\-. ])", stem) for marker in PROXY_NAME_MARKERS):
        return "proxy"

    return "source"


def normalized_clip_key(stem: str) -> str:
    normalized = stem.upper()
    normalized = re.sub(r"(?:^|[_\-. ])(?:PROXY|PROX|OPTIMIZED|OPT)(?:$|[_\-. ])", "_", normalized)
    normalized = re.sub(r"[^A-Z0-9]+", "", normalized)
    return normalized


def select_best_proxy(
    source: DiscoveredMedia,
    proxies: list[DiscoveredMedia],
) -> tuple[DiscoveredMedia | None, float, str]:
    if not proxies:
        return None, 0.0, "No proxy candidate found."

    ranked = sorted(
        ((score_proxy_match(source, proxy), proxy) for proxy in proxies),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, best_proxy = ranked[0]
    return best_proxy, round(best_score, 2), explain_proxy_match(best_score)


def score_proxy_match(source: DiscoveredMedia, proxy: DiscoveredMedia) -> float:
    score = 0.4

    if normalized_clip_key(source.stem) == normalized_clip_key(proxy.stem):
        score += 0.35

    if source.stem.lower() in proxy.stem.lower() or proxy.stem.lower() in source.stem.lower():
        score += 0.1

    if source.extension == proxy.extension:
        score += 0.05

    if source.probe and proxy.probe:
        duration_delta = abs((source.probe.duration_sec or 0.0) - (proxy.probe.duration_sec or 0.0))
        if duration_delta < 0.2:
            score += 0.1

        fps_delta = abs((source.probe.fps or 0.0) - (proxy.probe.fps or 0.0))
        if fps_delta < 0.2:
            score += 0.05

    return min(score, 1.0)


def explain_proxy_match(score: float) -> str:
    if score >= 0.85:
        return "Exact filename-style proxy match."
    if score >= 0.7:
        return "Strong filename match with compatible media characteristics."
    if score >= 0.55:
        return "Reasonable proxy match; review if the project has duplicate camera names."
    return "Weak proxy match; manual review recommended."


def humanize_stem(stem: str) -> str:
    spaced = re.sub(r"[_\-]+", " ", stem).strip()
    return spaced.title() if spaced else stem


def parse_float(value: str | None) -> float | None:
    if value in (None, "", "N/A"):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_ratio(value: str | None) -> float | None:
    if value in (None, "", "0/0"):
        return None

    if "/" not in value:
        return parse_float(value)

    numerator, denominator = value.split("/", 1)
    if denominator == "0":
        return None

    try:
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def default_probe_runner() -> FFprobeRunner | ExifToolRunner | None:
    if shutil.which("ffprobe"):
        return FFprobeRunner()
    if shutil.which("exiftool"):
        return ExifToolRunner()
    return None


def numeric_or_none(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return parse_float(value)
    return None


def integer_or_none(value: object) -> int | None:
    numeric = numeric_or_none(value)
    if numeric is None:
        return None
    return int(round(numeric))


def first_timecode_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and re.fullmatch(r"\d{2}:\d{2}:\d{2}:\d{2}", value):
            return value
    return None


def datetime_to_timecode(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None

    normalized = value.strip().replace("Z", "+00:00")
    normalized = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", normalized)

    for parser in (
        datetime.fromisoformat,
        lambda item: datetime.strptime(item, "%Y:%m:%d %H:%M:%S%z"),
        lambda item: datetime.strptime(item, "%Y:%m:%d %H:%M:%S"),
    ):
        try:
            parsed = parser(normalized)
            return f"{parsed.hour:02d}:{parsed.minute:02d}:{parsed.second:02d}:00"
        except ValueError:
            continue

    return None
