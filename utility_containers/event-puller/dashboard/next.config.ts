import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'export',
  distDir: 'out',
  images: {
    unoptimized: true,
  },
  trailingSlash: true,
  reactStrictMode: false,
  devIndicators: false,
  typescript: {
      ignoreBuildErrors: true,
  },
};

export default nextConfig;
