## 1. CLIP Embedding Reuse Infrastructure

- [x] 1.1 Extend `CLIPScorer` class to expose `get_embedding(image_path: str) -> np.ndarray` method that returns cached embeddings without re-scoring
- [x] 1.2 Update CLIPScorer to maintain an embedding cache keyed by image_path to avoid redundant computations
- [x] 1.3 Add `reuse_cached_embeddings()` context manager or flag to CLIPScorer to optimize storage during long runs
- [x] 1.4 Document embedding cache lifecycle and reuse guarantees in CLIPScorer docstring

## 2. CLIP-Based Deduplication Module

- [x] 2.1 Create `services/analyzer/app/clip_dedup.py` module with `CLIPDeduplicator` class
- [x] 2.2 Implement `CLIPDeduplicator.deduplicate(segments, clip_scorer) -> list[CandidateSegment]` method that:
  - Extracts embeddings from each shortlisted segment (contact sheet or first keyframe)
  - Computes cosine similarity matrix across all segments
  - Groups segments with similarity >= 0.95 into clusters
  - Selects keeper (highest composite score) and marks others as deduplicated
  - Returns modified segments with deduplicated=True and dedup_group_id set
- [x] 2.3 Implement keeper selection logic: prefer highest `(prefilter_score + clip_score) / 2.0` composite score
- [x] 2.4 Add handling for missing or malformed embeddings (fallback to histogram if embedding fails)
- [x] 2.5 Add comprehensive logging to CLIPDeduplicator showing dedup groups formed, eliminates, and keeper selections

## 3. Histogram Fallback Deduplication

- [x] 3.1 Refactor existing histogram dedup logic from `services/analyzer/app/deduplication.py` into separate `HistogramDeduplicator` class if not already modular
- [x] 3.2 Expose `HistogramDeduplicator.deduplicate(segments) -> list[CandidateSegment]` method with same signature as CLIPDeduplicator
- [x] 3.3 Ensure histogram dedup operates on shortlisted segments only (not on all candidates)
- [x] 3.4 Support cross-asset deduplication (histogram dedup currently operates per-asset; need to expand to full shortlist)

## 4. Pipeline Integration

- [x] 4.1 Update `services/analyzer/app/analysis.py` analyze_assets() function:
  - Identify the point after CLIP scoring completes (around line ~380)
  - Add new phase: "Deduplication pass"
  - Create router logic: if CLIP enabled and available, use CLIPDeduplicator; else use HistogramDeduplicator
- [x] 4.2 Call dedup with shortlisted segments: `dedup_result = deduplicator.deduplicate(shortlisted_segments)`
  - Update segment.prefilter.deduplicated and dedup_group_id from result
  - Update segment.prefilter.selection_reason if deduplicated (e.g., "Duplicate of segment XYZ")
- [x] 4.3 Add status callback logging for dedup phase (similar to CLIP scoring): log number of dedup groups and eliminated segments
- [x] 4.4 Update VLM target selection logic to exclude `deduplicated=True` segments from eligibility
- [x] 4.5 Verify that dedup executes after evidence building but before VLM targeting

## 5. Statistics and Reporting

- [x] 5.1 Add dedup statistics to `project.analysis_summary`:
  - `clip_dedup_group_count: int` (number of groups formed by CLIP dedup, 0 if not used)
  - `clip_dedup_eliminated_count: int` (number of segments marked deduplicated)
  - `histogram_dedup_group_count: int` (number of groups if histogram fallback used)
  - `histogram_dedup_eliminated_count: int` (duplicates marked by histogram)
- [x] 5.2 Update `scripts/process.sh` summary output to display dedup results:
  - Show which dedup algorithm was used (CLIP or histogram)
  - Show "X near-duplicates eliminated" message
- [x] 5.3 Verify dedup stats appear in `generated/process-summary.txt`

## 6. Generated Project Output

- [x] 6.1 Verify that deduplicated segments appear in `generated/project.json` with all required fields:
  - `deduplicated: bool`
  - `dedup_group_id: int | null`
  - Updated `selection_reason` naming the keeper
- [x] 6.2 Ensure non-deduplicated segments have `deduplicated=False` and `dedup_group_id=None`
- [x] 6.3 Test that FCPXML export skips deduplicated segments (only keeper appears in timeline)

## 7. Documentation Updates

- [x] 7.1 Update `docs/analyzer-pipeline.md` "What Gets Filtered and When" section:
  - Add new Step 2.8 or 2.9 for deduplication with header "Segment Deduplication (CLIP or Histogram)"
  - Describe CLIP semantic similarity (cosine >= 0.95) and histogram fallback (threshold configurable)
  - Note that dedup runs after shortlisting, evidence building, and CLIP scoring
  - Document keeper selection logic (highest composite score)
- [x] 7.2 Update pipeline diagram/flowchart if present to show dedup phase position
- [x] 7.3 Add configuration table entries for dedup-related variables if any are user-configurable:
  - TIMELINE_DEDUP_THRESHOLD (already exists for histogram)
  - Note that CLIP cosine threshold (0.95) is hardcoded
- [x] 7.4 Add section explaining that dedup is a pre-processing step (like shortlisting) and does not affect timeline assembly logic

## 8. Testing

- [x] 8.1 Add unit tests for `CLIPDeduplicator`:
  - Test embedding extraction (contact sheet vs. first keyframe priority)
  - Test cosine similarity computation and grouping (0.95 threshold)
  - Test keeper selection (highest composite score wins)
  - Test dedup_group_id assignment and deduplicated flag
- [x] 8.2 Add unit tests for histogram fallback:
  - Test HistogramDeduplicator with modified cross-asset logic
  - Verify histogram dedup and CLIP dedup produce non-contradictory results (both mark same duplicates)
- [x] 8.3 Add integration test: run analyze_assets() with CLIP enabled and verify:
  - Dedup phase executes after CLIP scoring
  - Statistics are populated correctly
  - Deduplicated segments excluded from VLM targeting
  - All segments remain in generated/project.json
- [x] 8.4 Add integration test: run with CLIP disabled and verify histogram fallback:
  - Same assertions as 8.3 but using histogram algorithm
  - Statistics show histogram counts instead of CLIP counts
- [x] 8.5 Add test for CLIP failure scenario: verify histogram fallback when CLIP fails to load

## 9. Verification and Integration

- [x] 9.1 Verify `python3 -m unittest discover services/analyzer/tests -v` — all tests pass
- [x] 9.2 Verify `npm run process` with default settings (CLIP enabled):
  - Dedup phase executes and eliminates some segments
  - Statistics appear in process output
  - Generated project includes deduplicated segments with correct fields
- [x] 9.3 Verify `npm run process` with `TIMELINE_AI_CLIP_ENABLED=false`:
  - Histogram dedup runs instead
  - No errors or warnings
  - Dedup statistics show histogram counts
- [x] 9.4 Verify `npm run build:desktop` still succeeds (no TypeScript errors)
- [x] 9.5 Test with actual media: run full workflow (setup → process → review → export) and verify:
  - Desktop app shows segments correctly (deduplicated segments may or may not appear based on UI logic)
  - Timeline export respects dedup grouping (keeper included, duplicates excluded)
  - FCPXML exports correctly to Resolve

## 10. Documentation and Cleanup

- [x] 10.1 Review all docstrings and add clarity on embedding reuse and dedup timing
- [x] 10.2 Add brief comment in analysis.py explaining why dedup runs after CLIP scoring and evidence building
- [x] 10.3 Update analyzer-pipeline.md "What Gets Filtered and When" section with new dedup phase
- [x] 10.4 Verify that docs/manifesto.md aligns with CLIP-based dedup (editorial usefulness, inspector-ability)
- [x] 10.5 Create or update docs/research.md with notes on CLIP dedup effectiveness (open questions from design doc)
