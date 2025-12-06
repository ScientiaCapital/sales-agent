import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Explicitly set Turbopack root to avoid confusion with parent lockfiles
  // This tells Turbopack to use the dashboard directory as the monorepo root
  turbopack: {
    root: __dirname,
  },
  async rewrites() {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
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
