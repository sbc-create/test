import { listCollections, listPosts, listTenantTitles } from '../../../lib/content'
import { currentSite, payloadClient } from '../../../lib/site'
import { tenantFind } from '../../../lib/tenant-query'
import { absoluteUrl } from '../../../seo/metadata'
import { PAGE_TYPES } from '../../../seo/matrix'

export const dynamic = 'force-dynamic'

type Entry = { loc: string; lastmod?: string }

const escapeXml = (value: string): string =>
  value.replace(/[<>&'"]/g, (char) =>
    ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', "'": '&apos;', '"': '&quot;' })[char]!,
  )

/**
 * В sitemap попадают только canonical + indexable + 200. Состав определяется
 * профилем сайта: три сайта не публикуют одинаковый список URL.
 */
export const GET = async () => {
  const site = await currentSite()

  if (!site.tenant.indexingEnabled) {
    // Карта сайта существует и проверяется, но отдаётся только когда индексация
    // разрешена: иначе стенд можно отправить в поисковую систему.
    return new Response('Sitemap недоступен: индексация сайта не разрешена.', {
      status: 404,
      headers: { 'content-type': 'text/plain; charset=utf-8', 'x-robots-tag': 'noindex' },
    })
  }

  const payload = await payloadClient()
  const profile = site.profile
  const entries: Entry[] = []
  const add = (path: string, lastmod?: unknown) => {
    entries.push({ loc: absoluteUrl(site.tenant, path), lastmod: lastmod ? String(lastmod) : undefined })
  }

  const includes = (type: keyof typeof PAGE_TYPES) => profile.sitemapTypes.includes(type)

  if (includes('home')) add('/')
  if (includes('category')) {
    add('/catalog/')
    add('/schedule/')
  }
  if (includes('news_index')) add('/news/')

  if (includes('title')) {
    const titles = await listTenantTitles(payload, site.tenant, { limit: 1000 })
    for (const doc of titles.docs) {
      const record = doc as unknown as Record<string, unknown>
      // Профиль требует собственного текста — без него страница noindex и в карту не идёт.
      if (profile.requiresOwnText.includes('title') && !String(record.editorialIntro ?? '').trim()) continue
      add(`/catalog/${String(record.slug)}/`, record.updatedAt)
    }
  }

  if (includes('collection')) {
    const collections = await listCollections(payload, site.tenant, { limit: 500 })
    for (const doc of collections.docs) {
      const record = doc as unknown as Record<string, unknown>
      const items = Array.isArray(record.items) ? record.items.length : 0
      if (items === 0) continue
      if (profile.requiresOwnText.includes('collection') && !String(record.intro ?? '').trim()) continue
      add(`/collections/${String(record.slug)}/`, record.updatedAt)
    }
  }

  if (includes('article')) {
    const posts = await listPosts(payload, site.tenant, { limit: 1000 })
    for (const doc of posts.docs) {
      const record = doc as unknown as Record<string, unknown>
      if (profile.requiresOwnText.includes('article') && !String(record.body ?? '').trim()) continue
      add(`/news/${String(record.slug)}/`, record.updatedAt)
    }
  }

  if (includes('legal')) {
    const pages = await tenantFind(payload, {
      collection: 'pages',
      tenant: site.tenant,
      where: { _status: { equals: 'published' } },
      limit: 200,
      depth: 0,
    })
    for (const doc of pages.docs) {
      const record = doc as unknown as Record<string, unknown>
      add(`/legal/${String(record.slug)}/`, record.updatedAt)
    }
  }

  const body = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...entries.map((entry) =>
      [
        '  <url>',
        `    <loc>${escapeXml(entry.loc)}</loc>`,
        entry.lastmod ? `    <lastmod>${escapeXml(new Date(entry.lastmod).toISOString())}</lastmod>` : null,
        '  </url>',
      ]
        .filter(Boolean)
        .join('\n'),
    ),
    '</urlset>',
    '',
  ].join('\n')

  return new Response(body, {
    headers: { 'content-type': 'application/xml; charset=utf-8', 'cache-control': 'public, max-age=300' },
  })
}
