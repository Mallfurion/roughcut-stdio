## ADDED Requirements

### Requirement: System SHALL include transcript context in segment evidence when available
The analyzer SHALL include transcript excerpts in persisted segment evidence and AI understanding prompts when transcript-backed analysis is available. When transcript-backed analysis is unavailable, the analyzer SHALL persist explicit fallback context rather than silently omitting the distinction.

#### Scenario: Transcript excerpt exists for a segment
- **WHEN** a candidate segment has a non-empty transcript excerpt
- **THEN** the persisted evidence bundle SHALL include that excerpt
- **THEN** AI understanding prompts and persisted understanding context SHALL use that transcript excerpt

#### Scenario: Speech-aware fallback is used without transcript text
- **WHEN** a segment is treated as speech-relevant through fallback behavior and transcript text is unavailable
- **THEN** the persisted evidence or review metadata SHALL indicate that speech fallback was used without transcript-backed text
- **THEN** downstream inspection SHALL be able to distinguish this case from a truly silent visual segment

#### Scenario: Transcript extraction is selectively skipped for an asset
- **WHEN** transcript support is enabled but the analyzer skips or rejects transcript extraction for an asset through selective targeting or probing
- **THEN** persisted segment review metadata SHALL indicate that transcript extraction was selectively skipped
- **THEN** downstream inspection SHALL be able to distinguish that case from provider-disabled, provider-unavailable, and excerpt-available states
