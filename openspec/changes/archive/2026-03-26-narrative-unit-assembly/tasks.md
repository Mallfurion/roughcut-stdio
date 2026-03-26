## 1. Assembly Model

- [x] 1.1 Add merge/split lineage fields needed for final narrative units in `domain.py` and generated project state
- [x] 1.2 Define deterministic continuity signals that can drive adjacency-based merge and split decisions

## 2. Merge And Split Rules

- [x] 2.1 Implement merge rules for adjacent refined regions with transcript or structural continuity
- [x] 2.2 Implement conservative split rules for refined regions with multiple strong internal ideas
- [x] 2.3 Add helpers to construct final candidate segments from merged or split refined regions

## 3. Downstream Integration

- [x] 3.1 Recalculate aggregated metrics and transcript excerpts on final narrative units
- [x] 3.2 Update scoring and take selection to operate on assembled units
- [x] 3.3 Ensure timeline assembly consumes final narrative units rather than pre-assembly regions

## 4. Verification

- [x] 4.1 Add unit tests for merge decisions, split decisions, and lineage persistence
- [x] 4.2 Add integration tests for speech-heavy, silent, and mixed-content continuity cases
- [x] 4.3 Verify assembled units preserve stable source references for export and downstream processing
