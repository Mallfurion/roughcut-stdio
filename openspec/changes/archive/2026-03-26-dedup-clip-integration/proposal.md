## Why

Histogram-based deduplication identifies visual near-duplicates through color histogram similarity, but this approach misses semantic relationships—it treats visual content at surface level rather than understanding composition, lighting, and editorial intent. CLIP embeddings, trained on image-text pairs, capture semantic meaning at the level editors care about: what the shot is *about* rather than just its pixel distribution. Migrating deduplication to use CLIP embeddings will surface more editorial-useful near-duplicate detection while maintaining the integrity of the shortlist and supporting the manifesto goal of editorial usefulness and inspector-ability.

## What Changes

- Replace histogram-based similarity comparison with CLIP semantic embeddings for near-duplicate detection
- Move deduplication execution from pre-shortlisting (early in the pipeline) to post-evidence-building (after CLIP embeddings are available)
- Implement segment-level CLIP embedding caching to avoid redundant model evaluations
- Update `docs/analyzer-pipeline.md` to document the new dedup timing and semantic scoring approach
- Maintain backward compatibility: histogram dedup remains available as fallback when CLIP is disabled

## Capabilities

### New Capabilities
- `clip-deduplication-semantic`: CLIP-based near-duplicate detection using pre-trained embeddings to identify segments with similar semantic content, replacing histogram-based color matching

### Modified Capabilities
- `segment-deduplication`: Execution timing moves from pre-shortlisting to post-evidence-building, with CLIP semantic embeddings as primary algorithm when available
- `clip-semantic-scoring`: Integration point—CLIP embeddings computed during semantic scoring pass are reused for deduplication
- `processing-workflow`: Reordering of analysis phases to enable CLIP-based dedup after evidence collection

## Impact

- **Analyzer pipeline**: Deduplication phase moves to after evidence building and CLIP scoring (currently it runs before shortlisting)
- **Performance**: CLIP embeddings computed once during scoring pass; deduplication reuses them (no additional model evaluations)
- **User experience**: More semantically meaningful near-duplicate detection; editor gets visually/conceptually similar segments flagged, not just color-similar ones
- **Fallback behavior**: When CLIP is disabled (TIMELINE_AI_CLIP_ENABLED=false), deduplication falls back to histogram-based approach
- **Documentation**: analyzer-pipeline.md updated to reflect new phase ordering and CLIP integration points
- **Dependencies**: Depends on clip-semantic-scoring being enabled; works independently when CLIP is disabled
