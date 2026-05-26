/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Proxy /api/* → backend so the browser never needs a CORS header.
  async rewrites() {
    const backend = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(
      /\/$/,
      "",
    );
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
