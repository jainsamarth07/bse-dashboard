/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  env: {
    // Empty string → axios baseURL falls back to "" → uses same origin as the page.
    // Works for both localhost:3000 and any Cloudflare tunnel URL automatically.
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "",
  },
  async rewrites() {
    // In Docker, the API container is reachable as http://api:8000 (service name).
    // For local dev outside Docker, set INTERNAL_API_URL=http://localhost:8000.
    // This value is baked at build time by Next.js standalone, so the Docker
    // service name must be the default (not localhost).
    const apiBase =
      process.env.INTERNAL_API_URL || "http://api:8000";
    return [
      // Proxy all /api/* and /ws/* requests to the FastAPI backend.
      // The browser never knows about port 8000 — no CORS, no hardcoded URLs.
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
      {
        source: "/ws/:path*",
        destination: `${apiBase}/ws/:path*`,
      },
      {
        source: "/health",
        destination: `${apiBase}/health`,
      },
    ];
  },
};

module.exports = nextConfig;
