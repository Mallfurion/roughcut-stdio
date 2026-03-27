## Why

Cross-asset story assembly is now shipped, but it is still a first-pass heuristic layer. The next improvement is not to find more clips, but to assemble better sequences that balance local clip strength with project-level pacing, variation, and story intent.

## What Changes

- Strengthen project-level story assembly beyond the current basic continuity and alternation heuristics.
- Improve how the analyzer chooses openers, release beats, adjacent variety, and story-prompt fit across the selected sequence.
- Preserve richer sequence rationale and assembly diagnostics in generated state so tuning remains inspectable.
- Keep the current review and export behavior intact while improving the quality of the automatically assembled rough cut.

## Capabilities

### New Capabilities

### Modified Capabilities
- `story-assembly`: Story assembly requirements expand from basic cross-asset sequence logic to stronger pacing, repetition control, and prompt-aware sequence construction.
- `processing-workflow`: Generated process artifacts must preserve richer sequence rationale and assembly diagnostics for the final timeline.

## Impact

- `services/analyzer/app/analysis.py`
- generated timeline state in `project.json`
- process summaries and assembly diagnostics
- sequence rationale and timeline selection metadata
