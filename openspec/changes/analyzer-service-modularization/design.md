## Context

The analyzer already has some healthy edges:

- `media.py`, `scoring.py`, `fcpxml.py`, and `service.py` are reasonably coherent.
- `domain.py` provides stable dataclasses used throughout the service.
- The test suite provides strong behavior coverage, especially through `test_analysis.py` and `test_ai.py`.

The main architectural debt is concentrated in the core pipeline files:

- `services/analyzer/app/analysis.py` owns end-to-end orchestration, transcript runtime selection, transcript probing, candidate construction, deterministic boundary refinement, narrative assembly, semantic boundary validation, prefilter shortlisting, CLIP gating, deduplication coordination, take selection, story sequencing, timeline assembly, review-state formatting, and assorted utility helpers.
- `services/analyzer/app/ai.py` owns provider config, runtime inspection, evidence extraction, keyframe extraction, prompt builders, provider adapters, output normalization, cache helpers, JSON salvage, boundary-validation request logic, and provider-specific fallback handling.
- `services/analyzer/app/deduplication.py` contains overlapping histogram deduplication flows in both function-oriented and class-oriented forms.
- `services/analyzer/app/domain.py` mixes domain model definitions with large nested JSON serialization logic.

The result is not just large files. It is hidden coupling: changing transcript policy can force edits in the same file as timeline heuristics; changing AI prompt composition touches the same module as environment parsing and model download preparation; deduplication decisions are coordinated partly in `analysis.py` and partly in dedicated helpers.

## Goals / Non-Goals

**Goals:**
- Reduce cognitive load by giving each major analyzer concern a single owning module.
- Preserve the current local-first, deterministic-fallback, and Resolve-compatible behavior while refactoring internals.
- Keep existing service-level entry points stable so callers do not need to learn a new API during the refactor.
- Create extraction seams that let future transcript, segmentation, AI, and story-assembly work happen with smaller diffs and more targeted tests.
- Centralize shared helpers and policy decisions so the same concern is not reimplemented in multiple files.

**Non-Goals:**
- Rewriting the analyzer behavior from scratch.
- Changing scoring, selection, or export semantics as part of this refactor.
- Introducing a new framework or dependency-injection library.
- Turning the analyzer into a distributed or network-dependent service.
- Replacing the current dataclass-based domain model in this change.

## Decisions

### 1. Keep stable service entry points and refactor internal modules behind them

`service.py` remains the supported public entry point. During the refactor, `analysis.py` and `ai.py` should become thinner internal coordination modules that delegate to new owners, but their incidental helper exports are not treated as a supported public API.

Rationale:
- The current scripts and product flows already anchor behavior on `service.py` entry points.
- Narrowing the supported API keeps extraction work honest and avoids preserving accidental module surfaces.

Alternatives considered:
- Preserve every historical import from `analysis.py` and `ai.py`: rejected because the project is still early, those surfaces are not product contracts, and carrying them forward would freeze accidental APIs.
- Leave everything in place and only add comments: rejected because it does not reduce coupling.

### 2. Extract by pipeline phase, not by helper type

The implementation should follow analyzer responsibilities with explicit phase owners:

- `analysis.py`
  - top-level orchestration plus a small repo-local convenience surface where needed
- `transcripts.py`
  - transcript provider interfaces, selective targeting and probes, span lookups, turn derivation, and spoken-structure helpers
- `segmentation.py`
  - candidate creation, deterministic boundary refinement, and narrative-unit assembly
- `semantic_validation.py`
  - semantic target selection and validation application
- `selection/`
  - `takes.py`: take recommendation building
  - `timeline.py`: timeline assembly and story sequencing
  - `review.py`: review-state construction and summary labels
- `ai_runtime/`
  - `config.py`: runtime config and provider status
  - `evidence.py`: segment evidence and keyframe/contact-sheet extraction
  - `prompts.py`: prompt builders
  - `normalize.py`: JSON salvage and normalized model outputs
  - `cache.py`: cache key and cache persistence
  - `adapters.py`: shared provider lifecycle helpers for cache lookup, fallback shaping, and runtime stats
- `ai.py`
  - deterministic fallback analyzer, transport/runtime objects, and boundary-validation coordination
- `serialization/`
  - `project_data.py`: JSON <-> dataclass conversion for `ProjectData`
- `shared/`
  - `numbers.py`, `strings.py`, `env.py`: small canonical helpers only where reuse is real

Rationale:
- The dominant pain is that behavior is organized around file history, not around pipeline ownership.
- Phase ownership makes it clearer where a future change belongs and what it may impact.

Alternatives considered:
- Split only by utility type, keeping orchestration logic largely intact: rejected because it preserves the hardest coupling in `analysis.py`.
- Introduce an object-heavy service graph: rejected because it adds ceremony without solving the core ownership problem.

### 3. Move AI provider duplication behind shared request and normalization flows

Provider-specific analyzers should own only provider invocation and provider-specific fallback details. Evidence building, prompt construction, cache lookup, cache store, model-output normalization, and boundary-validation normalization should live in shared modules.

Rationale:
- `LMStudioVisionLanguageAnalyzer` and `MLXVLMVisionLanguageAnalyzer` share the same lifecycle shape: cache check, request, parse, normalize, fallback, stats.
- Shared lifecycle helpers reduce drift between providers and make new providers cheaper to add.

Alternatives considered:
- Keep separate provider classes with ad hoc duplication: rejected because the current duplication is already growing.

### 4. Centralize duplicated policy helpers and make each one canonical

This refactor should explicitly remove duplicate helper ownership, starting with:

- score/value clamping
- env parsing helpers
- deduplication grouping logic
- generic label or string utilities
- project-data serialization

Rationale:
- Duplicate helpers create silent behavior drift.
- The current code already has repeated utility patterns and overlapping deduplication implementations.

Alternatives considered:
- Leave local helper copies in place for convenience: rejected because the main purpose of this change is to make policy easier to reason about.

### 5. Use characterization tests plus module-contract tests

Keep high-value end-to-end tests around `analyze_assets`, `build_take_recommendations`, `build_timeline`, `build_segment_review_state`, and AI evidence or provider flows. Add smaller tests around extracted modules so behavior stays pinned after each move.

Rationale:
- The existing suite is strong enough to protect external behavior.
- Smaller module tests are necessary so the new structure does not just recreate monoliths in test form.

Alternatives considered:
- Refactor first and clean tests later: rejected because it increases the chance of parity regressions.

## Parity Checkpoints

The refactor stays valid only if these checkpoints remain stable across the supported service entry points and the extracted modules:

- **Project payload shape**
  - `ProjectData.to_dict()` and `ProjectData.from_dict()` must preserve the current top-level `project`, `assets`, `candidate_segments`, `take_recommendations`, and `timeline` payload layout.
  - Nested candidate, take, review-state, and timeline metadata must round-trip without field loss.
- **Runtime summary fields**
  - `project.analysis_summary` must continue to expose runtime mode labels, runtime reliability summary fields, transcript targeting and probe counts, cache warmth counters, semantic validation counts, and deterministic-versus-live AI counters.
- **Take recommendation parity**
  - `build_take_recommendations()` must preserve take ids, `is_best_take`, `outcome`, `within_asset_rank`, `score_gap_to_winner`, driver labels, limiting labels, and the current selection-reason wording shape.
- **Review-state parity**
  - `build_segment_review_state()` must preserve shortlist, gating, deduplication, model-path, boundary-strategy, lineage, transcript, turn, speech-structure, and semantic-validation fields.
- **Timeline ordering parity**
  - `build_timeline()` must preserve ordering semantics plus `order_index`, trim ranges, labels, notes, story summary, `sequence_group`, `sequence_role`, `sequence_score`, rationale text, driver labels, and tradeoff labels.

The primary parity anchors are:

- `services/analyzer/tests/test_analysis.py`
- `services/analyzer/tests/test_ai.py`
- `services/analyzer/tests/test_architecture_modules.py`

## Risks / Trade-offs

- [Refactor spreads across many files] -> Keep service entry points stable and land changes in small, behavior-preserving slices.
- [Hidden coupling causes subtle parity regressions] -> Add characterization fixtures for project payloads, take recommendations, review state, and timeline outputs before moving core logic.
- [Module explosion replaces one monolith with too many thin wrappers] -> Extract only around real phase ownership, not every helper into its own file.
- [Provider code becomes harder to follow if over-abstracted] -> Share lifecycle helpers, but keep provider-specific request code explicit inside the provider adapters.
- [Open work on transcript and runtime features conflicts with refactor] -> Sequence extractions so transcript, AI, and selection seams are isolated first while keeping `service.py` stable.

## Migration Plan

1. Add or strengthen characterization coverage around supported service entry points and payload outputs.
2. Extract shared helpers and serialization out of `analysis.py`, `ai.py`, `deduplication.py`, and `domain.py` without changing behavior.
3. Extract transcript policy, transcript-turn derivation, and spoken-structure logic out of `analysis.py`.
4. Extract segmentation refinement, assembly, and semantic validation coordination into dedicated modules.
5. Extract take selection, story sequencing, timeline assembly, and review-state formatting into `selection/`.
6. Extract AI runtime config, evidence building, prompts, normalization, cache helpers, and provider adapters out of `ai.py`.
7. Reduce `analysis.py` and `ai.py` to orchestration-focused internal modules, then remove dead imports and duplicate helpers.
8. Update analyzer architecture documentation after the new ownership boundaries are stable.

Rollback strategy:
- Because the refactor preserves supported service entry points, any problematic extraction can be reverted at the module slice level without changing caller contracts.

## Open Questions

- Should `ProjectData` JSON serialization stay alongside the dataclasses under `domain.py`, or move fully into a serialization module in the first pass?
- Do we want a single `pipeline/asset_pipeline.py` coordinator, or separate coordinators for deterministic analysis and AI-enrichment phases?
- Should CLIP gating and deduplication stay in one post-prefilter module, or split into distinct `ranking` and `deduplication` responsibilities once the first extraction pass is done?
