## Why

The current analyzer detects speech-like audio but does not use a live transcript provider in production runs, so spoken clips can still be ranked as silent visual coverage. This is now blocking an important product promise: speech-heavy footage should surface as spoken narrative material when local transcript support is available and should still degrade gracefully when it is not.

## What Changes

- Add production transcript support to the analyzer process path so local runs can extract timed transcript spans and transcript excerpts when a supported local backend is installed.
- Add selective transcript probing so weak or ambiguous speech assets can be checked with a short transcript probe before the analyzer commits to a full local transcription pass.
- Add transcript runtime controls and runtime reporting so the process step and desktop app can show whether transcript extraction is enabled, available, disabled, cached, or unavailable.
- Add speech-aware fallback behavior when transcript extraction is missing or partial so spoken clips are not forced into pure visual scoring solely because transcript text is absent.
- Feed transcript-backed excerpts into deterministic boundary refinement, candidate scoring, AI evidence building, review metadata, and generated project state.
- Preserve deterministic fallback, source-only processing, silent-footage behavior, and Resolve export integrity when transcript support is unavailable.

## Capabilities

### New Capabilities
- `transcript-backed-analysis`: Extract timed transcript spans during processing and use them as first-class evidence for speech-aware candidate analysis.

### Modified Capabilities
- `deterministic-screening`: Candidate refinement and scoring must use transcript-backed speech evidence when available and speech-aware fallback behavior when transcript support is unavailable or partial.
- `ai-segment-understanding`: Segment evidence and understanding records must include transcript excerpts when present and explicit speech-related fallback context when transcript text is missing.
- `processing-workflow`: Process runs must report transcript runtime status and transcript-related fallback behavior in generated process artifacts.
- `desktop-workflow`: Desktop settings and runtime status must expose transcript support controls when they affect local process behavior.

## Impact

- Python analyzer modules under `services/analyzer/app/`
- Process entrypoint and generated process artifacts under `services/analyzer/scripts/` and `generated/`
- Desktop settings, process-state reporting, and `.env` persistence in `apps/desktop/`
- Local transcript dependency management, likely centered on `faster-whisper`, with explicit fallback behavior when not installed
