## MODIFIED Requirements

### Requirement: System SHALL generate candidate segments for each valid asset
The analyzer SHALL generate candidate segments for each valid asset using scene detection when available and SHALL refine those candidates with a low-cost visual prefilter stage that uses sampled frame or window evidence to identify promising regions. The analyzer SHALL first construct seed regions, SHALL deterministically refine those seed regions, SHALL assemble the refined regions into final narrative units when continuity evidence exists, and SHALL use those assembled units as the candidate segments that reach downstream shortlist and recommendation logic. The deterministic screening inputs used for that candidate generation MAY be prepared through batched local frame or audio extraction instead of one-process-per-sample work. When `artifacts_root` is available, the analyzer SHALL also be allowed to persist and reuse compatible deterministic preprocessing artifacts, including scene boundaries, sampled frame signals, and sampled audio signals, so repeated runs can avoid rebuilding unchanged screening inputs. Missing, stale, or incompatible preprocessing artifacts SHALL be rebuilt automatically, and deterministic fallback SHALL remain available when reusable artifacts are unavailable.

#### Scenario: Scene detection is available
- **WHEN** the runtime can use `PySceneDetect`
- **THEN** initial seed regions SHALL be derived from detected scene boundaries and other promising low-cost signals
- **THEN** those seed regions SHALL be deterministically refined into candidate segments before downstream shortlist decisions are made

#### Scenario: Scene detection is unavailable
- **WHEN** `PySceneDetect` is unavailable or produces no scenes
- **THEN** the analyzer SHALL generate fallback seed regions for the asset
- **THEN** the analyzer SHALL still refine those fallback seed regions into bounded candidate segments using available local structure

#### Scenario: Continuity evidence exists between adjacent refined regions
- **WHEN** adjacent refined regions from the same asset satisfy the assembly rules for one narrative unit
- **THEN** the analyzer SHALL merge them before candidate scoring and shortlist selection

#### Scenario: No continuity evidence exists
- **WHEN** refined regions do not satisfy merge or split rules
- **THEN** the analyzer SHALL keep the deterministically refined regions as the final candidate segments

#### Scenario: Compatible preprocessing artifacts already exist
- **WHEN** a repeated process run encounters compatible persisted scene, frame, or audio screening artifacts for an asset
- **THEN** the analyzer SHALL be allowed to reuse those artifacts instead of rebuilding the same deterministic preprocessing inputs
- **THEN** downstream candidate generation SHALL continue to behave as if those inputs had been freshly produced for the same asset and screening configuration

#### Scenario: Preprocessing artifacts are missing or stale
- **WHEN** deterministic preprocessing artifacts are missing, incompatible, or stale for an asset
- **THEN** the analyzer SHALL rebuild the required screening inputs automatically
- **THEN** the absence of reusable artifacts SHALL not fail the process run or disable deterministic candidate generation

#### Scenario: Batched extraction prepares deterministic screening inputs
- **WHEN** the analyzer prepares frame or audio screening inputs for an asset
- **THEN** it SHALL be allowed to batch that local extraction work into one bounded per-asset screening path instead of paying one subprocess per sample
- **THEN** downstream seed-region, transcript-targeting, and candidate-generation logic SHALL continue to receive deterministic screening inputs for the same sampled asset
