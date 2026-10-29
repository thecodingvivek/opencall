import CuelumeSounds from "../../components/CuelumeSounds";

export default function GetStarted() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-white px-6">
      <CuelumeSounds />
      <div className="flex w-full max-w-xs flex-col items-center gap-4">
        <label htmlFor="mobile" className="sr-only">Mobile number</label>
        <input
          id="mobile"
          name="mobile"
          type="tel"
          autoComplete="tel"
          placeholder="Mobile number"
          className="h-12 w-full rounded-full border border-[#e2e2e2] bg-white px-5 text-sm text-[#343433] outline-none placeholder:text-[#999] focus:border-[#999]"
        />
        <button type="button" disabled className="home-pill w-full cursor-not-allowed opacity-50">
          CONTINUE
        </button>
        <a href="/login" data-cuelume-tap="" className="text-sm text-[#777] underline decoration-[#c5c5c5] underline-offset-4 hover:text-[#343433]">
          try without mobile
        </a>
      </div>
    </main>
  );
}
