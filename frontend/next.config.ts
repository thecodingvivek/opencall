import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["67af-2a09-bac1-36a0-3110-00-1c5-125.ngrok-free.app"],
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  reactCompiler: true,
  turbopack: {
    rules: {
      "globals.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
