import Glass from "../Glass";

const offsets = [10, 35, 60, 100, 125, 150];

function FlowLines({ side, active }: { side: "left" | "right"; active: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 120 160" preserveAspectRatio="none" className={`pointer-events-none absolute top-1/2 h-40 w-[min(12vw,120px)] -translate-y-1/2 ${side === "left" ? "right-full" : "left-full"}`}>
      {offsets.map((y, index) => {
        const path = side === "left" ? `M0 ${y} C60 ${y} 60 80 120 80` : `M0 80 C60 80 60 ${y} 120 ${y}`;
        return <g key={y} fill="none" strokeWidth="1">
          <path d={path} stroke="#d4d4d4" vectorEffect="non-scaling-stroke" />
          {active && <path d={path} pathLength="100" stroke="#8c9f96" strokeLinecap="round" strokeDasharray="4 96" className="flow-pulse" style={{ animationDelay: `${index * -0.24}s` }} vectorEffect="non-scaling-stroke" />}
        </g>;
      })}
    </svg>
  );
}

export function Orb({ audioStream, active }: { audioStream: MediaStream | null; active: boolean }) {
  return <>
    <FlowLines side="left" active={active} />
    <Glass size={160} audioEnabled={!!audioStream} audioStream={audioStream} followCursor={false} />
    <FlowLines side="right" active={active} />
  </>;
}
