/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  output: 'standalone',
  async rewrites() {
    // Use rewrites only in Docker/container environment
    if (process.env.DOCKER_ENV === 'true') {
      return [
        {
          source: '/api/:path*',
          destination: 'http://backend:8000/:path*',
        },
      ]
    }
    return []
  },
}

export default nextConfig
