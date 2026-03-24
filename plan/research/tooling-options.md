# Tooling Research

## Summary

The stack should be built around proxy-first media analysis, Python-native video processing, and a React review UI.

The most practical tool mix is:

- `ffprobe` and `ffmpeg` for media metadata, frame/audio extraction, and draft renders
- `PySceneDetect` for candidate shot boundaries
- `faster-whisper` as the default local transcription engine
- `WhisperX` only when word-level alignment or speaker-aware transcripts materially improve selection quality
- a multimodal LLM for scene descriptions, take rationales, and story assembly
- `@remotion/player` plus a custom timeline UI for rough-cut preview
- `wavesurfer.js` for waveform and region interactions
- `FCPXML` export generation for Resolve import

## Tool Decisions By Concern

### 1. Media Inspection And Extraction

Recommended:

- `ffprobe` for clip metadata, stream structure, frame rate, timecode, duration
- `ffmpeg` for audio extraction, frame sampling, thumbnails, and proxy draft rendering

Why:

- these are the most standard and interoperable building blocks in the media pipeline
- `ffprobe` has machine-readable JSON/XML output
- `ffmpeg` concat demuxing is enough to generate preview cuts without building a full editing engine

### 2. Candidate Take Segmentation

Recommended:

- `PySceneDetect` for shot change detection
- silence/speech boundaries from the transcript/VAD pass
- optional max-duration splitting for long monologues or static shots

Why:

- pure scene cuts are not enough; some good takes live inside a single shot
- the combined strategy gives better candidate windows:
  - shot boundaries for visual structure
  - speech/silence boundaries for conversational beats
  - hard duration limits to avoid giant candidate ranges
- when footage is pure b-roll, the shot-boundary path becomes the primary segmentation method

### 3. Speech-To-Text

Recommended default:

- `faster-whisper`

Use when:

- you want local processing
- you need good baseline transcripts on proxy-derived audio
- you want predictable operating cost

Upgrade path:

- `WhisperX` if you need tighter word timestamps or speaker labels
- managed transcription API if you want operational simplicity over local execution

Why:

- `faster-whisper` is optimized for speed and memory efficiency
- `WhisperX` adds alignment, VAD-driven segmentation, and diarization support, but increases pipeline complexity
- transcription should be optional per segment, not assumed globally

### 3b. Footage Without Speech

Recommended:

- treat no-speech footage as a first-class workflow
- score silent regions from visual signals, pacing, motion, composition, subject visibility, and distinctiveness
- use multimodal image understanding on extracted keyframes to produce scene descriptions without relying on transcript text

Why:

- a large amount of editorial footage is b-roll, cinematic coverage, travel footage, or ambient inserts
- the system still needs to answer:
  - what happens in the shot
  - whether it is visually strong
  - whether it helps the story

Implementation note:

- use transcript features opportunistically
- never make transcript presence a prerequisite for candidate selection or story assembly

### 4. Speaker Diarization

Recommended:

- optional feature, not part of MVP-critical path
- use `WhisperX + pyannote` only when multi-speaker attribution changes editing value

Why:

- diarization is useful for interviews, podcasts, and dialogue-heavy footage
- it adds operational complexity and is not necessary for strong first-pass take selection

### 5. Semantic Scene Understanding

Recommended:

- extract representative keyframes from each candidate segment
- combine keyframes, transcript excerpt, and low-level metrics
- ask a multimodal LLM for:
  - a short description
  - whether the segment is a likely "best take"
  - why it is good or weak
  - what story role it could play
- support a local model path through `LM Studio` for privacy-sensitive and offline workflows

Why:

- "best take" is not only technical quality
- the system needs semantic judgment:
  - what happens in the shot
  - whether the moment is emotionally or narratively useful
  - whether it duplicates another segment

Important design choice:

- do not send full videos to the LLM in the first version
- send selected frames plus transcript excerpts and numeric signals
- for silent footage, send selected frames plus numeric motion/composition signals and neighboring shot context
- this is cheaper, faster, and easier to make deterministic

Recommended runtime boundary:

- define a provider adapter that can target:
  - `LM Studio` via its OpenAI-compatible local API
  - a hosted multimodal API
  - a hybrid path where local models do first-pass labeling and cloud models do final ranking only

Why:

- the project should not hardcode a single model vendor
- local models are attractive for private footage and repeated experimentation
- hosted models may still be useful for stronger narrative planning or evaluation baselines

### 6. Timeline Preview In The Browser

Recommended:

- `@remotion/player` for preview composition
- custom timeline lanes in React for takes and ordering
- `wavesurfer.js` for audio waveform and region selection

Why:

- you need composition preview, not a full editor at first
- Remotion is well suited for browser preview plus eventual MP4 rendering
- waveform regions make trims and review easier without overbuilding the timeline

What to avoid initially:

- building a full drag-heavy nonlinear editor from scratch
- trying to replicate Resolve inside the browser

### 7. Rough-Cut Rendering

Recommended:

- generate a draft preview video with `ffmpeg`
- keep the authoritative editable state as `timeline.json`

Why:

- preview renders are easy to share and verify
- JSON remains the system of record for downstream export logic

### 9. Resolve Export

Recommended:

- generate `FCPXML` as the primary interchange export for Resolve import
- generate a human-readable shot list and machine-readable `timeline.json` alongside it
- keep `EDL` as a fallback export for simple straight cuts if XML compatibility becomes an issue

Why:

- Resolve supports timeline import/export for XML-based interchange workflows according to Blackmagic documentation
- `FCPXML` can preserve clip order, source references, and in/out ranges better than a plain shot list
- `timeline.json` remains the canonical internal state for deterministic regeneration

What to avoid initially:

- relying on `.drt` as the first export target
- direct Resolve scripting as the primary integration path

Reason:

- `.drt` is a Resolve-native timeline format, but it is not the best first target for externally generated interchange
- scripting is useful later, but it is a more brittle dependency than file-based interchange

### 8. Storage And Jobs

Recommended:

- metadata DB: `Postgres`
- object/filesystem storage: local disk first, S3-compatible later
- async jobs: start simple with a single worker queue, add Redis-backed jobs once concurrency matters

Why:

- the app is analysis-heavy and asynchronous by nature
- job visibility matters more than scale on day one

## Recommended MVP Stack

Frontend:

- `Next.js`
- `TypeScript`
- `@remotion/player`
- `wavesurfer.js`

Backend:

- `Python`
- `FastAPI`
- `ffmpeg` / `ffprobe`
- `PySceneDetect`
- `faster-whisper`
- `OpenCV`

Optional AI adapters:

- multimodal LLM for descriptions, ranking rationale, and story assembly
- `LM Studio` as the preferred local model runtime for multimodal or text-only reasoning
- `WhisperX` only for projects that benefit from alignment and speaker labels
- `FCPXML` export builder for Resolve handoff

## Notes On Licensing And Product Risk

- `Remotion` is free for individuals and teams up to 3 people; larger teams need a paid license
- a cloud-only AI design increases both cost sensitivity and privacy friction
- local-first analysis is the safer default for editors working with private footage
- interchange export must be validated against real Resolve imports early because XML conform details can be version-sensitive

## Sources

- [OpenAI speech-to-text guide](https://platform.openai.com/docs/guides/speech-to-text?lang=javascript)
- [OpenAI images and vision guide](https://platform.openai.com/docs/guides/images-vision)
- [OpenAI structured outputs guide](https://platform.openai.com/docs/guides/structured-outputs?lang=javascript)
- [PySceneDetect detectors documentation](https://www.scenedetect.com/docs/latest/api/detectors.html)
- [PySceneDetect documentation index](https://www.scenedetect.com/docs/)
- [faster-whisper repository](https://github.com/SYSTRAN/faster-whisper)
- [WhisperX repository](https://github.com/m-bain/whisperX)
- [OpenAI Whisper repository](https://github.com/openai/whisper)
- [pyannote.audio package overview](https://pypi.org/project/pyannote.audio/)
- [Remotion homepage and product overview](https://www.remotion.dev/)
- [wavesurfer.js docs](https://wavesurfer.xyz/docs/)
- [wavesurfer.js regions plugin docs](https://wavesurfer.xyz/docs/modules/plugins_regions)
- [ffprobe documentation](https://ffmpeg.org/ffprobe.html)
- [FFmpeg formats documentation, including concat demuxer](https://ffmpeg.org/ffmpeg-formats.html)
- [DaVinci Resolve Editor's Guide excerpt on importing/exporting DRT and timeline interchange](https://documents.blackmagicdesign.com/UserManuals/DaVinci-Resolve-17-Editors-Guide.pdf?_v=1624410090000)
- [DaVinci Resolve manual excerpt on XML/AAF conform settings](https://documents.blackmagicdesign.com/UserManuals/DaVinci_Resolve_15_Reference_Manual.pdf)
