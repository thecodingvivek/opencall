import Glass from "../components/Glass";
import CuelumeSounds from "../components/CuelumeSounds";
import { instrumentSerif } from "./fonts";

export default function Home() {
  return (
    <main className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-white px-6 py-12">
      <CuelumeSounds />
      <div className="relative z-10 flex flex-col items-center gap-7">
       <div className="flex flex-wrap items-center justify-center gap-3">
        <span className="font-sans text-[36px] font-normal tracking-[-0.06em]">
          
        </span>
        <span className="font-sans text-[36px] font-normal tracking-[-0.06em]">
          opencall
        </span>
        <Glass size={60} audioEnabled={false} followCursor={false} />
        <p className="whitespace-nowrap text-[36px] tracking-[-0.03em]">
          <span className={`${instrumentSerif.className} instrument-emphasis`} style={instrumentSerif.style}>harness</span>{" "}
          <span className="font-sans font-normal tracking-normal">and</span>{" "}
          <span className={`${instrumentSerif.className} instrument-emphasis`} style={instrumentSerif.style}>harvest</span>
        </p>
       </div>
       <div className="flex flex-wrap items-center justify-center gap-3">
         <a href="/get-started" className="home-pill" data-cuelume-tap="">GET STARTED</a>
         <a href="#idea" className="home-pill home-pill-quiet" data-cuelume-tap="">SEE THE IDEA</a>
       </div>
      </div>
      <footer aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 overflow-hidden" style={{ aspectRatio: "1920 / 403" }}>
        {/* The SVG includes the blurred edges surrounding the Figma frame. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/footer-figma.svg" alt="" className="absolute max-w-none" style={{ left: "-2.32%", top: "-8.69%", width: "104.64%", height: "117.38%" }} />
      </footer>
    </main>
  );
}
