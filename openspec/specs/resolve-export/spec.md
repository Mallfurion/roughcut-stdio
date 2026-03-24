# resolve-export Specification

## Purpose
TBD - created by archiving change init-deterministic-pass. Update Purpose after archive.
## Requirements
### Requirement: System SHALL export the generated timeline as `FCPXML`
The repository SHALL export the current generated project timeline into an `FCPXML` document that preserves clip order, source references, and trim ranges for Resolve handoff.

#### Scenario: User runs export after processing
- **WHEN** `generated/project.json` exists and the user runs `npm run export`
- **THEN** the repository SHALL write `generated/timeline.fcpxml`

#### Scenario: Timeline contains multiple selected segments
- **WHEN** the generated project contains several timeline items
- **THEN** the exported `FCPXML` SHALL preserve their order and trim ranges

### Requirement: Export SHALL support source-only and proxy-backed assets
The exporter SHALL work whether an asset has a matched proxy or only a source file, and SHALL preserve relinkable metadata such as file path, reel name, frame rate, and source timecode when known.

#### Scenario: Timeline uses source-only footage
- **WHEN** a selected segment comes from an asset without a proxy
- **THEN** the exported timeline SHALL still reference the source media path for that segment

#### Scenario: Asset has normalized interchange metadata
- **WHEN** an asset includes reel name and source timecode data
- **THEN** the exporter SHALL carry that metadata into the generated interchange where supported

