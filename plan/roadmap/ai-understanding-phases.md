# AI Understanding Migration Phases

## Goal

Replace placeholder ranking with real multimodal editorial understanding in controlled phases, without breaking the existing `setup / process / view / export` workflow.

## Phase 1: Replace Synthetic Metrics With Real Segment Understanding

Objective:

Generate segment-level understanding from real evidence instead of hash-based placeholder metrics.

Build:

- keyframe extraction per segment
- evidence bundle builder
- structured segment-understanding schema
- provider adapter for local or cloud multimodal inference
- first local provider path using LM Studio
- persistence of model outputs into `project.json`
- web UI surface for AI summary, role, confidence, and rationale

Constraints:

- keep existing scene detection and export flow intact
- if the AI provider fails, preserve deterministic fallback behavior

Exit criteria:

- each candidate segment has real descriptive output
- editors can see why the model thinks a segment is strong or weak
- silent footage receives useful descriptions without transcript dependency

## Phase 2: Intra-Clip Best Take Ranking

Objective:

Choose the strongest moment inside each clip using comparative judgment, not only scalar scores.

Build:

- pairwise comparison prompts for segments from the same clip
- redundancy detection across adjacent segments
- keep / maybe / reject labels
- configurable thresholds for auto-selection versus review
- ranking explanation UI

Constraints:

- compare a bounded number of top candidates per clip to control cost
- keep deterministic tie-break rules

Exit criteria:

- the app can recommend zero, one, or many takes per clip based on model comparison
- backup candidates remain visible
- recommendations feel editorially grounded

## Phase 3: Cross-Clip Story Role Assignment

Objective:

Understand what function each selected segment can play in a sequence.

Build:

- role taxonomy: opener, setup, bridge, detail, escalation, payoff, outro
- role-classification prompt
- chronology-aware and chronology-relaxed modes
- visual repetition detection across the project
- shortlist construction for each role

Constraints:

- chronology should remain the default mode
- role assignment should be explainable and editable

Exit criteria:

- the system can explain why a shot is an opener, bridge, or payoff
- repetitive clips are actively filtered or downgraded

## Phase 4: AI Story Assembly

Objective:

Assemble rough-cut variants from shortlisted segments.

Build:

- story-planner prompt using shortlisted structured segments
- 1 to 3 timeline variants
- rationale per variant
- pacing controls: visual-first, dialogue-first, balanced
- editor choice between variants before export

Constraints:

- planning works only on vetted shortlisted segments, never on raw clip inventory
- export and trim bounds stay deterministic

Exit criteria:

- the app produces coherent timeline variants
- users can preview and compare them without rerunning full media analysis

## Phase 5: Human Feedback Loop

Objective:

Learn from editor overrides and improve the ranking/planning behavior.

Build:

- manual relabeling of best takes
- accept / reject / replace event logging
- override-aware analytics
- project-style presets
- optional fine-tuning dataset export

Constraints:

- user overrides must always win immediately
- collected feedback must be separable by project type

Exit criteria:

- repeated use improves selection relevance
- style presets become possible for different edit types

## Phase 6: Production Hardening

Objective:

Make the AI layer reliable enough for regular project use.

Build:

- LM Studio connection checks and model capability detection
- batched analysis jobs
- cache invalidation rules
- schema versioning for AI outputs
- fallback and retry policy
- evaluation suite on reference projects

Constraints:

- local-first remains the default
- cloud providers remain optional adapters, not required dependencies

Exit criteria:

- process runs are reproducible
- provider outages or malformed outputs do not break the pipeline
- users can switch between local and cloud inference without changing the rest of the app

## Delivery Notes

Recommended implementation order:

1. structured segment understanding
2. intra-clip comparative ranking
3. story-role assignment
4. timeline-variant planning
5. feedback loop
6. production hardening

Do not start with full-sequence planning. The project needs trustworthy segment understanding first.
