import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Explicitly set Turbopack root to dashboard directory
  // This prevents Next.js 16 from inferring wrong workspace root from parent lockfiles
  // See: https://nextjs.org/docs/app/api-reference/config/next-config-js/turbopack#root-directory
  turbopack: {
    root: process.cwd(),
  },

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
