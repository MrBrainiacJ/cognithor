import { useState, useRef, useCallback, useEffect } from "react";

/**
 * Voice Mode Hook: Wake-Word → Conversation → "Jarvis Ende"
 *
 * Flow:
 *   OFF → activate → LISTENING (waiting for wake word)
 *   LISTENING → "Jarvis" detected → CONVERSATION (continuous listening)
 *   CONVERSATION → speech → send as command → PROCESSING
 *   PROCESSING → response arrives → SPEAKING (TTS)
 *   SPEAKING → TTS done → CONVERSATION (resume listening)
 *   CONVERSATION → "Jarvis Ende" → LISTENING (back to wake word)
 *
 * Wake word detection uses Levenshtein distance so ANY pronunciation
 * that's phonetically close enough to "jarvis" works — no need for
 * an exhaustive variant list.
 */

const DEFAULT_WAKE_WORD = "jarvis";
const RESTART_DELAY_NORMAL = 400;
const RESTART_DELAY_SILENCE = 2000;
const RESTART_DELAY_ERROR = 5000;
const CONVERSATION_TIMEOUT = 45000;
// Max Levenshtein distance to accept as wake word (out of ~6 chars)
const WAKE_WORD_MAX_DISTANCE = 3;

const VoiceState = {
  OFF: "off",
  LISTENING: "listening",
  CONVERSATION: "conversation",
  PROCESSING: "processing",
  SPEAKING: "speaking",
};

// End keywords
const END_KEYWORDS_RE = /\b(?:ende|stop|stopp|aus|schluss|tsch[uü]ss)\s*[.!]?\s*$/i;

// ── Levenshtein distance ──────────────────────────────────────────────
function levenshtein(a, b) {
  const m = a.length, n = b.length;
  if (m === 0) return n;
  if (n === 0) return m;
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1));
  for (let i = 0; i <= m; i++) dp[i][0] = i;
  for (let j = 0; j <= n; j++) dp[0][j] = j;
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[i][j] = Math.min(
        dp[i - 1][j] + 1,      // deletion
        dp[i][j - 1] + 1,      // insertion
        dp[i - 1][j - 1] + cost // substitution
      );
    }
  }
  return dp[m][n];
}

/**
 * Phonetic normalization for German speech recognition.
 * Maps common German consonant clusters to simpler equivalents
 * so that "dschawis", "tschawis", "schavis" all normalize
 * close to "jarvis".
 */
function normalizePhonetic(s) {
  return s.toLowerCase()
    .replace(/ciao/g, "ja")    // Italian loan: "ciao bis" → "ja bis"
    .replace(/tsch/g, "j")     // tsch ≈ j (Dschungel, Tschechien)
    .replace(/dsch/g, "j")     // dsch ≈ j
    .replace(/sch/g, "j")      // sch → j (rough but effective for "jarvis")
    .replace(/ch/g, "k")       // ch → k
    .replace(/w/g, "v")        // w = v in German
    .replace(/ph/g, "f")       // ph = f
    .replace(/(.)\1+/g, "$1")  // remove double letters
    .replace(/[^a-z]/g, "");   // keep only letters
}

/**
 * Check if any word (or pair of consecutive words) in the text
 * sounds close enough to the wake word.
 * Uses phonetic normalization + Levenshtein distance.
 * Returns { index, count, matched } or null.
 */
function findWakeWord(text, wakeWord, maxDist) {
  const clean = text.toLowerCase().replace(/[.,!?;:]/g, "");
  const words = clean.split(/\s+/).filter(Boolean);
  const wwNorm = normalizePhonetic(wakeWord);

  // Check individual words (threshold: maxDist)
  for (let i = 0; i < words.length; i++) {
    const norm = normalizePhonetic(words[i]);
    if (norm.length >= 3 && levenshtein(norm, wwNorm) <= maxDist) {
      return { index: i, count: 1, matched: words[i] };
    }
  }

  // Check consecutive word pairs — stricter threshold (maxDist - 1)
  // and require first word to be >= 3 chars to avoid "ja + bis" false positives
  const pairDist = Math.max(maxDist - 1, 1);
  for (let i = 0; i < words.length - 1; i++) {
    if (words[i].length < 3) continue;
    const norm = normalizePhonetic(words[i] + words[i + 1]);
    if (levenshtein(norm, wwNorm) <= pairDist) {
      return { index: i, count: 2, matched: words[i] + " " + words[i + 1] };
    }
  }

  return null;
}

/**
 * Strip the wake word from text and return everything after it.
 */
function stripWakeFromText(text, wakeWord, maxDist) {
  const clean = text.toLowerCase().replace(/[.,!?;:]/g, "");
  const words = clean.split(/\s+/).filter(Boolean);
  const wwNorm = normalizePhonetic(wakeWord);
  const origWords = text.split(/\s+/);

  for (let i = 0; i < words.length; i++) {
    const norm = normalizePhonetic(words[i]);
    if (norm.length >= 3 && levenshtein(norm, wwNorm) <= maxDist) {
      return origWords.slice(i + 1).join(" ").replace(/^[\s,.:!?]+/, "").trim();
    }
  }
  const pairDist = Math.max(maxDist - 1, 1);
  for (let i = 0; i < words.length - 1; i++) {
    if (words[i].length < 3) continue;
    const norm = normalizePhonetic(words[i] + words[i + 1]);
    if (levenshtein(norm, wwNorm) <= pairDist) {
      return origWords.slice(i + 2).join(" ").replace(/^[\s,.:!?]+/, "").trim();
    }
  }
  return text;
}

function getSpeechRecognition() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

async function checkMicPermission() {
  try {
    const result = await navigator.permissions.query({ name: "microphone" });
    return result.state;
  } catch {
    return "prompt";
  }
}

export function useVoiceMode({ onCommand, wakeWord }) {
  const [voiceState, setVoiceState] = useState(VoiceState.OFF);
  const [lastHeard, setLastHeard] = useState("");
  const [isSupported] = useState(() => !!getSpeechRecognition());

  const recognitionRef = useRef(null);
  const audioRef = useRef(null);
  const restartTimerRef = useRef(null);
  const conversationTimerRef = useRef(null);
  const activeRef = useRef(false);
  const stateRef = useRef(VoiceState.OFF);
  const recognitionRunningRef = useRef(false);
  const lastHeardThrottleRef = useRef(0);
  const startRecognitionRef = useRef(null);
  const wakeWordRef = useRef((wakeWord || DEFAULT_WAKE_WORD).toLowerCase());

  useEffect(() => { stateRef.current = voiceState; }, [voiceState]);
  useEffect(() => { wakeWordRef.current = (wakeWord || DEFAULT_WAKE_WORD).toLowerCase(); }, [wakeWord]);

  const setState = useCallback((s) => {
    stateRef.current = s;
    setVoiceState(s);
  }, []);

  const clearTimers = useCallback(() => {
    if (restartTimerRef.current) { clearTimeout(restartTimerRef.current); restartTimerRef.current = null; }
    if (conversationTimerRef.current) { clearTimeout(conversationTimerRef.current); conversationTimerRef.current = null; }
  }, []);

  // Update lastHeard (throttled, max 3/sec)
  const updateLastHeard = useCallback((text) => {
    const now = Date.now();
    if (now - lastHeardThrottleRef.current > 333) {
      lastHeardThrottleRef.current = now;
      setLastHeard(text);
    }
  }, []);

  // ── Schedule recognition restart ──────────────────────────────────
  const scheduleRestart = useCallback((delay) => {
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
    restartTimerRef.current = setTimeout(() => {
      if (activeRef.current && stateRef.current !== VoiceState.SPEAKING) {
        startRecognitionRef.current?.();
      }
    }, delay);
  }, []);

  // ── Conversation inactivity timeout ────────────────────────────────
  const resetConversationTimeout = useCallback(() => {
    if (conversationTimerRef.current) clearTimeout(conversationTimerRef.current);
    conversationTimerRef.current = setTimeout(() => {
      if (stateRef.current === VoiceState.CONVERSATION) {
        console.log("[Voice] Conversation timeout — back to wake word listening");
        setState(VoiceState.LISTENING);
      }
    }, CONVERSATION_TIMEOUT);
  }, [setState]);

  // ── Stop recognition ──────────────────────────────────────────────
  const stopRecognition = useCallback(() => {
    recognitionRunningRef.current = false;
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch {}
    }
  }, []);

  // ── TTS Playback ──────────────────────────────────────────────────
  const playTTS = useCallback(async (text) => {
    if (!text) return;
    stopRecognition();
    setState(VoiceState.SPEAKING);
    try {
      const resp = await fetch("/api/v1/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!resp.ok || !(resp.headers.get("content-type") || "").includes("audio")) {
        console.warn("[Voice] TTS failed:", resp.status);
        if (activeRef.current) {
          setState(VoiceState.CONVERSATION);
          resetConversationTimeout();
          scheduleRestart(RESTART_DELAY_NORMAL);
        }
        return;
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;

      const onDone = () => {
        URL.revokeObjectURL(url);
        audioRef.current = null;
        if (activeRef.current) {
          setState(VoiceState.CONVERSATION);
          resetConversationTimeout();
          scheduleRestart(RESTART_DELAY_NORMAL);
        }
      };
      audio.onended = onDone;
      audio.onerror = onDone;
      audio.play().catch(onDone);
    } catch (err) {
      console.error("[Voice] TTS error:", err);
      if (activeRef.current) {
        setState(VoiceState.CONVERSATION);
        resetConversationTimeout();
        scheduleRestart(RESTART_DELAY_NORMAL);
      }
    }
  }, [setState, scheduleRestart, stopRecognition, resetConversationTimeout]);

  // ── Check for end phrase ──────────────────────────────────────────
  const isEndPhrase = useCallback((text) => {
    if (!END_KEYWORDS_RE.test(text)) return false;
    // Short utterances (≤ 3 words) ending with end keyword are always end phrases.
    // This handles Chrome mis-transcriptions like "Chavez Ende" for "Jarvis Ende".
    const words = text.trim().split(/\s+/);
    if (words.length <= 3) return true;
    // Longer text: require wake word before end keyword to avoid false positives
    const beforeEnd = text.replace(END_KEYWORDS_RE, "").trim();
    if (beforeEnd.length < 2) return true;
    return !!findWakeWord(beforeEnd, wakeWordRef.current, WAKE_WORD_MAX_DISTANCE);
  }, []);

  // ── Handle recognized speech ──────────────────────────────────────
  const handleResult = useCallback((event) => {
    const state = stateRef.current;
    if (state === VoiceState.OFF || state === VoiceState.SPEAKING || state === VoiceState.PROCESSING) return;

    let finalText = "";
    let interimText = "";

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const r = event.results[i];
      const t = r[0].transcript;
      if (r.isFinal) { finalText += t + " "; } else { interimText += t + " "; }
    }

    const allText = (finalText + interimText).trim();
    // Always show what Chrome hears (even in LISTENING state for debugging)
    if (allText) setLastHeard(allText);

    // ── LISTENING state: wait for wake word ──────────────────────────
    if (state === VoiceState.LISTENING) {
      // IMPORTANT: Only act on FINAL results to prevent a race condition.
      // Chrome fires interim → final events for the same utterance.
      // If we change state on an interim, the subsequent final event
      // would land in CONVERSATION state and get sent as a command.
      if (!finalText.trim()) return;

      const ww = wakeWordRef.current;
      const text = finalText.trim();
      const found = findWakeWord(text, ww, WAKE_WORD_MAX_DISTANCE);
      if (!found) return;

      console.log(`[Voice] Wake word detected: "${found.matched}" (in: "${text}")`);

      // Check if there's a command after the wake word
      const afterWake = stripWakeFromText(text, ww, WAKE_WORD_MAX_DISTANCE);
      if (afterWake.length > 1) {
        setState(VoiceState.PROCESSING);
        setLastHeard(afterWake);
        onCommand(afterWake);
        resetConversationTimeout();
        return;
      }

      // Just wake word alone → enter conversation mode
      setState(VoiceState.CONVERSATION);
      setLastHeard("");
      resetConversationTimeout();
      return;
    }

    // ── CONVERSATION state: everything is a command ──────────────────
    if (state === VoiceState.CONVERSATION) {
      if (!finalText.trim()) return;

      const text = finalText.trim();

      // Check for end phrase first
      if (isEndPhrase(text)) {
        console.log("[Voice] End phrase detected — back to wake word listening");
        setState(VoiceState.LISTENING);
        setLastHeard("");
        return;
      }

      // Strip wake word if accidentally included (e.g., user says "Jarvis, was...")
      const ww = wakeWordRef.current;
      let command = stripWakeFromText(text, ww, WAKE_WORD_MAX_DISTANCE);
      // If nothing remains after stripping, the text IS the wake word — skip it.
      // (Can happen if user repeats "Jarvis" in conversation mode.)
      if (command.length <= 1) {
        console.log(`[Voice] Ignoring wake-word-only text in conversation: "${text}"`);
        return;
      }

      resetConversationTimeout();
      setState(VoiceState.PROCESSING);
      setLastHeard(command);
      onCommand(command);
    }
  }, [onCommand, setState, isEndPhrase, resetConversationTimeout]);

  // ── Start SpeechRecognition ───────────────────────────────────────
  const startRecognition = useCallback(() => {
    const SR = getSpeechRecognition();
    if (!SR || !activeRef.current) return;
    if (recognitionRunningRef.current) return;

    if (recognitionRef.current) {
      try {
        recognitionRef.current.onresult = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.onend = null;
        recognitionRef.current.abort();
      } catch {}
      recognitionRef.current = null;
    }

    const rec = new SR();
    rec.lang = "de-DE";
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    recognitionRef.current = rec;

    rec.onstart = () => { recognitionRunningRef.current = true; };
    rec.onresult = handleResult;

    rec.onerror = (e) => {
      recognitionRunningRef.current = false;
      if (e.error === "aborted") return;
      if (e.error === "not-allowed") {
        console.error("[Voice] Microphone access blocked.");
        setState(VoiceState.OFF);
        activeRef.current = false;
        return;
      }
      if (e.error === "no-speech") {
        if (activeRef.current && stateRef.current !== VoiceState.SPEAKING) {
          scheduleRestart(RESTART_DELAY_SILENCE);
        }
        return;
      }
      console.warn("[Voice] SpeechRecognition error:", e.error);
      if (activeRef.current && stateRef.current !== VoiceState.SPEAKING) {
        scheduleRestart(RESTART_DELAY_ERROR);
      }
    };

    rec.onend = () => {
      recognitionRunningRef.current = false;
      if (activeRef.current && stateRef.current !== VoiceState.SPEAKING && stateRef.current !== VoiceState.OFF) {
        scheduleRestart(RESTART_DELAY_NORMAL);
      }
    };

    try {
      rec.start();
    } catch (err) {
      console.error("[Voice] start() failed:", err);
      recognitionRunningRef.current = false;
      if (activeRef.current) scheduleRestart(RESTART_DELAY_ERROR);
    }
  }, [handleResult, setState, scheduleRestart]);

  useEffect(() => { startRecognitionRef.current = startRecognition; }, [startRecognition]);

  // ── Activate / Deactivate ─────────────────────────────────────────
  const activate = useCallback(async () => {
    if (!isSupported) return;
    if (activeRef.current) return;

    const permState = await checkMicPermission();
    if (permState === "denied") {
      console.error("[Voice] Microphone permanently denied.");
      return;
    }
    if (permState === "prompt") {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(t => t.stop());
        await new Promise(r => setTimeout(r, 300));
      } catch (err) {
        console.error("[Voice] Microphone permission denied:", err);
        return;
      }
    }

    console.log("[Voice] Activating voice mode");
    activeRef.current = true;
    setState(VoiceState.LISTENING);
    localStorage.setItem("jarvis_voice_active", "1");
    startRecognition();
  }, [isSupported, startRecognition, setState]);

  const deactivate = useCallback(() => {
    activeRef.current = false;
    setState(VoiceState.OFF);
    clearTimers();
    stopRecognition();
    if (recognitionRef.current) {
      try { recognitionRef.current.onresult = null; recognitionRef.current.onerror = null; recognitionRef.current.onend = null; } catch {}
      recognitionRef.current = null;
    }
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    localStorage.removeItem("jarvis_voice_active");
  }, [setState, clearTimers, stopRecognition]);

  const toggle = useCallback(() => {
    if (voiceState === VoiceState.OFF) activate(); else deactivate();
  }, [voiceState, activate, deactivate]);

  const speakResponse = useCallback((text) => {
    if (!activeRef.current || !text) return;
    if (stateRef.current !== VoiceState.SPEAKING && stateRef.current !== VoiceState.OFF) {
      playTTS(text);
    }
  }, [playTTS]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      activeRef.current = false;
      if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
      if (conversationTimerRef.current) clearTimeout(conversationTimerRef.current);
      if (recognitionRef.current) {
        try { recognitionRef.current.onresult = null; recognitionRef.current.onerror = null; recognitionRef.current.onend = null; recognitionRef.current.abort(); } catch {}
      }
      if (audioRef.current) { audioRef.current.pause(); }
    };
  }, []);

  return {
    voiceState, lastHeard, isSupported,
    isActive: voiceState !== VoiceState.OFF,
    toggle, activate, deactivate,
    speakResponse, playTTS,
    VoiceState,
  };
}
