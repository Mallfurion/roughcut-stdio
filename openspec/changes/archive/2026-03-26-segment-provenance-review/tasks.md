## 1. Provenance Schema

- [x] 1.1 Normalize review-facing provenance fields in `domain.py` and generated project state
- [x] 1.2 Update serializers so provenance round-trips cleanly through `ProjectData`
- [x] 1.3 Verify provenance remains informational and does not affect export semantics

## 2. Review Workspace Integration

- [x] 2.1 Add desktop review components for boundary strategy, confidence, lineage summary, and semantic-validation status
- [x] 2.2 Render provenance for recommended segments without overwhelming the existing review flow
- [x] 2.3 Keep source references and timeline details visible alongside provenance

## 3. Verification

- [x] 3.1 Add tests for provenance serialization and loading
- [x] 3.2 Add UI tests or snapshot coverage for review provenance rendering
- [x] 3.3 Verify Resolve export behavior is unchanged when provenance is present
