## Why

Transcript support is now live, but the analyzer still treats transcript evidence mostly as span text. That is enough for excerpts, but not enough for conversational completeness, turn grouping, or turn-aware split and merge decisions.

## What Changes

- Introduce turn-level transcript structure as a first-class analyzer input.
- Use turn boundaries to improve speech-heavy segmentation, merge/split logic, and speech scoring.
- Preserve deterministic fallback when turn structure is unavailable.

## Capabilities

### Modified Capabilities
- `transcript-backed-analysis`: Transcript support must expose turn-aware structures, not only freeform excerpts.
- `context-complete-segmentation`: Merge and split logic must use transcript-turn structure when available.
- `deterministic-screening`: Speech-oriented scoring must incorporate turn completeness and continuity signals.

## Impact

- Transcript provider and transcript data modeling
- Analyzer segmentation and scoring
- Generated review metadata for speech-heavy segments
