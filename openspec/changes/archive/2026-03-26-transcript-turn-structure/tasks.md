## 1. Transcript Modeling

- [x] 1.1 Add turn-level transcript structures derived from timed transcript spans.
- [x] 1.2 Persist turn-aware transcript metadata in generated project state where it affects segmentation or review.

## 2. Analyzer Logic

- [x] 2.1 Update deterministic refinement to snap or extend speech segments around turn boundaries where available.
- [x] 2.2 Update merge and split logic to use turn continuity and turn breaks for speech-heavy footage.
- [x] 2.3 Update scoring and analysis-mode evidence so turn completeness can influence spoken-segment quality.

## 3. Validation

- [x] 3.1 Add analyzer tests for question/answer flow, continuous monologue turns, and turn-break splitting.
- [x] 3.2 Run `python3 -m unittest discover services/analyzer/tests -v` and the segmentation evaluation harness.

## 4. Docs

- [x] 4.1 Update [docs/analyzer-pipeline.md](/Users/florin/Projects/personal/roughcut-stdio/docs/analyzer-pipeline.md) and [docs/ROADMAP.md](/Users/florin/Projects/personal/roughcut-stdio/docs/ROADMAP.md) to reflect turn-aware transcript analysis.
