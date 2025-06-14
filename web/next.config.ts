import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    // Skip type checking during build temporarily
    ignoreBuildErrors: true,
  },
};

export default nextConfig;
