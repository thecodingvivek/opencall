"use client";

import { useEffect, useRef, useState } from "react";

type Props = { text: string; languageCode: string; disabled: boolean };
type Playback = "idle" | "loading" | "ready" | "playing";
type VoiceOptions = { voices: string[]; default_voice: string };
const deliveries = [
  ["neutral", "Neutral"], ["excited", "Excited"], ["whispers", "Whispering"],
  ["shouting", "Shouting"], ["laugh", "Laughing"], ["giggle", "Giggling"],
  ["sigh", "Sighing"], ["exhales", "Exhaling"], ["sniffles", "Sniffling"],
  ["yawns", "Yawning"], ["coughs", "Coughing"], ["clears throat", "Clearing throat"],
  ["slow", "Slow"], ["pauses", "Opening pause"],
];

export function TranscriptSpeaker({ text, languageCode, disabled }: Props) {
  const [options, setOptions] = useState<VoiceOptions | null>(null);
  const [voice, setVoice] = useState("");
  const [delivery, setDelivery] = useState("neutral");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    const timeout = setTimeout(() => {
      if (active) {
        active = false;
        setError("Loading voices timed out. Please retry.");
      }
    }, 15000);
    async function loadVoices() {
      try {
        const api = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
        const response = await fetch(`${api}/api/v1/speech/voices?language_code=${encodeURIComponent(languageCode)}`, { cache: "no-store" });
        if (!response.ok) throw new Error("Could not load voices. Check that the backend is running.");
        const result = await response.json();
        if (!Array.isArray(result.voices) || !result.voices.length ||
            !result.voices.every((value: unknown) => typeof value === "string") ||
            !result.voices.includes(result.default_voice)) {
          throw new Error("The speech service returned an invalid voice list.");
        }
        if (active) {
          setOptions(result);
          setVoice(result.default_voice);
        }
      } catch (cause) {
        if (active) setError(cause instanceof TypeError ? "Cannot reach the backend to load voices."
          : cause instanceof Error ? cause.message : "Could not load voices.");
      } finally {
        clearTimeout(timeout);
      }
    }
    void loadVoices();
    return () => { active = false; clearTimeout(timeout); };
  }, [languageCode, attempt]);

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex flex-wrap items-end justify-end gap-2">
        <label className="flex flex-col gap-1 text-[10px] text-[#69765e]">
          Voice
          <select
            aria-label="Speaking voice"
            className="max-w-[135px] rounded-[5px] border border-[#d4e2bc] bg-[#fafbf5] px-2 py-[7px] text-[10px] text-[#405b2d] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#739b44] disabled:opacity-40"
            value={voice}
            disabled={disabled || !text.trim() || !options}
            onChange={(event) => setVoice(event.target.value)}
          >
            {options ? options.voices.map((name) => <option key={name} value={name}>{name}</option>) : <option value="">{error ? "Unavailable" : "Loading voices…"}</option>}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[10px] text-[#69765e]">
          Delivery
          <select
            aria-label="Speaking delivery"
            className="max-w-[135px] rounded-[5px] border border-[#d4e2bc] bg-[#fafbf5] px-2 py-[7px] text-[10px] text-[#405b2d] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#739b44] disabled:opacity-40"
            value={delivery}
            disabled={disabled || !text.trim() || !options}
            onChange={(event) => setDelivery(event.target.value)}
          >
            {deliveries.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <TranscriptPlayback key={`${voice}:${delivery}`} text={text} languageCode={languageCode} voice={voice} delivery={delivery} disabled={disabled || !options} />
      </div>
      {error && <p role="status" className="max-w-[230px] text-right text-[11px] leading-relaxed text-[#91492d]">{error} <button type="button" className="cursor-pointer underline" onClick={() => { setError(""); setOptions(null); setVoice(""); setAttempt((value) => value + 1); }}>Retry</button></p>}
    </div>
  );
}

function TranscriptPlayback({ text, languageCode, disabled, voice, delivery }: Props & { voice: string; delivery: string }) {
  const [state, setState] = useState<Playback>("idle");
  const [message, setMessage] = useState("");
  const audio = useRef<HTMLAudioElement | null>(null);
  const audioUrl = useRef<string | null>(null);
  const request = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const busy = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      request.current?.abort();
      if (audio.current) {
        audio.current.onended = null;
        audio.current.onerror = null;
        audio.current.pause();
        audio.current.removeAttribute("src");
        audio.current.load();
      }
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
    };
  }, []);

  async function play(player: HTMLAudioElement) {
    try {
      await player.play();
      if (mounted.current) setState("playing");
    } catch (cause) {
      if (mounted.current) {
        setState("ready");
        setMessage(cause instanceof DOMException && cause.name === "NotAllowedError"
          ? "Audio is ready. Click Play to listen."
          : "Audio could not play. Please try again.");
      }
    }
  }

  async function listen() {
    if (disabled || !text.trim() || busy.current) return;
    setMessage("");
    if (audio.current) {
      if (!audio.current.paused) {
        audio.current.pause();
        audio.current.currentTime = 0;
        setState("ready");
      } else {
        await play(audio.current);
      }
      return;
    }

    busy.current = true;
    setState("loading");
    const controller = new AbortController();
    request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 90000);
    try {
      const api = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
      const response = await fetch(`${api}/api/v1/speech/synthesize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language_code: languageCode, voice, delivery }),
        signal: controller.signal,
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(typeof result.detail === "string" ? result.detail : "Could not generate speech for this transcript.");
      }
      if (!response.headers.get("content-type")?.startsWith("audio/wav")) {
        throw new Error("The speech service returned an invalid audio response.");
      }
      const blob = await response.blob();
      if (!mounted.current) return;
      if (!blob.size) throw new Error("The speech service returned empty audio.");
      audioUrl.current = URL.createObjectURL(blob);
      const player = new Audio(audioUrl.current);
      audio.current = player;
      player.onended = () => {
        if (mounted.current) setState("ready");
      };
      player.onerror = () => {
        if (!mounted.current) return;
        audio.current = null;
        if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
        audioUrl.current = null;
        setState("idle");
        setMessage("Could not play this audio. Click Listen to try again.");
      };
      await play(player);
    } catch (cause) {
      if (mounted.current) {
        setState("idle");
        setMessage(cause instanceof Error && cause.name === "AbortError"
          ? "Audio generation timed out. Please try again."
          : cause instanceof TypeError ? "Cannot reach the speech service. Check that the backend is running."
          : cause instanceof Error ? cause.message : "Could not generate audio.");
      }
    } finally {
      clearTimeout(timeout);
      busy.current = false;
    }
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        type="button"
        className="flex cursor-pointer items-center gap-1.5 rounded-[5px] border border-[#d4e2bc] bg-[#edf3e3] px-[9px] py-[7px] text-[10px] whitespace-nowrap text-[#405b2d] transition-colors hover:bg-[#e1ebd2] disabled:cursor-default disabled:opacity-40"
        disabled={disabled || !text.trim() || state === "loading"}
        onClick={listen}
        aria-label={state === "playing" ? "Stop reading transcript" : "Listen to transcript"}
        aria-pressed={state === "playing"}
        aria-busy={state === "loading"}
      >
        {state === "playing" ? <span className="size-3 rounded-[2px] bg-current" aria-hidden="true" /> : (
          <svg className={`size-3.5 ${state === "loading" ? "motion-safe:animate-pulse" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
            <path d="M11 4 6 8H3v8h3l5 4V4Z" strokeLinejoin="round" /><path d="M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14" strokeLinecap="round" />
          </svg>
        )}
        {state === "loading" ? "Generating…" : state === "playing" ? "Stop" : state === "ready" ? "Play" : "Listen"}
      </button>
      {message && <p role="status" className="max-w-[230px] text-right text-[11px] leading-relaxed text-[#91492d]">{message}</p>}
    </div>
  );
}
