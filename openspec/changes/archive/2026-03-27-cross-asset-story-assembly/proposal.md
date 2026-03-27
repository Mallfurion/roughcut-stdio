## Why

The analyzer is now much better at producing usable units within one asset, but the rough timeline still mostly picks good clips independently. The next step is to improve how segments relate to each other across assets.

## What Changes

- Add project-level story-assembly logic that scores relationships across assets instead of only within a clip.
- Improve rough-timeline ordering and grouping based on sequence-level continuity, diversity, and role fit.
- Surface sequence-level rationale in the review workspace.

## Capabilities

### New Capabilities
- `story-assembly`: Assemble recommended units into a stronger multi-asset rough-cut sequence.

### Modified Capabilities
- `processing-workflow`: Process output must report story-assembly decisions when project-level ordering is active.
- `review-workspace`: Review must show sequence-level rationale, not only local segment rationale.

## Impact

- Analyzer take selection and timeline assembly
- Generated timeline state and summaries
- Desktop review presentation for story order
