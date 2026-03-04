import { useState } from "react";

export function ApprovalBanner({ approval, onRespond }) {
  const [expanded, setExpanded] = useState(false);

  if (!approval) return null;

  return (
    <div className="cc-approval">
      <div className="cc-approval-header">
        <div className="cc-approval-info">
          <span className="cc-approval-icon">
            <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
          </span>
          <span className="cc-approval-tool">{approval.tool}</span>
          {approval.reason && (
            <span className="cc-approval-reason">— {approval.reason}</span>
          )}
        </div>
        <div className="cc-approval-actions">
          {approval.params && Object.keys(approval.params).length > 0 && (
            <button
              className="cc-approval-toggle"
              onClick={() => setExpanded(!expanded)}
              type="button"
            >
              {expanded ? "Details ausblenden" : "Details anzeigen"}
            </button>
          )}
          <button
            className="cc-approval-btn cc-approval-deny"
            onClick={() => onRespond(approval.id, false)}
            type="button"
          >
            Ablehnen
          </button>
          <button
            className="cc-approval-btn cc-approval-allow"
            onClick={() => onRespond(approval.id, true)}
            type="button"
          >
            Genehmigen
          </button>
        </div>
      </div>
      {expanded && approval.params && (
        <pre className="cc-approval-params">
          {JSON.stringify(approval.params, null, 2)}
        </pre>
      )}
    </div>
  );
}
