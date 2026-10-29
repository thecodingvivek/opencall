import Glass from "../components/Glass";
import CuelumeSounds from "../components/CuelumeSounds";
import { instrumentSerif } from "./fonts";

export default function Home() {
  return (
    <main className="flex min-h-screen w-full items-center justify-center bg-white px-6 py-12">
      <CuelumeSounds />
      <div className="flex flex-col items-center gap-7">
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
    </main>
  );
}
