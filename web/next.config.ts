import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained build for the Docker image (web/Dockerfile). Vercel ignores this.
  output: "standalone",
};

export default nextConfig;
