## MODIFIED Requirements

### Requirement: System SHALL detect and suppress near-duplicate candidate segments within each asset
After CLIP scoring completes and before VLM target selection, the analyzer SHALL compare shortlisted segments (across all assets) for visual similarity and eliminate all but the highest-scoring representative from each group of near-duplicates. When CLIP is enabled, similarity is measured by CLIP embedding cosine similarity; otherwise, histogram intersection is used.

#### Scenario: CLIP-based dedup with similar content across assets
- **WHEN** two shortlisted segments from different assets show high semantic similarity (cosine >= 0.95) after CLIP scoring
- **THEN** the segment with the lower composite score (prefilter_score + clip_score) / 2.0 SHALL be marked `deduplicated=True`
- **THEN** both segments SHALL receive matching `dedup_group_id`
- **THEN** only the retained segment SHALL be eligible for VLM targeting

#### Scenario: Histogram fallback when CLIP unavailable
- **WHEN** CLIP is disabled or fails to load and two shortlisted segments have histogram intersection score >= threshold
- **THEN** the segment with the lower prefilter score SHALL be marked `deduplicated=True`
- **THEN** both segments SHALL receive matching `dedup_group_id`

#### Scenario: Two candidates cover visually distinct content
- **WHEN** two shortlisted segments have CLIP cosine similarity < 0.95 (or histogram score < threshold with CLIP disabled)
- **THEN** both candidates SHALL remain eligible for VLM targeting independently

#### Scenario: Single shortlisted segment per group
- **WHEN** only one segment exists in a dedup group or shortlist is too small to form groups
- **THEN** deduplication pass completes with no eliminations for that group

### Requirement: System SHALL support a configurable similarity threshold
Similarity thresholds for both CLIP and histogram dedup are adjustable without code changes.

#### Scenario: CLIP cosine threshold (hardcoded default)
- **WHEN** CLIP dedup runs
- **THEN** segments with cosine similarity >= 0.95 are grouped as near-duplicates

#### Scenario: Histogram threshold is configurable
- **WHEN** `TIMELINE_DEDUP_THRESHOLD` is set to a value between 0.0 and 1.0
- **THEN** the histogram dedup pass SHALL use that value as the minimum histogram intersection score

#### Scenario: Histogram default threshold
- **WHEN** `TIMELINE_DEDUP_THRESHOLD` is not set
- **THEN** the histogram dedup pass SHALL use a default threshold of `0.85`

### Requirement: System SHALL support CLIP-based similarity as an optional upgrade
When `TIMELINE_AI_CLIP_ENABLED=true` is set and `open-clip-torch` is installed, the deduplication pass SHALL use CLIP embedding cosine similarity instead of histogram intersection as the primary algorithm.

#### Scenario: CLIP is enabled and available
- **WHEN** `TIMELINE_AI_CLIP_ENABLED=true` and `open-clip-torch` is importable
- **THEN** the deduplication pass SHALL use CLIP keyframe embedding cosine similarity as the comparison metric
- **THEN** embeddings are reused from the CLIP scoring pass (cached, no redundant computation)

#### Scenario: CLIP is enabled but not installed
- **WHEN** `TIMELINE_AI_CLIP_ENABLED=true` but `open-clip-torch` is not importable
- **THEN** the deduplication pass SHALL fall back to histogram intersection silently
- **THEN** no error SHALL be raised for the missing package during deduplication

## ADDED Requirements

### Requirement: System SHALL compute similarity from CLIP embeddings when available
When CLIP is enabled and scoring has completed, the deduplication pass SHALL derive segment embeddings from shortlisted segments' contact sheets (or first keyframe if contact sheet unavailable). Embeddings are computed once during CLIP scoring and cached for reuse by dedup.

#### Scenario: Embedding reuse avoids redundant computation
- **WHEN** CLIP scorer has cached embeddings during the scoring pass
- **THEN** dedup retrieves cached embeddings without re-invoking the model

#### Scenario: Contact sheet embedding preference
- **WHEN** evidence bundle contains both contact_sheet_path and keyframe_paths
- **THEN** contact sheet is used for embedding; if unavailable, first keyframe is used

### Requirement: Deduplication executes after evidence building and CLIP scoring
Deduplication runs as a standalone phase in the analysis pipeline, after shortlist selection, evidence building, and CLIP scoring have completed, and before VLM target selection.

#### Scenario: Phase ordering enables CLIP embeddings
- **WHEN** analysis pipeline executes
- **THEN** deduplication phase runs after CLIP scoring phase and before VLM targeting phase
- **THEN** CLIP embeddings computed during scoring are available for dedup's use

#### Scenario: Shortlist remains unchanged by dedup timing
- **WHEN** segments are marked shortlisted before dedup phase
- **THEN** dedup operates only on shortlisted segments; non-shortlisted candidates are unaffected

### Requirement: System SHALL provide deduplication statistics
The analysis summary SHALL report deduplication effectiveness with `clip_dedup_group_count`, `clip_dedup_eliminated_count` (for CLIP-based dedup), or equivalent histogram-based counts.

#### Scenario: CLIP dedup stats reported
- **WHEN** CLIP-based dedup executes
- **THEN** analysis_summary includes `clip_dedup_group_count` (number of dedup groups formed) and `clip_dedup_eliminated_count` (duplicates marked)

#### Scenario: Histogram dedup stats reported
- **WHEN** histogram-based dedup executes
- **THEN** analysis_summary includes `histogram_dedup_group_count` and `histogram_dedup_eliminated_count`

### Requirement: System SHALL preserve deterministic fallback guarantee
Deduplication SHALL never block the pipeline or prevent a deterministic result. When CLIP is unavailable, histogram dedup ensures continued functionality.

#### Scenario: Fallback when CLIP unavailable
- **WHEN** CLIP fails to load but deduplication is enabled
- **THEN** histogram dedup executes silently with no errors raised

#### Scenario: Deterministic result always available
- **WHEN** analysis completes with deduplication enabled
- **THEN** all segments have valid `deduplicated` and `dedup_group_id` values (from either CLIP or histogram)
