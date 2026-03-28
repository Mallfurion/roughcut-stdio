from __future__ import annotations

import os
import logging
from typing import Protocol

from .domain import CandidateSegment
from .prefilter import FrameSignal

logger = logging.getLogger(__name__)


class SimilarityComputer(Protocol):
    """Computes similarity between two segments."""

    def compute_similarity(self, segment1: CandidateSegment, segment2: CandidateSegment) -> float:
        """
        Compute similarity score between two segments.

        Returns a value between 0.0 and 1.0, where 1.0 means identical.
        """
        ...


class HistogramSimilarity:
    """Histogram-based visual similarity using grayscale frame data."""

    def __init__(self, frame_signals: dict[str, list[FrameSignal]]) -> None:
        """
        Initialize with frame signals mapped by segment ID.

        Args:
            frame_signals: Dict mapping segment ID to list of FrameSignal objects
        """
        self.frame_signals = frame_signals
        self._histogram_cache: dict[str, list[int]] = {}

    def compute_similarity(self, segment1: CandidateSegment, segment2: CandidateSegment) -> float:
        """Compute similarity between two segments using histogram intersection."""
        if segment1.id not in self.frame_signals or segment2.id not in self.frame_signals:
            return 0.0

        hist1 = self._get_segment_histogram(segment1.id)
        hist2 = self._get_segment_histogram(segment2.id)

        if not hist1 or not hist2:
            return 0.0

        return self._histogram_intersection(hist1, hist2)

    def _get_segment_histogram(self, segment_id: str) -> list[int]:
        """Get or compute normalized histogram for a segment."""
        if segment_id in self._histogram_cache:
            return self._histogram_cache[segment_id]

        signals = self.frame_signals.get(segment_id, [])
        if not signals:
            return []

        histogram = self._compute_histogram_from_signals(signals)
        self._histogram_cache[segment_id] = histogram
        return histogram

    @staticmethod
    def _compute_histogram_from_signals(signals: list[FrameSignal]) -> list[int]:
        """Compute a 256-bin grayscale histogram from frame signals."""
        # Create a 256-bin histogram initialized to 0
        histogram = [0] * 256

        # In a real implementation, we would process the actual pixel data.
        # For now, we use signal metrics to estimate histogram characteristics.
        for signal in signals:
            brightness = int(signal.brightness * 255)
            brightness = max(0, min(255, brightness))
            # Weight the brightness bin by the signal's distinctiveness
            weight = max(1, int(signal.distinctiveness * 10))
            histogram[brightness] += weight

        # Normalize histogram so sum equals 256 * num_signals
        total = sum(histogram)
        if total > 0:
            scale = (256.0 * len(signals)) / total
            histogram = [max(0, int(h * scale)) for h in histogram]

        return histogram

    @staticmethod
    def _histogram_intersection(hist1: list[int], hist2: list[int]) -> float:
        """
        Compute histogram intersection similarity.

        Returns normalized intersection (0-1), where 1 means identical histograms.
        """
        if len(hist1) != len(hist2) or len(hist1) == 0:
            return 0.0

        intersection = sum(min(h1, h2) for h1, h2 in zip(hist1, hist2))
        # Normalize by the sum of the first histogram
        total = sum(hist1)
        if total == 0:
            return 0.0

        return intersection / total


def deduplicate_segments(
    segments: list[CandidateSegment],
    frame_signals_by_id: dict[str, list[FrameSignal]],
    similarity_threshold: float = 0.85,
    similarity_computer: SimilarityComputer | None = None,
) -> dict[str, tuple[bool, int | None]]:
    """
    Deduplicate segments within an asset using histogram similarity.

    Args:
        segments: List of candidate segments from the same asset
        frame_signals_by_id: Dict mapping segment ID to its frame signals
        similarity_threshold: Similarity threshold for grouping (0-1, default 0.85)
        similarity_computer: Custom similarity computer (uses HistogramSimilarity if None)

    Returns:
        Dict mapping segment ID to (deduplicated: bool, dedup_group_id: int | None)
    """
    if not similarity_computer:
        similarity_computer = HistogramSimilarity(frame_signals_by_id)

    return _group_similar_segments(
        segments=segments,
        similarity_computer=similarity_computer,
        similarity_threshold=similarity_threshold,
    )


def apply_deduplication_results(
    segments: list[CandidateSegment],
    dedup_results: dict[str, tuple[bool, int | None]],
) -> None:
    """
    Apply deduplication results to segment prefilter records.

    Modifies segments in-place, setting deduplicated flag, dedup_group_id, and selection_reason.
    """
    for segment in segments:
        if segment.prefilter is not None and segment.id in dedup_results:
            deduplicated, group_id = dedup_results[segment.id]
            segment.prefilter.deduplicated = deduplicated
            segment.prefilter.dedup_group_id = group_id

            if deduplicated:
                # Find the keeper segment (highest-scoring non-deduplicated segment in this group)
                keeper = next(
                    (s for s in segments
                     if s.prefilter and s.prefilter.dedup_group_id == group_id and not s.prefilter.deduplicated),
                    None
                )
                if keeper:
                    segment.prefilter.selection_reason = f"Duplicate of segment {keeper.id} (histogram similarity)"


def is_deduplication_enabled() -> bool:
    """Check if deduplication is enabled via environment variable."""
    return os.environ.get("TIMELINE_DEDUPLICATION_ENABLED", "true").lower() in ("true", "1", "yes")


def get_dedup_threshold() -> float:
    """Get deduplication similarity threshold from environment variable."""
    try:
        return float(os.environ.get("TIMELINE_DEDUP_THRESHOLD", "0.85"))
    except ValueError:
        return 0.85


class HistogramDeduplicator:
    """
    Deduplicate candidate segments using histogram-based visual similarity.

    Segments with histogram intersection >= threshold are grouped as near-duplicates.
    The highest-scoring segment is kept as the representative; others are marked as deduplicated.
    """

    def __init__(self, frame_signals_by_id: dict[str, list[FrameSignal]], threshold: float = 0.85):
        """
        Initialize deduplicator with frame signals.

        Args:
            frame_signals_by_id: Dict mapping segment ID to list of FrameSignal objects
            threshold: Histogram intersection threshold for dedup grouping (default 0.85)
        """
        self.similarity_computer = HistogramSimilarity(frame_signals_by_id)
        self.threshold = threshold

    def deduplicate(self, segments: list[CandidateSegment]) -> list[CandidateSegment]:
        """
        Deduplicate segments using histogram similarity.

        Groups segments by visual similarity and marks duplicates.
        Modifies segments in-place: sets deduplicated and dedup_group_id.

        Args:
            segments: Shortlisted candidate segments (across all assets)

        Returns:
            Modified segments list with dedup fields set
        """
        if len(segments) < 2:
            logger.debug(f"Skipping histogram dedup: only {len(segments)} segment(s)")
            return segments

        dedup_results = _group_similar_segments(
            segments=segments,
            similarity_computer=self.similarity_computer,
            similarity_threshold=self.threshold,
        )

        # Apply results
        dedup_count = 0
        dedup_group_count = len({group_id for _deduplicated, group_id in dedup_results.values() if group_id is not None})
        for seg in segments:
            if seg.id in dedup_results:
                deduplicated, group_id = dedup_results[seg.id]
                seg.prefilter.deduplicated = deduplicated
                seg.prefilter.dedup_group_id = group_id
                if deduplicated:
                    dedup_count += 1
                    # Find keeper to update selection reason
                    keeper = next((s for s in segments if s.prefilter.dedup_group_id == group_id and not s.prefilter.deduplicated), None)
                    if keeper:
                        seg.prefilter.selection_reason = f"Duplicate of segment {keeper.id} (histogram similarity)"

        logger.info(f"Histogram dedup: {dedup_group_count} groups formed, {dedup_count} duplicates marked")
        return segments


def _group_similar_segments(
    *,
    segments: list[CandidateSegment],
    similarity_computer: SimilarityComputer,
    similarity_threshold: float,
) -> dict[str, tuple[bool, int | None]]:
    result: dict[str, tuple[bool, int | None]] = {}
    processed: set[str] = set()
    dedup_group_id = 0

    for segment in sorted(segments, key=lambda s: s.prefilter.score if s.prefilter else 0, reverse=True):
        if segment.id in processed:
            continue

        result[segment.id] = (False, dedup_group_id)
        processed.add(segment.id)

        for other in segments:
            if other.id in processed:
                continue
            similarity = similarity_computer.compute_similarity(segment, other)
            if similarity >= similarity_threshold:
                result[other.id] = (True, dedup_group_id)
                processed.add(other.id)

        dedup_group_id += 1

    return result
