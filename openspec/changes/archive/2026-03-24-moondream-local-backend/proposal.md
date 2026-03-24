## Why

The current local-AI path depends on LM Studio as an external runtime. That works for power users, but it makes the project harder to package, harder to explain, and less reproducible for other users. It also splits core behavior across this repository and an external app that must be installed, configured, and kept running separately.

This project already has a local-first Python analyzer and an npm-first workflow. Adding a direct `moondream-local` backend lets the repository own its vision-model path end to end while keeping LM Studio available as an optional provider. That improves portability, makes `setup -> process -> view -> export` more self-contained, and creates a clearer default path for users who want local visual analysis without extra runtime coordination.

## What Changes

- Add a new `moondream-local` AI backend alongside the existing `lmstudio` and `deterministic` backends.
- Integrate Moondream directly into the Python analyzer so shortlisted segment contact sheets can be analyzed in-process instead of via an external HTTP runtime.
- Add setup-time bootstrap support so `npm run setup` can install Python dependencies and download the configured Moondream model into a local cache.
- Extend `npm run check:ai` so it validates the embedded Moondream backend, including imports, model availability, and a minimal load/smoke-check path.
- Keep the existing screening-first architecture intact: prefilter first, shortlist second, VLM last.
- Keep LM Studio support available for users who still want that provider.
- Preserve deterministic fallback so processing still succeeds when the local model cannot be loaded or inference fails.

## Capabilities

### New Capabilities
- `moondream-local-backend`: direct in-process vision-model inference using Moondream without requiring LM Studio.

### Modified Capabilities
- `ai-segment-understanding`: add backend selection and direct Moondream execution alongside LM Studio.
- `processing-workflow`: extend setup and AI health-check flows to support direct model bootstrap and validation.

## Impact

- Affected code:
  - `services/analyzer/app/ai.py`
  - new model bootstrap / loader utilities under `services/analyzer/app/` or `services/analyzer/scripts/`
  - `services/analyzer/scripts/check_ai_provider.py`
  - `scripts/setup.sh`
  - `scripts/check_ai.sh`
  - environment and README documentation
- Affected outputs:
  - `generated/process.log`
  - `generated/process-summary.txt`
  - possible model cache directory under repo-controlled storage
- Dependencies and systems:
  - Python model runtime dependencies such as `torch`, `transformers`, `Pillow`, and Moondream-specific packages if required
  - local model cache/download strategy
  - device selection (`mps`, `cpu`, optional `cuda`) and startup-time model loading behavior
