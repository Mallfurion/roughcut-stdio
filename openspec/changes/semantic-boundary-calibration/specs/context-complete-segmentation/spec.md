## MODIFIED Requirements

### Requirement: System SHALL refine seed regions into deterministically bounded candidate segments
The analyzer SHALL treat low-cost candidate windows as seed regions and SHALL deterministically refine those regions into bounded candidate segments before final scoring and downstream AI analysis. After deterministic refinement, the analyzer SHALL assemble adjacent refined regions into final narrative units through bounded merge and split operations before recommendation and timeline assembly. For refined or assembled segments whose boundary confidence is below the configured ambiguity threshold, the analyzer MAY run an optional semantic boundary-validation pass when enabled and within budget, and SHALL preserve deterministic output when that pass does not run. The targeting logic for that pass SHALL be calibrated against evaluation-harness results and MAY include a bounded minimum-target rule when no segment clears the primary threshold.

#### Scenario: No segment clears the primary ambiguity threshold
- **WHEN** semantic boundary validation is enabled, runtime budget remains, and no segment crosses the primary ambiguity threshold
- **THEN** the analyzer MAY still select a very small bounded subset of the most ambiguous segments for validation
- **THEN** the generated project SHALL record that minimum-target activation was used
