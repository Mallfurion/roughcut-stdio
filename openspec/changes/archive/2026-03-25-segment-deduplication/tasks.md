## 1. Domain Model

- [x] 1.1 Add `deduplicated` boolean field to `PrefilterDecision` in `domain.py` (default `False`)
- [x] 1.2 Add `dedup_group_id` optional string field to `PrefilterDecision` — set to the retained candidate's segment ID when a segment is eliminated
- [x] 1.3 Update `selection_reason` population logic to include a deduplication reason string when `deduplicated=True`

## 2. Histogram Computation

- [x] 2.1 Implement `compute_segment_histogram(signals: list[FrameSignal], start_sec, end_sec) -> list[float]` in `prefilter.py`: extract the grayscale pixel values from the `FrameSignal` records that overlap the segment window, bucket them into 16 luminance bins, and return a normalized histogram
- [x] 2.2 Handle the edge case where no `FrameSignal` records overlap the segment window: return a uniform histogram (all bins equal) so the segment is treated as maximally similar to nothing and survives deduplication
- [x] 2.3 Implement `histogram_intersection(h1: list[float], h2: list[float]) -> float` in `prefilter.py`: return `sum(min(h1[i], h2[i]) for i in range(len(h1)))`, normalized to [0, 1]

## 3. Deduplication Pass

- [x] 3.1 Implement `deduplicate_segments(segments, signals, threshold) -> list[CandidateSegment]` in `prefilter.py`: compute a histogram per segment, compare all pairs within the asset using histogram intersection, group pairs whose similarity meets or exceeds the threshold, retain the highest-scoring segment per group, and mark the rest as `deduplicated=True` with `dedup_group_id` set
- [x] 3.2 Add a guard: if the asset has fewer than 2 candidate segments, skip the deduplication pass and return the segment list unchanged
- [x] 3.3 Ensure that deduplication group membership is deterministic across reruns when inputs are identical

## 4. Pipeline Integration

- [x] 4.1 Call `deduplicate_segments()` in `analyze_assets()` in `analysis.py` after prefilter scoring and before shortlist selection
- [x] 4.2 Update `select_prefilter_shortlist_ids()` to exclude segments where `prefilter.deduplicated=True` from the shortlist candidate pool
- [x] 4.3 Ensure deduplicated segments do not count against `max_segments_per_asset` when the shortlist is built in fast mode
- [x] 4.4 Ensure deduplicated segments are still written to `generated/project.json` with their full prefilter record intact

## 5. Configuration

- [x] 5.1 Add `TIMELINE_DEDUP_THRESHOLD` environment variable loading, defaulting to `0.85`
- [x] 5.2 Pass the threshold value into `deduplicate_segments()` from the analysis config
- [x] 5.3 Define the CLIP upgrade path interface: when `TIMELINE_AI_CLIP_ENABLED=true` and `open-clip-torch` is importable, use CLIP embedding cosine similarity instead of histogram intersection; fall back to histogram silently when the package is unavailable

## 6. Reporting

- [x] 6.1 Add per-asset deduplication statistics to the analysis summary in `project.analysis_summary`: `dedup_candidate_count` (total before dedup), `dedup_eliminated_count` (marked deduplicated), `dedup_forwarded_count` (passed to shortlist)
- [x] 6.2 Extend process reporting in `scripts/process.sh` to print per-asset deduplication counts in the summary output and `generated/process.log`

## 7. Validation

- [x] 7.1 Add unit tests for `compute_segment_histogram()` covering: normal case, no overlapping signals, single-frame segment
- [x] 7.2 Add unit tests for `histogram_intersection()` covering: identical histograms (score = 1.0), disjoint histograms (score = 0.0), partial overlap
- [x] 7.3 Add unit tests for `deduplicate_segments()` covering: two near-identical segments (lower-scored eliminated), two distinct segments (both retained), single segment (pass-through), threshold boundary behavior
- [x] 7.4 Add a test verifying that deduplicated segments appear in the output with `deduplicated=True` and a valid `dedup_group_id`
- [x] 7.5 Add a test verifying that deduplicated segments do not appear in the shortlist candidate pool
- [x] 7.6 Verify `python3 -m unittest discover services/analyzer/tests -v`
- [x] 7.7 Verify `npm run process` produces `generated/project.json` with `dedup_eliminated_count` in `analysis_summary`
- [x] 7.8 Verify `npm run build:desktop` still succeeds
