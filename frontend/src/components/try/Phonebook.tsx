import { useEffect, useRef } from "react";

export type PhonebookState =
  | { status: "loading" | "guest" | "error" }
  | { status: "ready"; username: string; description: string };

export function Phonebook({ phonebook }: { phonebook: PhonebookState }) {
  const panelRef = useRef<HTMLDivElement>(null);
  const pointerRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const panel = panelRef.current;
    const pointer = pointerRef.current;
    if (!panel || !pointer) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let timer: ReturnType<typeof setTimeout> | undefined;
    let animation: Animation | undefined;
    let x = 0;
    let y = 0;
    let stopped = false;

    function wander() {
      if (stopped || reducedMotion.matches || !panel || !pointer) return;
      const maxX = Math.max(0, panel.clientWidth - pointer.getBoundingClientRect().width - 32);
      const nextX = -Math.random() * maxX;
      const nextY = -Math.random() * 12;
      animation = pointer.animate([
        { transform: `translate(${x}px, ${y}px)` },
        { transform: `translate(${nextX}px, ${nextY}px)` },
      ], { duration: 1800 + Math.random() * 1200, easing: "ease-in-out", fill: "forwards" });
      x = nextX;
      y = nextY;
      animation.onfinish = () => {
        pointer.style.transform = `translate(${nextX}px, ${nextY}px)`;
        animation?.cancel();
        timer = setTimeout(wander, 500 + Math.random() * 1200);
      };
    }

    function onMotionChange() {
      if (timer) clearTimeout(timer);
      animation?.cancel();
      if (pointer) pointer.style.transform = "";
      x = 0;
      y = 0;
      if (!reducedMotion.matches) wander();
    }
    reducedMotion.addEventListener("change", onMotionChange);
    wander();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      animation?.cancel();
      reducedMotion.removeEventListener("change", onMotionChange);
    };
  }, []);

  return (
    <section aria-label="Phonebook" className="flex min-w-0 items-center px-6">
      <div className="mx-auto w-full max-w-sm text-left">
        <div ref={panelRef} className="relative mb-8 flex h-24 w-full items-end justify-end gap-2 overflow-hidden rounded-2xl border border-[#e5e5e5] bg-[#f7f7f7] pr-4">
          <p className="absolute left-4 top-3 text-xs font-semibold uppercase tracking-wider text-[#777]">Subagents and jobs</p>
          <svg ref={pointerRef} className="h-10 w-auto" viewBox="0 0 70 67" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <radialGradient id="maps-pointer-orb" cx="30%" cy="25%" r="80%">
                <stop offset="0%" stopColor="#bdacf5" />
                <stop offset="45%" stopColor="#8ee6c5" />
                <stop offset="100%" stopColor="#5420ad" />
              </radialGradient>
            </defs>
            <path d="M5 5 Q4 3 7 5 L43 27 Q47 30 42 31 L25 34 Q23 34 22 36 L13 49 Q10 53 9 48 Z" transform="scale(.75)" fill="#111111" stroke="white" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="35" cy="51" r="16" fill="url(#maps-pointer-orb)" />
          </svg>
        </div>
        <p className="mb-8 text-xs font-semibold uppercase tracking-wider text-[#777]">Maps tool</p>
        <p className="mb-8 text-xs font-semibold uppercase tracking-wider text-[#777]">Weather tool</p>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[#777]">Phonebook</h2>
        <div className="mt-2 text-sm leading-6 text-[#999]" aria-live="polite">
          {phonebook.status === "loading" && <p>Loading phonebook…</p>}
          {phonebook.status === "guest" && <p>The user is currently unknown.</p>}
          {phonebook.status === "error" && <p>Phonebook unavailable. Reload the page to try again.</p>}
          {phonebook.status === "ready" && <><p className="font-medium text-[#343433]">{phonebook.username}</p><p className="whitespace-pre-wrap break-words">{phonebook.description || "No description yet."}</p></>}
        </div>
      </div>
    </section>
  );
}
