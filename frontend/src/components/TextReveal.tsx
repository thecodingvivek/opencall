"use client";

import { motion, useReducedMotion } from "motion/react";

export default function TextReveal({ text, delay = 0, className }: { text: string; delay?: number; className?: string }) {
  const reducedMotion = useReducedMotion();
  return <span className={className} aria-hidden="true">
    {Array.from(text).map((letter, index) => letter === " " ? <span key={index}>{"\u00a0"}</span> : (
      <motion.span key={index} className="inline-block"
        initial={reducedMotion ? false : { opacity: 0, filter: "blur(8px)" }}
        animate={{ opacity: 1, filter: "blur(0px)" }}
        transition={reducedMotion ? { duration: 0 } : { duration: 0.6, delay: delay + index * 0.04, ease: "easeOut" }}
      >{letter}</motion.span>
    ))}
  </span>;
}
