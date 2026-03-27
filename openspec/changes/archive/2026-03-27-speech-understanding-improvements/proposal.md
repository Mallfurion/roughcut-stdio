## Why

Transcript-backed analysis and transcript-turn structure improved speech-heavy footage, but the system still models spoken content only partially. Dialogue, question-and-answer flow, and monologue continuity still expose some of the biggest remaining quality gaps in the analyzer.

## What Changes

- Improve how transcript-backed analysis models spoken beats beyond raw turn boundaries.
- Strengthen segmentation and scoring for question/answer continuity, monologue completeness, and other speech-heavy structures.
- Persist clearer speech-structure context in generated state so spoken-beat decisions remain inspectable.
- Keep transcript-free and silent-footage workflows first-class while improving speech-heavy material when transcript evidence is available.

## Capabilities

### New Capabilities

### Modified Capabilities
- `transcript-backed-analysis`: Transcript-backed processing requirements expand from span and turn extraction into richer spoken-structure modeling.
- `context-complete-segmentation`: Speech-aware refinement and assembly requirements expand to better preserve complete spoken beats, not just turn-aligned segments.
- `ai-segment-understanding`: Persisted understanding and evidence requirements expand to distinguish richer speech-structure context when it is available.

## Impact

- `services/analyzer/app/analysis.py`
- `services/analyzer/app/scoring.py`
- `services/analyzer/app/domain.py`
- transcript span and turn derivation logic
- generated segment evidence and review metadata for speech-heavy material
