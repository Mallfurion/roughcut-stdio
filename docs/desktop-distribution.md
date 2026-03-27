# Desktop Distribution

## Runtime Modes

Roughcut Stdio now runs in two distinct desktop modes:

- **Repository development mode** uses the checked-out repo, `.env`, `.venv`, and the existing shell-script workflow for local development and debugging.
- **Packaged app mode** uses bundled desktop resources plus app-managed storage. It does not require a checked-out repository, host Python, or Homebrew `ffmpeg`.

The packaged desktop backend now owns runtime checks, setup/bootstrap, process execution, and Resolve export orchestration.

## Bundled Runtime

The packaged desktop build bundles these runtime components inside the app resources:

- Python runtime
- analyzer site-packages and Python entrypoints
- analyzer/export scripts under `services/`
- `ffmpeg`
- `ffprobe`
- bundled sample project/fixtures used by the review shell

The Tauri build stages those resources under `apps/desktop/src-tauri/.runtime-bundle/` during packaging, and packaged mode copies the executable sidecars into an app-owned runtime directory before use.

## Packaged Storage

Packaged mode uses Tauri app directories instead of repository paths.

On macOS these are typically rooted under the app identifier `com.roughcutstdio.desktop`:

- **Config**: `~/Library/Application Support/com.roughcutstdio.desktop/runtime.env`
- **Generated data**: `~/Library/Application Support/com.roughcutstdio.desktop/generated/`
- **Model storage**: `~/Library/Application Support/com.roughcutstdio.desktop/models/`
- **Runtime cache / staged sidecars**: `~/Library/Caches/com.roughcutstdio.desktop/runtime/{bin,lib}`
- **Model caches**: `~/Library/Caches/com.roughcutstdio.desktop/` via `HF_HOME`, `HF_HUB_CACHE`, `TORCH_HOME`, and `XDG_CACHE_HOME`
- **Logs**: `~/Library/Logs/com.roughcutstdio.desktop/`

Packaged generated output keeps the same artifact shapes the review flow expects:

- `generated/project.json`
- `generated/process.log`
- `generated/process-summary.txt`
- `generated/process-output.txt`
- `generated/benchmarks/history.jsonl`
- `generated/timeline.fcpxml`
- `generated/best-take-overrides.json`

Only the storage root changes in packaged mode.

## Startup Bootstrap

Packaged startup distinguishes:

- **Bundled runtime readiness**: whether the app has the bundled Python/analyzer/`ffmpeg` stack it needs
- **Model asset readiness**: whether the configured workflow has the model assets it expects

The startup bootstrap screen shows:

- default packaged workflow assets
- provider-specific assets
- missing assets for the current workflow
- a download action to prepare missing assets
- a re-check action
- a fallback action when the missing assets can be skipped by changing settings

## Default And Optional Assets

The packaged default workflow currently treats these as first-run model assets when enabled:

- CLIP semantic scoring weights
- transcript model assets for the selected transcript size

Provider-specific assets are currently:

- MLX-VLM model assets for the configured `TIMELINE_AI_MODEL_ID` when `mlx-vlm-local` is selected

## Fallback Behavior

When optional or skippable assets are unavailable, packaged mode can continue in a reduced-capability configuration instead of dead-ending the app:

- missing transcript assets -> disable transcript extraction
- missing CLIP assets -> disable CLIP semantic scoring
- missing MLX-VLM assets -> switch the provider to deterministic mode

Those changes are persisted through packaged settings storage and re-checked immediately.

## Verification

Use the packaged runtime verifier before cutting a desktop release:

```bash
apps/desktop/scripts/verify_packaged_runtime.sh
```

It verifies:

- staged packaged runtime resources build successfully
- bundled `ffmpeg` can generate test media
- packaged deterministic runtime checks work with transcript disabled
- packaged processing can run without repo `.venv` or Homebrew `ffmpeg`
- Resolve export still produces FCPXML
- staged media tools no longer link to `/opt/homebrew`

## Release Checklist

Before shipping a packaged desktop build:

1. Run `npm run build:desktop`.
2. Run `apps/desktop/scripts/verify_packaged_runtime.sh`.
3. Launch the packaged app with fresh cache/model directories and verify the bootstrap screen appears when expected.
4. Verify both bootstrap success and the fallback-settings path from the startup screen.
5. Sign the packaged app and bundled sidecars.
6. Notarize the macOS app bundle.
7. Re-run a packaged launch smoke test after signing/notarization.
