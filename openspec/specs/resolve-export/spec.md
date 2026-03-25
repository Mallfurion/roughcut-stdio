# resolve-export Specification

## Purpose
TBD - created by archiving change init-deterministic-pass. Update Purpose after archive.
## Requirements
### Requirement: System SHALL export the generated timeline as `FCPXML`
The system SHALL continue to export the current generated project timeline into an `FCPXML` document for Resolve handoff, but the primary user-facing export flow SHALL be initiated from the desktop app.

#### Scenario: User exports from the desktop app
- **WHEN** the user triggers Resolve timeline export from the desktop app after processing
- **THEN** the app SHALL write an `FCPXML` file to the user-selected save location

#### Scenario: Desktop export follows reviewed results
- **WHEN** the desktop review surface shows processed project results
- **THEN** the export action SHALL operate on that active generated project state

### Requirement: Export SHALL support source-only and proxy-backed assets
The exporter SHALL work whether an asset has a matched proxy or only a source file, and SHALL preserve relinkable metadata such as file path, reel name, frame rate, and source timecode when known.

#### Scenario: Timeline uses source-only footage
- **WHEN** a selected segment comes from an asset without a proxy
- **THEN** the exported timeline SHALL still reference the source media path for that segment

#### Scenario: Asset has normalized interchange metadata
- **WHEN** an asset includes reel name and source timecode data
- **THEN** the exporter SHALL carry that metadata into the generated interchange where supported

