## Context

The standalone desktop app currently stages a packaged Python home plus site-packages by copying broad runtime content out of the local development environment. The resulting bundle is dominated by the Python payload rather than the Tauri shell or media sidecars. A recent staged bundle showed roughly:

- packaged runtime total: about 1.9 GB
- Python home: about 518 MB
- site-packages: about 1.3 GB
- largest packages: `torch`, `mlx`, `pyarrow`, `cv2`, `transformers`, `sympy`, `pandas`, `onnxruntime`

That means the practical size problem is not “Tauri vs Rust” first. It is that the packaged runtime currently ships a broad Python environment with heavyweight optional ML dependencies already included, even when the installed app only needs deterministic processing and export on day one.

## Goals / Non-Goals

**Goals:**
- Reduce the initial packaged app size substantially without removing deterministic processing or Resolve export.
- Keep the installed app immediately usable for deterministic processing after install.
- Move heavy optional capabilities into explicit downloadable runtime packs.
- Replace whole-environment packaging with a runtime-only packaged Python payload.
- Add measurable bundle-size budgets and verification to release builds.

**Non-Goals:**
- Rewriting the analyzer core in Rust as part of this change.
- Removing optional transcript, CLIP, or MLX-VLM capabilities entirely.
- Changing analyzer scoring, segmentation, or export semantics.
- Introducing network requirements for deterministic core processing after install.

## Decisions

### 1. Ship a deterministic core bundle and move heavy features into runtime packs

The packaged app will ship only the runtime required for:
- desktop launch
- deterministic processing
- generated artifact writing
- Resolve export
- media probing/extraction via `ffmpeg` and `ffprobe`

Heavy optional capabilities will be packaged as installable runtime packs:
- transcript pack
- CLIP pack
- MLX-VLM pack

Rationale:
- Deterministic processing is the non-negotiable offline baseline.
- Heavy optional features are the main bundle-size drivers and are already conceptually bootstrapped assets.

Alternatives considered:
- Keep bundling everything and only prune around the edges: rejected because the biggest wins come from not shipping heavyweight optional runtimes up front.
- Rewrite analyzer orchestration in Rust first: rejected because it does not remove the heavyweight ML/runtime stack by itself.

### 2. Build a runtime-only packaged Python environment instead of copying the whole development environment

The packaged app build will construct runtime payloads from explicit dependency sets for:
- core deterministic/export runtime
- transcript pack
- CLIP pack
- MLX-VLM pack

The build must stop copying the entire local `.venv` into the packaged payload.

Rationale:
- The current staging approach pulls in broad dependencies that are not all needed in the shipped app.
- Pack-specific dependency sets make it possible to reason about and verify payload composition.

Alternatives considered:
- Continue copying `.venv` and delete files heuristically afterward: rejected because it is harder to reason about and more fragile over time.

### 3. Prune the packaged Python home aggressively

The packaged Python home will exclude content not needed for runtime execution, including where safe:
- docs
- manpages
- headers
- test data
- GUI/Tk/Tcl frameworks if the runtime does not use them
- development metadata not needed for execution

Rationale:
- The staged Python home currently contains substantial non-runtime content.
- This is a low-risk size win compared with behavioral changes.

Alternatives considered:
- Leave Python home untouched: rejected because it preserves obvious dead weight.

### 4. Make payload composition explicit through manifests and budgets

Each packaged runtime component will declare:
- included dependency set
- pack name/version
- whether it is shipped in core or downloaded on demand
- size budget or ceiling for verification

Release verification will report:
- core bundle size
- per-pack size
- largest packaged dependencies
- failures when agreed budgets are exceeded

Rationale:
- Bundle growth is otherwise too easy to miss until late in release packaging.
- Explicit budgets make optimization an enforced behavior, not a one-off cleanup.

### 5. Keep fallback behavior explicit when requested packs are not installed

If the configured runtime mode requires an optional pack that is not installed:
- transcript pack missing -> transcript-disabled fallback remains available where supported
- CLIP pack missing -> CLIP-disabled fallback remains available
- MLX-VLM pack missing -> deterministic fallback remains available

The desktop UI must distinguish shipped core runtime from installable optional packs.

Rationale:
- Size reduction must not degrade the local-first fallback contract.

## Risks / Trade-offs

- [Pack split increases packaging complexity] -> Use explicit pack manifests and shared verification instead of ad hoc downloads.
- [Dependency trimming could accidentally remove required runtime files] -> Add smoke tests for deterministic core, transcript pack, CLIP pack, and MLX-VLM pack separately.
- [Users may be surprised that some features are not installed initially] -> Make the startup/runtime UI explicit about shipped core vs optional installs.
- [Core deterministic bundle may still be larger than desired] -> Combine pack splitting with Python-home pruning and runtime-only dependency sets.
- [Some heavy dependencies may be transitively required by current package choices] -> Audit actual runtime imports and refactor dependency groups where needed.

## Migration Plan

1. Audit the current packaged payload and classify dependencies into core vs optional packs.
2. Introduce explicit build-time runtime payload definitions instead of copying the full `.venv`.
3. Prune Python home and runtime payload content for the shipped core bundle.
4. Move transcript, CLIP, and MLX-VLM support into installable runtime packs.
5. Update desktop runtime/bootstrap UX to show installed packs and install missing ones on demand.
6. Add size-budget reporting and release verification for core and optional packs.

## Open Questions

- Should CLIP remain part of the initial installed experience if its package footprint turns out to be small after dependency auditing, or should it still move to an optional pack for conceptual consistency?
- Do we want one shared Python interpreter across core and optional packs, or separate pack-specific embedded environments?
- What target size budget do we want for the initial core macOS bundle?
