## 1. MLX Runtime Batching

- [ ] 1.1 Add a batch-capable `mlx-vlm-local` runtime path that can analyze multiple shortlisted segment images for one asset while retaining the current single-image fallback path.
- [ ] 1.2 Update `MLXVLMVisionLanguageAnalyzer.analyze_asset_segments()` to collect cached hits, submit one or more live MLX batch requests for pending segments, and fall back per segment when a batch item is missing or invalid.

## 2. Prompting And Normalization

- [ ] 2.1 Reuse or adapt the existing batch prompt contract for MLX so one batched response can be normalized back into per-segment understanding records.
- [ ] 2.2 Extend normalization and runtime stats so MLX batch responses preserve segment-level fallback visibility and request-level accounting.

## 3. Reporting And Benchmarks

- [ ] 3.1 Update process diagnostics and benchmark serialization to distinguish serialized-local execution from batched-local execution, including live segments versus live provider-call counts.
- [ ] 3.2 Ensure the benchmark comparison context stays honest when MLX batching changes effective execution behavior across runs.

## 4. Validation And Docs

- [ ] 4.1 Add analyzer tests covering MLX batched success, mixed cached/live batches, and partial-batch fallback behavior.
- [ ] 4.2 Verify benchmark and process-summary coverage with targeted tests and update analyzer/runtime documentation for the new MLX execution mode.
- [ ] 4.3 Verify the change with `python3 -m unittest discover services/analyzer/tests -v` and a representative `npm run process` run that reports batched-local MLX execution.
