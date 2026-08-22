import type { Metadata } from 'next'

import { HomeBlocks, type HomeData } from '../../components/HomeBlocks'
import { JsonLd } from '../../components/JsonLd'
import { listGenres, listPosts, listReleaseEvents, listTenantTitles } from '../../lib/content'
import { currentSite, payloadClient } from '../../lib/site'
import { tenantGlobal } from '../../lib/tenant-query'
import { buildMetadata, absoluteUrl } from '../../seo/metadata'

export const dynamic = 'force-dynamic'

const heading = 'Главная'

export const generateMetadata = async (): Promise<Metadata> => {
  const site = await currentSite()
  return buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'home',
      path: '/',
      heading: site.siteName,
      description: String(site.settings?.defaultDescription ?? '') || site.profile.purpose,
    },
    site.siteName,
  )
}

const HomePage = async () => {
  const site = await currentSite()
  const payload = await payloadClient()

  const layout = (await tenantGlobal(payload, 'home-layout', site.tenant, 2)) as
    | Record<string, unknown>
    | null
  const blocks = Array.isArray(layout?.blocks) ? (layout!.blocks as Record<string, unknown>[]) : []

  const now = new Date()
  const horizon = new Date(now.getTime() + 7 * 24 * 3600 * 1000)
  const [latest, posts, events, genres] = await Promise.all([
    listTenantTitles(payload, site.tenant, { limit: 12 }),
    listPosts(payload, site.tenant, { limit: 6 }),
    listReleaseEvents(payload, { from: now, to: horizon }),
    listGenres(payload),
  ])

  const data: HomeData = {
    latest: latest.docs,
    posts: posts.docs,
    schedule: events.docs.map((event) => ({
      label: event.label,
      airsAt: event.airsAt,
      href: null,
    })),
    genres: genres.docs.map((genre) => ({ id: genre.id, name: genre.name, slug: genre.slug })),
  }

  return (
    <>
      <h1>{site.siteName}</h1>
      <p style={{ maxWidth: '70ch' }}>{String(site.settings?.tagline ?? site.profile.purpose)}</p>
      <JsonLd
        data={{
          '@context': 'https://schema.org',
          '@type': 'WebSite',
          name: site.siteName,
          url: absoluteUrl(site.tenant, '/'),
          inLanguage: 'ru-RU',
          potentialAction: {
            '@type': 'SearchAction',
            target: `${absoluteUrl(site.tenant, '/search/')}?q={search_term_string}`,
            'query-input': 'required name=search_term_string',
          },
        }}
      />
      <HomeBlocks site={site} blocks={blocks} data={data} />
      <span className="visually-hidden">{heading}</span>
    </>
  )
}

export default HomePage
