# Architecture Overview

## Project Structure

```
roughcut-stdio/
├── apps/desktop/              # Native macOS Tauri desktop app
├── services/analyzer/         # Python analysis engine
├── scripts/                   # Shell entrypoints
├── openspec/                  # Architectural specs (OpenSpec format)
├── docs/                      # Documentation
└── generated/                 # Output files (project.json, timeline.fcpxml)
```

---

## Three-Layer Architecture

### Frontend — `apps/desktop/`

Native macOS desktop application built with Tauri (Rust shell + TypeScript/React UI).

**Responsibilities:**
- File dialog integration for media folder selection
- Display processing progress and status
- Timeline review and segment inspection
- Export dialog for saving FCPXML to chosen location
- Launch and manage backend processes

**Tech:** Tauri, TypeScript, React, CSS

### Backend — `services/analyzer/` (Python)

Complete analysis and export engine that runs the four-phase pipeline.

**Responsibilities:**
- Media discovery and proxy matching
- Frame and audio signal extraction
- Scene detection and candidate segment building
- Prefilter scoring and shortlist selection
- Evidence building (keyframe/contact sheet extraction)
- CLIP semantic scoring and deduplication
- VLM analysis (deterministic or model-based understanding)
- FCPXML export for DaVinci Resolve

**Key Modules:**
- `media.py` — File discovery, asset creation
- `prefilter.py` — Signal extraction, scoring
- `clip.py` — CLIP semantic scoring with embedding cache
- `clip_dedup.py` — CLIP-based deduplication
- `deduplication.py` — Histogram-based fallback dedup
- `ai.py` — VLM provider orchestration
- `scoring.py` — Final segment scoring
- `export.py` — FCPXML generation

**Tech:** Python 3.12+, ffmpeg, PySceneDetect, CLIP, MLX/LLM frameworks

### Scripts — `scripts/`

Shell entrypoints for setup, processing, and export. These wrap the Python analyzer and are called by the desktop app.

**Key Scripts:**
- `setup.sh` — Environment initialization
- `process.sh` — Runs the analysis pipeline
- `export.sh` — Generates FCPXML

---

## Data Flow

```
Video Files
    ↓
[Media Discovery] → Assets (source + proxy pairs)
    ↓
[Per-Asset Analysis]
  ├─ Frame Signals (sharpness, contrast, motion)
  ├─ Audio Signals (RMS energy, silence detection)
  ├─ Scene Detection → Candidate Segments
  ├─ Prefilter Scoring → Shortlist Selection
  ├─ Evidence Building (keyframes, contact sheets)
  ├─ CLIP Scoring (semantic embeddings)
  └─ Segment Deduplication (CLIP or histogram)
    ↓
[VLM Target Selection] → Filtered segments for AI analysis
    ↓
[VLM Analysis] → Segment understanding (subjects, actions, story role)
    ↓
[Take Selection] → Best segment per asset
    ↓
[Timeline Assembly] → Ordered rough cut
    ↓
generated/project.json (all data)
generated/timeline.fcpxml (Resolve import)
```

---

## Configuration Flow

Environment variables control behavior at multiple points:

```
User sets env vars
    ↓
├─ TIMELINE_MEDIA_DIR → Media discovery scope
├─ TIMELINE_AI_PROVIDER → Determines VLM or deterministic path
├─ TIMELINE_AI_CLIP_ENABLED → Enables CLIP scoring and dedup
├─ TIMELINE_AI_MODE → fast (limited VLM) or full (all shortlisted)
├─ TIMELINE_AI_MAX_SEGMENTS_PER_ASSET → Per-asset VLM limit
└─ TIMELINE_DEDUP_THRESHOLD → Histogram dedup sensitivity
    ↓
Analyzer applies settings at each phase
    ↓
Output reflects configuration choices
```

---

## Key Design Decisions

### CLIP Embeddings for Deduplication

**Why:** Visual similarity based on semantic meaning (CLIP) is more useful than histogram intersection. Prevents semantically identical shots from both reaching the timeline.

**How:**
- CLIP embeddings are computed once during scoring pass and cached
- Dedup uses cached embeddings (zero redundant computation)
- Segments with cosine similarity >= 0.95 are grouped as near-duplicates
- Highest-scoring segment in each group is kept as keeper

**Fallback:** When CLIP unavailable, histogram-based dedup uses `TIMELINE_DEDUP_THRESHOLD`.

📖 [Segment Deduplication Spec](../openspec/specs/segment-deduplication/spec.md)
📖 [CLIP Deduplication Semantic Spec](../openspec/specs/clip-deduplication-semantic/spec.md)

### Three-Stage VLM Target Selection

**Why:** Reduces VLM compute by filtering out obvious misses before expensive model calls.

**Stages:**
1. **Dedup filter** — Exclude segments marked `deduplicated=true`
2. **CLIP gate** — Exclude segments scoring below `TIMELINE_AI_CLIP_MIN_SCORE`
3. **Per-asset limit + budget cap** — Select top `TIMELINE_AI_MAX_SEGMENTS_PER_ASSET` per asset, then apply global budget percentage

**Result:** VLM only analyzes highest-confidence segments; others get deterministic understanding.

### Local-First, No Network Dependencies

**Why:** User data never leaves the machine. Full control, full privacy.

**Implementation:**
- MLX-VLM runs entirely on-device using Apple Silicon
- LM Studio option uses local server
- Deterministic mode requires no models at all
- FCPXML export is self-contained; can be imported offline into Resolve

### Per-Phase Caching

**Why:** Users iterate often; redundant work is expensive.

**Caching Points:**
- Frame/audio signals cached per asset
- CLIP embeddings cached during scoring phase (reused by dedup)
- VLM responses cached by input hash; same image + prompt = cached result
- Enable/disable with `TIMELINE_AI_CACHE=true|false`

---

## OpenSpec Architectural Specs

The project uses OpenSpec format for detailed specifications:

- **segment-deduplication** — Deduplication logic, CLIP vs histogram, thresholds
- **clip-deduplication-semantic** — CLIP embedding reuse, keeper selection, fallback guarantees
- **audio-signal-layer** — Audio extraction, silence detection, RMS energy
- **vision-prefilter-pipeline** — Frame signals, prefilter scoring
- **processing-workflow** — Pipeline phases, orchestration, phase ordering

These specs define requirements, scenarios, and design rationale. Start with [docs/analyzer-pipeline.md](analyzer-pipeline.md) for the narrative walkthrough, then dive into OpenSpec for technical details.

---

## Extensibility Points

### Adding a New VLM Provider

Implement the provider interface in `services/analyzer/app/ai.py`:

```python
class YourProvider(VLMProvider):
    async def analyze(self, image_path: str, prompt: str) -> SegmentUnderstanding:
        # Call your model
        # Return SegmentUnderstanding
```

Then add to provider routing:

```python
if TIMELINE_AI_PROVIDER == "your-provider":
    provider = YourProvider()
```

### Adding a New Signal Type

Frame signals live in `prefilter.py`. Audio signals in `audio.py`. Add a new signal:

1. Define the signal class (e.g., `HotSpotSignal`)
2. Extract it during phase 2 (per-asset analysis)
3. Use it in prefilter scoring or downstream phases
4. Update docs/analyzer-pipeline.md with the new signal

### Tuning Deduplication Sensitivity

Adjust `TIMELINE_DEDUP_THRESHOLD` (histogram) or modify `SIMILARITY_THRESHOLD = 0.95` in `clip_dedup.py` (CLIP) to be more or less aggressive.

---

## Performance Considerations

### Bottleneck: VLM Analysis

VLM calls are the slowest part. Optimize with:

- `TIMELINE_AI_MODE=fast` — Reduces VLM targets per asset
- `TIMELINE_AI_MAX_SEGMENTS_PER_ASSET=1` — Analyze only 1 segment per asset
- `TIMELINE_AI_VLM_BUDGET_PCT=50` — Limit total VLM budget to 50% of shortlisted segments
- `TIMELINE_AI_CACHE=true` — Reuse results from previous runs

### Bottleneck: Media Processing

Frame/audio extraction via ffmpeg is I/O-bound. Optimize with:

- `TIMELINE_AI_CONCURRENCY=4` — Increase parallel ffmpeg calls (if system allows)
- Hardware encoding if available (modify media.py)

### Bottleneck: CLIP Scoring

CLIP inference is moderate cost. Mitigate with:

- Embedding cache (enabled by default; embeddings reused for dedup)
- Use smaller model: `TIMELINE_AI_CLIP_MODEL=ViT-B-16` (faster, less accurate)

---

## Reliability & Fallbacks

**Signal extraction fails** → Use synthetic fallback values (deterministic hash-based)

**Scene detection unavailable** → Divide into fixed time windows

**CLIP unavailable** → Histogram dedup continues without error

**VLM unavailable** → Deterministic understanding from quality metrics

**Audio stream missing** → All audio signals default to silent/zero energy

The system is designed so that failures degrade gracefully; the pipeline always produces usable output.
