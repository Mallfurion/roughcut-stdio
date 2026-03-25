# Changelog

## [Unreleased]

## [1.1.0] - 2026-03-25

### 🚀 Features
- Add Phase 1 AI detection capabilities for segment understanding.
- Add the vision prefilter pipeline to shortlist segments before VLM analysis.
- Add `moondream-local` setup as an intermediate embedded local VLM backend.
- Add `mlx-vlm-local` support and align the local MLX-VLM workflow.
- Implement the Tauri desktop app for folder selection, processing, review, and Resolve export.

### 🛠 Fixes & Improvements
- Improve process logging and AI runtime reporting.
- Consolidate docs into `docs/` and OpenSpec, and update the desktop-first workflow documentation.
- Refresh general documentation and configuration guidance.

### 📦 Other
- Rename the product to Roughcut Stdio.
- Add a repo-local `release` skill for semantic-versioned releases and changelog generation.

## [1.0.0] - 2026-03-24

### 🚀 Features
- Initial implementation of the local footage analysis and timeline generation workflow.

### 🛠 Fixes & Improvements
- Allow processing footage without proxy files.
- Fix timeline encoding and add environment-variable media folder support.
- Add project versioning for the first tagged release.
