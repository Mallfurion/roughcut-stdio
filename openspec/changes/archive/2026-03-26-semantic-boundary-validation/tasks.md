## 1. Boundary Validation Contract

- [x] 1.1 Add configuration fields for semantic boundary validation enablement, ambiguity thresholds, and runtime caps in `ai.py`
- [x] 1.2 Define the boundary-validation response schema and persisted metadata in `domain.py`
- [x] 1.3 Add serializer support for semantic validation results and skip metadata

## 2. AI Integration

- [x] 2.1 Implement a dedicated boundary-validation prompt and response parser in `services/analyzer/app/ai.py`
- [x] 2.2 Identify eligible ambiguous segments from deterministic refinement and assembly outputs
- [x] 2.3 Enforce runtime caps before issuing semantic validation calls
- [x] 2.4 Apply bounded semantic decisions while preserving deterministic fallback behavior

## 3. Verification

- [x] 3.1 Add unit tests for prompt parsing, budget caps, and skip reasons
- [x] 3.2 Add tests covering AI unavailable, disabled, and over-budget behavior
- [x] 3.3 Add integration tests for ambiguous speech-heavy and action-heavy segments
