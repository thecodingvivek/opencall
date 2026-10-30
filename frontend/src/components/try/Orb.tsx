import Glass, { type GlassPalette } from "../Glass";

const offsets = [10, 35, 60, 100, 125, 150];
const pulseColors = ["#00a884", "#00a4d6", "#6657e8", "#db4d94", "#e77b24", "#40a84e"];

function FlowLines({ side, active }: { side: "left" | "right"; active: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 120 160" preserveAspectRatio="none" className={`pointer-events-none absolute top-1/2 h-40 w-[min(12vw,120px)] -translate-y-1/2 ${side === "left" ? "right-full" : "left-full"}`}>
      {offsets.map((y, index) => {
        const path = side === "left" ? `M0 ${y} C60 ${y} 60 80 120 80` : `M0 80 C60 80 60 ${y} 120 ${y}`;
        return <g key={y} fill="none" strokeWidth="1">
          <path d={path} stroke="#d4d4d4" vectorEffect="non-scaling-stroke" />
          {active && <line x1="-5" y1="0" x2="5" y2="0" stroke={pulseColors[index]} strokeWidth="1.5" strokeLinecap="round" vectorEffect="non-scaling-stroke" className="flow-pulse">
            <animateMotion path={path} rotate="auto" dur="2.4s" begin={`${index * -0.3}s`} repeatCount="indefinite" />
          </line>}
        </g>;
      })}
    </svg>
  );
}

export function Orb({ audioStream, active, colors }: { audioStream: MediaStream | null; active: boolean; colors: Pick<GlassPalette, "top" | "bottom" | "accent"> }) {
  return <>
    <FlowLines side="left" active={active} />
    <Glass size={160} colors={colors} audioEnabled={!!audioStream} audioStream={audioStream} followCursor={false} />
    <FlowLines side="right" active={active} />
  </>;
}
