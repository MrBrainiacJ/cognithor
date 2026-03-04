import { useEffect, useRef } from "react";

function formatTime(d) {
  if (!d) return "";
  const dt = d instanceof Date ? d : new Date(d);
  return dt.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

/**
 * Simple markdown-like rendering:
 * **bold**, *italic*, `inline code`, ```code blocks```
 */
function renderMarkdown(text) {
  if (!text) return null;

  // Split by code blocks first
  const parts = text.split(/(```[\s\S]*?```)/g);

  return parts.map((part, i) => {
    // Code block
    if (part.startsWith("```") && part.endsWith("```")) {
      const inner = part.slice(3, -3);
      // Remove optional language identifier on first line
      const lines = inner.split("\n");
      const firstLine = lines[0].trim();
      const isLang = /^[a-z]+$/i.test(firstLine) && lines.length > 1;
      const code = isLang ? lines.slice(1).join("\n") : inner;
      return (
        <pre key={i} className="cc-msg-codeblock">
          <code>{code}</code>
        </pre>
      );
    }

    // Inline formatting
    return <span key={i}>{renderInline(part)}</span>;
  });
}

function renderInline(text) {
  // Split by inline code first
  const parts = text.split(/(`[^`]+`)/g);
  return parts.map((seg, i) => {
    if (seg.startsWith("`") && seg.endsWith("`")) {
      return <code key={i} className="cc-msg-inline-code">{seg.slice(1, -1)}</code>;
    }
    // Bold
    let result = seg.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    // Italic (single *)
    result = result.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "<em>$1</em>");
    return <span key={i} dangerouslySetInnerHTML={{ __html: result }} />;
  });
}

export function MessageList({ messages, streamText, isStreaming }) {
  const endRef = useRef(null);
  const listRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (endRef.current) {
      endRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, streamText]);

  const isEmpty = messages.length === 0 && !streamText;

  return (
    <div className="cc-msg-list" ref={listRef}>
      {isEmpty && (
        <div className="cc-msg-empty">
          <div className="cc-msg-empty-icon">
            <svg width="48" height="48" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24" style={{ opacity: 0.3 }}>
              <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"/>
            </svg>
          </div>
          <div className="cc-msg-empty-text">Hallo! Frag mich etwas...</div>
        </div>
      )}

      {messages.map(msg => (
        <div key={msg.id} className={`cc-msg-row cc-msg-row-${msg.role}`}>
          <div className={`cc-msg-bubble cc-msg-${msg.role}`}>
            <div className="cc-msg-content">
              {msg.role === "assistant" ? renderMarkdown(msg.text) : msg.text}
            </div>
            <div className="cc-msg-time">{formatTime(msg.time)}</div>
          </div>
        </div>
      ))}

      {isStreaming && streamText && (
        <div className="cc-msg-row cc-msg-row-assistant">
          <div className="cc-msg-bubble cc-msg-assistant cc-msg-streaming">
            <div className="cc-msg-content">
              {renderMarkdown(streamText)}
            </div>
          </div>
        </div>
      )}

      <div ref={endRef} />
    </div>
  );
}
