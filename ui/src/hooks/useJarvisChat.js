import { useState, useRef, useCallback, useEffect } from "react";

const WS_RECONNECT_DELAY = 3000;
const WS_MAX_RETRIES = 10;
const WS_HEARTBEAT_INTERVAL = 30000;

function makeSessionId() {
  return `web_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function useJarvisChat() {
  const [messages, setMessages] = useState([]);
  const [streamText, setStreamText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [canvasHtml, setCanvasHtml] = useState("");
  const [canvasTitle, setCanvasTitle] = useState("");
  const [activeTool, setActiveTool] = useState(null);
  const [pendingApproval, setPendingApproval] = useState(null);
  const [statusText, setStatusText] = useState("");

  const wsRef = useRef(null);
  const retriesRef = useRef(0);
  const heartbeatRef = useRef(null);
  const sessionIdRef = useRef(makeSessionId());
  const streamAccRef = useRef("");
  const reconnectTimerRef = useRef(null);

  const addMessage = useCallback((role, text, meta) => {
    setMessages(prev => [...prev, {
      id: Date.now() + Math.random(),
      role,
      text,
      time: new Date(),
      ...meta,
    }]);
  }, []);

  const handleWsMessage = useCallback((evt) => {
    let data;
    try { data = JSON.parse(evt.data); } catch { return; }

    switch (data.type) {
      case "assistant_message":
        setIsStreaming(false);
        setStreamText("");
        streamAccRef.current = "";
        addMessage("assistant", data.text || data.content || "");
        break;

      case "stream_token":
        setIsStreaming(true);
        streamAccRef.current += (data.token || data.content || "");
        setStreamText(streamAccRef.current);
        break;

      case "stream_end":
        setIsStreaming(false);
        if (streamAccRef.current) {
          addMessage("assistant", streamAccRef.current);
        }
        setStreamText("");
        streamAccRef.current = "";
        break;

      case "tool_start":
        setActiveTool({ name: data.tool || data.name, args: data.args });
        break;

      case "tool_result":
        setActiveTool(null);
        break;

      case "approval_request":
        setPendingApproval({
          id: data.id || data.request_id,
          tool: data.tool || data.name,
          reason: data.reason || "",
          params: data.params || data.args || {},
        });
        break;

      case "canvas_push":
        setCanvasHtml(data.html || data.content || "");
        setCanvasTitle(data.title || "Canvas");
        break;

      case "canvas_reset":
        setCanvasHtml("");
        setCanvasTitle("");
        break;

      case "canvas_eval":
        // handled in ChatCanvas via postMessage
        break;

      case "transcription":
        // Backend transcribed audio — update the last user message
        setMessages(prev => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === "user" && updated[i].text === "[Sprachnachricht]") {
              updated[i] = { ...updated[i], text: data.text };
              break;
            }
          }
          return updated;
        });
        break;

      case "status_update":
        setStatusText(data.text || data.status || "");
        break;

      case "error":
        addMessage("system", data.message || data.error || "Ein Fehler ist aufgetreten.");
        setIsStreaming(false);
        setStreamText("");
        streamAccRef.current = "";
        break;

      case "pong":
        // heartbeat response, ignore
        break;

      default:
        break;
    }
  }, [addMessage]);

  const startHeartbeat = useCallback((ws) => {
    if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    heartbeatRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, WS_HEARTBEAT_INTERVAL);
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  // Use refs for stable connect/disconnect to avoid useEffect re-triggering
  const handleWsMsgRef = useRef(handleWsMessage);
  useEffect(() => { handleWsMsgRef.current = handleWsMessage; }, [handleWsMessage]);

  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/ws/${sessionIdRef.current}`;

    let ws;
    try {
      ws = new WebSocket(url);
    } catch (err) {
      console.error("[WS] Failed to create WebSocket:", err);
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[WS] Connected to", url);
      setIsConnected(true);
      retriesRef.current = 0; // reset retries on successful connection
      startHeartbeat(ws);
    };

    ws.onmessage = (evt) => handleWsMsgRef.current(evt);

    ws.onclose = () => {
      setIsConnected(false);
      stopHeartbeat();
      wsRef.current = null;
      // Auto-reconnect with backoff
      if (retriesRef.current < WS_MAX_RETRIES) {
        retriesRef.current++;
        const delay = WS_RECONNECT_DELAY * Math.min(retriesRef.current, 3);
        console.log(`[WS] Reconnecting in ${delay}ms (attempt ${retriesRef.current}/${WS_MAX_RETRIES})`);
        reconnectTimerRef.current = setTimeout(connect, delay);
      } else {
        console.warn("[WS] Max retries reached. Click to reconnect or reload page.");
      }
    };

    ws.onerror = () => {
      // onclose will fire after onerror
    };
  }, [startHeartbeat, stopHeartbeat]);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    stopHeartbeat();
    if (wsRef.current) {
      wsRef.current.onclose = null; // prevent reconnect from cleanup
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, [stopHeartbeat]);

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    connect();
    return () => disconnect();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const sendMessage = useCallback((text) => {
    if (!text.trim()) return;
    addMessage("user", text.trim());
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "user_message",
        text: text.trim(),
        session_id: sessionIdRef.current,
      }));
    }
  }, [addMessage]);

  const sendFile = useCallback((file) => {
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result.split(",")[1];
      addMessage("user", `[Datei: ${file.name}]`);
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: "user_message",
          text: `[Datei: ${file.name}]`,
          session_id: sessionIdRef.current,
          metadata: {
            file_name: file.name,
            file_type: file.type,
            file_base64: base64,
          },
        }));
      }
    };
    reader.readAsDataURL(file);
  }, [addMessage]);

  const sendVoice = useCallback((blob) => {
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result.split(",")[1];
      addMessage("user", "[Sprachnachricht]");
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: "user_message",
          text: "[Sprachnachricht]",
          session_id: sessionIdRef.current,
          metadata: {
            audio_base64: base64,
            audio_type: blob.type || "audio/webm",
          },
        }));
      }
    };
    reader.readAsDataURL(blob);
  }, [addMessage]);

  const respondApproval = useCallback((id, approved) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "approval_response",
        id,
        approved,
        session_id: sessionIdRef.current,
      }));
    }
    setPendingApproval(null);
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setStreamText("");
    streamAccRef.current = "";
    setIsStreaming(false);
    setActiveTool(null);
    setPendingApproval(null);
    setCanvasHtml("");
    setCanvasTitle("");
    setStatusText("");
  }, []);

  return {
    messages,
    streamText,
    isStreaming,
    isConnected,
    canvasHtml,
    canvasTitle,
    activeTool,
    pendingApproval,
    statusText,
    sendMessage,
    sendFile,
    sendVoice,
    respondApproval,
    clearMessages,
  };
}
