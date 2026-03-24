# AI Understanding Pipeline

## Objective

Move the project from deterministic placeholder scoring to real multimodal understanding, while keeping timeline export, manual override, and local-first execution stable.

The key principle is:

- `AI decides meaning`
- `rules enforce safety, bounds, and export correctness`

## Current Gap

Today the pipeline already does:

- media discovery
- proxy/source matching
- metadata extraction
- candidate segmentation
- deterministic ranking
- rough timeline assembly
- Resolve export

What it does not yet do well:

- understand what is happening in a shot
- distinguish visually redundant shots from truly distinct ones
- decide story role from content rather than position
- rank clips based on actual narrative or editorial value
- explain selections from real evidence

## Target Architecture

Use a layered decision stack.

### Layer 1: Deterministic Extraction

Keep these rule-based and measurable:

- file discovery
- source/proxy matching
- frame rate, duration, resolution, timecode extraction
- scene boundaries
- transcript extraction when speech exists
- keyframe extraction
- audio feature extraction
- export-safe trim limits

These are infrastructure, not editorial intelligence.

### Layer 2: Segment Understanding

For each candidate segment, generate an evidence bundle:

- 3 to 8 representative keyframes
- optional low-resolution video excerpt
- transcript excerpt if available
- low-level visual/audio metrics
- clip metadata
- neighboring segment context
- project story prompt

Feed that evidence into a multimodal model and request structured output.

Suggested output schema:

```json
{
  "summary": "People gather near an outdoor stage while the camera drifts across the crowd.",
  "subjects": ["crowd", "event attendees", "stage area"],
  "actions": ["standing", "watching", "moving through the frame"],
  "shot_type": "wide",
  "camera_motion": "slow pan",
  "mood": "anticipatory",
  "story_roles": ["opener", "bridge"],
  "visual_distinctiveness": 0.78,
  "clarity": 0.71,
  "story_relevance": 0.66,
  "keep_label": "maybe",
  "keep_reason": "Useful atmosphere and context, but not the strongest payoff shot.",
  "risks": ["slightly repetitive with other crowd coverage"]
}
```

### Layer 3: Pairwise Or Setwise Ranking

Do not rely only on independent segment scores.

Add a ranking pass that compares:

- segments from the same source clip
- visually similar segments across the project
- candidates for opener / bridge / payoff / outro roles

This pass should answer:

- which candidate is strongest inside a clip
- which candidates are redundant with one another
- which candidates best satisfy the story prompt

### Layer 4: Story Assembly

Use an AI planner to assemble from already-ranked segments, not from raw media.

Inputs:

- shortlisted segments
- their structured understanding output
- the project story prompt
- desired pacing style
- chronology preference

Outputs:

- ordered rough-cut candidates
- assigned story roles
- rationale for ordering
- possible alternate variants

### Layer 5: Deterministic Guardrails

Always keep these outside the model:

- source path and proxy path integrity
- source timecode validity
- trim bounds inside available media duration
- max suggested segment duration
- duplicate timeline item prevention
- export validation for Resolve

## Model Runtime Strategy

Support a provider adapter boundary instead of binding the project to one model backend.

### Provider Modes

- `local_vlm`
  - default local multimodal model via LM Studio
- `local_text`
  - local text model for ranking/planning only, paired with deterministic visual features
- `cloud_vlm`
  - optional hosted multimodal model for stronger reasoning
- `hybrid`
  - local vision tagging + cloud ranking/planning

### LM Studio Role

LM Studio is a strong fit for local-first execution because it can expose an OpenAI-compatible API and run local multimodal or text models.

Use it for:

- segment descriptions
- story-role tagging
- pairwise ranking prompts
- timeline-assembly prompts

Do not depend on it for:

- clip discovery
- scene detection
- frame extraction
- timecode logic
- export generation

### Provider Abstraction

Add a dedicated adapter such as:

- `VisionLanguageAnalyzer`
- `RankingPlanner`
- `ProviderClient`

Each provider should return the same structured schema so the rest of the pipeline does not care whether the result came from LM Studio or a hosted API.

## Recommended Data Model Additions

### SegmentUnderstanding

- `segment_id`
- `provider`
- `provider_model`
- `schema_version`
- `summary`
- `subjects`
- `actions`
- `shot_type`
- `camera_motion`
- `mood`
- `story_roles`
- `quality_findings`
- `keep_label`
- `confidence`
- `rationale`
- `risk_flags`
- `tokens_or_runtime_ms`

### PairwisePreference

- `left_segment_id`
- `right_segment_id`
- `winner_segment_id`
- `comparison_reason`
- `confidence`
- `applies_to_role`

### StoryPlan

- `timeline_variant_id`
- `story_mode`
- `ordered_segment_ids`
- `role_map`
- `sequence_rationale`
- `variant_summary`

## Prompting Strategy

Use narrow prompts with structured outputs.

### Segment Understanding Prompt

Ask:

- what is visible
- what changes during the segment
- whether the shot is usable
- what editorial role it might play
- what makes it weak or strong

### Pairwise Ranking Prompt

Ask:

- which of two segments is stronger for a stated role
- whether they are redundant
- whether one should replace the other

### Story Assembly Prompt

Ask:

- assemble from shortlisted structured segments
- preserve chronology by default unless told otherwise
- avoid adjacent redundancy
- produce 1 to 3 variants with rationales

## Confidence Strategy

Store confidence per AI output and do not over-trust a single pass.

Recommended rules:

- if confidence is low, downgrade to `candidate`, not `best take`
- if two segments are nearly tied, surface both
- if the model marks segments as redundant, keep the stronger one and expose the weaker as alternate
- if model output is malformed or missing, fall back to deterministic ranking

## Validation Strategy

Measure model usefulness against editor behavior, not just internal scores.

Track:

- how often the editor keeps AI-selected takes
- how often the editor swaps to a backup
- whether AI descriptions help users choose faster
- whether opener / outro choices are accepted
- whether local LM Studio results are good enough compared to cloud baselines

## Non-Goals For The First AI Upgrade

Do not attempt all of these at once:

- full video-to-video end-to-end generative editing
- autonomous final cut decisions with no user review
- perfect cinematic understanding
- direct Resolve automation as the control plane

The right first target is:

- believable segment descriptions
- better-than-random best-take selection
- coherent rough timeline variants
- clear manual override points
