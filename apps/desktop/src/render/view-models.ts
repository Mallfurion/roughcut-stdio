import type { ClipView, SegmentView, TimelineProject } from "../app/types.ts";

export function resolveClipViews(project: TimelineProject): ClipView[] {
  const segmentViews = resolveSegmentViews(project);

  return project.assets
    .map((asset) => ({
      asset,
      segments: segmentViews
        .filter((view) => view.asset.id === asset.id)
        .sort((left, right) => left.segment.start_sec - right.segment.start_sec),
    }))
    .filter((view) => view.segments.length > 0);
}

export function resolveRankedSegmentViews(project: TimelineProject): SegmentView[] {
  return resolveSegmentViews(project).sort(compareScoreOrderedSegmentViews);
}

function resolveSegmentViews(project: TimelineProject): SegmentView[] {
  const assetById = new Map(project.assets.map((asset) => [asset.id, asset]));
  const takeBySegmentId = new Map(project.take_recommendations.map((take) => [take.candidate_segment_id, take]));
  const timelineItemByRecommendationId = new Map(project.timeline.items.map((item) => [item.take_recommendation_id, item]));

  return project.candidate_segments.flatMap((segment) => {
    const asset = assetById.get(segment.asset_id);
    if (!asset) {
      return [];
    }

    const recommendation = takeBySegmentId.get(segment.id);

    return [
      {
        asset,
        segment,
        recommendation,
        timelineItem: recommendation ? timelineItemByRecommendationId.get(recommendation.id) : undefined,
        orderingScore: resolveSegmentOrderingScore(segment, recommendation?.score_total),
      },
    ];
  });
}

function compareScoreOrderedSegmentViews(left: SegmentView, right: SegmentView) {
  const scoreDelta = right.orderingScore - left.orderingScore;
  if (Math.abs(scoreDelta) > Number.EPSILON) {
    return scoreDelta;
  }

  const recommendationDelta = Number(Boolean(right.recommendation)) - Number(Boolean(left.recommendation));
  if (recommendationDelta !== 0) {
    return recommendationDelta;
  }

  const assetNameDelta = left.asset.name.localeCompare(right.asset.name);
  if (assetNameDelta !== 0) {
    return assetNameDelta;
  }

  if (left.segment.start_sec !== right.segment.start_sec) {
    return left.segment.start_sec - right.segment.start_sec;
  }

  return left.segment.id.localeCompare(right.segment.id);
}

function resolveSegmentOrderingScore(
  segment: TimelineProject["candidate_segments"][number],
  totalScore?: number,
) {
  if (typeof totalScore === "number") {
    return totalScore;
  }

  return segment.prefilter?.score ?? 0;
}
