import CuelumeSounds from "@/components/CuelumeSounds";
import FooterGradient from "@/components/FooterGradient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function JoinPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-white px-6">
      <CuelumeSounds />
      <nav aria-label="Main navigation" className="absolute inset-x-0 top-0 z-10 flex items-center justify-between px-6 py-5">
        <span className="text-base font-medium tracking-tight text-[#171717]">Opencall</span>
        <a href="/get-started" className="home-pill home-pill-quiet nav-back" data-cuelume-tap="">Back</a>
      </nav>
      <div className="relative z-10 flex w-full max-w-xs -translate-y-[clamp(2rem,8vh,6rem)] flex-col items-center gap-4">
        <h1 className="w-full text-lg font-medium text-[#171717]">Join a room</h1>
        <p className="w-full text-sm text-[#777]">QR codes and room numbers will be available when room sharing is connected.</p>
        <label htmlFor="room-number" className="w-full text-sm text-[#343433]">room number</label>
        <Input id="room-number" placeholder="Room number" disabled className="h-12 w-full rounded-full border border-[#e2e2e2] bg-white px-5 text-sm" />
        <Button type="button" disabled variant="secondary" className="h-10 w-full rounded-full bg-[#f3f3f3] text-[#343433]">JOIN ROOM</Button>
      </div>
      <FooterGradient />
    </main>
  );
}
