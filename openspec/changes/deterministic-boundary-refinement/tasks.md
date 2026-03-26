## 1. Seed Region Model

- [ ] 1.1 Add seed-region and boundary-provenance fields to `domain.py` and generated project state
- [ ] 1.2 Add configuration flags for deterministic boundary refinement and legacy-path fallback in `ai.py`
- [ ] 1.3 Update serializers so refined segments and provenance round-trip through `ProjectData`

## 2. Transcript And Audio Boundary Inputs

- [ ] 2.1 Extend the transcript adapter to expose timed transcript spans for internal analyzer use
- [ ] 2.2 Add transcript-aware boundary snapping helpers for speech-heavy clips
- [ ] 2.3 Add silence-gap and audio-transition snapping helpers using existing audio signals

## 3. Deterministic Refinement Core

- [ ] 3.1 Refactor prefilter output to emit seed regions instead of final candidate windows
- [ ] 3.2 Implement scene-boundary and duration-rule snapping for visual or transcript-light clips
- [ ] 3.3 Compute a boundary strategy label and confidence score for every refined segment
- [ ] 3.4 Feed refined segments, not raw seeds, into downstream scoring and shortlist selection

## 4. Verification

- [ ] 4.1 Add unit tests for transcript, audio, scene, and fallback boundary refinement
- [ ] 4.2 Add integration tests comparing refined output with the legacy candidate path
- [ ] 4.3 Verify deterministic fallback remains available when transcript or audio cues are missing
