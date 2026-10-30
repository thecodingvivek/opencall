import Glass from "../components/Glass";
import CuelumeSounds from "../components/CuelumeSounds";
import FooterGradient from "../components/FooterGradient";
import HomeReveal from "../components/HomeReveal";
import TextReveal from "../components/TextReveal";
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
        <div className="flex items-center gap-3">
          <span aria-label="opencall" className="font-sans text-[36px] font-normal tracking-[-0.06em]"><TextReveal text="opencall" delay={0.2} /></span>
          <HomeReveal delay={0.2}>
          <Glass size={60} audioEnabled={false} followCursor={false} />
          </HomeReveal>
        </div>
        <p aria-label="harness and harvest" className="whitespace-nowrap text-[36px] tracking-[-0.03em]">
          <span className={`${instrumentSerif.className} instrument-emphasis`} style={instrumentSerif.style}><TextReveal text="harness" delay={1} /></span>{" "}
          <span className="font-sans font-normal tracking-normal"><TextReveal text="and" delay={1.28} /></span>{" "}
          <span className={`${instrumentSerif.className} instrument-emphasis`} style={instrumentSerif.style}><TextReveal text="harvest" delay={1.4} /></span>
        </p>
       </div>
       <HomeReveal delay={1.8} className="flex flex-wrap items-center justify-center gap-3">
         <a href="/get-started" className="home-pill" data-cuelume-tap="">GET STARTED</a>
         <a href="#idea" className="home-pill home-pill-quiet" data-cuelume-tap="">SEE THE IDEA</a>
       </HomeReveal>
      </div>
      <FooterGradient playIntro />
    </main>
  );
}
