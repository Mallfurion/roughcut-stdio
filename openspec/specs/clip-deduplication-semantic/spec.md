# clip-deduplication-semantic Specification

## Purpose

Enable semantic near-duplicate detection using CLIP embeddings during the analysis pipeline, allowing segments with visually similar compositional elements to be grouped and deduplicated based on high-dimensional visual/semantic similarity rather than low-level histogram intersection.

## Requirements

### Requirement: CLIP-based semantic near-duplicate detection
The system SHALL use CLIP semantic embeddings to identify near-duplicate segments based on visual/compositional similarity. Segments with cosine similarity >= 0.95 SHALL be grouped as duplicates, with the highest-scoring segment marked as keeper and others marked as `deduplicated=True`. The dedup pass SHALL execute after evidence building and CLIP scoring, operating on shortlisted segments only.

#### Scenario: CLIP embeddings enable semantic grouping
- **WHEN** CLIP scoring is enabled and two shortlisted segments show visually/compositionally similar content (same action, composition, but different lighting or framing)
- **THEN** segments are grouped with cosine similarity >= 0.95, keeper selection respects prefilter score and order, duplicate marked with dedup_group_id

#### Scenario: Embedding cache prevents redundant computation
- **WHEN** CLIP scorer computes embeddings during scoring pass and dedup phase requests them
- **THEN** dedup reuses cached embeddings without re-invoking the model

#### Scenario: Contact sheet preferred for embedding extraction
- **WHEN** evidence bundle contains both contact_sheet_path and keyframe_paths
- **THEN** contact sheet is used for embedding extraction; if unavailable or missing, first keyframe is used

### Requirement: Dedup statistics added to analysis summary
The system SHALL add `clip_dedup_group_count` and `clip_dedup_eliminated_count` to `project.analysis_summary` to report deduplication coverage when CLIP-based dedup executes.

#### Scenario: Summary shows dedup results
- **WHEN** CLIP-based dedup completes
- **THEN** analysis_summary includes clip_dedup_group_count (number of dedup groups formed) and clip_dedup_eliminated_count (number of segments marked as duplicates)

### Requirement: Fallback to histogram dedup when CLIP unavailable
The system SHALL fall back to histogram-based dedup (existing algorithm) when CLIP is disabled (`TIMELINE_AI_CLIP_ENABLED=false`) or fails to load. Fallback dedup operates on the same shortlisted segments and produces identical `deduplicated` and `dedup_group_id` fields.

#### Scenario: Dedup available when CLIP disabled
- **WHEN** CLIP is disabled but deduplication is enabled
- **THEN** histogram-based dedup runs after shortlisting (existing behavior) using histogram similarity

#### Scenario: CLIP failure triggers histogram fallback
- **WHEN** CLIP model fails to load but deduplication is enabled
- **THEN** system logs warning and falls back to histogram dedup without interrupting pipeline

### Requirement: Per-asset dedup grouping respects shortlist boundaries
The system SHALL deduplicate across the entire shortlist (all assets combined), not just within-asset. Dedup groups MAY span multiple assets if semantic similarity is high.

#### Scenario: Cross-asset deduplication
- **WHEN** segments from asset A and asset B show high semantic similarity (same action shot from multiple clips)
- **THEN** they are grouped into the same dedup group and keeper is selected by composite score

### Requirement: Deduplication output format
The system SHALL set `deduplicated: True` on segments marked as duplicates and populate `dedup_group_id: int` on all grouped segments (keeper and duplicates). Non-duplicated segments have `dedup_group_id=None`.

#### Scenario: Dedup fields in generated/project.json
- **WHEN** segments are processed and dedup groups formed
- **THEN** all segments in generated/project.json include deduplicated (bool) and dedup_group_id (int|null) fields

### Requirement: Preserve deterministic fallback guarantee
The system SHALL ensure that deduplication results do not depend on AI model availability beyond the CLIP embedding step. When CLIP is disabled, dedup uses histogram similarity (deterministic, no model required).

#### Scenario: Deterministic dedup available always
- **WHEN** deduplication is enabled
- **THEN** system can always produce dedup results (either via CLIP if available, or histogram fallback)
