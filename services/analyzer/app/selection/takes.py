from __future__ import annotations

from ..ai import VisionLanguageAnalyzer
from ..domain import Asset, CandidateSegment, TakeRecommendation
from ..scoring import limiting_factor_labels, score_segment, top_score_driver_labels
from ..shared.strings import human_join

TAKE_SELECTION_MIN_SCORE = 0.68
TAKE_SELECTION_ALT_GAP = 0.08


def build_take_recommendations(
    assets: list[Asset],
    candidate_segments: list[CandidateSegment],
) -> list[TakeRecommendation]:
    takes: list[TakeRecommendation] = []

    for asset in assets:
        asset_segments = [segment for segment in candidate_segments if segment.asset_id == asset.id]
        if not asset_segments:
            continue
        ranked_segment_data = sorted(
            ((segment, score_segment(asset, segment)) for segment in asset_segments),
            key=lambda item: item[1].total,
            reverse=True,
        )
        ranked_segments = [segment for segment, _breakdown in ranked_segment_data]
        breakdown_by_segment_id = {segment.id: breakdown for segment, breakdown in ranked_segment_data}
        selected_segments = select_segments_for_asset(asset, ranked_segments)
        selected_ids = {selected.id for selected in selected_segments}
        winner_segment = ranked_segments[0]
        winner_score = breakdown_by_segment_id[winner_segment.id].total
        rank_by_segment_id = {segment.id: index for index, segment in enumerate(ranked_segments, start=1)}

        for index, segment in enumerate(asset_segments, start=1):
            breakdown = breakdown_by_segment_id[segment.id]
            is_best_take = segment.id in selected_ids
            outcome = recommendation_outcome(segment, winner_segment, selected_ids)
            drivers = top_score_driver_labels(asset, segment)
            limiting_factors = (
                []
                if segment.id == winner_segment.id
                else limiting_factor_labels(asset, segment, winner_segment)
            )
            takes.append(
                TakeRecommendation(
                    id=f"{asset.id}-take-{index:02d}",
                    candidate_segment_id=segment.id,
                    title=make_take_title(asset, segment, breakdown.analysis_mode, outcome),
                    is_best_take=is_best_take,
                    selection_reason=make_selection_reason(
                        asset=asset,
                        segment=segment,
                        total_score=breakdown.total,
                        outcome=outcome,
                        winner_score=winner_score,
                        within_asset_rank=rank_by_segment_id[segment.id],
                        driver_labels=drivers,
                        limiting_labels=limiting_factors,
                    ),
                    score_technical=breakdown.technical,
                    score_semantic=breakdown.semantic,
                    score_story=breakdown.story,
                    score_total=breakdown.total,
                    outcome=outcome,
                    within_asset_rank=rank_by_segment_id[segment.id],
                    score_gap_to_winner=round(max(0.0, winner_score - breakdown.total), 4),
                    score_driver_labels=drivers,
                    limiting_factor_labels=limiting_factors,
                )
            )

    return takes


def make_take_title(asset: Asset, segment: CandidateSegment, analysis_mode: str, outcome: str) -> str:
    title_prefix = "Best" if outcome == "best" else "Alternate" if outcome == "alternate" else "Candidate"
    role = "Dialogue" if analysis_mode == "speech" else "Visual"
    return f"{title_prefix} {role}: {asset.name}"


def recommendation_outcome(
    segment: CandidateSegment,
    winner_segment: CandidateSegment,
    selected_ids: set[str],
) -> str:
    if segment.id == winner_segment.id:
        return "best"
    if segment.id in selected_ids:
        return "alternate"
    return "backup"


def make_selection_reason(
    *,
    asset: Asset,
    segment: CandidateSegment,
    total_score: float,
    outcome: str,
    winner_score: float,
    within_asset_rank: int,
    driver_labels: list[str],
    limiting_labels: list[str],
) -> str:
    score = round(total_score * 100)
    score_gap = round(max(0.0, (winner_score - total_score) * 100))
    drivers = human_join(driver_labels[:3])
    limiting = human_join(limiting_labels[:2])

    if outcome == "best":
        return f"Won this clip at {score}/100 on {drivers}."

    if outcome == "alternate":
        return (
            f"Kept as an alternate {score_gap} point{'s' if score_gap != 1 else ''} behind the winner "
            f"because it still cleared the selection gap on {drivers}."
        )

    if total_score < TAKE_SELECTION_MIN_SCORE:
        return (
            f"Usable, but below the {round(TAKE_SELECTION_MIN_SCORE * 100):d}/100 selection threshold. "
            f"Strongest factors were {drivers}."
        )

    if asset.duration_sec >= 18 and total_score < winner_score - TAKE_SELECTION_ALT_GAP:
        return (
            f"Usable, but {score_gap} points behind the winner and outside the alternate gap, "
            f"mainly on {limiting or drivers}."
        )

    return (
        f"Usable, but ranked #{within_asset_rank} behind the selected take for this clip, "
        f"mainly on {limiting or drivers}."
    )


def select_segments_for_asset(asset: Asset, segments: list[CandidateSegment]) -> list[CandidateSegment]:
    if not segments:
        return []

    selected: list[CandidateSegment] = []
    primary_score = score_segment(asset, segments[0]).total
    for segment in segments:
        breakdown = score_segment(asset, segment)
        if breakdown.total < TAKE_SELECTION_MIN_SCORE:
            continue
        if selected and breakdown.total < primary_score - TAKE_SELECTION_ALT_GAP:
            continue
        selected.append(segment)
        if len(selected) >= (2 if asset.duration_sec >= 18 else 1):
            break

    return selected or segments[:1]


def select_ai_target_segment_ids(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    analyzer: VisionLanguageAnalyzer,
    max_segments_per_asset: int,
    mode: str,
) -> set[str]:
    if not segments:
        return set()
    if not analyzer.requires_keyframes:
        return set()
    if mode != "fast":
        return {segment.id for segment in segments}

    return select_prefilter_shortlist_ids(
        asset=asset,
        segments=segments,
        max_segments_per_asset=max_segments_per_asset,
        mode=mode,
    )


def select_vlm_targets_three_stage(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    analyzer: VisionLanguageAnalyzer,
    prefilter_shortlist_ids: set[str],
    max_segments_per_asset: int,
    vlm_budget_pct: int,
    clip_enabled: bool = False,
) -> set[str]:
    """
    Select VLM targets using three-stage gating:
    1. Filter out CLIP-gated and deduplicated segments
    2. Apply per-asset limit
    3. Apply global budget cap (placeholder for global logic)
    """
    del asset, clip_enabled
    if not analyzer.requires_keyframes:
        return set()

    eligible = [s for s in segments if s.id in prefilter_shortlist_ids]
    eligible = [s for s in eligible if not (s.prefilter and (s.prefilter.clip_gated or s.prefilter.deduplicated))]

    ranked = sorted(
        eligible,
        key=lambda s: (s.prefilter.metrics_snapshot.get("clip_score", 0.0) + s.prefilter.score) / 2.0
        if s.prefilter else 0.0,
        reverse=True,
    )
    per_asset_limit = max(1, min(max_segments_per_asset, len(ranked)))
    stage2_targets = ranked[:per_asset_limit]

    if vlm_budget_pct < 100 and stage2_targets:
        budget_count = max(1, int(len(stage2_targets) * vlm_budget_pct / 100.0))
        for i, segment in enumerate(stage2_targets):
            if i >= budget_count and segment.prefilter is not None:
                segment.prefilter.vlm_budget_capped = True

    return {s.id for s in stage2_targets if not (s.prefilter and s.prefilter.vlm_budget_capped)}


def select_prefilter_shortlist_ids(
    *,
    asset: Asset,
    segments: list[CandidateSegment],
    max_segments_per_asset: int,
    mode: str,
) -> set[str]:
    if not segments:
        return set()
    if mode != "fast":
        return {segment.id for segment in segments}

    ranked = sorted(
        segments,
        key=lambda segment: (
            segment.prefilter.score if segment.prefilter is not None else score_segment(asset, segment).total
        ),
        reverse=True,
    )
    limit = max(1, min(max_segments_per_asset, len(ranked)))
    return {segment.id for segment in ranked[:limit]}


def describe_prefilter_selection(
    *,
    score: float,
    shortlisted: bool,
    filtered_before_vlm: bool,
    clip_gated: bool = False,
    vlm_budget_capped: bool = False,
) -> str:
    score_label = f"{round(score * 100):d}/100"
    if filtered_before_vlm:
        if clip_gated:
            return f"Gated by CLIP semantic scoring at {score_label}."
        if vlm_budget_capped:
            return f"Excluded by global VLM budget cap at {score_label}."
        return f"Filtered before VLM analysis during vision prefiltering at {score_label}."
    if shortlisted:
        return f"Shortlisted by vision prefiltering at {score_label}."
    return f"Scored {score_label} during vision prefiltering."
