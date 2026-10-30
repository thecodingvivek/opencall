export type PhonebookState =
  | { status: "loading" | "guest" | "error" }
  | { status: "ready"; username: string; description: string };

export function Phonebook({ phonebook }: { phonebook: PhonebookState }) {
  return (
    <section aria-label="Phonebook" className="flex min-w-0 items-center px-6">
      <div className="mx-auto w-full max-w-sm text-left">
        <p className="mb-8 text-xs font-semibold uppercase tracking-wider text-[#777]">Maps tool</p>
        <p className="mb-8 text-xs font-semibold uppercase tracking-wider text-[#777]">Weather tool</p>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[#777]">Phonebook</h2>
        <div className="mt-2 text-sm leading-6 text-[#999]" aria-live="polite">
          {phonebook.status === "loading" && <p>Loading phonebook…</p>}
          {phonebook.status === "guest" && <p>The user is currently unknown.</p>}
          {phonebook.status === "error" && <p>Phonebook unavailable. Retrying…</p>}
          {phonebook.status === "ready" && <><p className="font-medium text-[#343433]">{phonebook.username}</p><p className="whitespace-pre-wrap break-words">{phonebook.description || "No description yet."}</p></>}
        </div>
      </div>
    </section>
  );
}
