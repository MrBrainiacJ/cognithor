export function VoiceIndicator({ voiceState, lastHeard, VoiceState }) {
  const stateLabels = {
    [VoiceState.LISTENING]: "Sag \"Jarvis\"...",
    [VoiceState.CONVERSATION]: "Ich hoere zu... (\"Jarvis Ende\" zum Beenden)",
    [VoiceState.PROCESSING]: "Verarbeite...",
    [VoiceState.SPEAKING]: "Spricht...",
  };

  const stateIcons = {
    [VoiceState.LISTENING]: "cc-voice-pulse",
    [VoiceState.CONVERSATION]: "cc-voice-record",
    [VoiceState.PROCESSING]: "cc-voice-spin",
    [VoiceState.SPEAKING]: "cc-voice-speak",
  };

  const label = stateLabels[voiceState] || "";
  const iconClass = stateIcons[voiceState] || "cc-voice-pulse";

  if (voiceState === VoiceState.OFF) return null;

  // Show what Chrome transcribes in LISTENING and CONVERSATION states
  const showTranscript = lastHeard && (
    voiceState === VoiceState.LISTENING ||
    voiceState === VoiceState.CONVERSATION
  );

  return (
    <div className="cc-voice-bar">
      <span className={`cc-voice-indicator ${iconClass}`} />
      <span className="cc-voice-label">{label}</span>
      {showTranscript && (
        <span className="cc-voice-transcript">"{lastHeard}"</span>
      )}
    </div>
  );
}
