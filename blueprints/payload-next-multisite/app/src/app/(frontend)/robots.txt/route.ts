import { currentSite } from '../../../lib/site'
import { absoluteUrl } from '../../../seo/metadata'

export const dynamic = 'force-dynamic'

/**
 * robots.txt строится из состояния сайта, а не лежит статическим файлом.
 * Пока индексация не разрешена явно, сайт закрыт целиком: «забыли открыть» —
 * безопасная ошибка, «забыли закрыть» — попадание стенда в индекс.
 */
export const GET = async () => {
  const site = await currentSite()

  const lines = ['User-agent: *']
  if (!site.tenant.indexingEnabled) {
    lines.push('Disallow: /')
  } else {
    lines.push('Disallow: /search/')
    lines.push('Disallow: /admin/')
    lines.push('Disallow: /api/')
    lines.push('Allow: /')
    lines.push('')
    lines.push(`Sitemap: ${absoluteUrl(site.tenant, '/sitemap.xml')}`)
  }

  return new Response(`${lines.join('\n')}\n`, {
    headers: {
      'content-type': 'text/plain; charset=utf-8',
      'x-robots-tag': 'noindex',
      'cache-control': 'public, max-age=300',
    },
  })
}
