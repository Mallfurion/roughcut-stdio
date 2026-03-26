## 1. Recommendation Review Schema

- [x] 1.1 Extend `TakeRecommendation` with review-facing ranking metadata such as outcome, within-asset rank, score gap to winner, and bounded score-driver summaries
- [x] 1.2 Add scorer-owned helpers that derive review explanations from the same weighted inputs used for deterministic ranking
- [x] 1.3 Update project serialization and loading so the richer recommendation records round-trip through `generated/project.json`

## 2. Analysis-Path Review Contract

- [x] 2.1 Normalize the segment-level review state needed to explain whether a segment was shortlisted, CLIP scored or gated, deduplicated, budget-capped, model-analyzed, or handled deterministically
- [x] 2.2 Verify reviewed analysis state remains consistent for both VLM-analyzed and skipped segments
- [x] 2.3 Add fixture coverage for mixed cases: best take, alternate, backup, duplicate, CLIP-gated, and budget-capped segments

## 3. Desktop Review Integration

- [x] 3.1 Join `candidate_segments` with `take_recommendations` in the desktop app so each segment card can render recommendation outcome and ranking explanation
- [x] 3.2 Add a compact score panel showing total score plus technical, semantic, and story components
- [x] 3.3 Add an analysis-path row that explains what was analyzed and what was skipped for each segment
- [x] 3.4 Preserve existing AI summary, rationale, and evidence details while lowering their visual priority below the actual recommendation result

## 4. Verification

- [x] 4.1 Add unit tests for recommendation ranking metadata and score-driver summary generation
- [x] 4.2 Add desktop rendering coverage for winner, alternate, backup, and blocked-segment cards
- [x] 4.3 Verify timeline export and recommendation selection behavior remain unchanged
