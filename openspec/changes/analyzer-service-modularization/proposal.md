## Why

The analyzer service has accumulated too many responsibilities inside a few oversized, tightly connected modules. `analysis.py` now mixes orchestration, transcript policy, boundary refinement, semantic validation, selection, timeline assembly, and review-state formatting, while `ai.py` mixes provider configuration, runtime inspection, evidence building, prompt construction, caching, normalization, and provider-specific execution paths. That makes routine changes slow, increases regression risk, and encourages more duplication each time the pipeline grows.

The service is still at a stage where behavior is changing quickly, especially around transcript-backed analysis, semantic validation, and runtime controls. Establishing cleaner seams now will reduce the cost of future analyzer work without changing the product contract around local-first processing, deterministic fallback, or Resolve handoff.

## What Changes

- Reorganize the analyzer core around explicit phase-owned modules instead of continuing to grow `analysis.py` and `ai.py` as catch-all files.
- Split pipeline concerns into dedicated modules for orchestration, transcript handling, segmentation and assembly, semantic boundary validation, take selection, story assembly, and review-state formatting.
- Split AI concerns into dedicated modules for runtime config and status, evidence extraction, prompt generation, provider adapters, cache helpers, and output normalization.
- Preserve the supported `service.py` entry points and payload contracts while the internal module layout changes.
- Remove duplicate policy and helper implementations where the same concern currently exists in multiple places.
- Add characterization and module-level tests so the refactor can proceed incrementally with parity checks instead of a one-shot rewrite.

## Capabilities

### New Capabilities
- `analyzer-service-architecture`: Define the modular analyzer service boundaries, supported service entry points, shared helper ownership, and parity expectations required for the refactor.

### Modified Capabilities

None.

## Impact

- `services/analyzer/app/analysis.py`
- `services/analyzer/app/ai.py`
- `services/analyzer/app/deduplication.py`
- `services/analyzer/app/domain.py`
- `services/analyzer/app/service.py`
- `services/analyzer/tests/test_analysis.py`
- `services/analyzer/tests/test_ai.py`
- Analyzer documentation, especially architecture and pipeline notes under `docs/`
