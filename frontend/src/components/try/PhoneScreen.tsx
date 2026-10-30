"use client";

import { useEffect, useRef } from "react";

type CallStatus = "idle" | "connecting" | "active";

export function PhoneScreen({ status }: { status: CallStatus }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const started = useRef<number | null>(null);

  useEffect(() => {
    if (status === "idle") started.current = null;
    if (status === "active" && started.current === null) started.current = Date.now();
    const context = canvas.current?.getContext("2d");
    if (!context) return;

    function draw() {
      if (!context) return;
      context.fillStyle = "#17181a";
      context.fillRect(0, 0, 480, 600);
      context.textAlign = "center";
      context.fillStyle = "#b8bdba";
      context.font = "24px Arial, sans-serif";
      context.fillText(status === "active" ? "CALL IN PROGRESS" : "CONNECTING", 240, 150);
      const elapsed = started.current === null ? 0 : Math.floor((Date.now() - started.current) / 1000);
      const time = `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}`;
      context.fillStyle = "#f4f6f4";
      context.font = "64px Arial, sans-serif";
      context.fillText(time, 240, 260);
      context.fillStyle = "#8e9690";
      context.font = "25px Arial, sans-serif";
      context.fillText("OpenCall agent", 240, 315);
    }

    draw();
    const timer = window.setInterval(draw, 1000);
    return () => window.clearInterval(timer);
  }, [status]);

  return <canvas ref={canvas} width={480} height={600} className="absolute rounded-[4%]" style={{ left: "34.38%", top: "15.33%", width: "31.37%", height: "29.30%" }} />;
}
