# Configuration Guide

The analyzer is configured through environment variables, typically set in `.env.local`:

## Media & Project

- `TIMELINE_MEDIA_DIR` — Root directory to scan for video files
- `TIMELINE_PROJECT_NAME` — Name for the project and output files
- `TIMELINE_STORY_PROMPT` — Optional narrative goal passed to VLM as context
- `TIMELINE_PYTHON` — Path to Python executable (auto-detected if not set)

## AI Provider Selection

- `TIMELINE_AI_PROVIDER` — One of: `deterministic`, `lmstudio`, `mlx-vlm-local` (default: `deterministic`)
- `TIMELINE_AI_TIMEOUT_SEC` — Timeout for VLM requests

## CLIP Semantic Scoring

- `TIMELINE_AI_CLIP_ENABLED` — Enable CLIP embedding-based semantic scoring (default: `true`)
- `TIMELINE_AI_CLIP_MIN_SCORE` — Score threshold for CLIP-gating [0–1] (default: `0.35`)
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

- `TIMELINE_AI_MODE` — `fast` or `full` (default: `fast`); limits VLM targets per asset in fast mode
- `TIMELINE_AI_MAX_SEGMENTS_PER_ASSET` — Max VLM targets per asset in fast mode (default: `3`)
- `TIMELINE_AI_MAX_KEYFRAMES` — Keyframes to extract per segment (default: `3`)
- `TIMELINE_AI_KEYFRAME_MAX_WIDTH` — Max width for keyframe/contact sheet (default: `720`)
- `TIMELINE_AI_CONCURRENCY` — Parallel VLM requests (default: `2`)
- `TIMELINE_AI_CACHE` — Cache VLM responses across runs (default: `true`)
- `TIMELINE_AI_AUDIO_ENABLED` — Enable audio signal extraction (default: `true`)
- `TIMELINE_AI_VLM_BUDGET_PCT` — Percentage of shortlisted candidates sent to VLM (default: `100`)

See [.env.example](../.env.example) for the current defaults.

---

## Getting Started With AI

### Fastest: Deterministic (No Model)

Requires no AI setup. Uses only visual quality metrics:

```bash
TIMELINE_AI_PROVIDER=deterministic
```

This mode analyzes footage using frame-level visual signals (sharpness, contrast, motion energy, distinctiveness) without running any neural network models. Good for quick testing or systems without GPU/MLX support.

### Recommended: MLX-VLM Local (Apple Silicon)

Fast inference on Mac using embedded MLX runtime:

```bash
TIMELINE_AI_PROVIDER=mlx-vlm-local
TIMELINE_AI_MODEL_ID=mlx-community/Qwen3.5-0.8B-4bit
TIMELINE_AI_MODE=fast
TIMELINE_AI_MAX_SEGMENTS_PER_ASSET=1
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
TIMELINE_AI_CLIP_MIN_SCORE=0.35
TIMELINE_DEDUP_THRESHOLD=0.85
```

**How it works:**
1. CLIP embeddings are computed during the semantic scoring pass
2. During deduplication, segments with cosine similarity >= 0.95 are grouped as duplicates
3. The highest-scoring segment in each group is kept as the keeper
4. Other segments in the group are marked `deduplicated=true` and excluded from VLM targeting

If CLIP is unavailable or disabled, deduplication falls back to histogram-based similarity using `TIMELINE_DEDUP_THRESHOLD`.

Read more: [Segment Deduplication Spec](../openspec/specs/segment-deduplication/spec.md)
