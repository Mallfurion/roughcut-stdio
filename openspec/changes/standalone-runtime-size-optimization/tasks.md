## 1. Payload Audit And Runtime Boundaries

- [ ] 1.1 Audit the current packaged runtime contents and classify dependencies into deterministic core, transcript pack, CLIP pack, MLX-VLM pack, or removable dead weight.
- [ ] 1.2 Define and persist package manifests for the shipped core payload and each optional runtime pack.
- [ ] 1.3 Set initial bundle-size budgets for the core payload and optional packs.

## 2. Runtime Build Changes

- [ ] 2.1 Replace whole-`.venv` packaging with an explicit runtime-only packaged Python environment for the deterministic core.
- [ ] 2.2 Move heavyweight transcript, CLIP, and MLX-VLM dependencies into separately staged optional runtime packs.
- [ ] 2.3 Prune packaged Python-home content that is not required at runtime, including docs, headers, and unused GUI/support assets where safe.

## 3. Desktop Runtime UX

- [ ] 3.1 Update packaged runtime readiness reporting to distinguish installed core runtime from installable optional packs.
- [ ] 3.2 Add desktop actions to install optional runtime packs when the user enables a capability that requires them.
- [ ] 3.3 Preserve and verify deterministic or reduced-capability fallback behavior when optional packs are absent.

## 4. Verification And Documentation

- [ ] 4.1 Extend packaged runtime verification to report payload composition, largest dependencies, and size-budget regressions.
- [ ] 4.2 Add smoke coverage for deterministic core processing plus per-pack installation or availability checks.
- [ ] 4.3 Document the new payload model, optional pack behavior, and bundle-size budgets for desktop releases.
