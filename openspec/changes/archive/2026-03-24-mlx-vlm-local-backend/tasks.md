## 1. Provider Replacement

- [x] 1.1 Remove `moondream-local` provider support from the analyzer and scripts
- [x] 1.2 Add `mlx-vlm-local` provider support
- [x] 1.3 Preserve `lmstudio` and deterministic fallback behavior

## 2. Runtime Integration

- [x] 2.1 Add an MLX / MLX-VLM runtime adapter for shortlisted-segment image analysis
- [x] 2.2 Configure the default embedded model as Qwen 3.5 0.8B for the MLX path
- [x] 2.3 Normalize MLX outputs into the existing `SegmentUnderstanding` schema

## 3. Setup And Health Check

- [x] 3.1 Update `npm run setup` to install MLX runtime dependencies and prepare the embedded model
- [x] 3.2 Update `npm run check:ai` to validate the MLX backend
- [x] 3.3 Update process logging with effective MLX backend details

## 4. Documentation And Config

- [x] 4.1 Remove Moondream env/config examples
- [x] 4.2 Add MLX env/config examples
- [x] 4.3 Make `mlx-vlm-local` the recommended embedded backend in the docs

## 5. Validation

- [x] 5.1 Add or update tests for provider selection and fallback behavior
- [x] 5.2 Verify `python3 -m unittest discover services/analyzer/tests -v`
- [x] 5.3 Verify `npm run build:web`
