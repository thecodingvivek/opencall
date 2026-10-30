"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

export default function HomeReveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const reducedMotion = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reducedMotion ? false : { opacity: 0, y: 12, filter: "blur(4px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={reducedMotion ? { duration: 0 } : { duration: 0.7, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
