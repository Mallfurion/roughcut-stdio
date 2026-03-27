# Analyzer Pipeline

This document describes what the analyzer does when `npm run process` is run.

The entry point is [process.sh](/Users/florin/Projects/personal/roughcut-stdio/scripts/process.sh). It loads `.env` and `.env.local`, invokes `services/analyzer/scripts/scan_media_root.py`, writes the result to `generated/project.json`, and persists latest-run logs and benchmark artifacts under `generated/`.

## Overview

The pipeline runs in four phases:

1. **Media discovery** - find all video files, match sources to proxies, build asset records
2. **Per-asset analysis** - extract signals, build seed regions, refine and assemble candidate segments, score them, and optionally analyze them with local AI
3. **Take selection** - score all candidates and pick the best segment or segments per asset
4. **Timeline assembly** - order selected takes into a rough cut and write the output

Each phase narrows the candidate pool so expensive work only happens on stronger segments.

## Phase 1: Media Discovery

**Code:** `services/analyzer/app/media.py`

The analyzer walks the media root recursively and collects supported video files. For each file it probes metadata such as duration, frame rate, dimensions, timecode, and audio-stream presence.

Files are classified as `source` or `proxy` from path and filename hints. Sources are matched to the best proxy candidate by name, duration, and frame-rate similarity. If no proxy exists, the source file is still processed directly.

Each matched pair becomes an **Asset**. Assets record:

- source path and proxy path
- duration, frame rate, dimensions
- `has_speech` / audio-stream availability
- `interchange_reel_name` for Resolve handoff

## Phase 2: Per-Asset Analysis

**Code:** `services/analyzer/app/analysis.py`, `prefilter.py`, `ai.py`

This is where most of the work happens.

### Step 2.1 - Scene Detection And Seed Inputs

The analyzer runs PySceneDetect when available to find content-based boundaries. Those ranges are only one input to segmentation, not the final segments.

If scene detection is unavailable or weak, the analyzer still produces fallback seed inputs from lightweight duration-based heuristics.

**Output:** scene boundaries and fallback seed inputs.

### Step 2.2 - Frame Signal Sampling

The analyzer samples grayscale frames across the asset with ffmpeg and computes low-cost visual signals:

- sharpness
- contrast
- brightness
- motion energy
- distinctiveness
- center focus

These signals are combined into a frame score that estimates how visually promising a moment is.

If frame extraction fails, deterministic fallback values are generated so the pipeline can continue.

**Output:** `FrameSignal` records on sampled timestamps.

### Step 2.3 - Audio Signal Sampling

For assets with audio, the analyzer runs:

- `silencedetect` to find silence intervals
- `astats` to measure RMS energy over short windows

Those measurements are aligned to the same sampling grid as frame signals and stored as `AudioSignal` records. Missing audio or extraction failures fall back to silent defaults.

**Output:** `AudioSignal` records on sampled timestamps.

### Step 2.4 - Transcript Runtime Selection

Before segmentation begins, the analyzer resolves transcript support from runtime config:

- `TIMELINE_TRANSCRIPT_PROVIDER=auto` tries the local `faster-whisper` backend when installed
- `TIMELINE_TRANSCRIPT_PROVIDER=faster-whisper` requests that backend explicitly
- `TIMELINE_TRANSCRIPT_PROVIDER=disabled` skips transcript extraction entirely

The run records transcript runtime status in `project.analysis_summary`, including configured provider, effective provider, status, model size, targeted/skipped/probed transcript counts, transcribed asset counts, transcript failures, transcript-bearing segments, and speech-fallback segment counts.

When AI cache is enabled and `artifacts_root` is available, transcript spans are also cached on disk under the analysis artifacts so repeated `npm run process` calls can reuse prior transcription results.

Before a full transcript pass begins, the analyzer can selectively target assets:

- clear speech assets may go straight to full transcription
- weak assets may be skipped
- borderline assets may receive a short transcript probe over selected high-energy windows first

Only assets whose probe returns real transcript text are promoted into the full transcript pass.

If transcript support is unavailable, processing continues and spoken clips can still enter speech-aware scoring through deterministic fallback.

When transcript spans are available, the analyzer also derives lightweight **transcript turns** by grouping adjacent spans with short internal gaps. These turns become first-class structure for downstream speech segmentation and scoring.

### Step 2.5 - Seed Region Building

The analyzer combines low-cost structure into **seed regions**. Inputs include:

- scene-derived ranges
- visually strong peaks from frame signals
- audio-energy peaks when speech or loud events are present

Seed regions are intermediate structures. They are not yet the final candidate segments used for scoring or review.

**Output:** deduplicated seed regions.

### Step 2.6 - Deterministic Boundary Refinement

Deterministic seed-region refinement is enabled by default. Each seed region is refined into a bounded segment before scoring.

Depending on available evidence, the analyzer may:

- snap to transcript turn edges
- snap to transcript span edges
- snap to audio transitions or silence gaps
- align to nearby scene boundaries
- apply bounded duration heuristics when stronger cues are unavailable

If refinement is enabled but a seed region has weak structure, the analyzer still produces a deterministic bounded result. If `TIMELINE_SEGMENT_LEGACY_FALLBACK=true`, legacy fallback behavior remains available when refinement yields nothing usable.

Each refined region records provenance such as boundary strategy, confidence, source seed lineage, and aligned transcript-turn metadata when available.

**Output:** deterministically refined regions.

### Step 2.7 - Narrative Unit Assembly

After refinement, the analyzer can merge or split regions before they become final candidate segments.

- **Merge:** adjacent refined regions from the same asset may be combined when transcript continuity, question/answer flow, or short continuous action suggests they form one beat
- **Split:** a refined region may be divided when it clearly contains multiple ideas, a strong transcript turn break, or a scene divider

Assembly lineage is preserved so review can explain how a final segment was formed, including whether a merge came from turn continuity or whether a split was triggered by a turn break.

**Output:** final candidate ranges used for scoring and review.

### Step 2.8 - Candidate Segment Creation

For each final candidate range, the analyzer creates a `CandidateSegment`. This includes:

- transcript excerpt lookup for the time range
- `analysis_mode` selection (`speech` or `visual`)
- speech-aware fallback classification when transcript text is missing but speech signals remain strong
- aggregated metrics snapshot from frame and audio signals
- derived quality metrics such as `hook_strength`, `story_alignment`, `duration_fit`, `audio_energy`, `speech_ratio`, and `turn_completeness`
- initial prefilter decision and segmentation provenance

When transcript turns are present, each speech-heavy segment also records:

- which turns it overlaps
- whether it is turn-aligned, mostly complete, or partial
- a `turn_completeness` score used later during speech scoring

**Output:** `CandidateSegment` records with quality metrics attached.

### Step 2.9 - Optional Semantic Boundary Validation

Semantic boundary validation is enabled by default, but only ambiguous segments are eligible for a boundary-validation pass.

Eligibility is based on boundary confidence, turn completeness, and assembly strategy. Validation is bounded by:

- `TIMELINE_SEGMENT_SEMANTIC_AMBIGUITY_THRESHOLD`
- `TIMELINE_SEGMENT_SEMANTIC_FLOOR_THRESHOLD`
- `TIMELINE_SEGMENT_SEMANTIC_MIN_TARGETS`
- `TIMELINE_SEGMENT_SEMANTIC_VALIDATION_BUDGET_PCT`
- `TIMELINE_SEGMENT_SEMANTIC_VALIDATION_MAX_SEGMENTS`
- `TIMELINE_SEGMENT_SEMANTIC_MAX_ADJUSTMENT_SEC`

If no segment crosses the primary threshold, the analyzer may still validate a very small floor-targeted subset of the most ambiguous segments so the semantic stage does not stay permanently dormant.

Disabled, unavailable, over-budget, or not-eligible validation keeps deterministic output unchanged and persists the reason in review metadata, including whether a validated segment was threshold-targeted or floor-targeted.

**Output:** validated or skipped segments with persisted validation status.

### Step 2.10 - Shortlist Selection

In `fast` mode, only the top `max_segments_per_asset` candidates by prefilter score proceed to the expensive evidence and AI stages. The rest are marked `filtered_before_vlm=true` and receive deterministic understanding instead of a VLM call.

In `full` mode, all candidates proceed.

**Output:** shortlist IDs for evidence building and downstream analysis.

### Step 2.11 - Evidence Building

For each shortlisted segment, the analyzer extracts keyframes and prepares an evidence bundle.

- short segments usually get 3 keyframes
- longer segments usually get 4 keyframes
- keyframes are stitched into a contact sheet when possible
- neighboring time context is recorded for downstream analysis
- transcript status and speech-mode source are recorded for review and prompt building
- transcript turn count, turn ranges, and turn completeness are attached for review and downstream debugging

**Output:** `SegmentEvidence` records with keyframe paths, contact sheet path, transcript evidence, transcript status, speech-mode source, transcript-turn metadata, and metrics.

### Step 2.12 - CLIP Semantic Scoring

If `TIMELINE_AI_CLIP_ENABLED=true` and `open-clip-torch` is available, the analyzer runs CLIP scoring on shortlisted contact sheets.

CLIP scores:

- contribute to downstream scoring
- can gate weak segments before VLM analysis using `TIMELINE_AI_CLIP_MIN_SCORE`
- reuse cached embeddings later during deduplication

If CLIP is unavailable, the pipeline continues without failing.

**Output:** `clip_score` and CLIP-gating flags on `PrefilterDecision`.

### Step 2.13 - Segment Deduplication

After CLIP scoring, the analyzer removes near-duplicate segments across assets.

- when CLIP is available, cosine similarity on cached embeddings is used
- otherwise, histogram-based similarity is used with `TIMELINE_DEDUP_THRESHOLD`

Deduplicated segments remain in `generated/project.json` with their elimination reason recorded, but they do not receive VLM targeting.

**Output:** updated `PrefilterDecision` records with dedup flags and group IDs.

### Step 2.14 - VLM Target Selection

After deduplication, the analyzer selects which shortlisted segments receive VLM analysis using a staged gate:

1. exclude deduplicated segments
2. exclude CLIP-gated segments when CLIP is enabled
3. apply per-asset limit and optional global VLM budget cap

Segments excluded here still receive deterministic understanding.

**Output:** VLM target IDs plus budget-cap metadata.

### Step 2.15 - AI Analysis

Each segment in the VLM target set is analyzed by one of:

- `deterministic`
- `lmstudio`
- `mlx-vlm-local`

The analyzer produces `SegmentUnderstanding` records with summary, rationale, story roles, shot type, camera motion, mood, confidence, and keep label. Cached results are reused when inputs match.

When transcript excerpts are missing, prompts receive explicit transcript-status text instead of an empty placeholder so speech-aware fallback segments remain inspectable.

## Phase 3: Take Selection

**Code:** `services/analyzer/app/scoring.py`, `analysis.py`

After all segments are analyzed, scoring produces:

- technical score
- semantic score
- story score

These roll into a total score used to pick the strongest one or two takes per asset. The best scorer becomes the primary take; a second take may be included when the asset is long enough and the score gap is small.

## Phase 4: Timeline Assembly

**Code:** `services/analyzer/app/analysis.py`

Best takes are assembled into a rough timeline with bounded cross-asset story assembly heuristics rather than pure asset-order sorting. The current sequence pass works on already-selected per-asset winners and prefers a cleaner multi-asset flow by considering:

- opener strength
- speech/visual alternation
- role variety across adjacent beats
- a cleaner visual or low-friction release beat when the project is mixed

Each selected take becomes a `TimelineItem` with trims, a label, notes, source references, and story-assembly metadata such as:

- `sequence_group`
- `sequence_role`
- `sequence_score`
- `sequence_rationale`

Timeline trims now preserve more of refined segment length instead of flattening every visual clip to five seconds. Speech beats may run up to `7.5s`; trusted refined visual beats may run up to `6.5s`, and merged visual beats up to `7.0s`. Legacy/fallback visual windows still cap at `5.0s`.

The analyzer also generates a short story summary for the timeline composition and records story-assembly counters in `project.analysis_summary`, including transition count, mode alternations, and sequence-group count.

## Final Output

The complete result is serialized to `generated/project.json`. It includes:

- project metadata
- assets
- candidate segments
- prefilter decisions
- AI understanding
- review-facing provenance
- take recommendations
- assembled timeline

The desktop app reads this file to display recommendations, segment provenance, and timeline state. The export command reads it to produce `generated/timeline.fcpxml` for Resolve.

The process step also writes:

- `generated/process.log`
- `generated/process-summary.txt`
- `generated/process-output.txt`
- `generated/benchmarks/history.jsonl`
- `generated/benchmarks/<run-id>/benchmark.json`
- `generated/benchmarks/<run-id>/process-output.txt`

## Segmentation Evaluation Workflow

The repository also has a fixture-driven segmentation evaluation workflow layered on top of the normal process run.

**Command:** `npm run evaluate:segmentation -- --fixture-set <name> [--media-dir <path>]`

That workflow:

1. runs `npm run process` unless `--skip-process` is provided
2. loads a stable fixture manifest from [fixtures/segmentation-evaluation.json](/Users/florin/Projects/personal/roughcut-stdio/fixtures/segmentation-evaluation.json)
3. evaluates the latest `generated/project.json` against the selected fixture set
4. writes a human-readable summary to `generated/segmentation-evaluation-summary.txt`
5. attaches the full evaluation result to the latest benchmark run as `generated/benchmarks/<run-id>/segmentation-evaluation.json`

The latest `benchmark.json` and `history.jsonl` entry are also updated with a summary of the quality-evaluation result, so segmentation-quality checks travel with the existing benchmark artifacts.

## What Gets Filtered And When

The pipeline filters progressively:

| Stage | What is filtered |
| --- | --- |
| Seed-region dedup | overlapping low-cost seed regions are collapsed before scoring |
| Prefilter shortlist | low-scoring segments do not reach the evidence and VLM stages in `fast` mode |
| Semantic validation | only ambiguous segments are eligible, and only within runtime limits |
| CLIP gate | weak semantic matches are excluded from VLM targeting when CLIP is enabled |
| Deduplication | near-duplicate segments are collapsed to one keeper |
| VLM budget cap | remaining eligible segments can still be excluded by budget limits |
| Take selection | low-scoring segments are not recommended unless they are the best available fallback for an asset |

Filtered segments remain in `generated/project.json` with their review state and elimination reasons recorded.

## Configuration

The main behavior switches are:

| Variable | Default | Effect |
| --- | --- | --- |
| `TIMELINE_MEDIA_DIR` | `./media` | Root directory to scan for video files |
| `TIMELINE_AI_PROVIDER` | `deterministic` | AI provider: `deterministic`, `lmstudio`, `mlx-vlm-local` |
| `TIMELINE_AI_MODE` | `fast` | Limits VLM targets in fast mode |
| `TIMELINE_AI_MAX_SEGMENTS_PER_ASSET` | provider-dependent | Per-asset shortlist cap for expensive AI work |
| `TIMELINE_AI_AUDIO_ENABLED` | `true` | Disable to skip audio extraction and use silent fallback |
| `TIMELINE_TRANSCRIPT_PROVIDER` | `auto` | Transcript backend selection (`auto`, `disabled`, `faster-whisper`) |
| `TIMELINE_TRANSCRIPT_MODEL_SIZE` | `small` | Local `faster-whisper` model size |
| `TIMELINE_AI_CLIP_ENABLED` | `true` | Enable CLIP scoring and CLIP-based dedup |
| `TIMELINE_AI_CLIP_MIN_SCORE` | `0.35` | CLIP gate threshold for VLM targeting |
| `TIMELINE_AI_VLM_BUDGET_PCT` | `100` | Percent of shortlisted segments that may reach VLM analysis |
| `TIMELINE_SEGMENT_BOUNDARY_REFINEMENT` | `true` | Enable deterministic seed refinement before scoring |
| `TIMELINE_SEGMENT_LEGACY_FALLBACK` | `true` | Keep legacy fallback available if refinement yields nothing |
| `TIMELINE_SEGMENT_SEMANTIC_VALIDATION` | `true` | Enable semantic boundary validation for ambiguous segments |
| `TIMELINE_SEGMENT_SEMANTIC_AMBIGUITY_THRESHOLD` | `0.6` | Minimum ambiguity needed to be validation-eligible |
| `TIMELINE_SEGMENT_SEMANTIC_VALIDATION_BUDGET_PCT` | `100` | Percent of eligible ambiguous segments that may be validated |
| `TIMELINE_SEGMENT_SEMANTIC_VALIDATION_MAX_SEGMENTS` | `2` | Hard cap on validated segments per run |
| `TIMELINE_SEGMENT_SEMANTIC_MAX_ADJUSTMENT_SEC` | `1.5` | Max boundary change applied from semantic validation |

For the broader environment reference, see [configuration.md](/Users/florin/Projects/personal/roughcut-stdio/docs/configuration.md).
