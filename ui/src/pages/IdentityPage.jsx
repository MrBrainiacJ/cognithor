import { useState, useEffect, useCallback } from "react";

const api = async (method, path, body) => {
  const token = sessionStorage.getItem("jarvis-token") || "";
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (token) opts.headers.Authorization = `Bearer ${token}`;
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  return res.json();
};

export default function IdentityPage() {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionResult, setActionResult] = useState("");

  const fetchState = useCallback(async () => {
    try {
      const data = await api("GET", "/api/v1/identity/state");
      setState(data);
    } catch { setState(null); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchState(); }, [fetchState]);

  const doAction = async (action) => {
    setActionResult("...");
    try {
      const res = await api("POST", `/api/v1/identity/${action}`);
      setActionResult(JSON.stringify(res));
      fetchState();
    } catch (e) { setActionResult(e.message); }
  };

  if (loading) return <div className="cc-page-content"><p>Loading...</p></div>;
  if (!state || !state.available) {
    return (
      <div className="cc-page-content">
        <h2>Cognitive Identity</h2>
        <p style={{color: "var(--text2)"}}>Identity Layer not available. Install with: <code>pip install cognithor[identity]</code></p>
      </div>
    );
  }

  return (
    <div className="cc-page-content" style={{padding: "20px", maxWidth: "800px"}}>
      <h2 style={{marginBottom: "16px"}}>Cognitive Identity</h2>

      {/* State Overview */}
      <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "20px"}}>
        <div className="cc-id-card">
          <div className="cc-id-label">Energy</div>
          <div className="cc-id-bar">
            <div className="cc-id-bar-fill" style={{width: `${(state.somatic?.energy_level || 0.5) * 100}%`, background: "#00e676"}} />
          </div>
          <div className="cc-id-value">{state.somatic?.classify || "normal"}</div>
        </div>
        <div className="cc-id-card">
          <div className="cc-id-label">Interactions</div>
          <div className="cc-id-value" style={{fontSize: "24px"}}>{state.total_interactions || 0}</div>
        </div>
        <div className="cc-id-card">
          <div className="cc-id-label">Memories</div>
          <div className="cc-id-value" style={{fontSize: "24px"}}>{state.total_memories || 0}</div>
        </div>
        <div className="cc-id-card">
          <div className="cc-id-label">Character Strength</div>
          <div className="cc-id-bar">
            <div className="cc-id-bar-fill" style={{width: `${Math.min((state.character_strength || 0) * 10, 100)}%`, background: "#00d4ff"}} />
          </div>
          <div className="cc-id-value">{(state.character_strength || 0).toFixed(2)}</div>
        </div>
      </div>

      {/* Status */}
      <div style={{marginBottom: "20px", padding: "12px", background: "var(--bg)", borderRadius: "8px", border: "1px solid var(--border)"}}>
        <strong>Status:</strong> {state.is_frozen ? "Frozen" : "Active"} |
        <strong> Belief Crises:</strong> {state.active_belief_crises || 0} |
        <strong> GC Pruned:</strong> {state.gc_total_pruned || 0}
      </div>

      {/* Controls */}
      <div style={{display: "flex", gap: "8px", marginBottom: "16px"}}>
        <button className="cc-plan-btn cc-plan-btn-approve" onClick={() => doAction("dream")}>Dream Cycle</button>
        <button className="cc-plan-btn" onClick={() => doAction(state.is_frozen ? "unfreeze" : "freeze")} style={{background: "rgba(255,171,64,0.1)", color: "#ffab40", borderColor: "#ffab40"}}>
          {state.is_frozen ? "Unfreeze" : "Freeze"}
        </button>
        <button className="cc-plan-btn cc-plan-btn-reject" onClick={() => { if (confirm("Reset identity? Memories will be lost.")) doAction("reset"); }}>
          Soft Reset
        </button>
      </div>

      {actionResult && <pre style={{fontSize: "11px", color: "var(--text2)", padding: "8px", background: "var(--bg)", borderRadius: "4px"}}>{actionResult}</pre>}

      {/* Genesis Anchors */}
      <h3 style={{marginTop: "20px", marginBottom: "8px"}}>Genesis Anchors</h3>
      <div style={{fontSize: "12px", color: "var(--text2)"}}>
        {(state.genesis_anchors || []).map((a, i) => (
          <div key={i} style={{padding: "6px 0", borderBottom: "1px solid var(--border)"}}>
            <span style={{color: "#00e676", marginRight: "6px"}}>{i + 1}.</span> {a}
          </div>
        ))}
      </div>
    </div>
  );
}
