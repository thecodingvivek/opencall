"use client";

import { useEffect, useRef } from "react";

export default function FooterGradient({ playIntro = false }: { playIntro?: boolean }) {
  const footer = useRef<HTMLElement>(null);
  const audio = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    if (!playIntro || !audio.current) return;
    const sound = audio.current;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    let cancelled = false;
    let started = false;

    function update() {
      if (cancelled || !footer.current || reduceMotion.matches) return;
      const t = sound.currentTime;
      let offset = 0;
      if (t < 1) {
        const progress = t * t * (3 - 2 * t);
        offset = 70 * (1 - progress);
      } else if (t < 1.35) {
        offset = -7 * Math.sin(((t - 1) / 0.35) * Math.PI / 2);
      } else if (t < 2.3) {
        offset = -7 * (1 - (t - 1.35) / 0.95);
      }
      footer.current.style.transform = `translateY(${offset}%)`;
      if (!sound.paused && !sound.ended) frame = requestAnimationFrame(update);
    }

    function onPlaying() {
      started = true;
      window.removeEventListener("pointerdown", tryPlay);
      window.removeEventListener("keydown", tryPlay);
      cancelAnimationFrame(frame);
      update();
    }
    function tryPlay() {
      if (!started && !cancelled) void sound.play().catch(() => {});
    }
    sound.addEventListener("playing", onPlaying);
    window.addEventListener("pointerdown", tryPlay);
    window.addEventListener("keydown", tryPlay);
    tryPlay();
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      sound.removeEventListener("playing", onPlaying);
      window.removeEventListener("pointerdown", tryPlay);
      window.removeEventListener("keydown", tryPlay);
      sound.pause();
    };
  }, [playIntro]);

  return (
    <>
      {playIntro && <audio ref={audio} src="/onboard.mp3" preload="auto" />}
      <footer ref={footer} aria-hidden="true" className="pointer-events-none absolute bottom-0 left-1/2 w-[180%] -translate-x-1/2 translate-y-[62%]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/footer-figma.svg" alt="" className="block h-auto w-full max-w-none" />
      </footer>
    </>
  );
}
