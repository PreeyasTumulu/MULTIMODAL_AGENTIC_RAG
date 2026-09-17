import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone build for the Docker image (docker/frontend.Dockerfile): a
  // self-contained server bundle instead of copying node_modules whole.
  output: "standalone",
};

export default nextConfig;
