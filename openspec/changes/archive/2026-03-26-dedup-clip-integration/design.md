## Context

**Current State**:
- Histogram-based deduplication runs in the prefilter phase (before shortlisting)
- Compares pixel-level color distributions to identify near-duplicates
- Independent of AI analysis; runs on every candidate segment

**Proposed Integration**:
- CLIP semantic scoring is now enabled by default and computes image embeddings for all shortlisted segments
- These embeddings are cached during the scoring pass and can be reused for deduplication
- Moving dedup to post-evidence-building phase allows us to leverage CLIP embeddings instead of histogram similarity

**Timeline Constraints**:
- Deterministic fallback must remain available (when CLIP disabled)
- Resolve export and timeline integrity are unchanged
- Dedup remains optional (controlled by TIMELINE_DEDUPLICATION_ENABLED)

## Goals / Non-Goals

**Goals:**
- Replace histogram similarity with CLIP semantic embeddings for more editorial-useful near-duplicate detection
- Reuse CLIP embeddings computed during semantic scoring (no additional model inference)
- Move deduplication to execute after evidence building to enable embedding-based logic
- Maintain backward compatibility: histogram dedup available as fallback when CLIP disabled
- Implement segment-level embedding caching to avoid redundant computations
- Update documentation to reflect new pipeline ordering

**Non-Goals:**
- Change the prefilter logic or shortlisting criteria
- Modify CLIP semantic scoring itself (that's done in clip-semantic-scoring change)
- Alter Resolve export correctness or timeline item selection
- Add user-facing controls for dedup algorithm selection (internal design detail)

## Decisions

### Decision 1: Embed Reuse vs. Fresh Computation
**Choice**: Reuse CLIP embeddings from the semantic scoring pass.

**Rationale**: Embeddings are already computed and cached during clip_scorer initialization. Computing them again for dedup would be wasteful. By executing dedup after evidence building and CLIP scoring, we can read cached embeddings.

**Alternatives Considered**:
- Fresh computation for dedup: Would be redundant when CLIP scoring is already running, doubling inference cost
- Different embedding model: Would add complexity and maintenance burden; CLIP embeddings are already vetted for visual quality

### Decision 2: Embedding Storage Level (Segment vs. Frame)
**Choice**: Store embeddings at segment level (one embedding per segment, computed from contact sheet or keyframe).

**Rationale**: Segments are the dedup unit anyway. Frame-level embeddings would require aggregation logic and storage overhead. Segment-level is simpler, aligns with evidence bundle structure.

**Alternatives Considered**:
- Frame-level embeddings: Would allow frame-to-frame matching within segments but adds storage and aggregation complexity
- Contact sheet only: Too rigid if contact sheet generation fails

### Decision 3: Timing in Pipeline
**Choice**: Execute dedup in a new phase after evidence building and CLIP scoring, before deterministic fallback.

**Current Order**:
1. Build candidate segments
2. Prefilter (with histogram dedup) → shortlist
3. Build evidence (keyframes)
4. CLIP scoring
5. VLM targeting (3-stage gate)
6. AI analysis (VLM or deterministic)

**New Order**:
1. Build candidate segments
2. Prefilter (filter by audio/motion, no dedup) → shortlist
3. Build evidence (keyframes)
4. CLIP scoring
5. **CLIP-based deduplication** ← NEW PHASE
6. VLM targeting (3-stage gate)
7. AI analysis (VLM or deterministic)

**Rationale**:
- Moving dedup after CLIP scoring lets us use semantic embeddings
- Keeps dedup independent of VLM targeting logic
- Maintains clear separation of concerns: prefilter → shortlist, evidence → build materials, CLIP → semantic scoring, dedup → near-duplicate grouping, VLM gate → budget constraints

**Alternatives Considered**:
- Dedup before shortlisting: Loses opportunity to use CLIP embeddings (not available until after prefilter)
- Dedup after VLM targeting: Would lose visibility into gated segments; adds coupling to budget logic

### Decision 4: Fallback Behavior
**Choice**: When CLIP is disabled, fall back to histogram-based dedup (existing algorithm).

**Rationale**: Preserves deterministic fallback guarantee. Histogram dedup is fast and works without AI. Users with CLIP disabled continue to get dedup functionality.

**Alternatives Considered**:
- Disable dedup when CLIP unavailable: Would break functionality; editors rely on dedup to find duplicates
- Compute embeddings from scratch: Defeats purpose of local-first; CLIP disabled implies user wants to avoid AI

### Decision 5: Caching and Reuse
**Choice**: Implement segment-level embedding cache in CLIPScorer. Reuse same scorer instance across scoring and dedup phases.

**Rationale**: CLIPScorer already caches embeddings from `score()` calls. We extend it to expose raw embeddings for dedup without re-scoring. Single scorer instance avoids model reloading.

**Alternatives Considered**:
- Separate caching layer: Would duplicate logic; CLIPScorer is the right place for CLIP concerns
- Recompute embeddings for dedup: Wasteful; embeddings already available

## Risks / Trade-trades

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Embedding cache memory growth** | First run with many segments could use significant RAM | Implement cache eviction (LRU) if cache exceeds threshold; segment-level (not frame-level) minimizes footprint |
| **Dependency on CLIP availability** | Editor cannot deduplicate if CLIP fails to load | Fallback to histogram dedup when CLIP unavailable; no silent failures |
| **Phase reordering introduces bugs** | Moving dedup could affect shortlist size or VLM budget calculation | Test that shortlist size unchanged; verify budget cap logic independent of dedup |
| **Embedding quality for non-photographic content** | CLIP trained on diverse images; performance on abstract/animation footage unknown | Document limitation; histogram dedup still available as fallback; user can disable CLIP if results unsatisfactory |
| **Deterministic reproducibility** | Floating-point embedding operations may vary slightly across machines | Accept minor variance; dedup is heuristic (editor always has final say) |

## Migration Plan

**Deployment**:
1. Implement clip-deduplication module with embedding reuse logic
2. Update analysis.py to call dedup after CLIP scoring phase
3. Add dedup statistics to summary output (unchanged from histogram version)
4. Update docs/analyzer-pipeline.md with new phase ordering

**Testing**:
- Verify shortlist size unchanged (dedup runs after shortlisting, only affects within-shortlist)
- Verify fallback to histogram dedup when CLIP disabled
- Confirm embedding cache working and embeddings reused
- Integration test: run with sample media, verify dedup groups formed sensibly

**Rollback** (if needed):
- Revert to histogram dedup by disabling CLIP-based path in dedup module
- Can be done at runtime via TIMELINE_DEDUP_ALGORITHM env var if needed

## Open Questions

1. **Embedding distance metric**: Should we use cosine similarity (like CLIP scoring does) or another metric for dedup? Recommendation: Use cosine similarity to stay consistent with CLIP scoring logic.

2. **Dedup threshold tuning**: What cosine similarity threshold defines a near-duplicate? Recommendation: Start conservative (0.95) to only flag very similar segments; user feedback may adjust.

3. **Within-asset vs. cross-asset dedup**: Should dedup search only within an asset or across the entire shortlist? Recommendation: Cross-asset to catch duplicates from multiple clips of same scene/action.

4. **Contact sheet vs. keyframe selection**: If contact sheet unavailable, which keyframe to embed? Recommendation: Use first keyframe (highest temporal priority); fall back to contact sheet if available.
