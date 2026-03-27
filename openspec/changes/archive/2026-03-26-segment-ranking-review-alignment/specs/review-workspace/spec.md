## MODIFIED Requirements

### Requirement: Web app SHALL expose recommended segments and timeline state
The review experience SHALL present recommended takes, segment descriptions, scoring context, asset metadata, and rough timeline state in the desktop application as the primary product surface. For each candidate segment, the desktop review surface SHALL combine recommendation outcome with analysis-path details so the editor can see what was analyzed, what was calculated, and why the segment won, lost, or was blocked.

#### Scenario: Desktop review shows a winning segment
- **WHEN** the generated project contains a segment whose recommendation outcome is the winning take for its asset
- **THEN** the desktop UI SHALL display its recommendation status, total score, technical score, semantic score, story score, and review-facing explanation of why it won

#### Scenario: Desktop review shows a non-winning segment
- **WHEN** the generated project contains a segment that is an alternate or backup rather than the winning take
- **THEN** the desktop UI SHALL display its recommendation status, within-asset rank, score gap to the winner, and explanation of why it did not win

#### Scenario: Desktop review shows analysis-path state
- **WHEN** the generated project contains a candidate segment with screening or analysis status such as shortlist, deduplication, CLIP gate, VLM budget cap, or model-backed evidence
- **THEN** the desktop UI SHALL display a concise analysis-path summary for that segment without requiring the user to inspect process logs
