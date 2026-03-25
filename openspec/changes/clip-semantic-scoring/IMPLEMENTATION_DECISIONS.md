# CLIP-Semantic-Scoring: Implementation Decisions Checklist

Use this to confirm final decisions before starting implementation.

## Architectural Decisions (APPROVED)

- [x] Evidence building extracts keyframes for **all shortlisted segments**, not just VLM targets
  - Cost: ~30-50% more keyframe extraction in fast mode
  - Benefit: Enables CLIP and future semantic layers without restructuring

- [x] CLIP scoring runs as **explicit Stage 2.9** between evidence building and VLM targeting
  - Clear pipeline stages: shortlist → evidence → CLIP → VLM targets → analysis

- [x] VLM target selection becomes **three-stage gate**:
  1. CLIP gate (below threshold → deterministic)
  2. Per-asset limit (top N by score)
  3. Global budget cap (top N% of all candidates)

- [x] **Dedup integration deferred** to separate future change
  - CLIP and dedup evolve independently
  - Follow-up: "dedup-clip-upgrade" to use CLIP embeddings instead of histograms

## Configuration Decisions

- [ ] **CLIP model selection**
  - ✅ **DECIDED:** Use `ViT-B-32 / laion2b_s34b_b79k` (150MB, fast on CPU)
  - ✅ **DECIDED:** Do NOT expose `TIMELINE_AI_CLIP_MODEL` in v1
  - Can be added as follow-up if needed

- [ ] **Composite score for budget ranking**
  - **REQUIRED DECISION:** Formula for ranking segments globally
  - **Proposed:** `(prefilter_score + clip_score) / 2.0`
  - **Questions:**
    - Are both metrics normalized [0, 1]? (Yes)
    - Should they be weighted equally? (Proposed: yes)
    - Alternative: `prefilter as primary, clip as tiebreaker`?
  - **DECIDE:** Equal weighting or weighted? Any weighting formula?

- [ ] **Default threshold values**
  - **Proposed defaults:**
    - `TIMELINE_AI_CLIP_MIN_SCORE=0.35` (conservative, permit marginal cases)
    - `TIMELINE_AI_VLM_BUDGET_PCT=10` (10% of candidates to VLM)
  - **Questions:**
    - Should we validate these on sample footage before release?
    - Or proceed with proposed defaults and tune in production?
  - **DECIDE:** Validate before release, or use as is?

## Pipeline Behavior Decisions

- [ ] **Evidence building scope**
  - **Current:** Fast mode limits to 1 VLM target per asset, full mode allows more
  - **Proposed:** Extract keyframes for ALL shortlisted in both modes
  - **Impact:** Consistent behavior, ~30-50% more extraction (acceptable cost)
  - **CONFIRM:** Acceptable?

- [ ] **Silent/audio-only segments**
  - **How they work:**
    - Still get frame signal extraction (step 2.2 runs for all assets)
    - Contact sheets created from whatever visual signal exists
    - CLIP scores the visual content (may be bland/featureless)
    - If no visual interest, CLIP scores low (expected behavior)
  - **Question:** Should audio-only segments skip CLIP, or is low score acceptable?
  - **DECIDE:** Skip CLIP for silent segments, or score them normally?

- [ ] **Global budget cap distribution**
  - **Proposed:** Global top-N by composite score (simpler)
  - **Alternative:** Distribute budget proportionally across assets (more complex)
  - **Tradeoff:** Top-N may starve weak assets but prioritizes strongest material globally
  - **DECIDE:** Global top-N or proportional distribution?

## Storage & Memory Decisions

- [ ] **CLIP embedding storage**
  - **Proposed:** Hold in memory during run, do not persist to disk
  - **Benefit:** Simpler, no I/O, faster for sequential access
  - **Cost:** ~10-50MB memory per run (acceptable)
  - **CONFIRM:** Acceptable?

- [ ] **CLIP model lifecycle**
  - **Proposed:** Load model once at start of CLIP scoring pass, hold for duration
  - **Benefit:** Avoids reload overhead for multi-asset projects
  - **Cost:** ~300-500MB memory while CLIP is active
  - **CONFIRM:** Acceptable?

## Reporting Decisions

- [ ] **Process reporting granularity**
  - **Proposed:** Global summary in process-summary.txt
    - `CLIP scored: X segments`
    - `CLIP gated: Y segments`
    - `VLM budget cap: binding (Z% of candidates selected)`
  - **Alternative:** Per-asset stats (more detailed but verbose)
  - **DECIDE:** Global summary or per-asset stats?

## Testing Strategy

- [ ] Coverage requirements
  - [x] CLIPScorer class (unit tests for scoring formula, embedding caching, is_available())
  - [x] CLIP gating logic (segments below threshold marked clip_gated=True)
  - [x] Three-stage VLM target selection
  - [x] Global budget cap enforcement
  - [x] Fallback behavior when CLIP disabled
  - [x] Integration test: full pipeline with/without CLIP
  - [x] Regression test: `npm run process` output matches baseline when CLIP disabled

## Sign-Off

**Before implementation starts, confirm:**

1. Architectural decisions approved? (all marked with ✅)
2. Configuration decisions made? (composite score formula, thresholds, model selection)
3. Pipeline behavior acceptable? (evidence scope, silent segments, budget distribution)
4. Storage/memory approach acceptable? (embeddings in memory, model held)
5. Reporting strategy clear? (global vs per-asset)
6. Testing strategy sufficient?

**Once confirmed, proceed with:**
- Task 1: Domain Model (add fields)
- Task 2: CLIPScorer class
- Task 3: Configuration loading
- Task 4: Pipeline integration
- ... (rest of tasks in order)

---

## Deferred Decisions (Future Changes)

The following are intentionally deferred to follow-up changes:

- Story prompt integration (`TIMELINE_STORY_PROMPT` as CLIP anchor) → future change
- Dedup upgrade to use CLIP embeddings → separate proposal (DEDUP_INTEGRATION_PROPOSAL.md)
- Custom CLIP model support → if needed in future
- Per-asset CLIP statistics → if detailed reporting needed later
