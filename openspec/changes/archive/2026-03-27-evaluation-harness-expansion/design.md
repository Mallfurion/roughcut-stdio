## Context

Roughcut Stdio already has a fixture-driven segmentation evaluation harness, but it was introduced to stabilize the segmentation overhaul rather than to evaluate the full rough-cut pipeline. Now that the analyzer includes story assembly, transcript turns, semantic calibration, and benchmark history, the existing checks are too narrow to answer higher-value questions like: did the sequence get more repetitive, did the opener get weaker, or did a change improve one repeated dataset run without confusing that result with an entirely different footage set?

The next evaluation pass should remain lightweight and local-first, but it needs two clearer modes:
- portable shared fixtures for pass/fail validation
- dataset-aware benchmarking for repeated runs on the same footage

## Goals / Non-Goals

**Goals:**
- Expand evaluation beyond narrow segment-shape checks.
- Add sequence-level quality checks that reflect rough-cut behavior.
- Preserve evaluation outputs in benchmark artifacts so same-dataset runs can be compared safely.
- Keep fixture sets explicit, repeatable, and easy to evolve.

**Non-Goals:**
- Building a cloud-hosted evaluation platform.
- Replacing real editorial review with automated scoring.
- Introducing model-judged evaluation as a hard requirement for every run.

## Decisions

### 1. Split shared validation from local dataset benchmarking

The evaluation system will keep named fixture sets with hand-authored expectations for portable shared validation, while real footage runs will be treated as dataset-aware benchmarking rather than universal pass/fail contracts.

Rationale:
- Shared fixtures are easier to maintain and reason about when they are repo-owned.
- Real datasets are still useful, but they should not become the project-wide baseline for everyone.

Alternatives considered:
- Snapshot the entire generated project and diff it wholesale: rejected because it is too brittle and too noisy for analyzer evolution.
- Keep private footage as the default fixture baseline: rejected because the project can be used by people who do not have that footage.

### 2. Add sequence-level checks next to segment-level checks

The harness will add expectations for rough-cut behavior such as:
- opener suitability
- adjacent repetition limits
- mode or role variety
- sequence-group counts or other assembly-shape signals

Rationale:
- Story assembly is now part of the shipped product behavior.
- Measuring only segment boundaries is no longer enough.

Alternatives considered:
- Keep story assembly unmeasured and rely on manual review: rejected because later tuning would become subjective again.

### 3. Persist dataset-aware quality summaries in benchmark artifacts

Each evaluation run will continue to attach structured quality summaries to benchmark artifacts, but the preserved summary will grow to include fixture identity, sequence-level metrics, and dataset identity so comparisons can stay scoped to repeated runs on the same footage.

Rationale:
- Runtime history without quality context is not very useful for tuning.
- This keeps evaluation results paired with the run they describe.

Alternatives considered:
- Write evaluation output only to a standalone text file: rejected because it weakens run-to-run comparison and release tracking.

### 4. Keep pass/fail limited to portable fixtures

Portable repo-owned fixtures will remain the only shared pass/fail validation contract. Real-footage benchmarking will be observational: it records metrics, attaches quality summaries, and compares against prior runs only when dataset identity matches, but it does not turn user footage into a universal regression baseline.

Rationale:
- Different users will process different footage sets.
- Benchmarking is still useful on private footage, but it should not fail simply because the dataset changed.

Alternatives considered:
- Treat every evaluated project as a failing or passing regression target: rejected because the result would depend on which footage happened to be processed.

## Risks / Trade-offs

- [Broader checks may become brittle] -> Keep shared fixture expectations high-signal and avoid overfitting to incidental ordering details.
- [Evaluation maintenance cost grows with fixture count] -> Add fixture sets deliberately by scenario, not by dumping large media corpora into the harness.
- [Sequence-level quality is partly subjective] -> Prefer bounded, testable heuristics that mirror product goals rather than pretending to measure perfect editorial quality.
- [Cross-dataset comparisons can mislead] -> Compare runtime and quality trends only when dataset identity matches.

## Migration Plan

1. Extend the fixture schema to support sequence-level expectations.
2. Replace private-footage assumptions in the shared manifest with portable repo-owned fixtures.
3. Add richer evaluation metrics and summaries.
4. Attach those summaries to benchmark artifacts and process comparisons using dataset-aware matching.
5. Keep real-dataset comparison observational and same-dataset-scoped.

## Open Questions

- Which sequence-level expectations are stable enough to assert without causing brittle tests?
- Should dataset identity rely only on media-root labels, or also on an asset-based fingerprint derived from the generated project?
