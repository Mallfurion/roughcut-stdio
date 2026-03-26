import type { ClipView, TimelineProject } from "../app/types.ts";

export function resolveClipViews(project: TimelineProject): ClipView[] {
  const takeBySegmentId = new Map(
    project.take_recommendations.map((take) => [take.candidate_segment_id, take]),
  );

  return project.assets
    .map((asset) => ({
      asset,
      segments: project.candidate_segments
        .filter((segment) => segment.asset_id === asset.id)
        .sort((left, right) => left.start_sec - right.start_sec)
        .map((segment) => ({
          segment,
          recommendation: takeBySegmentId.get(segment.id),
        })),
    }))
    .filter((view) => view.segments.length > 0);
}
