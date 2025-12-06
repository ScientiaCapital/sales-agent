import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Set turbopack root for local development to avoid conflicts with parent-level lockfiles
  // In production (Vercel), this is managed automatically
  ...(process.env.NODE_ENV === "development" && {
    turbopack: {
      root: path.resolve(__dirname),
    },
  }),

  async rewrites() {
    // Get backend URL and clean any whitespace/newlines (env vars can have trailing \n)
    const rawUrl = process.env.NEXT_PUBLIC_API_URL || "";
    const backendUrl = rawUrl.trim();

    // Only enable rewrites if we have a valid backend URL
    // In production without a backend proxy, return empty rewrites
    if (!backendUrl || (!backendUrl.startsWith("http://") && !backendUrl.startsWith("https://"))) {
      return [];
    }

    return [
      // Routes that already include /v1/ - pass through directly
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
      // Routes without /v1/ - add the prefix (dashboard components use /api/X)
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
