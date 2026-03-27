## 1. Spoken-Structure Evidence

- [ ] 1.1 Extend transcript-backed processing to derive richer spoken-structure signals beyond raw turns.
- [ ] 1.2 Define bounded speech-structure cues that cover monologue continuity and question/answer flow without requiring full diarization.
- [ ] 1.3 Preserve graceful fallback when transcript evidence is weak, missing, or unavailable.

## 2. Segmentation And Scoring

- [ ] 2.1 Integrate richer spoken-structure cues into speech-aware refinement or assembly decisions.
- [ ] 2.2 Integrate those cues into speech-oriented scoring without destabilizing transcript-free paths.
- [ ] 2.3 Add regression tests for speech-heavy fixtures that previously produced incomplete spoken beats.

## 3. Reviewability

- [ ] 3.1 Persist richer speech-structure metadata in generated project state.
- [ ] 3.2 Verify that transcript-backed and transcript-free cases remain distinguishable in review data and diagnostics.
