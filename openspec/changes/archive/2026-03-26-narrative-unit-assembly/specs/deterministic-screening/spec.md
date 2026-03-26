## MODIFIED Requirements

### Requirement: System SHALL generate candidate segments for each valid asset
The analyzer SHALL generate candidate segments for each valid asset using scene detection when available and SHALL refine those candidates with a low-cost visual prefilter stage that uses sampled frame or window evidence to identify promising regions. The analyzer SHALL first construct seed regions, SHALL deterministically refine those seed regions, SHALL assemble the refined regions into final narrative units when continuity evidence exists, and SHALL use those assembled units as the candidate segments that reach downstream shortlist and recommendation logic.

#### Scenario: Continuity evidence exists between adjacent refined regions
- **WHEN** adjacent refined regions from the same asset satisfy the assembly rules for one narrative unit
- **THEN** the analyzer SHALL merge them before candidate scoring and shortlist selection

#### Scenario: No continuity evidence exists
- **WHEN** refined regions do not satisfy merge or split rules
- **THEN** the analyzer SHALL keep the deterministically refined regions as the final candidate segments
