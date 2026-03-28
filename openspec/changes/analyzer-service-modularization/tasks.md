## 1. Characterization And Migration Guardrails

- [x] 1.1 Add or tighten characterization coverage for `analyze_assets`, `build_take_recommendations`, `build_timeline`, `build_segment_review_state`, and AI evidence flows before moving core logic.
- [x] 1.2 Freeze the supported public analyzer entry points in `service.py` and narrow `analysis.py` and `ai.py` to internal coordination responsibilities during the refactor.
- [x] 1.3 Identify and document current parity checkpoints for project payload shape, runtime summary fields, take recommendations, review-state fields, and timeline ordering.

## 2. Shared Foundations

- [x] 2.1 Extract canonical shared helpers for number clamping, environment parsing, and string utilities where analyzer modules currently duplicate them.
- [x] 2.2 Move `ProjectData` JSON serialization and related nested payload conversion into a dedicated serialization module or otherwise isolate it from pure domain definitions.
- [x] 2.3 Consolidate deduplication grouping logic so histogram deduplication has one owned implementation and one integration path.

## 3. Pipeline Extraction

- [x] 3.1 Extract transcript provider, transcript targeting or probing, span handling, turn derivation, and spoken-structure helpers out of `analysis.py`.
- [x] 3.2 Extract candidate creation, deterministic boundary refinement, and narrative assembly into dedicated segmentation modules.
- [x] 3.3 Extract semantic boundary target selection, request coordination, and application logic into a dedicated semantic-validation module.
- [x] 3.4 Extract take selection, story sequencing, timeline assembly, and review-state formatting into phase-owned selection modules.

## 4. AI Runtime Extraction

- [x] 4.1 Extract AI runtime config loading and provider-status inspection into a dedicated runtime-config module.
- [x] 4.2 Extract segment evidence building, keyframe extraction, and contact-sheet generation into a dedicated evidence module.
- [x] 4.3 Extract prompt builders, output normalization, cache helpers, and JSON salvage helpers into shared AI runtime modules.
- [x] 4.4 Reduce LM Studio and MLX-VLM analyzer classes to provider adapters that reuse the shared lifecycle components.

## 5. Compatibility Cleanup And Documentation

- [x] 5.1 Reduce `analysis.py` and `ai.py` to thinner orchestration or coordination modules and remove dead imports and duplicate helpers.
- [x] 5.2 Add focused module-level tests for extracted transcript, segmentation, selection, and AI runtime modules.
- [x] 5.3 Update analyzer architecture documentation to reflect the new ownership boundaries and the supported `service.py` entry points.
