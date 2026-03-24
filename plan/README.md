# AI-Assisted Video Take Selection Plan

## Goal

Build a local-first web application that:

- scans original clips and DaVinci Resolve proxy media
- detects candidate moments within each clip
- identifies zero, one, or many "best takes" per clip
- generates short scene descriptions for each take, even for silent b-roll
- assembles selected takes into a rough story-driven timeline
- lets the editor preview and adjust that draft before moving into Resolve
- exports the selected order, source clip ranges, and trims into a Resolve-usable interchange format

## Recommended Direction

Use a split architecture:

- `React + Next.js` web app for review, scoring controls, and rough timeline preview
- `Python` analysis service for video/audio processing and AI orchestration
- proxy-first processing for speed and lower compute cost
- local models for baseline analysis, with optional cloud AI for semantic summaries and story assembly
- transcript-aware when speech exists, but not transcript-dependent

This is the right split because the browser is good at review UX, while the strongest video tooling still lives in Python and native media libraries.

## Core Product Flow

1. User creates a project and points the app at a media root.
2. The app discovers source clips and matching proxy clips.
3. The backend extracts metadata, audio, scene boundaries, representative frames, and quality signals.
4. The system proposes candidate takes with timestamps, confidence, and short descriptions, using transcript evidence when available and visual evidence when not.
5. The system ranks takes based on technical quality, semantic value, and story contribution.
6. The app assembles a draft timeline from selected takes.
7. The user previews the rough cut, reorders or trims takes, and exports a Resolve-ready timeline package.

## Recommended Stack

- Media inspection: `ffmpeg`, `ffprobe`
- Scene/shot segmentation: `PySceneDetect`
- Transcription baseline: `faster-whisper`
- Precise timestamps/diarization when needed: `WhisperX`
- Visual quality metrics: `OpenCV`
- Semantic scene descriptions and story planning: multimodal LLM via extracted keyframes + transcript
- Timeline preview: `@remotion/player`
- Waveform/region UI: `wavesurfer.js`
- Draft render/export: `ffmpeg`
- Resolve interchange export: `FCPXML` first, `EDL/CSV` fallback
- Metadata store: `Postgres` for production, `SQLite` acceptable for an MVP

## Strong Recommendation

Do not try to build a full browser NLE first.

For the first version, the app should be an AI screening and rough-cut assistant:

- ingest proxies
- propose the best take candidates
- explain why they were selected
- generate a draft sequence
- preview the sequence
- export machine-readable decisions and a Resolve-importable timeline

That gets the biggest workflow win with the least engineering risk.

## What The MVP Should Decide Well

- which segments are worth watching
- which segments are probably the strongest takes
- why each segment matters
- how selected segments could form a coherent beginning, middle, and end
- how to preserve clip order, in/out ranges, and relinkable media references for Resolve

## Documents

- `research/tooling-options.md`: evaluated tools and final recommendations
- `product/requirements.md`: scope, workflows, and acceptance criteria
- `architecture/system-design.md`: pipeline, components, and data model
- `roadmap/phases.md`: phased implementation plan
- `decisions/open-questions.md`: assumptions that must be validated early
