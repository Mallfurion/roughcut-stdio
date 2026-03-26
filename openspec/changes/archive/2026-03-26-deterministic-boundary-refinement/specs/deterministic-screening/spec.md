## MODIFIED Requirements

### Requirement: System SHALL generate candidate segments for each valid asset
The analyzer SHALL generate candidate segments for each valid asset using scene detection when available and SHALL refine those candidates with a low-cost visual prefilter stage that uses sampled frame or window evidence to identify promising regions. The analyzer SHALL first construct seed regions, SHALL deterministically refine those seed regions into candidate segments before downstream shortlist decisions are made, and SHALL still produce bounded fallback seed regions when scene detection is not available or yields no segments.

#### Scenario: Scene detection is available
- **WHEN** the runtime can use `PySceneDetect`
- **THEN** initial seed regions SHALL be derived from detected scene boundaries and other promising low-cost signals
- **THEN** those seed regions SHALL be deterministically refined into candidate segments before downstream shortlist decisions are made

#### Scenario: Scene detection is unavailable
- **WHEN** `PySceneDetect` is unavailable or produces no scenes
- **THEN** the analyzer SHALL generate fallback seed regions for the asset
- **THEN** the analyzer SHALL still refine those fallback seed regions into bounded candidate segments using available local structure
