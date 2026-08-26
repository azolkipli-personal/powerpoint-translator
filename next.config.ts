import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: [
    "fedora-nuc.tailc24d36.ts.net",
    "*.tailc24d36.ts.net",
  ],
  // Middleware buffers request bodies (added for the auth wall) and Next.js
  // caps those at 10MB by default. Our app accepts 100MB PPTX uploads, so the
  // cap must match — otherwise large uploads get truncated mid-multipart,
  // losing the closing boundary ("Failed to parse body as FormData").
  experimental: {
    middlewareClientMaxBodySize: "100mb",
  },
};

export default nextConfig;
