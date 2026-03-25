## 1. Desktop Foundation

- [x] 1.1 Add a Tauri app workspace for the new desktop product
- [x] 1.2 Define desktop application state for media folder, AI mode, process state, review state, and export state
- [x] 1.3 Stop treating the current web app as the primary product surface

## 2. Pre-Launch Setup

- [x] 2.1 Keep provider/runtime configuration outside the desktop app through env configuration
- [x] 2.2 Keep setup as a terminal pre-launch workflow that installs shared requirements and the embedded MLX path by default
- [ ] 2.3 Document the desktop pre-launch workflow clearly in the product docs

## 3. Media And Process Flow

- [x] 3.1 Add native folder selection for the media root
- [x] 3.2 Implement desktop process launch against the Python analyzer
- [x] 3.3 Add process progress updates for asset counts, current asset, and completion state
- [x] 3.4 Render visual process progress in the desktop UI
- [x] 3.5 Add per-run AI mode selection for `fast` and `full`
- [ ] 3.6 Replace stdout parsing with a stable machine-readable progress protocol

## 4. Review Flow

- [x] 4.1 Build a desktop review surface around clips, sections, scores, rationale, and metadata
- [x] 4.2 Load processed project state into the desktop app after successful runs
- [x] 4.3 Replace browser-only review assumptions with desktop review assumptions in the product workflow
- [x] 4.4 Make clips collapsible and show per-section VLM output when opened
- [ ] 4.5 Refine the section review presentation further as VLM output quality improves

## 5. Export Flow

- [x] 5.1 Add desktop export action for Resolve timeline export
- [x] 5.2 Use a native save dialog to choose the export destination
- [x] 5.3 Keep `FCPXML` as the exported Resolve handoff format

## 6. Validation

- [x] 6.1 Add or update tests/build checks for desktop orchestration boundaries where practical
- [ ] 6.2 Validate the OpenSpec change
- [ ] 6.3 Validate the new desktop-first workflow against the analyzer pipeline end to end
