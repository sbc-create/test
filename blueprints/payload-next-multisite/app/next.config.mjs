import { withPayload } from '@payloadcms/next/withPayload'

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Три tenant обслуживаются одним приложением; домен определяется по заголовку Host.
  // URL-политика фабрики: слэш на конце — канонический вид. Без этого Next
  // редиректит /catalog/ на /catalog, и canonical начинает указывать на редирект.
  trailingSlash: true,
  // Автоматический редирект Next применяется и к /api/*, где он ломает POST.
  // Канонизацию адресов страниц делает middleware, а API остаётся без слэша.
  skipTrailingSlashRedirect: true,
  reactStrictMode: true,
  poweredByHeader: false,
  images: { remotePatterns: [] },
  experimental: { reactCompiler: false },
}

export default withPayload(nextConfig)
