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

Native macOS desktop application built with Tauri and a Vite-powered TypeScript UI.

**Responsibilities:**
- File dialog integration for media folder selection
- Display processing progress and status
- Review recommended segments, provenance, timeline state, and preview frames
- Persist per-asset best-take overrides without mutating the analyzer baseline project JSON
- Export dialog for saving FCPXML to chosen location
- Launch and manage backend processes
- In packaged mode, own runtime checks, bootstrap, process orchestration, and export over bundled runtime resources

**Tech:** Tauri, TypeScript, Vite, CSS

### Backend — `services/analyzer/` (Python)

Complete analysis and export engine that runs the four-phase pipeline.

**Responsibilities:**
- Media discovery and proxy matching
- Frame and audio signal extraction
- Seed-region generation and deterministic boundary refinement
- Narrative-unit merge/split assembly
- Optional semantic boundary validation for ambiguous segments
- Cross-asset story assembly for rough timeline ordering
- Prefilter scoring and shortlist selection
- Evidence building (keyframe/contact sheet extraction)
- CLIP semantic scoring and deduplication
- VLM analysis (deterministic or model-based understanding)
- FCPXML export for DaVinci Resolve

**Key Modules:**
- `media.py` — File discovery, asset creation
- `prefilter.py` — Signal extraction and low-cost candidate generation
- `analysis.py` — Pipeline orchestration and composition of phase-owned modules
- `transcripts.py` — Transcript providers, selective targeting, probe policy, spans, turns, and spoken-structure helpers
- `segmentation.py` — Candidate creation, deterministic refinement, and narrative-unit assembly
- `semantic_validation.py` — Semantic boundary target selection and application
- `selection/` — Take recommendation, story sequencing, timeline assembly, and review-state formatting
- `clip.py` — CLIP semantic scoring with embedding cache
- `clip_dedup.py` — CLIP-based deduplication
- `deduplication.py` — Histogram-based fallback dedup
- `ai_runtime/` — Shared AI config, evidence, prompt, normalization, cache, and provider lifecycle helpers
- `ai.py` — Deterministic fallback, provider transport/runtime objects, and boundary-validation coordination
- `serialization/` — `ProjectData` payload round-tripping
- `shared/` — Canonical numeric, string, and environment helpers
- `scoring.py` — Final segment scoring
- `fcpxml.py` — FCPXML generation

**Tech:** Python 3.12+, ffmpeg, PySceneDetect, CLIP, MLX/LLM frameworks

### Scripts — `scripts/`

Shell entrypoints for setup, processing, and export in repository development mode. These wrap the Python analyzer for local development and debugging.

**Key Scripts:**
- `setup.sh` — Environment initialization
- `process.sh` — Runs the analysis pipeline
- `export.sh` — Generates FCPXML

The packaged desktop runtime no longer depends on these scripts as its required execution path; packaged mode runs through the Tauri backend runtime abstraction instead.

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
  ├─ Scene Detection + Peaks → Seed Regions
  ├─ Deterministic Boundary Refinement
  ├─ Narrative Unit Assembly (merge / split)
  ├─ Optional Semantic Boundary Validation
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
[Story Assembly + Timeline Assembly] → Ordered rough cut
    ↓
generated/project.json (all data)
    ↓
[Desktop Review Overrides] → generated/best-take-overrides.json (optional)
    ↓
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
├─ TIMELINE_SEGMENT_BOUNDARY_REFINEMENT → Enables deterministic seed refinement
├─ TIMELINE_SEGMENT_SEMANTIC_VALIDATION → Enables optional semantic boundary validation
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

### Segmentation Before AI

**Why:** raw scene ranges or peak-centered windows are not reliable edit units.

**Current flow:**
- low-cost scene and peak signals generate seed regions
- deterministic snapping uses transcript, audio, scene, and duration cues
- adjacent refined regions can be merged or split into final narrative units
- only ambiguous boundaries are eligible for optional semantic validation

**Result:** scoring and review operate on stronger within-asset edit units, not raw signal windows.

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

- **context-complete-segmentation** — Segment refinement, assembly, semantic validation, and provenance requirements
- **segment-deduplication** — Deduplication logic, CLIP vs histogram, thresholds
- **clip-deduplication-semantic** — CLIP embedding reuse, keeper selection, fallback guarantees
- **audio-signal-layer** — Audio extraction, silence detection, RMS energy
- **ai-segment-understanding** — Persisted AI understanding and runtime controls
- **review-workspace** — Desktop review requirements and provenance display
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

Frame and audio signals live in `prefilter.py`, with orchestration in `analysis.py`. Add a new signal:

1. Define the signal class (e.g., `HotSpotSignal`)
2. Extract it during phase 2 (per-asset analysis)
3. Use it in prefilter scoring or downstream phases
4. Update `docs/analyzer-pipeline.md` with the new signal

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

**Scene detection unavailable** → Build fallback seed regions and apply deterministic duration rules

**CLIP unavailable** → Histogram dedup continues without error

**VLM unavailable** → Deterministic understanding from quality metrics

**Audio stream missing** → All audio signals default to silent/zero energy

**Desktop override file is stale** → Override payload is ignored and the analyzer-selected baseline project is loaded instead

The system is designed so that failures degrade gracefully; the pipeline always produces usable output.
