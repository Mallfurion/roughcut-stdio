import {
  computeScoreLabel,
  formatDuration,
  loadActiveProject,
  resolveTakeViews
} from "../lib/project";

export default async function Page() {
  const loaded = await loadActiveProject();
  const project = loaded.project;
  const takeViews = resolveTakeViews(project);
  const aiAnalyzedCount = project.candidate_segments.filter((segment) => segment.ai_understanding).length;
  const keyframedCount = project.candidate_segments.filter(
    (segment) => (segment.evidence_bundle?.keyframe_paths.length ?? 0) > 0
  ).length;
  const silentCount = project.assets.filter((asset) => !asset.has_speech).length;
  const dialogueCount = project.assets.length - silentCount;
  const sourceOnlyCount = project.assets.filter((asset) => asset.has_proxy === false).length;
  const proxyBackedCount = project.assets.length - sourceOnlyCount;
  const totalTimelineDuration = project.timeline.items.reduce(
    (sum, item) => sum + Math.max(0, item.trim_out_sec - item.trim_in_sec),
    0
  );

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="panel hero-copy">
          <div className="eyebrow">Local-first rough cut</div>
          <h1>Review footage before the edit starts.</h1>
          <p>
            This scaffold treats silent b-roll and dialogue-led footage as equal citizens. The system
            proposes best takes, explains why they matter, and keeps the timeline exportable into
            DaVinci Resolve as a real interchange file.
          </p>
          <p>{project.project.story_prompt}</p>
          <p>
            Active source: {loaded.source === "generated" ? "generated timeline" : "sample fixture"}.
          </p>
          <div className="hero-actions">
            <a className="button" href="/api/export/fcpxml">
              Export FCPXML
            </a>
            <a className="button secondary" href="/api/project">
              Inspect Project JSON
            </a>
          </div>
        </div>
        <div className="panel hero-metrics">
            <MetricCard label="Project" value={project.project.name} />
            <MetricCard label="Best takes" value={String(takeViews.length)} />
            <MetricCard label="AI analyzed" value={String(aiAnalyzedCount)} />
            <MetricCard label="Keyframed" value={String(keyframedCount)} />
            <MetricCard label="Silent clips" value={String(silentCount)} />
            <MetricCard label="Dialogue clips" value={String(dialogueCount)} />
            <MetricCard label="Proxy-backed" value={String(proxyBackedCount)} />
            <MetricCard label="Source-only" value={String(sourceOnlyCount)} />
            <MetricCard label="Timeline" value={`${totalTimelineDuration.toFixed(2)}s`} />
            <MetricCard label="Timeline version" value={`v${project.timeline.version}`} />
        </div>
      </section>

      <section className="panel section">
        <div className="section-header">
          <div>
            <h2>Recommended Takes</h2>
          </div>
          <p>
            These cards show the current recommendation layer and the new Phase 1 AI-understanding
            output. Segment selection is still deterministic, but each segment can now carry
            structured evidence and provider-backed editorial analysis.
          </p>
        </div>
        <div className="take-grid">
          {takeViews.map(({ take, segment, asset }) => (
            <article className="take-card" key={take.id}>
              <div className="take-art" />
              <div className="take-meta">
                <span className="badge">{segment.analysis_mode}</span>
                <span className="score-chip">Score {computeScoreLabel(take, segment)}</span>
              </div>
              <div>
                <h3>{take.title}</h3>
                <p>{segment.description}</p>
              </div>
              {segment.ai_understanding ? (
                <div className="ai-panel">
                  <div className="take-meta">
                    <span className="badge subtle">{segment.ai_understanding.keep_label}</span>
                    <span className="score-chip">
                      {segment.ai_understanding.provider} · {Math.round(segment.ai_understanding.confidence * 100)}%
                    </span>
                  </div>
                  <p>{segment.ai_understanding.summary}</p>
                  <div className="take-facts">
                    <span>roles: {segment.ai_understanding.story_roles.join(", ")}</span>
                    <span>shot: {segment.ai_understanding.shot_type}</span>
                    <span>motion: {segment.ai_understanding.camera_motion}</span>
                    <span>mood: {segment.ai_understanding.mood}</span>
                  </div>
                  <p>{segment.ai_understanding.rationale}</p>
                </div>
              ) : null}
              <div className="take-facts">
                <span>{asset.name}</span>
                <span>{formatDuration(segment.start_sec, segment.end_sec)}</span>
                <span>{asset.interchange_reel_name}</span>
                <span>{asset.has_proxy === false ? "source-only" : "proxy-backed"}</span>
              </div>
              {segment.evidence_bundle ? (
                <div className="take-facts">
                  <span>
                    keyframes {segment.evidence_bundle.keyframe_paths.length}/
                    {segment.evidence_bundle.keyframe_timestamps_sec.length}
                  </span>
                  <span>
                    context {segment.evidence_bundle.context_window_start_sec.toFixed(2)}s to{" "}
                    {segment.evidence_bundle.context_window_end_sec.toFixed(2)}s
                  </span>
                </div>
              ) : null}
              <p>{take.selection_reason}</p>
              {asset.proxy_match_reason ? <p>{asset.proxy_match_reason}</p> : null}
              {segment.transcript_excerpt ? <p>“{segment.transcript_excerpt}”</p> : null}
              {segment.ai_understanding?.risk_flags.length ? (
                <p>Risk flags: {segment.ai_understanding.risk_flags.join(", ")}</p>
              ) : null}
            </article>
          ))}
        </div>
      </section>

      <section className="panel section">
        <div className="section-header">
          <div>
            <h2>Rough Timeline</h2>
          </div>
          <p>
            The timeline keeps order, trims, and source references stable so the same state can drive
            browser review and Resolve export.
          </p>
        </div>
        <div className="timeline-list">
          {project.timeline.items.map((item, index) => {
            const take = takeViews.find((view) => view.take.id === item.take_recommendation_id);

            if (!take) {
              return null;
            }

            const duration = Math.max(0, item.trim_out_sec - item.trim_in_sec);
            const width = Math.max(16, Math.round((duration / totalTimelineDuration) * 100));

            return (
              <article className="timeline-item" key={item.id}>
                <div className="timeline-index">{index + 1}</div>
                <div>
                  <div className="take-meta">
                    <span className="badge">{item.label}</span>
                    <span className="score-chip">{duration.toFixed(2)}s used</span>
                  </div>
                  <h3>{take.take.title}</h3>
                  <p>{item.notes}</p>
                  <div className="take-facts">
                    <span>{item.source_reel}</span>
                    <span>
                      Segment trim {item.trim_in_sec.toFixed(2)}s to {item.trim_out_sec.toFixed(2)}s
                    </span>
                    <span>{take.asset.source_path}</span>
                    {take.segment.ai_understanding ? (
                      <span>roles: {take.segment.ai_understanding.story_roles.join(", ")}</span>
                    ) : null}
                  </div>
                  <div className="timeline-bar">
                    <span style={{ width: `${width}%` }} />
                  </div>
                </div>
              </article>
            );
          })}
        </div>
        <p className="footnote">{project.timeline.story_summary}</p>
      </section>
    </main>
  );
}

type MetricCardProps = {
  label: string;
  value: string;
};

function MetricCard({ label, value }: MetricCardProps) {
  return (
    <article className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </article>
  );
}
