## Dedup-CLIP Integration (Future Change)

**Status:** Proposal for follow-up implementation, not part of clip-semantic-scoring v1

### Overview

After `clip-semantic-scoring` is implemented, segment deduplication can be upgraded to use CLIP image embeddings instead of histogram-based similarity. This improves dedup accuracy by comparing semantic/visual coherence rather than pixel distributions.

### Why Separate?

1. **clip-semantic-scoring** introduces CLIP as a scoring/gating layer
2. **clip-dedup-upgrade** refactors dedup to use those embeddings
3. Keeping them separate allows:
   - Ship CLIP v1 without restructuring dedup
   - Validate CLIP scoring works well before investing in dedup refactor
   - Dedup can be upgraded independently

### Proposed Pipeline After This Change

```
Evidence building (all shortlisted segments)
  → Extract/cache CLIP embeddings for all shortlisted
  → Use CLIP embeddings for dedup comparison (instead of histograms)
  → Use same embeddings for CLIP scoring gate
  → VLM target selection
```

### What Changes

1. **CLIP embedding extraction becomes centralized**
   - Run once per segment during evidence building
   - Cache embeddings for reuse (dedup + scoring + future layers)
   - Embed all shortlisted segments, not just VLM targets

2. **Dedup switches from histogram to embedding similarity**
   - Current: histogram intersection (visual pixel distribution)
   - New: cosine similarity of CLIP embeddings (semantic/visual coherence)
   - More accurate for "is this the same shot?" comparison

3. **Dedup order might shift**
   - Current: dedup runs after prefilter scoring, before shortlisting
   - With CLIP: could run after evidence building (has embeddings)
   - Or run both: histogram dedup early (fast), CLIP dedup later (accurate)

4. **Threshold will need re-tuning**
   - CLIP similarity (cosine) uses different scale than histogram intersection
   - `TIMELINE_DEDUP_THRESHOLD` may need different default
   - Or use separate `TIMELINE_DEDUP_CLIP_THRESHOLD`

### Open Questions for This Change

1. Should we run CLIP dedup in addition to histogram dedup, or replace it?
   - **Replace:** simpler, cleaner, but loses current dedup logic
   - **Both:** more accurate, but adds complexity and latency

2. Should dedup move to after evidence building (when embeddings exist), or stay where it is?
   - Current position: early, before VLM shortlisting
   - New position: after evidence building, uses cached embeddings
   - Impacts when segments are eliminated

3. Should we cache CLIP embeddings at the segment level or the frame level?
   - Segment-level: simpler, faster, loses per-frame variation
   - Frame-level: more nuanced, but slower and more storage

### Dependencies

- Requires `clip-semantic-scoring` to be implemented first
- Requires CLIP embeddings to be extracted and cached during evidence building
- No changes needed to `segment-deduplication` specs or tasks; this is a new change

### Effort Estimate

- ~10-15 tasks
- Dedup refactor (~5 tasks)
- Integration + testing (~5-10 tasks)
- Should be done after CLIP v1 is validated in production
