import Glass from "../Glass";

export function Orb() {
  return (
    <>
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
    </>
  );
}
