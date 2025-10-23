/** @type {import('next').NextConfig} */
const nextConfig = {
  // Rewrites for API and WebSocket proxying in single-pod deployment
  async rewrites() {
    // Get backend URL from environment or use loopback
    const backendUrl = process.env.INTERNAL_API_URL || 'http://127.0.0.1:8000';

    return [
      // Proxy WebSocket connections to backend sidecar
      {
        source: '/ws/:path*',
        destination: `${backendUrl}/ws/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
