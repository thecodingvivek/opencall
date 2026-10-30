import Glass from "../../components/Glass";
import { Button } from "@/components/ui/button";
import { Phone } from "lucide-react";

export default function TryPage() {
  return (
    <main className="grid min-h-screen grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] bg-white">
      <section aria-label="Phonebook" className="flex min-w-0 items-center px-6">
        <div className="mx-auto w-full max-w-sm text-left">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[#777]">Phonebook</h2>
          <p className="mt-2 text-sm leading-6 text-[#999]">The user is currently unknown.</p>
        </div>
      </section>
      <section aria-label="Call" className="relative flex items-center justify-center">
        <svg aria-hidden="true" viewBox="0 0 120 160" preserveAspectRatio="none" className="pointer-events-none absolute right-full top-1/2 h-40 w-[min(12vw,120px)] -translate-y-1/2 text-[#d4d4d4]">
          <g fill="none" stroke="currentColor" strokeWidth="1" vectorEffect="non-scaling-stroke">
            <path d="M0 10 C60 10 60 80 120 80" vectorEffect="non-scaling-stroke" />
            <path d="M0 35 C60 35 60 80 120 80" vectorEffect="non-scaling-stroke" />
            <path d="M0 60 C60 60 60 80 120 80" vectorEffect="non-scaling-stroke" />
            <path d="M0 100 C60 100 60 80 120 80" vectorEffect="non-scaling-stroke" />
            <path d="M0 125 C60 125 60 80 120 80" vectorEffect="non-scaling-stroke" />
            <path d="M0 150 C60 150 60 80 120 80" vectorEffect="non-scaling-stroke" />
          </g>
        </svg>
        <Glass size={160} audioEnabled={false} followCursor={false} />
        <svg aria-hidden="true" viewBox="0 0 120 160" preserveAspectRatio="none" className="pointer-events-none absolute left-full top-1/2 h-40 w-[min(12vw,120px)] -translate-y-1/2 text-[#d4d4d4]">
          <g fill="none" stroke="currentColor" strokeWidth="1">
            <path d="M0 80 C60 80 60 10 120 10" vectorEffect="non-scaling-stroke" />
            <path d="M0 80 C60 80 60 35 120 35" vectorEffect="non-scaling-stroke" />
            <path d="M0 80 C60 80 60 60 120 60" vectorEffect="non-scaling-stroke" />
            <path d="M0 80 C60 80 60 100 120 100" vectorEffect="non-scaling-stroke" />
            <path d="M0 80 C60 80 60 125 120 125" vectorEffect="non-scaling-stroke" />
            <path d="M0 80 C60 80 60 150 120 150" vectorEffect="non-scaling-stroke" />
          </g>
        </svg>
        <div className="absolute inset-x-0 bottom-10 flex justify-center">
          <Button type="button" className="home-pill call-pill">
            <Phone aria-hidden="true" />
            Call agent
          </Button>
        </div>
      </section>
      <section aria-label="Conversation" className="relative min-w-0 px-6 text-left">
        <div className="absolute inset-x-6 bottom-1/2 mx-auto flex max-h-[calc(50vh-2rem)] max-w-sm flex-col gap-8 overflow-y-auto" aria-live="polite">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#777]">Agent</h2>
            <p className="mt-2 text-sm leading-6 text-[#999]">Agent responses will appear here.</p>
          </div>
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#777]">User</h2>
            <p className="mt-2 text-sm leading-6 text-[#999]">Your messages will appear here.</p>
          </div>
        </div>
      </section>
    </main>
  );
}
