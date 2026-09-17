import type { NextConfig } from "next";

// One secrets file for the whole repo: in local dev, read ../.env (ADMIN_API_KEY) instead of
// keeping a second copy in frontend/.env.local. Variables already set win. In Docker the file
// is outside the build context and compose passes the variables, so a miss is expected.
try {
  process.loadEnvFile("../.env");
} catch {}

const nextConfig: NextConfig = {
  // Standalone build for the Docker image (frontend/Dockerfile): a self-contained
  // server bundle instead of copying node_modules whole.
  output: "standalone",
};

export default nextConfig;
