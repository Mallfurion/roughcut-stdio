## 1. Seed Region Model

- [x] 1.1 Add seed-region and boundary-provenance fields to `domain.py` and generated project state
- [x] 1.2 Add configuration flags for deterministic boundary refinement and legacy-path fallback in `ai.py`
- [x] 1.3 Update serializers so refined segments and provenance round-trip through `ProjectData`

## 2. Transcript And Audio Boundary Inputs

- [x] 2.1 Extend the transcript adapter to expose timed transcript spans for internal analyzer use
- [x] 2.2 Add transcript-aware boundary snapping helpers for speech-heavy clips
- [x] 2.3 Add silence-gap and audio-transition snapping helpers using existing audio signals

## 3. Deterministic Refinement Core

- [x] 3.1 Refactor prefilter output to emit seed regions instead of final candidate windows
- [x] 3.2 Implement scene-boundary and duration-rule snapping for visual or transcript-light clips
- [x] 3.3 Compute a boundary strategy label and confidence score for every refined segment
- [x] 3.4 Feed refined segments, not raw seeds, into downstream scoring and shortlist selection

## 4. Verification

- [x] 4.1 Add unit tests for transcript, audio, scene, and fallback boundary refinement
- [x] 4.2 Add integration tests comparing refined output with the legacy candidate path
- [x] 4.3 Verify deterministic fallback remains available when transcript or audio cues are missing
