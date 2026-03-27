# Configuration Guide

The analyzer is configured through environment variables loaded from `.env` and optionally overridden by `.env.local`.

## Media & Project

- `TIMELINE_MEDIA_DIR` — Root directory to scan for video files
- `TIMELINE_PROJECT_NAME` — Name for the project and output files
- `TIMELINE_STORY_PROMPT` — Optional narrative goal passed to VLM as context
- `TIMELINE_PYTHON` — Path to Python executable (auto-detected if not set)

## AI Provider Selection

- `TIMELINE_AI_PROVIDER` — One of: `deterministic`, `lmstudio`, `mlx-vlm-local` (default: `mlx-vlm-local`)
- `TIMELINE_AI_TIMEOUT_SEC` — Timeout for VLM requests

## CLIP Semantic Scoring

- `TIMELINE_AI_CLIP_ENABLED` — Enable CLIP embedding-based semantic scoring (default: `true`)
- `TIMELINE_AI_CLIP_MIN_SCORE` — Score threshold for CLIP-gating [0–1] (default: `0.1`)
- `TIMELINE_AI_CLIP_MODEL` — CLIP model name from `open-clip-torch` (default: `ViT-B-32`)
- `TIMELINE_DEDUP_THRESHOLD` — Histogram similarity threshold for dedup when CLIP unavailable (default: `0.85`)
- `TIMELINE_DEDUPLICATION_ENABLED` — Enable near-duplicate segment removal (default: `true`)

## VLM Provider: LM Studio

- `TIMELINE_AI_MODEL` — Model name (e.g., `qwen3.5-9b`)
- `TIMELINE_AI_BASE_URL` — Server URL (e.g., `http://127.0.0.1:1234/v1`)

## VLM Provider: MLX-VLM Local

- `TIMELINE_AI_MODEL_ID` — Model identifier from HuggingFace
- `TIMELINE_AI_MODEL_REVISION` — Model revision/version tag
- `TIMELINE_AI_MODEL_CACHE_DIR` — Cache directory for model weights
- `TIMELINE_AI_DEVICE` — Device to run on (`auto`, `cpu`, `gpu`)
- `TIMELINE_SKIP_MODEL_DOWNLOAD` — Skip auto-download if weights already cached

## Runtime Tuning

- `TIMELINE_AI_MODE` — `fast` or `full` (default: `full`); limits VLM targets per asset in fast mode
- `TIMELINE_AI_MAX_SEGMENTS_PER_ASSET` — Max VLM targets per asset (default: `1` in `fast`, `99` in `full`)
- `TIMELINE_AI_MAX_KEYFRAMES` — Keyframes to extract per segment (default: `1` in `fast`, `4` in `full`)
- `TIMELINE_AI_KEYFRAME_MAX_WIDTH` — Max width for keyframe/contact sheet (default: `448` in `fast`, `960` in `full`)
- `TIMELINE_AI_CONCURRENCY` — Parallel VLM requests (default: `2`)
- `TIMELINE_AI_CACHE` — Cache VLM responses across runs (default: `true`)
- `TIMELINE_AI_AUDIO_ENABLED` — Enable audio signal extraction (default: `true`)
- `TIMELINE_AI_VLM_BUDGET_PCT` — Percentage of shortlisted candidates sent to VLM (default: `100`)
- `TIMELINE_AI_CLIP_MODEL_PRETRAINED` — CLIP pretrained weights tag (default: `laion2b_s34b_b79k`)

## Transcript Support

- `TIMELINE_TRANSCRIPT_PROVIDER` — One of: `auto`, `disabled`, `faster-whisper` (default: `auto`)
- `TIMELINE_TRANSCRIPT_MODEL_SIZE` — Local `faster-whisper` model size (default: `small`)

When transcript support is enabled, the analyzer will try to extract timed transcript spans during processing. It does not blindly transcribe every audio-bearing asset: strong speech assets can go straight to full transcription, weak assets can be skipped, and borderline assets can be promoted through a short transcript probe first. If the backend is unavailable, the run continues and speech-aware fallback scoring is used for strong speech segments instead of failing the pipeline.

`npm run setup` installs the transcript dependency automatically whenever `TIMELINE_TRANSCRIPT_PROVIDER` is not `disabled`.

If `TIMELINE_AI_CACHE=true`, transcript spans are cached between process runs under the generated analysis artifacts, which can materially reduce rerun time on the same media set. `project.analysis_summary` and `generated/process-summary.txt` now report transcript-targeted, transcript-skipped, transcript-probed, transcript-probe-rejected, transcribed, and cached asset counts.

## Segment Boundary Refinement

- `TIMELINE_SEGMENT_BOUNDARY_REFINEMENT` — Enable deterministic seed-region refinement before scoring (default: `true`)
- `TIMELINE_SEGMENT_LEGACY_FALLBACK` — Keep legacy candidate behavior available when refinement yields nothing (default: `true`)
- `TIMELINE_SEGMENT_SEMANTIC_VALIDATION` — Enable optional semantic boundary validation for ambiguous segments (default: `true`)
- `TIMELINE_SEGMENT_SEMANTIC_AMBIGUITY_THRESHOLD` — Ambiguity threshold used to select validation candidates [0–1] (default: `0.6`)
- `TIMELINE_SEGMENT_SEMANTIC_FLOOR_THRESHOLD` — Softer ambiguity floor for the minimum-target rule [0–1] (default: `0.45`)
- `TIMELINE_SEGMENT_SEMANTIC_MIN_TARGETS` — Minimum number of most-ambiguous segments that may still be validated when nothing crosses the primary threshold (default: `1`)
- `TIMELINE_SEGMENT_SEMANTIC_VALIDATION_BUDGET_PCT` — Percentage of eligible ambiguous segments that may be semantically validated (default: `100`)
- `TIMELINE_SEGMENT_SEMANTIC_VALIDATION_MAX_SEGMENTS` — Hard cap on semantically validated segments per run (default: `2`)
- `TIMELINE_SEGMENT_SEMANTIC_MAX_ADJUSTMENT_SEC` — Max boundary change applied from semantic validation (default: `1.5`)

Semantic boundary validation no longer depends only on the primary threshold. If no segment clears `TIMELINE_SEGMENT_SEMANTIC_AMBIGUITY_THRESHOLD`, the analyzer can still activate the pass for a very small number of floor-qualified segments using `TIMELINE_SEGMENT_SEMANTIC_FLOOR_THRESHOLD` and `TIMELINE_SEGMENT_SEMANTIC_MIN_TARGETS`. This keeps the pass measurable without turning it into a blanket second stage on every segment.

See [.env.example](../.env.example) for the baseline project settings. The analyzer source in [ai.py](../services/analyzer/app/ai.py) is the source of truth for advanced runtime defaults.

---

## Getting Started With AI

### Fastest: Deterministic (No Model)

Requires no AI setup. Uses only visual quality metrics:

```bash
TIMELINE_AI_PROVIDER=deterministic
```

This mode analyzes footage using frame-level visual signals (sharpness, contrast, motion energy, distinctiveness) without running any neural network models. Good for quick testing or systems without GPU/MLX support.

If you want the current deterministic segmentation stack without any VLM calls, keep the default boundary refinement on and disable semantic validation explicitly:

```bash
TIMELINE_AI_PROVIDER=deterministic
TIMELINE_SEGMENT_BOUNDARY_REFINEMENT=true
TIMELINE_SEGMENT_SEMANTIC_VALIDATION=false
TIMELINE_TRANSCRIPT_PROVIDER=disabled
```

### Recommended: MLX-VLM Local (Apple Silicon)

Fast inference on Mac using embedded MLX runtime:

```bash
TIMELINE_AI_PROVIDER=mlx-vlm-local
TIMELINE_AI_MODEL_ID=mlx-community/Qwen3.5-0.8B-4bit
TIMELINE_AI_MODE=full
TIMELINE_AI_CLIP_MIN_SCORE=0.1
```

The setup script installs MLX and model weights automatically. This provides high-quality semantic understanding of footage while keeping everything local on your Mac.

**Recommended for:**
- Local workflows
- Privacy-conscious projects
- Fast iteration
- Apple Silicon Macs (M1, M2, M3, etc.)

### Alternative: LM Studio Server

Run a local LM Studio server, then point the analyzer to it:

```bash
TIMELINE_AI_PROVIDER=lmstudio
TIMELINE_AI_MODEL=qwen3.5-9b
TIMELINE_AI_BASE_URL=http://127.0.0.1:1234/v1
```

Download and install [LM Studio](https://lmstudio.ai), load a model, and the analyzer will connect to the local server.

**Recommended for:**
- Trying different models easily
- Systems without MLX support
- Testing with larger models

### Using CLIP for Semantic Deduplication

When `TIMELINE_AI_CLIP_ENABLED=true`, the analyzer uses CLIP embeddings to detect near-duplicate segments across the entire shortlist:

```bash
TIMELINE_AI_CLIP_ENABLED=true
TIMELINE_AI_CLIP_MIN_SCORE=0.1
TIMELINE_DEDUP_THRESHOLD=0.85
```

**How it works:**
1. CLIP embeddings are computed during the semantic scoring pass
2. During deduplication, segments with cosine similarity >= 0.95 are grouped as duplicates
3. The highest-scoring segment in each group is kept as the keeper
4. Other segments in the group are marked `deduplicated=true` and excluded from VLM targeting

If CLIP is unavailable or disabled, deduplication falls back to histogram-based similarity using `TIMELINE_DEDUP_THRESHOLD`.

Read more: [Segment Deduplication Spec](../openspec/specs/segment-deduplication/spec.md)

## Using Local Transcript Support

Enable transcript extraction with the local `faster-whisper` backend:

```bash
TIMELINE_TRANSCRIPT_PROVIDER=auto
TIMELINE_TRANSCRIPT_MODEL_SIZE=small
```

If `faster-whisper` is installed, `generated/project.json` will include transcript-backed excerpts and `project.analysis_summary` will record transcript runtime status, targeted/skipped/probed transcript counts, transcribed or cached asset counts, excerpt-bearing segments, and speech-fallback segments. If the backend is missing or disabled, processing still completes and spoken clips can fall back to speech-aware scoring when `speech_ratio` and `audio_energy` are strong enough.
