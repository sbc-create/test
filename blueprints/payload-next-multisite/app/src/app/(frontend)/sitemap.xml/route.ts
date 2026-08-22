import { listCollections, listEpisodes, listPosts, listSeasons, listTenantTitles } from '../../../lib/content'
import { currentSite, payloadClient } from '../../../lib/site'
import { tenantFind } from '../../../lib/tenant-query'
import { absoluteUrl } from '../../../seo/metadata'
import { inSitemap, seasonInSitemap, titleInSitemap } from '../../../seo/inclusion'
import { PAGE_TYPES } from '../../../seo/matrix'
import { ownsListing } from '../../../seo/profiles'

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
    // Перечисляем только разделы, которыми сайт владеет: чужой раздел отдаётся
    // с noindex, и его место не в карте сайта, а в навигации.
    for (const listing of ['/catalog/', '/schedule/', '/series/', '/films/', '/calendar/']) {
      if (ownsListing(profile, listing)) add(listing)
    }
  }

  // Посадочные страницы фильтров — закрытый список профиля. Произвольные
  // комбинации фильтров в карту не попадают и не индексируются.
  if (includes('tag')) {
    for (const facet of profile.indexableFacets) add(facet)
  }
  if (includes('collection') && ownsListing(profile, '/collections/')) add('/collections/')
  if (includes('news_index') && ownsListing(profile, '/news/')) add('/news/')

  if (includes('title')) {
    const titles = await listTenantTitles(payload, site.tenant, { limit: 1000 })
    for (const doc of titles.docs) {
      const record = doc as unknown as Record<string, unknown>
      // Профиль требует собственного текста — без него страница noindex и в карту
      // не идёт; страницу произведения к тому же индексирует ровно один сайт.
      const sharedRecord = record.title as { kind?: unknown; releaseState?: unknown } | null
      if (!titleInSitemap(profile, record, sharedRecord)) continue
      add(`/catalog/${String(record.slug)}/`, record.updatedAt)

      // Сезоны и серии перечисляются, только если профиль их индексирует. Раньше
      // они были объявлены в sitemapTypes, но ни одной ветки для них не было —
      // сотни индексируемых страниц оставались вне карты сайта.
      if (!includes('season') && !includes('episode')) continue
      const shared = record.title as { id?: string | number } | null
      if (!shared?.id) continue
      const seasons = await listSeasons(payload, shared.id)
      for (const season of seasons.docs) {
        const seasonRecord = season as unknown as Record<string, unknown>
        const seasonPath = `/catalog/${String(record.slug)}/season-${String(seasonRecord.number)}/`
        const episodes = await listEpisodes(payload, seasonRecord.id as string | number)
        // Пустой сезон отдаёт 404, поэтому в карту он не попадает.
        if (episodes.docs.length === 0) continue
        // Сезон без заметки сайта отдаётся с noindex, поэтому и в карте ему не место.
        if (seasonInSitemap(profile, record, Number(seasonRecord.number))) add(seasonPath, seasonRecord.updatedAt)
        if (includes('episode')) {
          for (const episode of episodes.docs) {
            const episodeRecord = episode as unknown as Record<string, unknown>
            add(`${seasonPath}episode-${String(episodeRecord.number)}/`, episodeRecord.updatedAt)
          }
        }
      }
    }
  }

  if (includes('collection')) {
    const collections = await listCollections(payload, site.tenant, { limit: 500 })
    for (const doc of collections.docs) {
      const record = doc as unknown as Record<string, unknown>
      const items = Array.isArray(record.items) ? record.items.length : 0
      if (items === 0) continue
      if (!inSitemap(profile, 'collection', record)) continue
      add(`/collections/${String(record.slug)}/`, record.updatedAt)
    }
  }

  if (includes('article')) {
    const posts = await listPosts(payload, site.tenant, { limit: 1000 })
    for (const doc of posts.docs) {
      const record = doc as unknown as Record<string, unknown>
      if (!inSitemap(profile, 'article', record)) continue
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
