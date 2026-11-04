import CuelumeSounds from "../../components/CuelumeSounds";
import FooterGradient from "../../components/FooterGradient";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import Link from "next/link";
import { RoomCode } from "@/components/RoomCode";

export default function GetStarted() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-white px-6">
      <CuelumeSounds />
      <nav aria-label="Main navigation" className="absolute inset-x-0 top-0 z-10 flex items-center justify-between px-6 py-5">
        <span className="text-base font-medium tracking-tight text-[#171717]">Opencall</span>
        <Link href="/" className="home-pill home-pill-quiet nav-back" data-cuelume-tap="">Back</Link>
      </nav>
      <div className="relative z-10 flex w-full max-w-xs -translate-y-[clamp(2rem,8vh,6rem)] flex-col items-center gap-4">
        <RoomCode />
        <label htmlFor="mobile" className="w-full text-sm text-[#343433]">enter number you want to call with</label>
        <Input
          id="mobile"
          name="mobile"
          type="tel"
          autoComplete="tel"
          placeholder="Mobile number"
          className="h-12 w-full rounded-full border border-[#e2e2e2] bg-white px-5 text-sm text-[#343433] outline-none placeholder:text-[#999] focus:border-[#999]"
        />
        <Button type="button" disabled variant="secondary" className="h-10 w-full rounded-full bg-[#f3f3f3] text-[#343433]">
          CONTINUE
        </Button>
        <a href="/try" data-cuelume-tap="" className={cn(buttonVariants({ variant: "secondary" }), "h-10 w-full rounded-full bg-[#f3f3f3] text-[#343433]")}>
          try without mobile
        </a>
      </div>
      <FooterGradient />
    </main>
  );
}
