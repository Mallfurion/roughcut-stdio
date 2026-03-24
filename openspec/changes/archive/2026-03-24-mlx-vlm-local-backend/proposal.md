## Why

The current embedded local-model path is based on `moondream-local` through generic `transformers` integration. That path has proven unstable on Apple Silicon in this project, including Metal runtime issues and dtype mismatches. The product goal now is to support a local vision-model path that is specifically aligned with Apple Silicon instead of relying on a generic Python model stack and remote-code execution.

`MLX` and `MLX-VLM` are designed for Apple Silicon and provide a more appropriate runtime foundation for this repository. Replacing `moondream-local` with `mlx-vlm-local` gives the app an embedded local backend that is aligned with the target hardware while preserving the screening-first pipeline and keeping `lmstudio` available as an alternative provider.

## What Changes

- Remove `moondream-local` support from the repository.
- Add a new `mlx-vlm-local` backend for direct local inference on Apple Silicon.
- Make `mlx-vlm-local` the recommended embedded backend for macOS.
- Use an MLX-compatible Qwen 3.5 0.8B vision-language model as the default embedded model target.
- Update `setup`, `check:ai`, and `process` so they understand and prepare the MLX runtime path.
- Preserve `lmstudio` and `deterministic` as the remaining alternative providers.
- Keep the current screening-first architecture: cheap prefilter first, shortlist second, VLM last.

## Capabilities

### New Capabilities
- `mlx-vlm-local-backend`: direct Apple-Silicon-optimized local VLM inference using MLX / MLX-VLM.

### Modified Capabilities
- `ai-segment-understanding`: replace the embedded `moondream-local` provider with `mlx-vlm-local`.
- `processing-workflow`: update setup and AI health checks to bootstrap and validate the MLX runtime path.

## Impact

- Affected code:
  - `services/analyzer/app/ai.py`
  - setup/bootstrap scripts for local model preparation
  - `services/analyzer/scripts/check_ai_provider.py`
  - `scripts/setup.sh`
  - README and env examples
- Affected outputs:
  - `generated/process.log`
  - `generated/process-summary.txt`
- Dependencies and systems:
  - MLX / MLX-VLM runtime packages
  - Apple Silicon runtime assumptions
  - local model cache/download strategy for the embedded MLX model
