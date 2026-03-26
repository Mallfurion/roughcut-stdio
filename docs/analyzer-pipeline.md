# Analyzer Pipeline

This document describes what the analyzer does when `npm run process` is run, step by step.

The entry point is `scripts/process.sh`. It sets up the environment, invokes `services/analyzer/scripts/scan_media_root.py`, writes the result to `generated/project.json`, then persists latest-run logs and benchmark artifacts under `generated/`.

---

## Overview

The pipeline runs in four phases:

1. **Media discovery** — find all video files, match sources to proxies, build asset records
2. **Per-asset analysis** — for each asset, extract frame and audio signals, build candidate segments, score them, and optionally analyze them with a vision model
3. **Take selection** — score all candidates, pick the best segment or segments per asset
4. **Timeline assembly** — order selected takes into a rough cut and write the output

Each phase narrows the candidate pool. The goal is to spend compute only where it matters.

---

## Phase 1: Media Discovery

**Code:** `services/analyzer/app/media.py`

The analyzer walks the media root directory recursively and collects all video files (`.mp4`, `.mov`, `.mxf`, `.m4v`, `.avi`, `.mkv`, `.webm`).

For each file it:

- Probes metadata using ffprobe or exiftool: duration, frame rate, dimensions, timecode, audio stream presence
- Classifies the file as `source` or `proxy` based on folder name and filename markers (e.g. a path containing `proxy` or `proxies`)

Once all files are collected, the analyzer pairs sources with proxies. Each source clip is matched to its best proxy candidate by scoring name similarity, duration delta, and frame rate delta. If no proxy exists, the source file is used directly. This produces a list of matched pairs.

Each matched pair becomes an **Asset** — the canonical unit of media in the project. An asset records:

- source path and proxy path
- duration, frame rate, dimensions
- `has_speech` — whether the file has an audio stream
- `interchange_reel_name` — the source filename stem, used for Resolve handoff

---

## Phase 2: Per-Asset Analysis

**Code:** `services/analyzer/app/analysis.py`, `prefilter.py`, `ai.py`

This is where most of the work happens. Each asset is processed independently through a sequence of steps.

### Step 2.1 — Scene Detection

The analyzer runs PySceneDetect on the asset to find content-based cut boundaries. These boundaries produce an initial list of candidate time ranges.

If PySceneDetect is unavailable or the clip is short, a fallback kicks in: the duration is divided into overlapping fixed windows of approximately 5.5 seconds each.

**Output:** a list of `(start_sec, end_sec)` ranges.

### Step 2.2 — Frame Signal Sampling

The analyzer extracts 4 to 10 grayscale frames from the asset using ffmpeg, spaced evenly across the duration. For each frame it computes:

- **Sharpness** — gradient magnitude in horizontal and vertical directions
- **Contrast** — standard deviation of pixel values
- **Brightness** — mean pixel value
- **Motion energy** — pixel-level difference from the previous frame
- **Distinctiveness** — also derived from frame-to-frame difference; measures how unlike this frame is from its neighbor
- **Center focus** — contrast in the center region of the frame only

These six signals are combined into a single **frame score** using fixed weights. The score is an estimate of how visually interesting a given moment in the clip is.

If ffmpeg frame extraction fails for any frame, a deterministic fallback computes synthetic but stable signal values from a hash of the asset identifier and timestamp.

**Output:** a list of `FrameSignal` records, one per sampled timestamp.

### Step 2.3 — Audio Signal Sampling

For assets with an audio stream, the analyzer runs two additional ffmpeg passes over the full audio track, aligned to the same timestamp grid as frame sampling.

**Pass 1** — `silencedetect` marks time intervals where the audio falls below −35 dB for at least 0.3 seconds. The output is a list of `(start_sec, end_sec)` silence intervals.

**Pass 2** — `astats` with short windows computes RMS amplitude for each chunk across the asset. Each chunk's amplitude (linear, [0, 1]) is recorded with its timestamp.

These two outputs are combined per sampling timestamp: the RMS values within the window around each timestamp are averaged to produce `rms_energy`, and the fraction of windows not classified as silent produces `is_silent`. Each result is stored as an `AudioSignal` record.

If the asset has no audio stream, or if ffmpeg audio extraction fails, all `AudioSignal` records fall back to `rms_energy=0.0`, `is_silent=True` — preserving exact scoring parity with silent-footage workflows.

**Output:** a list of `AudioSignal` records, one per sampled timestamp.

### Step 2.4 — Prefilter Segment Building

The frame signals are used to find the most promising time windows in the clip. The top-scoring frames are identified, and a window of approximately `duration / 8` seconds (clamped between 2.5 and 5.5 seconds) is built around each peak.

Audio energy peaks — timestamps where `rms_energy` is above a minimum threshold and the window is not classified as silent — are also used as boundary hints, using the same peak-window logic as visual peaks. This ensures speech-heavy or audio-energetic moments have their own candidate windows even if visual signal there is weak.

All windows (scene boundary ranges, visual peak windows, audio peak windows) are merged, and near-duplicate ranges (more than 90% overlap) are removed.

In **fast mode**, two visual and two audio peak windows are generated per asset. In **full mode**, three of each.

**Output:** a deduplicated list of `(start_sec, end_sec)` candidate ranges.

### Step 2.5 — Candidate Segment Creation

For each candidate range, the analyzer creates a `CandidateSegment` record. This involves:

- Extracting any transcript excerpt that overlaps the time range (if speech is present and a transcript provider is configured)
- Setting `analysis_mode` to `speech` if a transcript excerpt was found, otherwise `visual`
- Aggregating the frame signals that fall within the range to produce a **metrics snapshot**: sharpness, stability, visual novelty, subject clarity, motion energy, brightness, contrast, prefilter score, `audio_energy`, and `speech_ratio`
- Computing derived quality metrics from the snapshot: `hook_strength`, `story_alignment`, `duration_fit`, `audio_energy`, and `speech_ratio`

`audio_energy` is the normalized mean RMS energy for the segment's time window. `speech_ratio` is the fraction of the window that is not classified as silent. Both default to `0.0` for assets without an audio stream.

Each segment also receives a `PrefilterDecision` that records its prefilter score, whether it made the shortlist, and whether it was filtered before the VLM stage.

**Output:** a `CandidateSegment` for each range, with quality metrics attached.

### Step 2.6 — Shortlist Selection

In **fast mode**, only the top `max_segments_per_asset` candidates by prefilter score proceed to the next stages. The rest are marked `filtered_before_vlm=true` and receive a deterministic understanding instead of a VLM call.

In **full mode**, all candidates proceed.

**Output:** a set of segment IDs designated as the shortlist for evidence building and downstream analysis.

### Step 2.7 — Evidence Building

For each shortlisted segment, the analyzer extracts keyframes and prepares an evidence bundle.

- 3 keyframes are extracted for segments under 8 seconds; 4 for longer segments
- Keyframes are evenly spaced within the segment's time range
- If more than one keyframe is extracted, they are stitched horizontally into a **contact sheet** using ffmpeg
- The contact sheet (or the first keyframe if stitching is unavailable) becomes the primary visual input for downstream analysis
- The evidence bundle also records the segment's context window: the start of the preceding segment and the end of the following segment, giving context for analysis

**Output:** a `SegmentEvidence` record per shortlisted segment, including keyframe paths, contact sheet path, transcript, and metrics.

### Step 2.8 — CLIP Semantic Scoring

If `TIMELINE_AI_CLIP_ENABLED=true` and the `open-clip-torch` library is installed, the analyzer runs CLIP inference on each shortlisted segment's contact sheet to measure semantic alignment with editorial quality criteria.

The scoring uses a fixed set of positive prompts (e.g., "cinematic shot with clear subject") and negative prompts (e.g., "blurry or out of focus footage") to produce a `clip_score` in [0, 1] per segment. Segments scoring below `TIMELINE_AI_CLIP_MIN_SCORE` (default 0.35) are marked as `clip_gated=true` and excluded from VLM targeting; they receive deterministic understanding instead.

The CLIP score is also incorporated into the final scoring calculation as a semantic input when available.

If `open-clip-torch` is not installed or an error occurs during model loading, CLIP scoring is silently disabled and the pipeline continues without interruption.

**Output:** `clip_score` added to prefilter metrics snapshot; `clip_gated` flag set on `PrefilterDecision` for segments below threshold.

### Step 2.9 — Segment Deduplication (CLIP or Histogram)

After CLIP scoring completes, the analyzer removes near-duplicate segments across all assets using semantic similarity.

If `TIMELINE_AI_CLIP_ENABLED=true` and CLIP scoring succeeded, the deduplication uses CLIP embeddings:
1. Extracts CLIP embeddings for each shortlisted segment (reusing embeddings cached during scoring)
2. Computes cosine similarity between all segment pairs
3. Groups segments with similarity >= 0.95 into clusters
4. Retains the highest-scoring segment in each group (by composite score: `(prefilter_score + clip_score) / 2.0`)
5. Marks remaining segments in the group as `deduplicated=true` and assigns `dedup_group_id`

If CLIP is disabled or unavailable, histogram-based deduplication is used instead:
1. Computes 256-bin grayscale histograms from sampled frame signals
2. Compares histograms using histogram intersection
3. Groups segments whose similarity exceeds `TIMELINE_DEDUP_THRESHOLD` (default: 0.85)
4. Retains the highest-scoring segment in each group (by prefilter score)
5. Marks remaining segments as `deduplicated=true` and assigns `dedup_group_id`

Deduplicated segments do not receive VLM targeting. They are retained in `generated/project.json` with their elimination reason recorded and may receive deterministic understanding.

This step improves signal-to-noise ratio by preventing multiple variants of the same shot (e.g., different windows around a static moment, or semantically identical content) from reaching the final timeline.

**Output:** `PrefilterDecision` records updated with `deduplicated` flag and `dedup_group_id`; dedup statistics added to analysis summary.

### Step 2.10 — VLM Target Selection

After deduplication, the analyzer selects which shortlisted segments will receive VLM analysis using a three-stage gate:

1. **Stage 1: Dedup filter** — Exclude segments marked `deduplicated=true`
2. **Stage 2: CLIP gate** — Exclude segments marked `clip_gated=true` (if CLIP is enabled)
3. **Stage 3: Per-asset limit and budget cap** — Select the top `max_segments_per_asset` per asset; if `TIMELINE_AI_VLM_BUDGET_PCT` is below 100%, limit total VLM targets to that percentage of candidates and mark remaining eligible segments as `vlm_budget_capped=true`

Excluded segments receive deterministic understanding instead of VLM analysis.

This multi-stage approach keeps VLM cost proportional to project size while maintaining quality through deduplication and semantic filtering.

**Output:** a set of segment IDs designated for VLM targeting; `vlm_budget_capped` flag set for segments excluded by the budget cap.

### Step 2.11 — AI Analysis

Each segment in the VLM target set is sent for analysis. The analyzer supports three providers:

**`lmstudio`** — sends the contact sheet and a structured prompt to a locally running LM Studio server over HTTP. Segments from the same asset are batched into a single request where possible.

**`mlx-vlm-local`** — runs a multimodal model locally using the MLX framework, optimized for Apple Silicon. Calls the model directly in-process.

**`deterministic`** — derives segment understanding from the quality metrics already computed. No model call, no image, no network. Always available.

Segments that were filtered before the VLM stage go directly to the deterministic path.

Each segment receives a `SegmentUnderstanding` record containing: subjects, actions, shot type, camera motion, mood, story roles, confidence, visual distinctiveness, clarity, story relevance, rationale, and a `keep_label` of `keep`, `maybe`, or `reject`.

If a result is cached from a previous run with the same inputs, the cache is used and no model call is made.

**Output:** a `SegmentUnderstanding` per candidate segment.

---

## Phase 3: Take Selection

**Code:** `services/analyzer/app/scoring.py`, `analysis.py`

After all segments for all assets have been analyzed, each one is scored.

Scoring produces a `ScoreBreakdown` with three components:

- **Technical score** — sharpness, stability, duration fit, subject clarity, and either `audio_energy` (speech mode) or motion energy (visual mode)
- **Semantic score** — hook strength, visual novelty, story alignment, subject clarity, and `speech_ratio` in speech mode
- **Story score** — story alignment, hook strength, duration fit

The total score is `technical × 0.35 + semantic × 0.4 + story × 0.25`.

For each asset, the highest-scoring segment becomes the **best take**. A second take is included if the asset is at least 18 seconds long and a second segment scores within 0.08 of the best. Segments must score at least 0.68 to be considered at all; if none meet the threshold, the highest scorer is used regardless.

**Output:** a `TakeRecommendation` per selected segment, with `is_best_take` set on the primary selection.

---

## Phase 4: Timeline Assembly

**Code:** `services/analyzer/app/analysis.py`

Best takes are assembled into a rough timeline.

Takes are ordered by:
1. The original discovery order of their parent asset
2. Segment start time within the asset
3. Score descending (to break ties)

Each take becomes a `TimelineItem` with a suggested trim duration: up to 7.5 seconds for speech segments, up to 5.0 seconds for visual segments. Items are labeled contextually as Opener, Outro, Narrative beat, or Visual bridge.

A short story summary is generated from the composition of selected segments: dialogue-led, visually progressive, or mixed.

**Output:** a `Timeline` with ordered `TimelineItem` records.

---

## Final Output

The complete result — project metadata, all assets, all candidate segments with their prefilter decisions and AI understanding, all take recommendations, and the assembled timeline — is serialized to `generated/project.json`.

This file is the source of truth for the review workspace and export stage. The desktop app reads it to display recommendations and the rough timeline. The export command reads it to produce the FCPXML file for Resolve.

The process step also writes operational artifacts for the latest run:

- `generated/process.log` — key/value runtime configuration and benchmark metadata
- `generated/process-summary.txt` — human-readable operational summary including total runtime and benchmark comparison
- `generated/process-output.txt` — the exact terminal-facing output emitted during the run

Benchmark history is stored separately under `generated/benchmarks/`:

- `generated/benchmarks/history.jsonl` — append-only lightweight benchmark index
- `generated/benchmarks/<run-id>/benchmark.json` — structured per-run benchmark payload with phase timings, workload counts, runtime configuration, and artifact paths
- `generated/benchmarks/<run-id>/process-output.txt` — run-scoped copy of the saved terminal-facing output

---

## What Gets Filtered and When

The pipeline filters footage progressively:

| Stage | What is removed |
| --- | --- |
| Frame sampling | Frames that ffmpeg cannot extract (corrupt or missing) |
| Deduplication | Near-duplicate segments within each asset (keep highest-scoring of similar group) |
| Prefilter shortlist | Low-scoring segments that do not reach `max_segments_per_asset` in fast mode |
| CLIP gate | Segments scoring below `TIMELINE_AI_CLIP_MIN_SCORE` (if CLIP enabled) — sent to deterministic path instead |
| VLM budget cap | Segments excluded by global budget percentage limit (if set below 100%) — sent to deterministic path instead |
| VLM targeting | Remaining segments: either in VLM target set or sent to deterministic understanding |
| Take selection | All segments below the score threshold, except the highest scorer per asset as a fallback |

Segments removed at any stage remain in `generated/project.json` with their reason for removal recorded. Nothing is silently discarded.

---

## Configuration

The pipeline behavior is controlled by environment variables, typically set in `.env.local`:

| Variable | Default | Effect |
| --- | --- | --- |
| `TIMELINE_MEDIA_DIR` | `./media` | Root directory to scan for video files |
| `TIMELINE_AI_PROVIDER` | `deterministic` | AI provider: `deterministic`, `lmstudio`, `mlx-vlm-local` |
| `TIMELINE_AI_MODE` | `fast` | `fast` limits VLM targets per asset; `full` sends all shortlisted segments |
| `TIMELINE_AI_MAX_SEGMENTS_PER_ASSET` | `3` | Maximum VLM targets per asset in fast mode |
| `TIMELINE_AI_MAX_KEYFRAMES` | `3` | Keyframes extracted per segment for VLM input |
| `TIMELINE_AI_CONCURRENCY` | `2` | Parallel VLM requests |
| `TIMELINE_AI_CACHE` | `true` | Whether to cache VLM responses across runs |
| `TIMELINE_AI_AUDIO_ENABLED` | `true` | Set to `false` to skip audio signal extraction and use silent fallback for all assets |
| `TIMELINE_AI_CLIP_ENABLED` | `true` | Set to `false` to disable CLIP semantic scoring (requires `open-clip-torch` package for enabled mode) |
| `TIMELINE_AI_CLIP_MIN_SCORE` | `0.35` | CLIP score threshold [0, 1]; segments below this are excluded from VLM targeting |
| `TIMELINE_AI_VLM_BUDGET_PCT` | `100` | Percentage of shortlisted candidates sent to VLM (after CLIP gating); 100 = no budget constraint |
| `TIMELINE_AI_CLIP_MODEL` | `ViT-B-32` | CLIP model name from `open-clip-torch` (advanced configuration) |
| `TIMELINE_STORY_PROMPT` | — | Optional narrative goal passed to the VLM as context |
| `TIMELINE_DEDUPLICATION_ENABLED` | `true` | Set to `false` to disable near-duplicate segment removal |
| `TIMELINE_DEDUP_THRESHOLD` | `0.85` | Histogram similarity threshold for grouping near-duplicates (0–1); used only when CLIP is disabled or unavailable; higher = stricter deduplication |

**Deduplication notes:**
- When `TIMELINE_AI_CLIP_ENABLED=true` and CLIP is available, deduplication uses CLIP embedding cosine similarity (threshold: 0.95, hardcoded)
- When CLIP is disabled or unavailable, deduplication falls back to histogram-based similarity using `TIMELINE_DEDUP_THRESHOLD`
- Deduplication runs after evidence building and CLIP scoring, before VLM target selection
