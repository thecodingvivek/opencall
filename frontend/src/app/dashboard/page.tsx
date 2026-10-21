"use client";

import { useEffect, useRef, useState } from "react";
import { recordingToWav } from "@/lib/audio";
import { TranscriptSpeaker } from "./transcript-speaker";

const languages = [
  ["en-IN", "English (India)"], ["hi-IN", "Hindi"], ["te-IN", "Telugu"],
  ["ta-IN", "Tamil"], ["kn-IN", "Kannada"], ["ml-IN", "Malayalam"],
  ["mr-IN", "Marathi"], ["gu-IN", "Gujarati"], ["bn-IN", "Bengali"], ["pa-IN", "Punjabi"],
];
type Status = "idle" | "permission" | "recording" | "processing";

function Microphone() {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><rect x="9" y="2" width="6" height="13" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8" /></svg>;
}

export default function Dashboard() {
  const [status, setStatus] = useState<Status>("idle");
  const [language, setLanguage] = useState("en-IN");
  const [transcript, setTranscript] = useState<string | null>(null);
  const [transcriptLanguage, setTranscriptLanguage] = useState("en-IN");
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [copied, setCopied] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const request = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const busy = useRef(false);

  function releaseMicrophone() {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  }

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (recorder.current) {
        recorder.current.onstop = null;
        if (recorder.current.state !== "inactive") recorder.current.stop();
      }
      releaseMicrophone();
      request.current?.abort();
    };
  }, []);

  async function transcribe(blob: Blob, selectedLanguage: string) {
    if (!mounted.current) return;
    setStatus("processing");
    const controller = new AbortController();
    request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 90000);
    try {
      const wav = await recordingToWav(blob);
      if (!mounted.current) return;
      const form = new FormData();
      form.append("audio", wav, "recording.wav");
      form.append("language_code", selectedLanguage);
      const api = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
      const response = await fetch(`${api}/api/v1/speech/transcribe`, {
        method: "POST", body: form, signal: controller.signal,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "This recording could not be processed. Please try again.");
      if (typeof result.transcript !== "string") throw new Error("The speech service returned an invalid response.");
      if (mounted.current) {
        setTranscript(result.transcript);
        setTranscriptLanguage(selectedLanguage);
      }
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error && cause.name === "AbortError"
        ? "Transcription timed out. Please try a shorter recording."
        : cause instanceof TypeError ? "Cannot reach the speech service. Check that the backend is running."
        : cause instanceof Error ? cause.message : "Could not transcribe the recording.");
    } finally {
      clearTimeout(timeout);
      busy.current = false;
      if (mounted.current) setStatus("idle");
    }
  }

  async function startRecording() {
    if (busy.current) return;
    busy.current = true;
    setError("");
    setCopied(false);
    setSeconds(0);
    setTranscript(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Microphone recording requires a supported browser on localhost or HTTPS.");
      busy.current = false;
      return;
    }
    setStatus("permission");
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true } });
      if (!mounted.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = media;
      const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"].find((type) => MediaRecorder.isTypeSupported(type));
      const active = new MediaRecorder(media, mimeType ? { mimeType } : undefined);
      recorder.current = active;
      const chunks: Blob[] = [];
      active.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      active.onstop = () => {
        releaseMicrophone();
        void transcribe(new Blob(chunks, { type: active.mimeType }), language);
      };
      active.onerror = () => {
        active.onstop = null;
        if (active.state !== "inactive") active.stop();
        releaseMicrophone();
        busy.current = false;
        setStatus("idle");
        setError("Recording was interrupted. Please try again.");
      };
      active.start();
      setStatus("recording");
      const started = Date.now();
      timer.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - started) / 1000);
        setSeconds(elapsed);
        if (elapsed >= 55 && active.state === "recording") active.stop();
      }, 250);
    } catch (cause) {
      releaseMicrophone();
      busy.current = false;
      setStatus("idle");
      setError(cause instanceof DOMException && cause.name === "NotAllowedError"
        ? "Microphone access was denied. Allow it in your browser settings and try again."
        : "Could not start the microphone. Check that a microphone is connected and available.");
    }
  }

  function stopRecording() {
    if (recorder.current?.state === "recording") {
      setStatus("processing");
      recorder.current.stop();
    }
  }

  async function copyTranscript() {
    try {
      await navigator.clipboard.writeText(transcript || "");
      setCopied(true);
    } catch {
      setError("Could not copy automatically. Select and copy the transcript below.");
    }
  }

  return (
    <div className="flex min-h-screen bg-[#f6f8f3] font-sans text-[#21372d] [&_a:focus-visible]:outline-2 [&_a:focus-visible]:outline-offset-4 [&_a:focus-visible]:outline-[#739b44] [&_button:focus-visible]:outline-2 [&_button:focus-visible]:outline-offset-4 [&_button:focus-visible]:outline-[#739b44]">
      <aside className="hidden w-[238px] shrink-0 flex-col border-r border-[#e4e9e2] bg-[#fcfdf9] px-[22px] pt-[35px] pb-6 min-[851px]:flex max-[1100px]:w-[200px] max-[1100px]:px-4">
        <a className="flex items-center gap-[9px] text-[26px] font-semibold tracking-[-1.4px]" href="/dashboard">
          <span className="grid size-[31px] place-items-center rounded-[10px] bg-[#d9ef82] pb-[7px] text-[37px] leading-none">o</span>
          opencall
        </a>
        <span className="mx-3 mt-[57px] mb-[17px] text-[10px] tracking-[1.9px] text-[#8c948a]">WORKSPACE</span>
        <a href="/dashboard" aria-current="page" className="flex items-center gap-2.5 rounded-lg border border-[#e0e8d3] bg-[#eaf0df] px-3 py-[13px] text-[13px] font-medium [&_svg]:size-[17px]">
          <Microphone />Speech studio<span className="ml-auto text-[10px] text-[#738265]">01</span>
        </a>
        <div className="mt-auto flex items-center gap-2.5 pt-9 text-[11px]">
          <span className="grid size-[33px] place-items-center rounded-full border border-[#dce3d7] bg-[#edf1e6] text-[10px]">OC</span>
          <div>OpenCall workspace<small className="mt-[3px] block text-[10px] text-[#758078]">Voice tools</small></div>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[83px] items-center justify-between border-b border-[#e4e9e2] px-11 text-xs text-[#758078] max-[1100px]:px-[25px] max-[600px]:h-[65px] max-[600px]:px-5">
          <span>Workspace <span className="mx-[13px] text-[#bdc5b9]">/</span> <strong className="font-medium text-[#405044]">Speech studio</strong></span>
          <span className="rounded-full border border-[#dde4d6] bg-[#fcfdf9] px-3 py-[7px] text-[10px] max-[600px]:px-2 max-[600px]:text-[9px]">Powered by Gnani</span>
        </header>
        <main className="mx-auto w-full max-w-[1200px] px-11 pt-[52px] pb-[35px] min-[1600px]:pt-20 max-[1100px]:px-[25px] max-[1100px]:pt-[35px] max-[850px]:max-w-[740px] max-[600px]:px-[18px] max-[600px]:py-8">
          <div className="flex items-center gap-2 text-[10px] tracking-[2px] text-[#65785c]"><span className="size-1.5 rounded-full bg-[#759852]" />VOICE WORKSPACE</div>
          <h1 className="mt-4 mb-3 text-[clamp(30px,3.4vw,43px)] leading-[1.2] font-medium tracking-[-1.9px] max-[600px]:tracking-[-1.1px]">Your voice, in writing.</h1>
          <p className="mb-[35px] text-[13px] leading-[1.8] text-[#758078] max-[600px]:text-xs">Speak naturally. Turn a quick thought into text in seconds.</p>
          <div className="grid grid-cols-[minmax(290px,0.95fr)_minmax(300px,1.05fr)] gap-[22px] max-[1100px]:gap-4 max-[600px]:grid-cols-1">
            <section className="overflow-hidden rounded-[14px] border border-[#dfe5d9] bg-[#fffefa] p-[25px] shadow-[0_3px_4px_#243a2510] max-[1100px]:p-5" aria-labelledby="recorder-heading">
              <div className="flex items-center justify-between gap-2.5">
                <div><span className="text-[9px] tracking-[1.6px] text-[#829078]">01 / RECORD</span><h2 id="recorder-heading" className="mt-[9px] text-[15px] font-medium tracking-[-0.3px]">Start with your voice</h2></div>
                <span className="rounded border border-[#e5e9de] px-[7px] py-[5px] text-[9px] whitespace-nowrap text-[#7e8775] max-[1100px]:hidden">Up to 55 sec</span>
              </div>
              <label className="mt-[29px] mb-2 block text-[11px] text-[#6e786a]" htmlFor="language">Speaking language</label>
              <select id="language" className="w-full rounded-[7px] border border-[#dfe5d8] bg-[#fafbf5] px-3 py-[11px] text-xs text-[#344531] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#739b44] disabled:opacity-60" value={language} onChange={(event) => setLanguage(event.target.value)} disabled={status !== "idle"}>
                {languages.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
              </select>
              <div className="group flex flex-col items-center pt-8 pb-6" data-recording={status === "recording"}>
                <div className="grid size-[100px] place-items-center rounded-full border border-[#e4eadb] bg-[#f4f7ec] ring-[9px] ring-[#f9faf4] group-data-[recording=true]:ring-[#ecf3dc]">
                  <div className="grid size-[68px] place-items-center rounded-full bg-[#e4edcd] [&_svg]:size-7 [&_svg]:stroke-[#526c38]"><Microphone /></div>
                </div>
                <div className="mt-[22px] flex h-[46px] items-center gap-[3px]" aria-hidden="true">
                  {Array.from({ length: 29 }, (_, index) => (
                    <i key={index} className={`block w-[3px] rounded-[3px] bg-[#d3ddc4] group-data-[recording=true]:bg-[#7a994f] motion-safe:group-data-[recording=true]:animate-pulse ${["h-2", "h-4", "h-6", "h-3", "h-8", "h-5", "h-2.5"][index % 7]}`} />
                  ))}
                </div>
                <p className="mt-[9px] mb-[13px] text-center text-[11px] text-[#7e8875]" role="status">{status === "recording" ? "Listening to you…" : status === "processing" ? "Turning your voice into text…" : status === "permission" ? "Allow microphone access to begin" : "A little thought. A big idea. Say it."}</p>
                <span className="font-mono text-lg tracking-[-0.7px]">{`00:${String(seconds).padStart(2, "0")}`} <span className="text-xs tracking-normal text-[#a5ad9c]">/ 00:55</span></span>
              </div>
              <button className={`flex h-[45px] w-full cursor-pointer items-center justify-center gap-[9px] rounded-[7px] border text-xs font-semibold text-[#2d421d] transition-colors disabled:cursor-wait disabled:opacity-65 [&_svg]:size-[15px] ${status === "recording" ? "border-[#e7c8b5] bg-[#f1e0d5] hover:bg-[#eacbba]" : "border-[#ccdf80] bg-[#d9ee93] hover:bg-[#cce37f]"}`} onClick={status === "recording" ? stopRecording : startRecording} disabled={status === "permission" || status === "processing"}>
                {status === "recording" ? <span className="size-2.5 rounded-[2px] bg-current" /> : <Microphone />}
                {status === "recording" ? "Stop & transcribe" : status === "processing" ? "Transcribing…" : status === "permission" ? "Waiting for microphone…" : "Click to speak"}
              </button>
              <p className="mt-[13px] text-center text-[10px] text-[#919987]">Click to start. Click again when you’re done.</p>
            </section>
            <section className="flex flex-col overflow-hidden rounded-[14px] border border-[#dfe5d9] bg-white shadow-[0_3px_4px_#243a2510]" aria-labelledby="transcript-heading">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#edf0e7] p-[25px] max-[1100px]:p-5">
                <div><span className="text-[9px] tracking-[1.6px] text-[#829078]">02 / TRANSCRIPT</span><h2 id="transcript-heading" className="mt-[9px] text-[15px] font-medium tracking-[-0.3px]">Your words, captured</h2></div>
                <div className="flex flex-wrap items-end gap-2">
                  <TranscriptSpeaker key={`${transcriptLanguage}:${transcript}`} text={transcript || ""} languageCode={transcriptLanguage} disabled={status !== "idle"} />
                  <button className="cursor-pointer rounded-[5px] border border-[#e1e7da] bg-transparent px-[9px] py-[7px] text-[10px] whitespace-nowrap text-[#54694a] disabled:cursor-default disabled:opacity-40" disabled={!transcript || status !== "idle"} onClick={copyTranscript}>{copied ? "Copied ✓" : "Copy text ↗"}</button>
                </div>
              </div>
              <div className="flex max-h-[520px] min-h-[320px] flex-1 overflow-auto p-7 max-[600px]:min-h-[290px]" aria-live="polite" aria-busy={status === "processing"}>
                {transcript ? <p className="text-[17px] leading-[1.9] whitespace-pre-wrap text-[#334430] [overflow-wrap:anywhere]">{transcript}</p> : (
                  <div className="m-auto max-w-[245px] text-center">
                    <span className="mb-[19px] inline-grid h-[60px] w-[53px] -rotate-7 place-items-center rounded-[9px] border border-[#e9ede1] bg-[#f7f8f3] font-serif text-[25px] text-[#a3af97]">{status === "processing" ? "···" : "Aa"}</span>
                    <h3 className="mb-2.5 text-[13px] font-medium text-[#69765e]">{status === "processing" ? "Finding the words…" : transcript === "" ? "No speech detected" : "Your next thought starts here"}</h3>
                    <p className="text-[11px] leading-[1.9] text-[#8b947e]">{status === "processing" ? "Your recording is being transcribed. This may take a few moments." : transcript === "" ? "Try speaking a little louder or moving closer to your microphone." : "Record your voice and your transcript will appear right here, ready to copy."}</p>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-1.5 border-t border-[#edf0e7] px-[23px] py-[14px] text-[9px] text-[#8d9783]">
                <span className="size-[5px] rounded-full bg-[#b4c69e]" />{transcript !== null ? `${transcript.trim() ? transcript.trim().split(/\s+/).length : 0} words` : "Ready when you are"}<span className="ml-auto">Speech to text</span>
              </div>
            </section>
          </div>
          {error && <div className="mt-5 rounded-lg border border-[#edc7b5] bg-[#fff0e8] px-[18px] py-[15px] text-[13px] leading-[1.7] text-[#91492d]" role="alert">{error}</div>}
          <div className="mt-[23px] flex items-center gap-[14px] rounded-[9px] border border-[#e0e7d7] bg-[#edf2e5] px-[21px] py-[17px] max-[600px]:items-start">
            <span className="text-xl text-[#7e925f]">↗</span><p className="text-[10px] leading-[1.9] text-[#738363]"><strong className="font-medium text-[#637451]">Make yourself heard.</strong> Choose your language, find a quiet spot, and speak at your own pace. Your transcript stays in this tab.</p>
          </div>
        </main>
        <footer className="mt-auto flex justify-between px-11 py-[22px] text-[9px] text-[#939e88] max-[850px]:px-[25px] max-[600px]:px-5 max-[600px]:pt-2.5 max-[600px]:pb-[25px]">
          <span>Built for the way you speak.</span><span className="text-[8px] tracking-[1.7px] max-[600px]:hidden">OPEN CALL. OPEN POSSIBILITIES.</span>
        </footer>
      </div>
    </div>
  );
}
