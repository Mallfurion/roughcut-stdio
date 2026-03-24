# Delivery Roadmap

## Phase 0: Validate The Hard Parts

Objective:

Prove that proxy-first analysis is reliable enough to drive recommendations.

Build:

- media scanner
- proxy/source matcher
- metadata extractor
- basic scene detection prototype
- transcript extraction prototype
- silent-footage description prototype
- Resolve interchange validation on a tiny straight-cut timeline

Exit criteria:

- sample projects can be scanned end to end
- proxy matching confidence is measurable
- candidate segments can be generated consistently
- at least one exported test timeline imports into Resolve with correct order and trims

## Phase 1: Candidate Discovery MVP

Objective:

Find interesting regions quickly, even before "best take" logic is mature.

Build:

- project setup flow
- clip list with thumbnails and transcript excerpts
- visual descriptors for no-speech footage
- candidate segment generation
- quality metrics collection
- manual review and approve/reject flow

Exit criteria:

- users spend less time scrubbing whole clips
- the app reliably narrows footage down to reviewable candidates

## Phase 2: Best Take Recommendation

Objective:

Promote candidate segments into strong, explainable take recommendations.

Build:

- score model
- redundancy detection
- natural-language segment descriptions
- recommendation rationale UI
- configurable weighting by project style
- separate ranking heuristics for dialogue-led footage versus silent b-roll

Exit criteria:

- the app can recommend zero, one, or many takes per clip
- recommendations feel explainable rather than random

## Phase 3: Story Assembly And Preview

Objective:

Turn approved takes into a coherent first-pass rough cut.

Build:

- story prompt input
- role assignment for takes
- multi-variant sequence generator
- browser timeline preview
- background draft render from proxies
- Resolve export packaging from approved timeline state

Exit criteria:

- users can preview a story-like rough cut in the app
- users can reorder and trim without re-running full analysis
- users can export a Resolve-usable timeline package from the same state they previewed

## Phase 4: Export And Workflow Integration

Objective:

Make the output easy to continue inside the editing workflow.

Build:

- timeline JSON export hardening
- shot list export
- FCPXML export hardening and compatibility tests
- optional EDL fallback
- project history and timeline versioning

Exit criteria:

- shortlisted takes move cleanly into the editor's downstream workflow

## Technical Milestones

1. Working folder scan on real media
2. Candidate segmentation on proxies
3. Human-acceptable descriptions for speech and silent footage
4. Reliable best-take ranking
5. Rough timeline preview
6. Resolve-importable export package

## Suggested Delivery Order

If only one path should be pursued first, build in this order:

1. scanning and proxy matching
2. candidate segmentation
3. transcript-optional description generation
4. best-take ranking
5. story assembly
6. preview and export

This order reduces the chance of building a polished UI around weak analysis.

## Success Metrics

- reduction in manual review time per project
- precision of recommended takes after human review
- percentage of suggested takes kept by the editor
- time from import to first usable rough timeline
- number of manual corrections required for proxy matching
- percentage of exported timelines that import cleanly into Resolve without manual repair
