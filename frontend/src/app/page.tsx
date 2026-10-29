import Glass from "../components/Glass";
import { instrumentSerif } from "./fonts";

export default function Home() {
  return (
    <main className="flex min-h-screen w-full items-center justify-center bg-white px-6 py-12">
      <div className="flex flex-wrap items-center justify-center gap-3">
        <h1 className="font-sans text-[24px] font-normal tracking-[-0.06em]">
          OPENCALL
        </h1>
        <Glass size={32} audioEnabled={false} followCursor={false} />
        <p className="whitespace-nowrap text-[24px] tracking-[-0.03em]">
          <span className={instrumentSerif.className} style={instrumentSerif.style}>harness</span>{" "}
          <span className="font-sans font-normal tracking-normal">and</span>{" "}
          <span className={instrumentSerif.className} style={instrumentSerif.style}>harvest</span>
        </p>
      </div>
    </main>
  );
}
