import { withPayload } from '@payloadcms/next/withPayload'

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Три tenant обслуживаются одним приложением; домен определяется по заголовку Host.
  // URL-политика фабрики: слэш на конце — канонический вид. Без этого Next
  // редиректит /catalog/ на /catalog, и canonical начинает указывать на редирект.
  trailingSlash: true,
  reactStrictMode: true,
  poweredByHeader: false,
  images: { remotePatterns: [] },
  experimental: { reactCompiler: false },
}

export default withPayload(nextConfig)
