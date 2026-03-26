## MODIFIED Requirements

### Requirement: System SHALL refine seed regions into deterministically bounded candidate segments
The analyzer SHALL treat low-cost candidate windows as seed regions and SHALL deterministically refine those regions into bounded candidate segments before final scoring and downstream AI analysis. For refined or assembled segments whose boundary confidence is below the configured ambiguity threshold, the analyzer MAY run an optional semantic boundary-validation pass when enabled and within budget, and SHALL preserve deterministic output when that pass does not run.

#### Scenario: Ambiguous segment is semantically validated
- **WHEN** a refined or assembled segment is marked ambiguous, semantic boundary validation is enabled, and runtime budget remains
- **THEN** the analyzer SHALL submit that segment to the configured AI backend for boundary validation
- **THEN** the semantic decision SHALL be persisted alongside the segment provenance

#### Scenario: Ambiguous segment is not semantically validated
- **WHEN** a refined or assembled segment is marked ambiguous but semantic validation is disabled, unavailable, or over budget
- **THEN** the analyzer SHALL keep the deterministic segment unchanged
- **THEN** the generated project SHALL record why semantic validation did not run
