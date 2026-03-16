/**
 * PipelineCanvas — Compact inline PGE pipeline indicator.
 *
 * Shows Plan → Gate → Execute → Replan as a single horizontal bar
 * with colored phase segments and elapsed time.
 */
import { useState, useEffect, useRef } from "react";

const PHASES = [
  { key: "plan", icon: "\u{1F9E0}", label: "Plan" },
  { key: "gate", icon: "\u{1F6E1}\uFE0F", label: "Gate" },
  { key: "execute", icon: "\u2699\uFE0F", label: "Exec" },
  { key: "replan", icon: "\u{1F4DD}", label: "Reply" },
];

const STATUS_BG = {
  pending: "rgba(85,85,112,0.25)",
  running: "rgba(0,212,255,0.2)",
  done: "rgba(0,230,118,0.2)",
  error: "rgba(255,82,82,0.2)",
  skipped: "rgba(68,68,68,0.15)",
};

const STATUS_BORDER = {
  pending: "#555570",
  running: "#00d4ff",
  done: "#00e676",
  error: "#ff5252",
  skipped: "#444",
};

const STATUS_TEXT = {
  pending: "#8888a0",
  running: "#00d4ff",
  done: "#00e676",
  error: "#ff5252",
  skipped: "#666",
};

function useElapsed(startMs, active) {
  const [elapsed, setElapsed] = useState(0);
  const ref = useRef(null);
  useEffect(() => {
    if (!active || !startMs) {
      setElapsed(0);
      return;
    }
    const tick = () => setElapsed(Date.now() - startMs);
    tick();
    ref.current = setInterval(tick, 200);
    return () => clearInterval(ref.current);
  }, [startMs, active]);
  return elapsed;
}

function PhaseChip({ phase, status, durationMs, startMs }) {
  const isRunning = status === "running";
  const elapsed = useElapsed(startMs, isRunning);
  const isSkipped = status === "skipped";

  const timeStr = isRunning
    ? `${(elapsed / 1000).toFixed(1)}s`
    : durationMs != null && durationMs > 0
      ? `${(durationMs / 1000).toFixed(1)}s`
      : "";

  return (
    <span
      className="cc-pipe-chip"
      style={{
        background: STATUS_BG[status] || STATUS_BG.pending,
        borderColor: STATUS_BORDER[status] || STATUS_BORDER.pending,
        color: STATUS_TEXT[status] || STATUS_TEXT.pending,
        opacity: isSkipped ? 0.4 : 1,
        textDecoration: isSkipped ? "line-through" : "none",
      }}
    >
      <span className="cc-pipe-icon">{phase.icon}</span>
      <span className="cc-pipe-label">{phase.label}</span>
      {timeStr && <span className="cc-pipe-time">{timeStr}</span>}
      {isRunning && <span className="cc-pipe-pulse" />}
    </span>
  );
}

export default function PipelineCanvas({ pipeline, onCancel }) {
  const [collapsed, setCollapsed] = useState(false);

  if (!pipeline || !pipeline.iterations || pipeline.iterations.length === 0) {
    return null;
  }

  const lastIter = pipeline.iterations[pipeline.iterations.length - 1];
  const phases = lastIter.phases || {};
  const isActive = pipeline.active;

  // Total elapsed
  const totalMs = pipeline.startMs ? Date.now() - pipeline.startMs : 0;
  const totalElapsed = useElapsed(pipeline.startMs, isActive);
  const totalStr = isActive
    ? `${(totalElapsed / 1000).toFixed(1)}s`
    : pipeline.startMs
      ? `${(totalMs / 1000).toFixed(1)}s`
      : "";

  return (
    <div className="cc-pipeline">
      <div
        className="cc-pipeline-header"
        onClick={() => setCollapsed((c) => !c)}
        role="button"
        tabIndex={0}
      >
        <span className="cc-pipeline-title">
          {isActive ? "\u25CF" : "\u2713"} Pipeline {totalStr && `\u00B7 ${totalStr}`}
        </span>
        {isActive && onCancel && (
          <button
            className="cc-pipe-cancel"
            onClick={(e) => { e.stopPropagation(); onCancel(); }}
            type="button"
            title="Stop"
          >
            {"\u25A0"} Stop
          </button>
        )}
        <span className="cc-pipeline-chevron">{collapsed ? "\u25B6" : "\u25BC"}</span>
      </div>
      {!collapsed && (
        <div className="cc-pipe-phases">
          {PHASES.map((p, i) => {
            const phaseData = phases[p.key] || { status: "pending" };
            return (
              <span key={p.key} className="cc-pipe-phase-wrap">
                {i > 0 && <span className="cc-pipe-arrow">{"\u2192"}</span>}
                <PhaseChip
                  phase={p}
                  status={phaseData.status}
                  durationMs={phaseData.durationMs}
                  startMs={phaseData.startMs}
                />
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
