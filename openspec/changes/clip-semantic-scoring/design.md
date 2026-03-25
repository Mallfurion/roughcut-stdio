## Context

After `audio-signal-layer` and `segment-deduplication`, the prefilter stage produces a shortlist of candidates that are sharp, non-silent, and visually distinct from each other. That shortlist is an improvement over the current raw candidate set, but it still answers only a structural question — "is this frame well-exposed and non-repetitive?" — not an editorial one. A clip of an empty hallway can be perfectly sharp, non-silent, and unique. It will pass the prefilter and consume a VLM request. The VLM will then explain that the shot is uninteresting, at far greater cost than was necessary to reach that conclusion.

The gap between the prefilter shortlist and the VLM is where CLIP belongs. CLIP encodes both images and text into the same embedding space and scores their similarity. Running an image against prompts like `"interesting moment"` or `"clear subject well-framed"` takes under 100ms on CPU. It does not generate language. It does not reason about the shot. But it can reliably separate a visually coherent, editorially plausible shot from an empty, featureless, or compositionally weak one — which is exactly what the VLM gate needs before it is asked for more.

The global VLM budget cap addresses a separate but related problem. `max_segments_per_asset` limits VLM targets per clip, but a large project with 40 or 60 clips still sends `40–60 × max_segments_per_asset` segments to the VLM. Processing cost scales with clip count rather than with genuinely promising footage. A global percentage cap — VLM targets must not exceed N% of all candidates — makes cost proportional to the total footage pool regardless of how many clips it is spread across.

Both additions are optional and additive. When `TIMELINE_AI_CLIP_ENABLED=false` (the default), the CLIP step is skipped entirely and the pipeline runs identically to its current behavior. The global budget cap applies independently of CLIP.

Constraints:

- `open-clip-torch` must remain an optional dependency; the baseline pipeline must not require it
- CLIP inference runs on keyframes extracted for all shortlisted segments (not just VLM targets). This enables CLIP and future semantic layers without requiring separate frame extractions.
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

**Non-Goals:**

- Fine-tuning or custom CLIP models. The baseline uses a standard pretrained model from `open-clip-torch` with no modification.
- Story-prompt–aware CLIP scoring in the first implementation. Using `TIMELINE_STORY_PROMPT` as a CLIP query is a natural extension but is not part of this change.
- Upgrading segment deduplication to use CLIP embeddings instead of histograms. That is a separate future change (`dedup-clip-upgrade`) that can be implemented and validated after this change is released.
- Cross-asset semantic clustering (that belongs to a later change).
- Any change to the VLM prompt or model behavior.
- Any change to the FCPXML export or Resolve handoff.
- Any UI change to the desktop review workspace in this change.

## Decisions

### 1. Evidence building extracts keyframes for all shortlisted segments; CLIP runs on those keyframes

The `build_segment_evidence()` step extracts keyframes and stitches them into a contact sheet. Currently it only extracts for VLM targets. For CLIP (and future semantic layers), evidence building must produce contact sheets for **all shortlisted segments**.

This is a conceptual shift: evidence building becomes "gather evidence for downstream analysis" rather than "gather evidence specifically for VLM."

The execution order is now explicit:
1. Shortlist selection (prefilter scores)
2. Evidence building (extract keyframes + contact sheets for ALL shortlisted)
3. CLIP scoring (score all shortlisted segments)
4. VLM target selection (three-stage gate: CLIP + per-asset + global budget)
5. VLM analysis (only on selected targets)
6. Deterministic understanding (for remaining segments, which may use clip_score)

Trade-offs:
- **Benefit:** Enables CLIP and future semantic gates without restructuring the pipeline
- **Cost:** ~30-50% more keyframe extraction in fast mode (1 VLM target per asset → typically 3 shortlisted segments)
- **Mitigation:** Keyframe extraction is cheap (~100ms per segment) compared to VLM analysis (5-10s per segment)

Alternative considered:
- Extract CLIP-specific frames (lower resolution, cached separately) — rejected because it adds complexity and the keyframes are already there for VLM anyway.

Why this is better than the current proposal:
- Resolves the circular dependency (CLIP needs evidence before VLM target selection can be made)
- Makes the pipeline stages explicit and linear
- No new frame extractions, only scope expansion of existing evidence building

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
4. **[UPDATED]** Modify evidence building in `analyze_assets()` in `analysis.py` to extract keyframes for **all shortlisted segments**, not just VLM targets (change line 324).
5. **[NEW]** After evidence building, integrate CLIP scoring into `analyze_assets()`: score all shortlisted segments, compute `clip_score`, mark `clip_gated=True` for segments below threshold.
6. **[UPDATED]** Update VLM target selection to be a three-stage gate:
   - Stage 1: Filter out `clip_gated` segments
   - Stage 2: Apply per-asset limit (max_segments_per_asset)
   - Stage 3: Apply global budget cap using composite score ranking
7. Update `scoring.py` to include `clip_score` as a semantic input in the semantic score path when present in the metrics snapshot.
8. Extend process reporting with CLIP and VLM budget statistics.
9. Update `docs/analyzer-pipeline.md` to document the new pipeline stages (CLIP scoring as Step 2.9, VLM target selection updated).
10. Add tests for `CLIPScorer`, CLIP gating logic, VLM budget cap enforcement, three-stage VLM target selection, and fallback behavior when CLIP is disabled.

## Open Questions

1. **CLIP model selection (DECIDED):** Use `ViT-B-32 / laion2b_s34b_b79k` as hardcoded default (150MB, fast on CPU). Do not expose `TIMELINE_AI_CLIP_MODEL` in v1. If users need different models in the future, that can be added as a follow-up with validation.

2. **Composite score formula:** Confirm the global budget cap should rank segments by `(prefilter_score + clip_score) / 2.0`:
   - Both metrics are normalized [0, 1]?
   - Equal weighting appropriate, or should one be prioritized?
   - Should this formula be documented or configurable?

3. **Evidence building scope in fast vs full mode:**
   - Currently: fast mode limits to 1 VLM target per asset; full mode allows more
   - Decision: Extract keyframes for all shortlisted segments in both modes (consistent behavior, minimal cost difference)
   - Is this acceptable?

4. **CLIP embedding storage:**
   - Cache embeddings in memory during the run (like CLIPScorer model) or persist to disk?
   - Decision: Hold in memory only (simpler, no I/O overhead)
   - Acceptable?

5. **Threshold validation:**
   - Default `TIMELINE_AI_CLIP_MIN_SCORE=0.35` is intentionally permissive. Should this be tested/tuned on sample footage before v1 release?
   - Default `TIMELINE_AI_VLM_BUDGET_PCT=10` — is this sensible for typical projects (10% of all candidates sent to VLM)?

6. **Silent/audio-only segments:**
   - They still get frame signal extraction, so contact sheets exist. Confirmed?
   - CLIP will score whatever visual signal exists (may be bland for audio-heavy segments). Should audio-only segments skip CLIP scoring, or is low CLIP scores acceptable?

7. **Process reporting granularity:**
   - Report per-asset CLIP stats, or global summary only?
   - Decision: Global summary (CLIP scored X segments, gated Y, budget cap binding at Z%)
   - Acceptable?

8. **Story prompt integration (DEFERRED):** Should `TIMELINE_STORY_PROMPT` be usable as an additional positive CLIP anchor? Deferred to follow-up change.

9. **Global budget cap distribution:** Should the cap distribute remaining budget proportionally across assets, or use simple global top-N by score?
   - Decision: Global top-N (simpler, prioritizes strongest material globally)
   - Acceptable, even though it may starve weak assets?
