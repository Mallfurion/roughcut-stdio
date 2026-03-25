## Context

After `audio-signal-layer` and `segment-deduplication`, the prefilter stage produces a shortlist of candidates that are sharp, non-silent, and visually distinct from each other. That shortlist is an improvement over the current raw candidate set, but it still answers only a structural question — "is this frame well-exposed and non-repetitive?" — not an editorial one. A clip of an empty hallway can be perfectly sharp, non-silent, and unique. It will pass the prefilter and consume a VLM request. The VLM will then explain that the shot is uninteresting, at far greater cost than was necessary to reach that conclusion.

The gap between the prefilter shortlist and the VLM is where CLIP belongs. CLIP encodes both images and text into the same embedding space and scores their similarity. Running an image against prompts like `"interesting moment"` or `"clear subject well-framed"` takes under 100ms on CPU. It does not generate language. It does not reason about the shot. But it can reliably separate a visually coherent, editorially plausible shot from an empty, featureless, or compositionally weak one — which is exactly what the VLM gate needs before it is asked for more.

The global VLM budget cap addresses a separate but related problem. `max_segments_per_asset` limits VLM targets per clip, but a large project with 40 or 60 clips still sends `40–60 × max_segments_per_asset` segments to the VLM. Processing cost scales with clip count rather than with genuinely promising footage. A global percentage cap — VLM targets must not exceed N% of all candidates — makes cost proportional to the total footage pool regardless of how many clips it is spread across.

Both additions are optional and additive. When `TIMELINE_AI_CLIP_ENABLED=false` (the default), the CLIP step is skipped entirely and the pipeline runs identically to its current behavior. The global budget cap applies independently of CLIP.

Constraints:

- `open-clip-torch` must remain an optional dependency; the baseline pipeline must not require it
- CLIP inference must run on already-extracted keyframes — no additional frame extraction is introduced by this change
- silent footage must remain a first-class path; CLIP scoring is purely visual and does not penalize silent segments
- the `setup -> process -> view -> export` workflow must remain intact
- deterministic fallback must remain available at all times
- Resolve export correctness must not be affected

## Goals / Non-Goals

**Goals:**

- Add CLIP as an optional semantic gate between the prefilter shortlist and VLM targeting, enabled by `TIMELINE_AI_CLIP_ENABLED=true`.
- Score each shortlisted segment's keyframe or contact sheet against a small fixed set of positive and negative editorial prompts, producing a single `clip_score` in [0, 1].
- Gate segments below `TIMELINE_AI_CLIP_MIN_SCORE` away from VLM targeting; those segments receive deterministic understanding instead.
- Persist `clip_score` in the prefilter metrics snapshot and `clip_gated=true` in the `PrefilterDecision` for gated segments.
- Incorporate `clip_score` into `scoring.py` as a semantic input when available.
- Add a global VLM budget cap via `TIMELINE_AI_VLM_BUDGET_PCT` that applies regardless of whether CLIP is enabled.
- Extend process reporting with CLIP coverage, gate statistics, and VLM budget utilisation.
- Reuse the CLIP embedding path for the deduplication upgrade defined in `segment-deduplication`.

**Non-Goals:**

- Fine-tuning or custom CLIP models. The baseline uses a standard pretrained model from `open-clip-torch` with no modification.
- Story-prompt–aware CLIP scoring in the first implementation. Using `TIMELINE_STORY_PROMPT` as a CLIP query is a natural extension but is not part of this change.
- Cross-asset semantic clustering (that belongs to a later change).
- Any change to the VLM prompt or model behavior.
- Any change to the FCPXML export or Resolve handoff.
- Any UI change to the desktop review workspace in this change.

## Decisions

### 1. Run CLIP on already-extracted keyframes, not on new extractions

The `build_segment_evidence()` step extracts keyframes and stitches them into a contact sheet before VLM targeting. CLIP should run on the same contact sheet or first keyframe, not on a separate extraction. This avoids doubling ffmpeg invocations and keeps the dependency boundary clear: CLIP is a scoring layer over evidence that already exists, not a new extraction mechanism.

This means the execution order must be: evidence building (keyframe extraction + contact sheet) → CLIP scoring → VLM targeting gate. Evidence building currently happens at the same time as VLM targeting decisions. The ordering must be made explicit so keyframes are available before the CLIP gate runs.

Alternative considered:
- Extract a separate lower-resolution frame specifically for CLIP.

Why rejected:
- The keyframes already extracted for VLM input are adequate for CLIP. A second extraction adds subprocess overhead and complexity for no accuracy gain. CLIP is robust to JPEG compression and modest resolution differences.

### 2. Use a small fixed prompt set with positive and negative anchors

The CLIP score is computed as a weighted combination of cosine similarities against a small prompt set:

Positive anchors (similarity added):
- `"cinematic shot with clear subject"`
- `"sharp focus and good composition"`
- `"interesting and visually engaging moment"`
- `"subject clearly visible and well framed"`

Negative anchors (similarity subtracted):
- `"blurry or out of focus footage"`
- `"empty scene with no visible subject"`
- `"overexposed or underexposed shot"`

The final `clip_score` is: `mean(positive_similarities) - 0.5 × mean(negative_similarities)`, normalized to [0, 1].

The prompts are fixed in the first implementation. A future change may allow `TIMELINE_STORY_PROMPT` to be included as an additional positive anchor.

Alternative considered:
- Use only positive prompts and no negative anchors.

Why rejected:
- Positive-only scoring tends to compress the distribution toward the upper range. Negative anchors provide useful signal for explicitly weak footage — empty frames, blown highlights, heavy blur — that positive prompts do not reliably penalize.

Alternative considered:
- Allow users to configure the prompt set via environment variables.

Why rejected:
- Prompt engineering significantly affects output quality and is hard to validate without a test set. The prompt set should be fixed and tested before being exposed as a user-facing configuration. Customisation can be added later.

### 3. The CLIP gate operates on the shortlist before VLM targeting

The CLIP score is used as a gate, not as a ranking signal. Segments below `TIMELINE_AI_CLIP_MIN_SCORE` after CLIP scoring are marked `clip_gated=true` and excluded from VLM targeting. They receive deterministic understanding instead.

The gate threshold defaults to `0.35`. This is intentionally conservative: the goal is to suppress clearly weak footage, not to preempt the VLM on marginal cases. A segment that scores 0.36 on CLIP may still be editorially useful; the VLM should decide.

Alternative considered:
- Use `clip_score` as an additional ranking input only, without a hard gate.

Why rejected:
- Without a gate, CLIP only reshuffles the order of segments going to the VLM. It does not reduce VLM volume. The primary purpose of CLIP in this pipeline is cost reduction, not just ranking refinement. Both are needed, so `clip_score` serves as a gate and as a scoring input.

### 4. Global VLM budget cap is independent of CLIP

`TIMELINE_AI_VLM_BUDGET_PCT` (default: `10`) caps VLM targets at a percentage of the total candidate pool across all assets. This applies after deduplication and CLIP gating, making it a final hard enforcement rather than a first-pass filter.

When the cap is binding, segments are ranked across all assets by their composite prefilter + CLIP score and the top N are selected as VLM targets. Assets with no shortlisted segments after CLIP gating contribute zero to the VLM target count.

The cap defaults to `10%`. On a project with 100 total candidates, that is 10 VLM calls. On a project with 40 candidates (typical for a short doc or vlog project), it is 4 VLM calls. The VLM then explains and labels only the very strongest material.

Alternative considered:
- Keep `max_segments_per_asset` as the only budget control.

Why rejected:
- Per-asset limits do not prevent cost from scaling with clip count. A project with 60 assets and `max_segments_per_asset=3` sends 180 segments to the VLM — even if many of those 60 clips are weak. The global cap makes cost proportional to the total footage pool.

### 5. CLIP model is loaded once per process run and held in memory

`open-clip-torch` model loading takes 1–3 seconds and several hundred MB of memory. The model should be loaded once at the start of the CLIP scoring pass and held in memory for the duration of the run. It should not be reloaded per asset or per segment.

The model and preprocessing transform are initialised in a `CLIPScorer` class that wraps `open_clip.create_model_and_transforms()` and caches the text embeddings for the fixed prompt set on first use.

Alternative considered:
- Load and unload the model per asset to reduce peak memory use.

Why rejected:
- Model load latency would dominate the CLIP scoring cost for projects with many short assets. The memory overhead of holding the model loaded is acceptable given that it is only active when `TIMELINE_AI_CLIP_ENABLED=true`.

### 6. CLIP scoring is skipped entirely when disabled or unavailable

When `TIMELINE_AI_CLIP_ENABLED=false` (the default), or when `open-clip-torch` is not importable:

- No `CLIPScorer` is instantiated.
- No keyframe images are loaded for CLIP.
- `clip_score` is absent from the prefilter metrics snapshot.
- `clip_gated` is absent from all `PrefilterDecision` records.
- The global VLM budget cap still applies, using only prefilter scores for cross-asset ranking.
- Pipeline behavior is identical to the current post-deduplication behavior.

No warning or error is emitted for a missing `open-clip-torch` when `TIMELINE_AI_CLIP_ENABLED=false`.

## Risks / Trade-offs

- [CLIP model size adds setup burden] → Mitigation: default is disabled; document model size and download behavior clearly in setup instructions.
- [CLIP threshold may gate useful segments] → Mitigation: default threshold of 0.35 is intentionally permissive. Log which segments were gated and why so the operator can adjust.
- [Fixed prompt set may not generalise across project types] → Mitigation: the prompts are chosen to be genre-agnostic (subject presence, focus, composition). Genre-specific tuning is a future extension.
- [Global budget cap may produce uneven coverage across assets] → Mitigation: the cap selects top-scoring segments globally, which means assets with stronger footage get proportionally more VLM attention. This is the intended behavior, but it should be documented so operators understand the tradeoff.
- [CLIP inference adds latency per shortlisted segment] → Mitigation: 50–100ms per segment on CPU is negligible relative to VLM latency. On GPU it is under 10ms.

## Migration Plan

1. Add `clip_score` field to the prefilter metrics snapshot and `clip_gated` boolean to `PrefilterDecision` in `domain.py`.
2. Implement `CLIPScorer` class in a new `clip.py` module under `services/analyzer/app/`: loads model, caches prompt embeddings, exposes `score(image_path) -> float`.
3. Add `TIMELINE_AI_CLIP_ENABLED`, `TIMELINE_AI_CLIP_MIN_SCORE`, and `TIMELINE_AI_VLM_BUDGET_PCT` to the AI config loading in `ai.py`.
4. Integrate CLIP scoring into `analyze_assets()` in `analysis.py`: after evidence building, before VLM targeting, when CLIP is enabled.
5. Integrate the global VLM budget cap into `analyze_assets()`: after CLIP gating (or directly after deduplication when CLIP is disabled), enforce the budget across all asset shortlists.
6. Update `scoring.py` to include `clip_score` as a semantic input when present in the metrics snapshot.
7. Connect the CLIP embedding path to `segment-deduplication`'s upgrade point: when CLIP is enabled, pass embeddings to the deduplication pass instead of histograms.
8. Extend process reporting with CLIP and budget statistics.
9. Update `docs/analyzer-pipeline.md` to document the CLIP scoring step and VLM budget cap.
10. Add tests for `CLIPScorer`, gating logic, budget cap enforcement, and fallback behavior when CLIP is disabled.

## Open Questions

- Which `open-clip-torch` model should be the default? `ViT-B-32` with `laion2b_s34b_b79k` weights is a reasonable starting point (150MB, fast on CPU), but `ViT-L-14` would be more accurate at higher cost. Should both be supported via a `TIMELINE_AI_CLIP_MODEL` variable?
- Should `TIMELINE_STORY_PROMPT` be usable as an additional positive CLIP anchor in this change, or deferred to a follow-up?
- Should the global budget cap distribute remaining budget proportionally across assets, or use a simple global top-N by score? Global top-N is simpler but may starve assets with uniformly mediocre prefilter scores even when those assets contain the project's best footage.
