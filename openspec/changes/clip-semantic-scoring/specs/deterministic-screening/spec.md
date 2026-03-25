## MODIFIED Requirements

### Requirement: System SHALL produce deterministic take recommendations from candidate segments
The deterministic scoring path SHALL incorporate `clip_score` as a semantic input when it is present in the segment's prefilter metrics snapshot.

#### Scenario: clip_score is present in the metrics snapshot
- **WHEN** CLIP scoring was active and produced a `clip_score` for a segment
- **THEN** `scoring.py` SHALL include `clip_score` as a weighted input in the semantic score path
- **THEN** a segment with a high `clip_score` SHALL score higher than an otherwise identical segment with a low `clip_score`

#### Scenario: clip_score is absent from the metrics snapshot
- **WHEN** CLIP was not enabled or scoring did not produce a result for a segment
- **THEN** `scoring.py` SHALL compute the score using only the existing visual and audio inputs
- **THEN** scoring behavior SHALL be identical to the pre-CLIP baseline
