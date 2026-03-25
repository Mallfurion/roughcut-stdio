# CLIP-Semantic-Scoring: Updated Proposal Summary

**Status:** Updated for implementation readiness

## Key Changes from Original Proposal

### 1. **Pipeline Architecture (MAJOR UPDATE)**

**Original Problem:** Circular dependency — CLIP needed evidence before VLM targets were selected, but evidence was only extracted for VLM targets.

**Solution:** Restructured the pipeline to make stages explicit and linear.

**New Pipeline:**
```
Shortlist selection
  ↓
Evidence building [CHANGED: for ALL shortlisted segments]
  ↓
CLIP scoring [NEW stage 2.9]
  ↓
VLM target selection [CHANGED: three-stage gate]
  ↓
VLM analysis
  ↓
Deterministic understanding (for remaining segments)
  ↓
Final scoring
```

**Impact:** Evidence building now extracts keyframes for all shortlisted segments (~30-50% more extraction in fast mode), enabling CLIP to score the full shortlist before VLM targeting decisions.

### 2. **Evidence Building Scope**

**Before:** Only extracted keyframes for VLM targets
```python
extract_keyframes=segment.id in ai_target_ids
```

**After:** Extracts keyframes for all shortlisted segments
```python
extract_keyframes=segment.id in prefilter_shortlist_ids
```

**Rationale:** Evidence is now "for downstream analysis" not "specifically for VLM." Enables CLIP and future semantic layers without restructuring.

### 3. **VLM Target Selection Becomes Three-Stage Gate**

**Before:** Single-stage per-asset limit
- Select top N segments per asset by prefilter score

**After:** Three-stage sequential gating
1. **Stage 1: CLIP gate** — Exclude segments where `clip_gated=True` (below `TIMELINE_AI_CLIP_MIN_SCORE`)
2. **Stage 2: Per-asset limit** — Select top N per asset by composite score
3. **Stage 3: Global budget cap** — Rank all eligible segments across all assets by `(prefilter_score + clip_score) / 2.0`, select top N% of total candidates

### 4. **Deduplication Integration → Separate Future Change**

**Before:** Task 4.5 attempted to integrate CLIP embeddings with deduplication in v1

**After:** Removed from this change. Created separate proposal (`DEDUP_INTEGRATION_PROPOSAL.md`) for:
- Upgrade dedup to use CLIP embeddings instead of histograms
- Implement after CLIP v1 is validated in production
- Separate concern that can evolve independently

**Why:** Keeps this change focused on CLIP scoring/gating. Dedup can be upgraded when embeddings are cached and available.

## Updated Specifications

### Design.md
- ✅ Updated constraints to reflect evidence building for all shortlisted
- ✅ Removed dedup integration from goals
- ✅ Clarified Decision 1: evidence building scope
- ✅ Updated migration plan (8 clear steps)
- ✅ Reorganized open questions (9 items)

### Tasks.md
- ✅ Reorganized task 4 (Pipeline Integration) into 4 clear subtasks:
  - 4.1: Change evidence building scope
  - 4.2: CLIP scoring pass
  - 4.3: Three-stage VLM target selection
  - 4.4: Ensure gated segments get deterministic understanding
- ✅ Removed task 4.5 (dedup integration)

### Vision-Prefilter-Pipeline Spec
- ✅ Updated to reflect CLIP as stage 2.9 (after evidence building)
- ✅ Added requirement for universal evidence building

### AI-Segment-Understanding Spec
- ✅ Clarified global budget cap applies after CLIP gating

## Remaining Open Questions

1. **CLIP model selection (DECIDED)** → Use ViT-B-32, don't expose configuration in v1
2. **Composite score formula** → Confirm `(prefilter + clip) / 2.0` is appropriate
3. **Evidence building in fast/full mode** → Extract for all shortlisted in both (consistent)
4. **CLIP embedding storage** → Hold in memory only, don't persist
5. **Threshold validation** → Should defaults be tested on sample footage?
6. **Silent segments** → They still get frames → contact sheets exist → CLIP scores them (low if no visual content)
7. **Process reporting** → Global summary (not per-asset)
8. **Story prompt integration** → Deferred to future change
9. **Global budget cap distribution** → Global top-N (not proportional per-asset)

## Ready for Implementation?

### ✅ Clear
- Pipeline architecture and execution order
- Task breakdown and responsibilities
- Specification requirements
- Configuration variables
- Test strategy

### ⚠️ Decisions Needed (Before Starting Tasks)
1. Composite score weighting (equal or weighted?)
2. Threshold defaults need validation? (or proceed with 0.35 and 10%?)
3. Fast mode evidence extraction acceptable? (extra keyframes justified?)
4. Silent segment handling acceptable? (CLIP scores low if blank frames)

### 📋 Artifacts
- `design.md` — Updated architecture and decisions
- `tasks.md` — 55 tasks across 8 sections
- `DEDUP_INTEGRATION_PROPOSAL.md` — Future integration work
- `specs/` — Four spec files (clip-semantic-scoring, vision-prefilter-pipeline, deterministic-screening, ai-segment-understanding, processing-workflow)

## Recommended Next Steps

1. **Address remaining open questions** (15-20 min discussion)
2. **Mark proposal as ready for implementation**
3. **Begin task 1 (Domain Model)** — Add fields to domain.py
4. **Task 2 (CLIPScorer class)** — Core CLIP scoring logic
5. **Task 4.1 (Evidence Building)** — Pipeline change
6. **Task 4.2-4.3 (CLIP Integration)** — Wire into analyze_assets()
7. **Testing & validation** — Ensure CLIP doesn't break existing behavior when disabled

**Estimated effort:** ~50-60 hours for v1 implementation
