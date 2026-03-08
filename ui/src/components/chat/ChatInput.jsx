import { useState, useRef, useCallback } from "react";

const MAX_VOICE_DURATION = 15000; // 15 seconds

export function ChatInput({ onSend, onFile, onVoice, disabled }) {
  const [text, setText] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const textareaRef = useRef(null);
  const fileRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const recordTimerRef = useRef(null);

  const sendLockRef = useRef(false);
  const handleSend = useCallback(() => {
    if (!text.trim() || disabled || sendLockRef.current) return;
    sendLockRef.current = true;
    setTimeout(() => { sendLockRef.current = false; }, 500);
    onSend(text.trim());
    setText("");
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, disabled, onSend]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  const handleInput = useCallback((e) => {
    setText(e.target.value);
    // Auto-resize up to 5 lines
    const ta = e.target;
    ta.style.height = "auto";
    const lineHeight = 22;
    const maxHeight = lineHeight * 5 + 20; // 5 lines + padding
    ta.style.height = Math.min(ta.scrollHeight, maxHeight) + "px";
  }, []);

  const handleFileClick = useCallback(() => {
    fileRef.current?.click();
  }, []);

  const handleFileChange = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file && onFile) {
      onFile(file);
    }
    e.target.value = "";
  }, [onFile]);

  const startRecording = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        if (chunksRef.current.length > 0 && onVoice) {
          const blob = new Blob(chunksRef.current, { type: "audio/webm" });
          onVoice(blob);
        }
        setIsRecording(false);
        if (recordTimerRef.current) {
          clearTimeout(recordTimerRef.current);
          recordTimerRef.current = null;
        }
      };

      recorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);

      // Auto-stop after max duration
      recordTimerRef.current = setTimeout(() => {
        if (recorderRef.current?.state === "recording") {
          recorderRef.current.stop();
        }
      }, MAX_VOICE_DURATION);
    } catch {
      // Microphone access denied
    }
  }, [onVoice]);

  const stopRecording = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
  }, []);

  const handleVoiceClick = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  return (
    <div className="cc-chat-input">
      <div className="cc-chat-input-row">
        <textarea
          ref={textareaRef}
          className="cc-chat-textarea"
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Nachricht eingeben..."
          disabled={disabled}
          rows={1}
        />
        <div className="cc-chat-input-actions">
          <button
            className="cc-chat-input-btn"
            onClick={handleFileClick}
            disabled={disabled}
            title="Datei anhängen"
            type="button"
          >
            <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
            </svg>
          </button>
          <button
            className={`cc-chat-input-btn ${isRecording ? "cc-recording" : ""}`}
            onClick={handleVoiceClick}
            disabled={disabled}
            title={isRecording ? "Aufnahme stoppen" : "Sprachnachricht"}
            type="button"
          >
            <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/>
              <path d="M19 10v2a7 7 0 01-14 0v-2M12 19v4M8 23h8"/>
            </svg>
          </button>
          <button
            className="cc-chat-input-btn cc-chat-send-btn"
            onClick={handleSend}
            disabled={disabled || !text.trim()}
            title="Senden (Enter)"
            type="button"
          >
            <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
            </svg>
          </button>
        </div>
      </div>
      <input
        ref={fileRef}
        type="file"
        style={{ display: "none" }}
        onChange={handleFileChange}
      />
    </div>
  );
}
