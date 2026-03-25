"""CLIP-based semantic deduplication of candidate segments."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
import numpy as np

from .domain import CandidateSegment
from .clip import CLIPScorer

logger = logging.getLogger(__name__)


class CLIPDeduplicator:
    """
    Deduplicate candidate segments using CLIP semantic embeddings.

    Segments with cosine similarity >= 0.95 are grouped as near-duplicates.
    The highest-scoring segment (by composite score) is kept as the representative;
    others are marked as deduplicated.
    """

    SIMILARITY_THRESHOLD = 0.95  # Cosine similarity threshold for dedup grouping

    def __init__(self, clip_scorer: CLIPScorer):
        """
        Initialize deduplicator with a CLIP scorer instance.

        Args:
            clip_scorer: Initialized CLIPScorer with cached embeddings
        """
        self.clip_scorer = clip_scorer

    def deduplicate(self, segments: list[CandidateSegment]) -> list[CandidateSegment]:
        """
        Deduplicate segments using CLIP embeddings.

        Groups segments by semantic similarity and marks duplicates.
        Modifies segments in-place: sets deduplicated and dedup_group_id.

        Args:
            segments: Shortlisted candidate segments (assumed to have evidence bundles)

        Returns:
            Modified segments list with dedup fields set
        """
        if len(segments) < 2:
            logger.debug(f"Skipping CLIP dedup: only {len(segments)} segment(s)")
            return segments

        # Extract embeddings for all segments
        embeddings = []
        valid_indices = []

        for i, segment in enumerate(segments):
            embedding = self._get_segment_embedding(segment)
            if embedding is not None:
                # Squeeze to remove batch dimension [1, 512] -> [512]
                embedding = embedding.squeeze()
                embeddings.append(embedding)
                valid_indices.append(i)
            else:
                logger.warning(f"Failed to extract embedding for segment {segment.id}, treating as non-duplicate")

        if len(embeddings) < 2:
            logger.debug(f"Only {len(embeddings)} valid embeddings, skipping dedup")
            return segments

        embeddings = np.array(embeddings)  # [N, embedding_dim]

        # Compute cosine similarity matrix
        # Normalize embeddings (should already be normalized, but ensure)
        embeddings_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        similarity_matrix = embeddings_norm @ embeddings_norm.T  # [N, N]

        # Find dedup groups using agglomerative clustering
        groups = self._cluster_similar_segments(similarity_matrix, valid_indices)

        # Mark duplicates and assign group IDs
        dedup_count = 0
        group_count = 0
        for group_indices in groups:
            if len(group_indices) > 1:
                group_count += 1
                # Select keeper (highest composite score)
                keeper_idx = self._select_keeper(segments, group_indices)

                for idx in group_indices:
                    segment = segments[valid_indices[idx]]
                    if idx != keeper_idx:
                        segment.prefilter.deduplicated = True
                        segment.prefilter.dedup_group_id = group_count
                        keeper = segments[valid_indices[keeper_idx]]
                        segment.prefilter.selection_reason = f"Duplicate of segment {keeper.id} (CLIP semantic similarity)"
                        dedup_count += 1
                    else:
                        segment.prefilter.dedup_group_id = group_count

        logger.info(f"CLIP dedup: {group_count} groups formed, {dedup_count} duplicates marked")
        return segments

    def _get_segment_embedding(self, segment: CandidateSegment) -> Optional[np.ndarray]:
        """
        Extract embedding for a segment from its evidence bundle.

        Prefers contact sheet; falls back to first keyframe.

        Args:
            segment: Candidate segment with evidence bundle

        Returns:
            Embedding array or None if extraction fails
        """
        if segment.evidence_bundle is None:
            return None

        # Try contact sheet first
        image_path = segment.evidence_bundle.contact_sheet_path
        if image_path and Path(image_path).exists():
            embedding = self.clip_scorer.get_embedding(image_path)
            if embedding is not None:
                return embedding

        # Fall back to first keyframe
        if segment.evidence_bundle.keyframe_paths:
            image_path = segment.evidence_bundle.keyframe_paths[0]
            if Path(image_path).exists():
                embedding = self.clip_scorer.get_embedding(image_path)
                if embedding is not None:
                    return embedding

        logger.warning(f"Could not extract embedding for segment {segment.id}: no valid image path")
        return None

    def _cluster_similar_segments(self, similarity_matrix: np.ndarray, valid_indices: list[int]) -> list[list[int]]:
        """
        Cluster similar segments using single-linkage clustering.

        Args:
            similarity_matrix: [N, N] cosine similarity matrix
            valid_indices: Indices of valid segments (for logging)

        Returns:
            List of clusters, each cluster is a list of indices into the embeddings/valid_indices
        """
        n = similarity_matrix.shape[0]
        visited = np.zeros(n, dtype=bool)
        clusters = []

        for i in range(n):
            if visited[i]:
                continue

            # Start a new cluster with segment i
            cluster = [i]
            visited[i] = True
            queue = [i]

            # BFS to find all similar segments
            while queue:
                current = queue.pop(0)
                for j in range(n):
                    if not visited[j] and similarity_matrix[current, j] >= self.SIMILARITY_THRESHOLD:
                        cluster.append(j)
                        visited[j] = True
                        queue.append(j)

            clusters.append(cluster)

        return clusters

    def _select_keeper(self, segments: list[CandidateSegment], group_indices: list[int]) -> int:
        """
        Select the keeper segment from a dedup group.

        Keeper is the one with highest composite score: (prefilter_score + clip_score) / 2.0

        Args:
            segments: All candidate segments
            group_indices: Indices into embeddings array (which map to segments via valid_indices)

        Returns:
            Index of the keeper in the group_indices list
        """
        best_idx = 0
        best_score = -1.0

        for idx in group_indices:
            segment = segments[idx]
            if segment.prefilter is None:
                continue

            prefilter_score = segment.prefilter.score
            clip_score = segment.prefilter.metrics_snapshot.get("clip_score", 0.5)
            composite_score = (prefilter_score + clip_score) / 2.0

            if composite_score > best_score:
                best_score = composite_score
                best_idx = idx

        return best_idx
