## 1. Assembly Model

- [ ] 1.1 Add merge/split lineage fields needed for final narrative units in `domain.py` and generated project state
- [ ] 1.2 Define deterministic continuity signals that can drive adjacency-based merge and split decisions

## 2. Merge And Split Rules

- [ ] 2.1 Implement merge rules for adjacent refined regions with transcript or structural continuity
- [ ] 2.2 Implement conservative split rules for refined regions with multiple strong internal ideas
- [ ] 2.3 Add helpers to construct final candidate segments from merged or split refined regions

## 3. Downstream Integration

- [ ] 3.1 Recalculate aggregated metrics and transcript excerpts on final narrative units
- [ ] 3.2 Update scoring and take selection to operate on assembled units
- [ ] 3.3 Ensure timeline assembly consumes final narrative units rather than pre-assembly regions

## 4. Verification

- [ ] 4.1 Add unit tests for merge decisions, split decisions, and lineage persistence
- [ ] 4.2 Add integration tests for speech-heavy, silent, and mixed-content continuity cases
- [ ] 4.3 Verify assembled units preserve stable source references for export and downstream processing
