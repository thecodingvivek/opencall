export function Conversation() {
  return (
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
  );
}
