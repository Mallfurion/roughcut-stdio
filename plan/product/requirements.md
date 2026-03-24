# Product Requirements

## Product Vision

Turn a folder of raw clips and DaVinci Resolve proxies into:

- a shortlist of candidate moments
- a smaller shortlist of recommended best takes
- a rough sequence that already feels like a story
- a timeline export that can be imported or conformed inside DaVinci Resolve

The app should reduce the time spent scrubbing everything manually before real editing starts.

## Primary User

An editor or creator who:

- has many source clips
- often generates proxies in DaVinci Resolve
- wants help finding usable moments faster
- still wants final editorial control

## Jobs To Be Done

1. Import a shoot folder without manually preparing every clip.
2. Let the system find the watch-worthy sections.
3. Understand, in plain language, why each suggested take is interesting.
4. Preview a rough story from the selected takes.
5. Promote the shortlist into a proper edit in Resolve with clip order and trim decisions preserved.

## Functional Requirements

### Ingestion

- User can create a project from one or more media folders.
- System discovers source files and proxy files.
- System attempts automatic source-to-proxy matching.
- User can fix mismatches manually.

### Analysis

- System extracts clip metadata.
- System segments clips into candidate regions.
- System generates transcripts only for speech-containing regions.
- System computes basic quality signals per region:
  - sharpness
  - stability
  - loudness / speech presence
  - face visibility or subject presence when relevant
- System produces a short natural-language description per candidate region.
- System must work on silent b-roll without requiring transcript text.
- For silent footage, descriptions should be derived from visual action, subject, framing, and context rather than dialogue.

### Take Recommendation

- System may recommend zero, one, or multiple best takes per clip.
- Each recommendation includes:
  - source clip
  - in/out timecode
  - title or short label
  - 1 to 3 sentence description
  - confidence score
  - explanation of why it was selected
- System should identify near-duplicate moments and down-rank repetition.

### Story Assembly

- User can define a story goal or tone, for example:
  - energetic montage
  - behind-the-scenes progression
  - calm cinematic sequence
- System groups takes into tentative story roles:
  - opener
  - setup
  - development
  - payoff
  - outro
- System generates an initial sequence order.
- System should support story assembly for dialogue-led footage and purely visual montage footage.

### Review UX

- User can approve, reject, or pin suggested takes.
- User can change descriptions or labels.
- User can reorder the draft timeline.
- User can trim take boundaries.
- User can preview the timeline without leaving the app.

### Outputs

- System stores all decisions in a project timeline JSON document.
- System can render a rough preview cut from proxies.
- System can export a human-readable shot list.
- System can export a Resolve-usable interchange package containing clip order, source references, and in/out ranges.
- The first interchange target should be `FCPXML`, with fallback exports such as `EDL` or structured CSV/JSON for debugging and recovery.

## Non-Goals For The First Version

- full browser-based professional editing
- effects, transitions, or color grading
- frame-accurate finishing workflows
- auto-publishing directly to social platforms

## Quality Model For "Best Takes"

Each candidate take should be scored across three dimensions.

### 1. Technical Quality

- image clarity
- stable framing
- clean audible speech or useful ambient sound
- manageable duration

### 2. Semantic Value

- clear action or event
- understandable subject matter
- distinctiveness versus nearby segments
- strong visual or spoken hook

### 3. Story Value

- helps start, advance, or resolve a sequence
- complements other selected takes
- avoids repetitive coverage unless repetition is intentional

## Acceptance Criteria For MVP

- A project with proxy files can be analyzed without using original media for every step.
- At least one candidate segment list is generated for every valid clip.
- The app can recommend multiple takes from the same source clip.
- The app can recommend no takes from weak or redundant clips.
- Every recommended take includes a short description and selection rationale.
- The app can generate a first-pass ordered timeline from selected takes.
- The user can preview that timeline in the browser.
- The user can override AI choices without fighting the system.
- The app can export a timeline that preserves selected clip order and trim ranges for Resolve handoff.
