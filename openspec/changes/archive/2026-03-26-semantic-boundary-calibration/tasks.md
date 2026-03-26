## 1. Calibration Inputs

- [x] 1.1 Extend ambiguity reporting so benchmark artifacts can compare semantic-validation dormancy, targeting, and impact.
- [x] 1.2 Use evaluation-harness fixtures to define baseline semantic-validation expectations.

## 2. Analyzer Logic

- [x] 2.1 Retune ambiguity scoring with transcript-turn-aware signals and current provenance data.
- [x] 2.2 Add a bounded minimum-target rule so semantic validation can activate on the most ambiguous segments even when none cross the primary threshold.
- [x] 2.3 Persist richer semantic-validation impact metadata in generated project state.

## 3. Validation

- [x] 3.1 Add tests for dormant, threshold-hit, minimum-target, and over-budget semantic-validation paths.
- [x] 3.2 Run `python3 -m unittest discover services/analyzer/tests -v` and the segmentation evaluation harness.

## 4. Docs

- [x] 4.1 Update [docs/analyzer-pipeline.md](/Users/florin/Projects/personal/roughcut-stdio/docs/analyzer-pipeline.md) and [docs/configuration.md](/Users/florin/Projects/personal/roughcut-stdio/docs/configuration.md) to describe calibrated semantic activation.
