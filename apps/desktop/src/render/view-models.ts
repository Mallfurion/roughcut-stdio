import type { ClipView, TimelineProject } from "../app/types.ts";

export function resolveClipViews(project: TimelineProject): ClipView[] {
  const takeBySegmentId = new Map(
    project.take_recommendations.map((take) => [take.candidate_segment_id, take]),
  );
  const timelineItemByRecommendationId = new Map(
    project.timeline.items.map((item) => [item.take_recommendation_id, item]),
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
          timelineItem: takeBySegmentId.get(segment.id)
            ? timelineItemByRecommendationId.get(takeBySegmentId.get(segment.id)?.id ?? "")
            : undefined,
        })),
    }))
    .filter((view) => view.segments.length > 0);
}
