import { withPayload } from '@payloadcms/next/withPayload'

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Каталог сборки задаётся окружением: каждый релиз собирается в свой каталог,
  // и переключение `current` становится атомарным, а откат — без пересборки.
  distDir: process.env.NEXT_DIST_DIR ?? '.next',
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

/**
 * Заголовки безопасности. CSP разрешает ровно то, что нужно плееру провайдера,
 * и ничего сверх: внутренний cross-origin frame создаёт сам web component, это
 * деталь его реализации, а не наш iframe.
 */
const PLAYER_ORIGIN = 'https://player.cdnvideohub.com'

const csp = [
  "default-src 'self'",
  // Next вставляет собственные inline-скрипты загрузки; nonce для них требует
  // отдельного слоя, поэтому inline разрешён точечно и только для скриптов.
  `script-src 'self' 'unsafe-inline' ${PLAYER_ORIGIN}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "media-src 'self' blob: https:",
  `frame-src ${PLAYER_ORIGIN}`,
  `connect-src 'self' ${PLAYER_ORIGIN}`,
  "font-src 'self' data:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ')

nextConfig.headers = async () => [
  {
    source: '/:path*',
    headers: [
      { key: 'Content-Security-Policy', value: csp },
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'Permissions-Policy', value: 'geolocation=(), microphone=(), camera=()' },
      { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
    ],
  },
]

export default withPayload(nextConfig)
