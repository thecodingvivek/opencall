import CuelumeSounds from "../../components/CuelumeSounds";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export default function GetStarted() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-white px-6">
      <CuelumeSounds />
      <div className="flex w-full max-w-xs flex-col items-center gap-4">
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
    </main>
  );
}
