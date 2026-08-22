import { withPayload } from '@payloadcms/next/withPayload'

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Три tenant обслуживаются одним приложением; домен определяется по заголовку Host.
  reactStrictMode: true,
  poweredByHeader: false,
  images: { remotePatterns: [] },
  experimental: { reactCompiler: false },
}

export default withPayload(nextConfig)
