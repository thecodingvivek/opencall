import Glass from "../components/Glass";
import CuelumeSounds from "../components/CuelumeSounds";
import FooterGradient from "../components/FooterGradient";
import { instrumentSerif } from "./fonts";

export default function Home() {
  return (
    <main className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-white px-6 py-12">
      <CuelumeSounds />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0" style={{ backgroundImage: "linear-gradient(#d8d8d8 1px, transparent 1px), linear-gradient(90deg, #d8d8d8 1px, transparent 1px)", backgroundSize: "64px 64px", opacity: 0.22, maskImage: "radial-gradient(ellipse 75% 65% at center, transparent 15%, black 100%)", WebkitMaskImage: "radial-gradient(ellipse 75% 65% at center, transparent 15%, black 100%)" }} />
      <div className="relative z-10 flex -translate-y-[clamp(2rem,8vh,6rem)] flex-col items-center gap-7">
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
      <FooterGradient playIntro />
    </main>
  );
}
