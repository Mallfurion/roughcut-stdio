## ADDED Requirements

### Requirement: Packaged processing SHALL preserve fallback behavior when optional packs are absent
The packaged processing workflow SHALL preserve deterministic or reduced-capability fallback behavior when an optional runtime pack required for a configured capability is not installed or not ready.

#### Scenario: Configured capability needs an absent optional runtime pack
- **WHEN** the packaged app is configured for transcript, CLIP, or MLX-VLM behavior that depends on an uninstalled optional runtime pack
- **THEN** the workflow SHALL disclose that the pack is missing
- **THEN** processing SHALL either install the required pack or fall back to the supported deterministic or reduced-capability path instead of failing silently

### Requirement: Packaged processing SHALL verify payload composition during release checks
The packaged processing runtime SHALL participate in release verification that checks the composition and size of the shipped core runtime and optional packs.

#### Scenario: Packaged runtime verification runs
- **WHEN** packaged runtime verification is executed for a release build
- **THEN** the verification SHALL report the size and composition of the core runtime payload
- **THEN** the verification SHALL report the size and composition of optional runtime packs when they are staged
