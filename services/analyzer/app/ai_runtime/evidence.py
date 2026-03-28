from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from ..domain import Asset, CandidateSegment, SegmentEvidence


def build_segment_evidence(
    *,
    asset: Asset,
    segment: CandidateSegment,
    asset_segments: list[CandidateSegment],
    segment_index: int,
    story_prompt: str,
    artifacts_root: str | Path | None,
    extract_keyframes: bool,
    transcript_status: str = "",
    speech_mode_source: str = "",
    max_keyframes_per_segment: int = 3,
    keyframe_max_width: int = 640,
) -> SegmentEvidence:
    keyframe_timestamps = keyframe_timestamps_for_segment(
        segment.start_sec,
        segment.end_sec,
        target_count=max_keyframes_per_segment,
    )
    keyframe_paths: list[str] = []
    contact_sheet_path = ""

    if extract_keyframes and artifacts_root is not None:
        keyframe_paths = extract_segment_keyframes(
            asset=asset,
            segment=segment,
            timestamps=keyframe_timestamps,
            artifacts_root=artifacts_root,
            max_width=keyframe_max_width,
        )
        contact_sheet_path = create_segment_contact_sheet(
            asset=asset,
            segment=segment,
            keyframe_paths=keyframe_paths,
            artifacts_root=artifacts_root,
        )

    context_window_start_sec = segment.start_sec
    context_window_end_sec = segment.end_sec
    if segment_index > 0:
        context_window_start_sec = asset_segments[segment_index - 1].start_sec
    if segment_index < len(asset_segments) - 1:
        context_window_end_sec = asset_segments[segment_index + 1].end_sec

    return SegmentEvidence(
        media_path=asset.proxy_path,
        transcript_excerpt=segment.transcript_excerpt,
        story_prompt=story_prompt,
        analysis_mode=segment.analysis_mode,
        transcript_status=transcript_status,
        speech_mode_source=speech_mode_source,
        keyframe_timestamps_sec=[round(timestamp, 3) for timestamp in keyframe_timestamps],
        keyframe_paths=keyframe_paths,
        contact_sheet_path=contact_sheet_path,
        context_window_start_sec=round(context_window_start_sec, 3),
        context_window_end_sec=round(context_window_end_sec, 3),
        metrics_snapshot=dict(segment.quality_metrics),
        keyframe_max_width=keyframe_max_width if extract_keyframes else 0,
        transcript_turn_count=(
            len(segment.prefilter.transcript_turn_ids)
            if segment.prefilter is not None
            else 0
        ),
        transcript_turn_ranges_sec=(
            [list(item) for item in segment.prefilter.transcript_turn_ranges_sec]
            if segment.prefilter is not None
            else []
        ),
        turn_completeness=round(segment.quality_metrics.get("turn_completeness", 0.0), 4),
        speech_structure_label=(
            segment.prefilter.speech_structure_label
            if segment.prefilter is not None
            else ""
        ),
        speech_structure_cues=(
            list(segment.prefilter.speech_structure_cues)
            if segment.prefilter is not None
            else []
        ),
        speech_structure_confidence=round(
            segment.prefilter.speech_structure_confidence,
            4,
        ) if segment.prefilter is not None else 0.0,
    )


def segment_evidence_matches(
    *,
    evidence: SegmentEvidence | None,
    asset: Asset,
    segment: CandidateSegment,
    asset_segments: list[CandidateSegment],
    segment_index: int,
    story_prompt: str,
    extract_keyframes: bool,
    transcript_status: str = "",
    speech_mode_source: str = "",
    max_keyframes_per_segment: int = 3,
    keyframe_max_width: int = 640,
) -> bool:
    if evidence is None:
        return False

    expected_timestamps = [
        round(timestamp, 3)
        for timestamp in keyframe_timestamps_for_segment(
            segment.start_sec,
            segment.end_sec,
            target_count=max_keyframes_per_segment,
        )
    ]
    expected_context_window_start_sec = segment.start_sec
    expected_context_window_end_sec = segment.end_sec
    if segment_index > 0:
        expected_context_window_start_sec = asset_segments[segment_index - 1].start_sec
    if segment_index < len(asset_segments) - 1:
        expected_context_window_end_sec = asset_segments[segment_index + 1].end_sec

    return (
        evidence.media_path == asset.proxy_path
        and evidence.transcript_excerpt == segment.transcript_excerpt
        and evidence.story_prompt == story_prompt
        and evidence.analysis_mode == segment.analysis_mode
        and evidence.transcript_status == transcript_status
        and evidence.speech_mode_source == speech_mode_source
        and evidence.keyframe_timestamps_sec == expected_timestamps
        and evidence.context_window_start_sec == round(expected_context_window_start_sec, 3)
        and evidence.context_window_end_sec == round(expected_context_window_end_sec, 3)
        and evidence.metrics_snapshot == dict(segment.quality_metrics)
        and evidence.keyframe_max_width == (keyframe_max_width if extract_keyframes else 0)
    )


def keyframe_timestamps_for_segment(
    start_sec: float,
    end_sec: float,
    target_count: int | None = None,
) -> list[float]:
    duration = max(0.01, end_sec - start_sec)
    count = target_count or (3 if duration <= 8.0 else 4)
    count = max(1, count)
    step = duration / (count + 1)
    return [start_sec + (step * index) for index in range(1, count + 1)]


def extract_segment_keyframes(
    *,
    asset: Asset,
    segment: CandidateSegment,
    timestamps: list[float],
    artifacts_root: str | Path,
    max_width: int,
) -> list[str]:
    if shutil.which("ffmpeg") is None:
        return []

    segment_dir = Path(artifacts_root) / "keyframes" / asset.id
    segment_dir.mkdir(parents=True, exist_ok=True)

    targets = [
        segment_dir / f"{segment.id}-k{index:02d}.jpg"
        for index, _timestamp in enumerate(timestamps, start=1)
    ]
    extracted_by_target: dict[Path, str] = {}

    if len(targets) > 1:
        for path in _extract_segment_keyframes_batched(
            media_path=asset.proxy_path,
            timestamps=timestamps,
            targets=targets,
            max_width=max_width,
        ):
            extracted_by_target[Path(path)] = path

    for timestamp, target in zip(timestamps, targets):
        if target in extracted_by_target:
            continue
        extracted = _extract_single_segment_keyframe(
            media_path=asset.proxy_path,
            timestamp=timestamp,
            target=target,
            max_width=max_width,
        )
        if extracted:
            extracted_by_target[target] = extracted

    return [
        extracted_by_target[target]
        for target in targets
        if target in extracted_by_target
    ]


def _extract_single_segment_keyframe(
    *,
    media_path: str,
    timestamp: float,
    target: Path,
    max_width: int,
) -> str:
    process = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            media_path,
            "-vf",
            f"scale=min({max_width}\\,iw):-2",
            "-frames:v",
            "1",
            "-q:v",
            "4",
            str(target),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode == 0 and target.exists():
        return str(target)
    return ""


def _extract_segment_keyframes_batched(
    *,
    media_path: str,
    timestamps: list[float],
    targets: list[Path],
    max_width: int,
) -> list[str]:
    command = ["ffmpeg", "-y", "-v", "error"]
    for timestamp in timestamps:
        command.extend(["-ss", f"{timestamp:.3f}", "-i", media_path])
    for index, target in enumerate(targets):
        command.extend(
            [
                "-map",
                f"{index}:v:0",
                "-vf",
                f"scale=min({max_width}\\,iw):-2",
                "-frames:v",
                "1",
                "-q:v",
                "4",
                str(target),
            ]
        )

    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        return []
    return [str(target) for target in targets if target.exists()]


def create_segment_contact_sheet(
    *,
    asset: Asset,
    segment: CandidateSegment,
    keyframe_paths: list[str],
    artifacts_root: str | Path,
) -> str:
    if not keyframe_paths:
        return ""
    if len(keyframe_paths) == 1:
        return keyframe_paths[0]
    if shutil.which("ffmpeg") is None:
        return keyframe_paths[0]

    contact_dir = Path(artifacts_root) / "contact-sheets" / asset.id
    contact_dir.mkdir(parents=True, exist_ok=True)
    target = contact_dir / f"{segment.id}.jpg"
    command = ["ffmpeg", "-y", "-v", "error"]
    for path in keyframe_paths:
        command.extend(["-i", path])
    command.extend(
        [
            "-filter_complex",
            f"hstack=inputs={len(keyframe_paths)}",
            "-q:v",
            "4",
            str(target),
        ]
    )
    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode == 0 and target.exists():
        return str(target)
    return keyframe_paths[0]


def batch_image_path_for_evidence(evidence: SegmentEvidence) -> str:
    if evidence.contact_sheet_path:
        return evidence.contact_sheet_path
    if evidence.keyframe_paths:
        return evidence.keyframe_paths[0]
    return ""
