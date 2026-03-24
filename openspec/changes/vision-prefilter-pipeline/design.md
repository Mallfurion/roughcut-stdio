## Context

The current repository already has a working local screening pipeline, but its cheapest stages are too weak and its most expensive stage is used too early. Candidate windows are still generated primarily from scene boundaries or fallback windows, placeholder metrics are still used for prefiltering, and LM Studio is asked to analyze shortlisted segments before the pipeline has extracted enough low-cost visual evidence to justify those requests.

This change introduces a new architectural layer between media discovery and VLM refinement:

- cheap frame sampling
- lightweight visual feature extraction
- frame and segment scoring
- candidate shortlist generation

That layer should do most of the work of deciding where promising footage lives. LM Studio then becomes a late-stage editorial refinement step over a very small shortlist, not a first-pass screener.

Constraints:

- the product stays local-first
- silent footage remains a first-class path
- deterministic fallback must remain possible at all times
- Resolve export safety cannot regress
- the `setup -> process -> view -> export` workflow must remain intact

## Goals / Non-Goals

**Goals:**

- Reduce total LM Studio requests and payload volume dramatically.
- Replace placeholder-first prefiltering with real low-cost visual scoring.
- Build stronger candidate segments from scene cuts plus motion and score signals.
- Persist prefilter outputs so they are inspectable, cacheable, and reusable.
- Expose runtime stats showing how much work was filtered out before the VLM stage.
- Create a clean foundation for later `ai-segment-ranking` work.

**Non-Goals:**

- Replace final ranking with VLM-based comparative selection in this change.
- Introduce cloud inference.
- Build story-role assignment or multi-variant timeline planning.
- Change Resolve export format or timecode semantics.

## Decisions

### 1. Introduce a distinct prefilter stage before any VLM call

The pipeline should explicitly separate:

- deterministic extraction and feature computation
- cheap screening and shortlist construction
- expensive VLM refinement

This keeps the VLM at the end of the path and makes local runtime cost proportional to promising footage rather than to all candidate windows.

Alternative considered:
- Keep the current segment pipeline and only tune keyframe count and concurrency.

Why rejected:
- That improves constants, not architecture. The main problem is that too many segments still reach the expensive stage.

### 2. Use low-cost frame and window signals as the primary screening mechanism

The prefilter stage should compute signals such as:

- blur / sharpness proxy
- motion magnitude and motion consistency
- frame-to-frame distinctiveness
- stability proxy
- simple composition heuristics
- subjectness proxies when feasible
- optional CLIP or aesthetic-style embedding similarity if cheap enough

These signals should be used to score sampled frames and aggregate them into segment candidates.

Alternative considered:
- Depend on CLIP or another learned embedding model from the start.

Why rejected:
- The first version should not depend on an additional heavy model if OpenCV- and ffmpeg-based signals can already reduce the candidate set materially. Optional learned embeddings can be layered on later behind a feature flag or runtime capability check.

### 3. Build candidates from score structure, not just from static windows

Scene detection remains useful, but it should no longer be the only meaningful segmentation method. Candidate regions should be informed by:

- scene boundaries
- score peaks
- motion changes
- deduplicated near-identical frame runs

This should produce segments that better align with “good regions” instead of arbitrary fixed windows.

Alternative considered:
- Keep current scene/fallback segmentation unchanged and only rank the resulting segments better.

Why rejected:
- The user goal is to avoid watching weak footage. Better ranking over weak initial windows still wastes effort upstream and still sends too much material to later stages.

### 4. Persist prefilter outputs as first-class data

The generated project should store:

- sampled frame timestamps
- frame-level or window-level screening metrics
- shortlist membership
- reason a segment reached or did not reach the VLM stage

This makes the screening process inspectable and avoids a black-box “filtered somewhere upstream” experience.

Alternative considered:
- Treat prefiltering as temporary in-memory data only.

Why rejected:
- That would make debugging impossible and would weaken caching opportunities.

### 5. Keep deterministic fallback and Resolve-safe outputs outside the VLM path

Path integrity, timecodes, trim bounds, and export semantics remain deterministic guardrails. VLM output must not become required for the project to produce a valid timeline or export.

Alternative considered:
- Let VLM output drive segment generation directly when available.

Why rejected:
- That would couple core pipeline correctness to model availability and make failure behavior much worse.

## Risks / Trade-offs

- [Cheap features may not correlate strongly enough with editorial quality] -> Mitigation: treat the prefilter as a high-recall shortlist builder, not the final ranking authority.
- [New feature extraction may add CPU cost] -> Mitigation: keep sampling sparse, cache extracted metrics, and prefer cheap operations over model inference.
- [Candidate generation may become harder to reason about] -> Mitigation: persist prefilter metrics and shortlist reasons into generated project state and process logs.
- [Optional learned embeddings could complicate setup] -> Mitigation: make CLIP/aesthetic-style scoring optional and capability-driven, not required for the baseline pipeline.
- [Phase boundaries may blur with `ai-segment-ranking`] -> Mitigation: limit this change to shortlist construction and VLM reduction; keep authoritative best-take selection changes in the later ranking change.

## Migration Plan

1. Add frame-sampling and feature-extraction utilities.
2. Add prefilter records to the domain model and generated project state.
3. Build asset-level prefilter scoring and candidate shortlist construction.
4. Rewire the AI stage so only prefiltered shortlist segments reach LM Studio.
5. Add runtime logging and process summaries for prefilter hit rates and VLM reduction.
6. Verify deterministic fallback, generated project compatibility, and export stability.

## Open Questions

- Should optional CLIP or aesthetic scoring be part of the first implementation, or should the first pass stick to pure OpenCV/ffmpeg metrics?
- What sampling rate is the best default for long clips: fixed FPS, scene-aware sampling, or duration-scaled sampling?
- Should the UI expose frame-level evidence immediately, or only aggregate prefilter decisions at the segment level?
