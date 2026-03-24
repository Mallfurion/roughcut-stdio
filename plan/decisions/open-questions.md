# Open Questions And Assumptions

## Current Assumptions

- the app runs locally as a web app against local media folders
- DaVinci Resolve proxy media is available and preferred for analysis
- the user wants AI assistance, not autonomous final editing
- the first target workflow is footage review, rough-cut creation, and Resolve handoff

## Questions To Resolve Early

### Media Structure

- Are proxy filenames always traceable to source filenames?
- Do projects contain multicam, synced audio, or mostly single-file clips?
- Do clips usually contain dialogue, ambient footage, silent b-roll, or a mix?

### Editorial Intent

- Is the main goal social montage, documentary structure, vlog narrative, interview edit, or something else?
- Should the system preserve chronology by default?
- How aggressive should the system be about rejecting weak clips entirely?

### Output Requirements

- Is Resolve import required on day one via FCPXML, or is a fallback EDL acceptable in edge cases?
- Do you want one best timeline, or multiple timeline variants?
- Should the system export only selected takes, or also rejected-but-interesting alternates?

### AI Operating Model

- Must all analysis stay local?
- Is cloud AI acceptable for descriptions and story planning?
- Do you need multilingual transcription from the start?

## Recommended Product Decisions

- Make cloud semantics optional, not mandatory.
- Keep diarization off by default.
- Preserve chronology by default, especially for silent montage workflows, with an optional "cinematic reorder" mode later.
- Support multiple suggested timelines after the first ranking model is stable.
- Prioritize FCPXML as the first Resolve handoff format and validate it against real projects early.

## Risks Worth Prototyping First

- proxy/source mismatch edge cases
- poor transcripts on noisy footage
- silent b-roll over-selection with weak descriptions
- over-selection of repetitive b-roll
- story plans that sound coherent in text but feel weak in sequence
- Resolve import failures caused by path, reel-name, frame-rate, or timecode mismatch

## Immediate Next Prototype

If implementation starts now, the first prototype should only answer:

1. Can we map source clips to proxies reliably?
2. Can we generate useful candidate segments from proxies?
3. Can we produce descriptions that make an editor open the right moments first?
