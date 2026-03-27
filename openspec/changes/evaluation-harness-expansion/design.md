## Context

Roughcut Stdio already has a fixture-driven segmentation evaluation harness, but it was introduced to stabilize the segmentation overhaul rather than to evaluate the full rough-cut pipeline. Now that the analyzer includes story assembly, transcript turns, semantic calibration, and benchmark history, the existing checks are too narrow to answer higher-value questions like: did the sequence get more repetitive, did the opener get weaker, or did a change improve one fixture while regressing another?

The next evaluation pass should remain lightweight and local-first, but it needs to measure more of what the product now claims to do.

## Goals / Non-Goals

**Goals:**
- Expand evaluation beyond narrow segment-shape checks.
- Add sequence-level quality checks that reflect rough-cut behavior.
- Preserve evaluation outputs in benchmark artifacts so regressions can be compared across runs.
- Keep fixture sets explicit, repeatable, and easy to evolve.

**Non-Goals:**
- Building a cloud-hosted evaluation platform.
- Replacing real editorial review with automated scoring.
- Introducing model-judged evaluation as a hard requirement for every run.

## Decisions

### 1. Keep the harness fixture-driven and explicit

Evaluation will continue to run against named fixture sets with hand-authored expectations rather than inferred golden outputs.

Rationale:
- Explicit fixtures are easier to maintain and reason about.
- They keep the evaluation layer compatible with local-first development and CI-style runs.

Alternatives considered:
- Snapshot the entire generated project and diff it wholesale: rejected because it is too brittle and too noisy for analyzer evolution.

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

### 3. Persist quality summaries in benchmark artifacts

Each evaluation run will continue to attach structured quality summaries to benchmark artifacts, but the preserved summary will grow to include fixture identity, sequence-level metrics, and higher-level pass/fail context.

Rationale:
- Runtime history without quality context is not very useful for tuning.
- This keeps evaluation results paired with the run they describe.

Alternatives considered:
- Write evaluation output only to a standalone text file: rejected because it weakens run-to-run comparison and release tracking.

## Risks / Trade-offs

- [Broader checks may become brittle] -> Keep fixture expectations high-signal and avoid overfitting to exact IDs or incidental ordering details.
- [Evaluation maintenance cost grows with fixture count] -> Add fixture sets deliberately by scenario, not by dumping large media corpora into the harness.
- [Sequence-level quality is partly subjective] -> Prefer bounded, testable heuristics that mirror product goals rather than pretending to measure perfect editorial quality.

## Migration Plan

1. Extend the fixture schema to support sequence-level expectations.
2. Add richer evaluation metrics and summaries.
3. Attach those summaries to benchmark artifacts and process comparisons.
4. Add at least one broader fixture set beyond the current media-light baseline.

## Open Questions

- Which sequence-level expectations are stable enough to assert without causing brittle tests?
- Should release comparisons use named baseline runs or only compare against the latest prior benchmark?
