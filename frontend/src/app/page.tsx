import Glass from "../components/Glass";
import CuelumeSounds from "../components/CuelumeSounds";
import FooterGradient from "../components/FooterGradient";
import HomeReveal from "../components/HomeReveal";
import TextReveal from "../components/TextReveal";
import GoogleStart from "../components/GoogleStart";
import { BookUser, CloudSun, Languages, MapPin } from "lucide-react";
import { instrumentSerif } from "./fonts";

function LiquidPanel({ id, colors, seed, accentX, accentY, icon: Icon, title, description }: { id: string; colors: [string, string, string]; seed: number; accentX: number; accentY: number; icon: typeof BookUser; title: string; description: string }) {
  return (
    <article className="w-full md:max-w-[300px]">
    <div className="orb-panel h-56 sm:h-64" style={{ aspectRatio: "auto" }}>
      <svg aria-hidden="true" className="absolute inset-0 h-full w-full" preserveAspectRatio="none" viewBox="0 0 500 300">
        <defs>
          <linearGradient id={`${id}-base`} x1="0" y1="0" x2="0.4" y2="1">
            <stop stopColor={colors[0]} /><stop offset="1" stopColor={colors[1]} />
          </linearGradient>
          <radialGradient id={`${id}-accent`}>
            <stop stopColor={colors[2]} stopOpacity=".9" /><stop offset="1" stopColor={colors[2]} stopOpacity="0" />
          </radialGradient>
          <filter id={`${id}-liquid`} x="-30%" y="-30%" width="160%" height="160%">
            <feTurbulence type="fractalNoise" baseFrequency="0.006 0.008" numOctaves="3" seed={seed} result="noise" />
            <feDisplacementMap in="SourceGraphic" in2="noise" scale="155" xChannelSelector="R" yChannelSelector="G" />
            <feGaussianBlur stdDeviation="15" />
          </filter>
          <filter id={`${id}-grain`}>
            <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="3" seed="4" stitchTiles="stitch" />
            <feColorMatrix type="saturate" values="0" />
          </filter>
        </defs>
        <rect width="500" height="300" fill={`url(#${id}-base)`} />
        <g filter={`url(#${id}-liquid)`}>
          <ellipse cx="90" cy="40" rx="240" ry="160" fill={colors[0]} />
          <ellipse cx="390" cy="275" rx="270" ry="190" fill={colors[1]} />
          <ellipse cx={accentX} cy={accentY} rx="230" ry="170" fill={`url(#${id}-accent)`} />
        </g>
        <rect width="500" height="300" filter={`url(#${id}-grain)`} opacity=".13" style={{ mixBlendMode: "soft-light" }} />
      </svg>
      <div aria-hidden="true" className="absolute inset-0 z-10 flex items-center justify-center text-white">
        <div className="flex h-28 w-28 items-center justify-center rounded-full border border-white/20 bg-black/35 shadow-lg backdrop-blur-md">
          <Icon size={52} strokeWidth={1.2} />
        </div>
      </div>
    </div>
    <div className="py-5">
      <h3 className="text-xl tracking-[-0.04em]">{title}</h3>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-[#777]">{description}</p>
    </div>
    </article>
  );
}

export default function Home() {
  return (
    <main className="relative w-full overflow-hidden bg-white">
      <CuelumeSounds />
      <section className="relative flex min-h-screen w-full items-center justify-center overflow-hidden px-6 py-12" aria-labelledby="hero-title">
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
        <p id="hero-title" aria-label="harness and harvest" className="whitespace-nowrap text-[36px] tracking-[-0.03em]">
          <span className={`${instrumentSerif.className} instrument-emphasis`} style={instrumentSerif.style}><TextReveal text="harness" delay={1} /></span>{" "}
          <span className="font-sans font-normal tracking-normal"><TextReveal text="and" delay={1.28} /></span>{" "}
          <span className={`${instrumentSerif.className} instrument-emphasis`} style={instrumentSerif.style}><TextReveal text="harvest" delay={1.4} /></span>
        </p>
       </div>
       <HomeReveal delay={1.8} className="flex flex-wrap items-center justify-center gap-3">
         <GoogleStart />
         <a href="#idea" className="home-pill home-pill-quiet" data-cuelume-tap="">SEE THE IDEA</a>
       </HomeReveal>
      </div>
      <FooterGradient playIntro />
      </section>
      <section id="idea" className="relative z-10 grid min-h-[260px] grid-cols-1 border-y border-[#1717171a] md:grid-cols-[420px_minmax(0,1fr)]" aria-label="The idea">
        <div className="flex w-full flex-col justify-between border-b border-[#1717171a] p-8 md:border-b-0 md:border-r md:p-12">
          <span className="text-xs font-medium uppercase tracking-[0.16em] text-[#17171799]">01</span>
          <p className="text-[clamp(2rem,4vw,4rem)] leading-[0.9] tracking-[-0.06em] text-[#171717]">
            <span className="block">what&apos;s the</span>
            <span className="block">idea</span>
          </p>
        </div>
        <div className="flex flex-col justify-center gap-5 p-8 md:p-12 lg:px-20 lg:py-16">
          <p className="max-w-3xl text-[clamp(1.6rem,2.8vw,2.75rem)] leading-[1.15] tracking-[-0.045em]">Farming questions deserve answers that are easy to find.</p>
          <p className="max-w-2xl text-base leading-relaxed text-[#666] md:text-lg">From changing weather to crop concerns, useful information is often scattered across different places. OpenCall brings it together in a conversation you can have out loud.</p>
        </div>
      </section>
      <div className="w-full bg-white px-8 py-8 md:px-12">
        <iframe
          src="/phone-assembly.html"
          title="Animated exploded view of a phone"
          loading="lazy"
          className="mx-auto block aspect-[2048/1071] w-full max-w-[800px] overflow-hidden border-0"
        />
      </div>
      <section className="relative z-10 grid min-h-[260px] grid-cols-1 border-y border-[#1717171a] md:grid-cols-[420px_minmax(0,1fr)]" aria-label="The solution">
        <div className="flex w-full flex-col justify-between border-b border-[#1717171a] p-8 md:border-b-0 md:border-r md:p-12">
          <span className="text-xs font-medium uppercase tracking-[0.16em] text-[#17171799]">02</span>
          <p className="text-[clamp(2rem,4vw,4rem)] leading-[0.9] tracking-[-0.06em] text-[#171717]">
            <span className="block">the</span>
            <span className="block">solution</span>
          </p>
        </div>
        <div className="p-8 md:p-12 lg:px-20 lg:py-16">
          <p className="max-w-3xl text-[clamp(1.6rem,2.8vw,2.75rem)] leading-[1.15] tracking-[-0.045em]">An assistant that listens, looks things up, and keeps the conversation going.</p>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-[#666] md:text-lg">Ask naturally, speak in your preferred language, and interrupt when you have another question. OpenCall can use a short saved description to make future conversations more helpful.</p>
          <div className="mt-10 grid gap-7 border-t border-[#1717171a] pt-7 sm:grid-cols-3">
            <div><h3 className="text-sm font-medium">Crop guidance</h3><p className="mt-2 text-sm leading-relaxed text-[#777]">Explore sourced information about crop health and common concerns.</p></div>
            <div><h3 className="text-sm font-medium">Weather</h3><p className="mt-2 text-sm leading-relaxed text-[#777]">Ask about current conditions, forecasts, and past weather.</p></div>
            <div><h3 className="text-sm font-medium">Local services</h3><p className="mt-2 text-sm leading-relaxed text-[#777]">Find nearby farming shops and agriculture offices when available.</p></div>
          </div>
          <p className="mt-8 max-w-2xl text-sm leading-relaxed text-[#777]">You can also save a request for a farming-related call. Outbound calling is not available yet.</p>
        </div>
      </section>
      <div aria-hidden="true" className="h-[200px]" />
      <section className="relative z-10 flex w-full flex-col gap-12 px-8 pb-24 md:flex-row md:justify-between md:gap-8 md:px-12" aria-label="OpenCall features">
        <LiquidPanel id="lagoon" colors={["#48ddbe", "#1744a0", "#e5ef9d"]} seed={8} accentX={300} accentY={60} icon={BookUser} title="Phonebook" description="Keep a short description to give future conversations helpful context." />
        <LiquidPanel id="sunset" colors={["#ffad55", "#c92968", "#f6dbbc"]} seed={23} accentX={70} accentY={210} icon={CloudSun} title="Weather" description="Ask about current conditions, forecasts, and past weather." />
        <LiquidPanel id="aurora" colors={["#8ee6c5", "#5420ad", "#bdacf5"]} seed={41} accentX={420} accentY={150} icon={MapPin} title="Maps" description="Find nearby farming shops and agriculture offices when available." />
        <LiquidPanel id="language" colors={["#a9d8f5", "#6947b8", "#f5c7da"]} seed={15} accentX={140} accentY={80} icon={Languages} title="Language" description="Speak and receive responses in your preferred supported language." />
      </section>
      <footer className="px-8 py-8 text-center text-sm text-[#777]">
        Powered by Gnani and LiveKit
      </footer>
    </main>
  );
}
