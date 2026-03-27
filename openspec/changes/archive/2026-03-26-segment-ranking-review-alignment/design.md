## Context

The current review surface mixes three separate concepts without clearly tying them together:

- screening data from `prefilter`
- editorial interpretation from `ai_understanding`
- final recommendation data from `take_recommendations`

The analyzer already writes a recommendation record for every candidate segment, but the desktop app mostly ignores that record when rendering segment cards. As a result, the UI emphasizes "what the model said" more than "why this segment actually won or lost." That is the wrong hierarchy for a selection tool.

## Goals / Non-Goals

**Goals:**
- Align desktop segment review with the real best-take calculation path
- Show both analysis-path status and recommendation-path status on each segment
- Make winner/alternate/backup states obvious without requiring log inspection
- Keep review copy grounded in persisted analyzer output, not client-side guesswork

**Non-Goals:**
- Replacing deterministic ranking with a new AI ranking system
- Redesigning the whole desktop information architecture
- Exposing every raw metric or every internal threshold directly in the UI
- Changing timeline export behavior

## Decisions

### 1. Recommendation metadata stays authoritative in analyzer output

The analyzer will continue to own recommendation semantics. `TakeRecommendation` should be extended into a proper review-facing record for every candidate segment, keyed by `candidate_segment_id`, and should include:

- recommendation outcome such as `best`, `alternate`, or `backup`
- within-asset rank
- score gap to the winning segment
- total plus technical, semantic, and story scores
- a concise decision summary
- a bounded list of top score drivers

Rationale:
- The analyzer already knows the active scoring formula and sibling comparison set.
- The desktop app should render persisted review facts, not reconstruct recommendation logic.

### 2. The desktop card should show two layers: recommendation and analysis

Each segment card should combine recommendation and analysis into one readable block:

- recommendation layer:
  - outcome badge
  - total score
  - technical / semantic / story breakdown
  - why this segment won or lost
  - relative position inside the asset
- analysis layer:
  - prefilter status
  - CLIP score or CLIP gate state
  - deduplication or budget-cap state
  - evidence coverage such as keyframe count and context window when present
  - AI provider, keep label, confidence, and summary

Rationale:
- Editors need to understand both "what the system looked at" and "how the system chose."
- Splitting those layers keeps the UI legible without hiding important decision context.

### 3. Score explanations should name real drivers from the active formula

The review explanation should be derived from the same weighted inputs used in `score_segment()`, respecting analysis mode:

- speech segments emphasize hook strength, story alignment, speech ratio, and audio-aware technical inputs
- visual segments emphasize visual novelty, motion energy, hook strength, and visual/story pacing inputs

The analyzer should derive a short explanation from the highest-signal contributors rather than reuse generic winner/backup copy. For non-winning segments, it should also explain whether the segment:

- lost by rank only
- fell below the minimum score threshold
- missed the within-asset score-gap rule for alternates

Rationale:
- This keeps the explanation faithful to the current selector.
- A ranking surface is only trustworthy if the explanatory language matches the actual formula.

### 4. Analysis-path status should be explicit, not inferred from missing fields alone

The review model should make it obvious whether a segment was:

- shortlisted for expensive analysis
- CLIP scored
- CLIP gated
- deduplicated
- capped by VLM budget
- analyzed by a model
- handled deterministically after screening

The desktop app may still render from normalized persisted fields, but the resulting state must be coherent for both analyzed and skipped segments.

Rationale:
- "No evidence bundle" is not a compelling review explanation.
- Editors need clear reasons when a segment did not receive the same level of analysis as another segment.

### 5. Keep the change additive to current ranking behavior

This change does not alter score weights, thresholds, tie-break rules, or timeline assembly. It only makes the existing path reviewable and prepares the UI contract for later ranking work.

Rationale:
- Explainability is easier to validate when selection behavior is stable.
- This change should reduce ambiguity before larger ranking changes land.

## Example Review Card

For a winning segment, the desktop card should read more like:

`Best take | Score 67 | Story 77 | Semantic 77 | Technical 48`

`Won this clip on story alignment, hook strength, and speech ratio.`

`Analyzed: shortlisted -> CLIP 0.62 -> VLM (lmstudio, 3 keyframes)`

For a non-winning segment, it should read more like:

`Backup | Score 45 | 22 pts behind winner`

`Usable, but weaker on story alignment and hook strength than the selected beat.`

`Analyzed: shortlisted -> deterministic fallback after CLIP gate`

That presentation keeps the current AI summary available, but it no longer hides the actual recommendation path behind generic labels.

## Risks / Trade-offs

- [Too many badges can clutter the card] -> Keep a strict distinction between recommendation status and analysis status.
- [Score-driver copy may drift from code] -> Generate driver summaries from scorer-owned helper functions and test them.
- [Schema growth may duplicate existing fields] -> Reuse current score fields where possible and add only review-specific ranking metadata.
- [UI may overemphasize numbers] -> Pair score breakdown with short editorial explanations instead of showing raw metrics alone.
