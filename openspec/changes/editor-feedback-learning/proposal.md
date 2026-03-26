## Why

The desktop review surface now explains how segments were formed, but the analyzer still does not learn from what the editor accepts, rejects, trims, or rearranges. Once sequence-level behavior exists, that review activity becomes a high-value signal.

## What Changes

- Capture editor feedback events from review and timeline adjustment workflows.
- Persist feedback in a local-first form that can inform later analyzer heuristics.
- Introduce bounded heuristic adaptation based on repeated editor choices without removing explicit editor control.

## Capabilities

### New Capabilities
- `editor-feedback-learning`: Capture and reuse editor actions as analyzer feedback.

### Modified Capabilities
- `review-workspace`: Review must expose actionable editor decisions as persisted feedback events.
- `desktop-workflow`: Desktop interaction flow must support local feedback capture without blocking current editing workflows.

## Impact

- Desktop review actions and persistence
- Generated or local project-side feedback records
- Future analyzer ranking and assembly heuristics
