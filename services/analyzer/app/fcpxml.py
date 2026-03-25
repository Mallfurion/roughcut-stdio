from __future__ import annotations

from fractions import Fraction
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET

from .domain import Asset, CandidateSegment, ProjectData, TakeRecommendation, TimelineItem


@dataclass(slots=True)
class FCPXMLClipSummary:
    name: str
    asset_uid: str
    offset_sec: float
    start_sec: float
    duration_sec: float


def export_fcpxml(project_data: ProjectData) -> str:
    resources = ET.Element("resources")
    primary_asset = project_data.assets[0]
    format_id = "r1"
    ET.SubElement(
        resources,
        "format",
        {
            "id": format_id,
            "name": video_format_name(primary_asset),
            "frameDuration": seconds_to_fcpxml_time(1 / primary_asset.fps),
            "width": str(primary_asset.width),
            "height": str(primary_asset.height),
            "colorSpace": "1-1-1 (Rec. 709)",
        },
    )

    asset_id_by_asset: dict[str, str] = {}
    for index, asset in enumerate(project_data.assets, start=2):
        asset_id = f"r{index}"
        asset_id_by_asset[asset.id] = asset_id
        ET.SubElement(
            resources,
            "asset",
            {
                "id": asset_id,
                "name": asset.name,
                "uid": asset.interchange_reel_name,
                "src": to_file_uri(asset.source_path),
                "start": asset_start_time(asset),
                "duration": seconds_to_fcpxml_time(asset.duration_sec),
                "hasVideo": "1",
                "hasAudio": "1" if asset.has_speech else "0",
                "audioSources": "1" if asset.has_speech else "0",
                "audioChannels": "2" if asset.has_speech else "0",
                "format": format_id,
            },
        )

    library = ET.Element("library")
    event = ET.SubElement(library, "event", {"name": "Roughcut Stdio"})
    project = ET.SubElement(event, "project", {"name": project_data.project.name})

    total_timeline_duration = sum(
        max(0.0, item.trim_out_sec - item.trim_in_sec) for item in project_data.timeline.items
    )
    sequence = ET.SubElement(
        project,
        "sequence",
        {
            "format": format_id,
            "duration": seconds_to_fcpxml_time(total_timeline_duration),
            "tcStart": "0s",
            "tcFormat": "NDF",
            "audioLayout": "stereo",
            "audioRate": "48k",
        },
    )
    spine = ET.SubElement(sequence, "spine")

    asset_by_id = {asset.id: asset for asset in project_data.assets}
    segment_by_id = {segment.id: segment for segment in project_data.candidate_segments}
    take_by_id = {take.id: take for take in project_data.take_recommendations}

    offset = 0.0
    for item in sorted(project_data.timeline.items, key=lambda current: current.order_index):
        take = take_by_id[item.take_recommendation_id]
        segment = segment_by_id[take.candidate_segment_id]
        asset = asset_by_id[segment.asset_id]
        duration = max(0.0, item.trim_out_sec - item.trim_in_sec)
        segment_start = segment.start_sec + item.trim_in_sec
        clip_source_start = asset_start_seconds(asset) + segment_start

        ET.SubElement(
            spine,
            "asset-clip",
            {
                "name": item.label or take.title,
                "ref": asset_id_by_asset[asset.id],
                "offset": seconds_to_fcpxml_time(offset),
                "start": seconds_to_fcpxml_time(clip_source_start),
                "duration": seconds_to_fcpxml_time(duration),
                "tcFormat": "NDF",
                "enabled": "1",
            },
        )
        offset += duration

    fcpxml = ET.Element("fcpxml", {"version": "1.11"})
    fcpxml.append(resources)
    fcpxml.append(library)

    xml_payload = ET.tostring(fcpxml, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return xml_payload.replace("?>", "?>\n<!DOCTYPE fcpxml>", 1)


def video_format_name(asset: Asset) -> str:
    return f"FFVideoFormat{asset.height}p{int(round(asset.fps))}"


def seconds_to_fcpxml_time(seconds: float) -> str:
    value = Fraction(str(round(seconds, 6))).limit_denominator(24000)
    return f"{value.numerator}/{value.denominator}s"


def to_file_uri(raw_path: str) -> str:
    path = Path(raw_path)

    if path.is_absolute():
        return path.as_uri()

    return f"file://{quote(raw_path)}"


def asset_start_time(asset: Asset) -> str:
    return seconds_to_fcpxml_time(asset_start_seconds(asset))


def asset_start_seconds(asset: Asset) -> float:
    parts = asset.source_timecode.split(":")
    if len(parts) != 4:
        return 0.0

    hours, minutes, seconds, frames = parts
    try:
        total_seconds = (int(hours) * 3600) + (int(minutes) * 60) + int(seconds) + (int(frames) / asset.fps)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0

    return total_seconds


def parse_fcpxml_timeline(xml_payload: str) -> list[FCPXMLClipSummary]:
    sanitized = xml_payload.replace("<!DOCTYPE fcpxml>\n", "").replace("<!DOCTYPE fcpxml>", "")
    root = ET.fromstring(sanitized)

    asset_uid_by_id = {
        asset.attrib["id"]: asset.attrib.get("uid", "")
        for asset in root.findall("./resources/asset")
    }

    clips = []
    for clip in root.findall("./library/event/project/sequence/spine/asset-clip"):
        clips.append(
            FCPXMLClipSummary(
                name=clip.attrib["name"],
                asset_uid=asset_uid_by_id.get(clip.attrib["ref"], ""),
                offset_sec=fcpxml_time_to_seconds(clip.attrib["offset"]),
                start_sec=fcpxml_time_to_seconds(clip.attrib["start"]),
                duration_sec=fcpxml_time_to_seconds(clip.attrib["duration"]),
            )
        )

    return clips


def fcpxml_time_to_seconds(value: str) -> float:
    raw = value.rstrip("s")
    if "/" not in raw:
        return float(raw)

    numerator, denominator = raw.split("/", 1)
    return float(Fraction(int(numerator), int(denominator)))
