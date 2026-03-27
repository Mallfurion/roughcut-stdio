## 1. Runtime Diagnostics

- [x] 1.1 Audit current transcript, semantic, cache, and AI fallback statuses across process artifacts.
- [x] 1.2 Add clearer structured degraded-mode and gating statuses where current reporting is ambiguous.
- [x] 1.3 Ensure process outputs distinguish intentional skips from failures and fallback transitions.

## 2. Benchmark Context

- [x] 2.1 Extend benchmark artifacts with cache, gating, and degraded-runtime context.
- [x] 2.2 Update run-to-run comparisons so they explain capability changes, not only runtime deltas.
- [x] 2.3 Add regression tests for benchmark serialization of runtime-stability context.

## 3. Desktop Runtime Visibility

- [x] 3.1 Surface clearer runtime readiness and degraded-mode status in the desktop workflow.
- [x] 3.2 Verify that user-facing runtime state stays concise while preserving richer diagnostics in generated artifacts.
- [x] 3.3 Add tests for fallback-safe desktop runtime reporting where applicable.
