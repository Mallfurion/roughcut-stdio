# System Design

## Architecture Summary

Use a local-first web architecture with a browser UI and a Python analysis backend.

### Components

- `Web App`
  - project setup
  - take review
  - timeline preview
  - manual overrides
- `API Layer`
  - project CRUD
  - analysis job control
  - timeline persistence
- `Analysis Worker`
  - media probing
  - frame/audio extraction
  - scene segmentation
  - transcription
  - take scoring
  - story assembly
- `Storage`
  - media references
  - extracted thumbnails and waveform data
  - transcripts
  - candidate segments
  - final timeline JSON

## Pipeline

1. `Discover media`
   - scan selected folders
   - identify video files
   - detect proxy candidates

2. `Match sources to proxies`
   - filename/path heuristics first
   - duration/frame rate/timecode fallback checks
   - manual correction UI when confidence is low

3. `Extract metadata`
   - duration
   - frame rate
   - resolution
   - audio stream presence
   - starting timecode where available

4. `Generate candidate regions`
   - shot boundaries from scene detection
   - speech/silence boundaries from audio/transcript pass when speech exists
   - split long static regions into smaller windows

5. `Analyze each candidate region`
   - representative frames
   - audio excerpt or transcript excerpt when available
   - quality metrics from OpenCV/audio features
   - semantic description from multimodal AI
   - visual-only description path for silent b-roll

6. `Score and rank`
   - technical score
   - semantic score
   - story score
   - redundancy penalty

7. `Assemble draft timeline`
   - select best candidate set
   - order by story role and continuity
   - keep timeline editable

8. `Preview`
   - browser playback using project timeline state
   - optional async rough-cut render from proxies

## Data Model

### Project

- `id`
- `name`
- `media_roots`
- `story_prompt`
- `status`

### Asset

- `id`
- `project_id`
- `source_path`
- `proxy_path`
- `metadata`
- `analysis_status`
- `has_speech`
- `interchange_reel_name`

### CandidateSegment

- `id`
- `asset_id`
- `start_tc`
- `end_tc`
- `duration_sec`
- `transcript_excerpt`
- `analysis_mode`
- `quality_metrics`
- `description`

### TakeRecommendation

- `id`
- `candidate_segment_id`
- `is_best_take`
- `score_technical`
- `score_semantic`
- `score_story`
- `score_total`
- `selection_reason`

### Timeline

- `id`
- `project_id`
- `version`
- `story_summary`
- `preview_render_path`
- `export_fcpxml_path`
- `export_edl_path`

### TimelineItem

- `id`
- `timeline_id`
- `take_recommendation_id`
- `order_index`
- `trim_in_sec`
- `trim_out_sec`
- `label`
- `notes`
- `source_asset_path`
- `source_reel`

## Scoring Model

Use a hybrid scoring pipeline.

### Deterministic signals

- blur / sharpness proxy
- luminance sanity checks
- motion stability
- silence ratio
- speech presence
- duration fit
- visual novelty
- composition / subject clarity

### AI judgments

- what is happening
- whether the moment is usable
- whether it feels stronger than adjacent alternatives
- what role it could play in a sequence
- for silent footage, whether the shot functions as establishing shot, insert, transition, texture, action beat, or payoff

### Final score

`final_score = technical * 0.35 + semantic * 0.40 + story * 0.25 - redundancy_penalty`

The weights should remain configurable per project style.

## Story Assembly Strategy

Do not ask the model to invent a sequence from raw footage only.

Instead:

1. rank candidates first
2. remove near-duplicates
3. assign tentative story roles
4. generate 2 to 3 possible sequence variants
5. let the user choose or refine one

This keeps the system more controllable and easier to debug.

For silent montage projects, chronology and visual pacing should be the default ordering heuristic unless the user explicitly asks for thematic reordering.

## Preview Strategy

### MVP

- custom React timeline
- `@remotion/player` for sequence preview
- waveform regions for trims and review notes

### Rendered preview

- background job creates a draft MP4 from proxy clips
- rendered preview is useful for validation and sharing
- timeline JSON remains the source of truth

## Export Strategy

### Primary export

- write `FCPXML` from timeline JSON
- include clip order, source path or relinkable identifier, source in/out, and timeline placement
- validate the generated XML by importing it into Resolve on sample media

### Secondary exports

- `EDL` for very simple cut-only timelines
- shot list CSV/Markdown for human review
- raw `timeline.json` for debugging and regeneration

### Export adapter boundary

- isolate all Resolve-specific mapping in one export module
- store enough source metadata to rebuild exports after manual timeline edits
- keep file path, reel name, frame rate, and source timecode normalized early in the pipeline

## Resolve Integration Strategy

Phase 1 should include file-based Resolve handoff:

- timeline JSON
- shot list export
- preview render
- FCPXML export

Future integration options:

- markers or bin metadata import helpers
- direct Resolve scripting if version compatibility is acceptable

Keep this behind an adapter boundary because NLE interchange is version-sensitive.

## Main Risks

- source/proxy matching may be inconsistent across projects
- best-take quality is subjective and domain-specific
- diarization can add cost and complexity without enough gain
- browser preview can get slow if every action triggers rendering
- Resolve conform can fail if reel names, source paths, frame rates, or source timecodes are inconsistent
- silent b-roll ranking can become too generic without strong visual distinctiveness features

## Design Principle

The system should optimize for `editor trust`, not `full automation`.

That means every AI recommendation needs:

- a timestamp
- a reason
- an easy manual override
