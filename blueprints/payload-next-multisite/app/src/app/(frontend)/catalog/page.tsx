import type { Metadata } from 'next'

import { Breadcrumbs } from '../../../components/Breadcrumbs'
import { CatalogListing } from '../../../components/CatalogListing'
import { listGenres, listTenantTitles, PAGE_SIZE } from '../../../lib/content'
import { tenantTitleCard } from '../../../lib/present'
import { currentSite, payloadClient } from '../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../seo/metadata'

export const dynamic = 'force-dynamic'

type Search = Promise<Record<string, string | string[] | undefined>>

const HEADING = 'Каталог'

export const generateMetadata = async ({ searchParams }: { searchParams: Search }): Promise<Metadata> => {
  const site = await currentSite()
  const params = await searchParams
  const genre = typeof params.genre === 'string' ? params.genre : null

  const metadata = buildMetadata(
    {
      tenant: site.tenant,
      // Фильтр по жанру — не самостоятельная страница: она canonical на чистый /catalog/.
      pageType: genre ? 'filter_non_indexable' : 'category',
      path: '/catalog/',
      heading: HEADING,
      description: `Все материалы сайта «${site.siteName}»: ${site.profile.purpose}.`,
    },
    site.siteName,
  )
  if (genre) {
    metadata.alternates = { canonical: absoluteUrl(site.tenant, '/catalog/') }
  }
  return metadata
}

const CatalogPage = async ({ searchParams }: { searchParams: Search }) => {
  const site = await currentSite()
  const payload = await payloadClient()
  const params = await searchParams
  const genreSlug = typeof params.genre === 'string' ? params.genre : null

  const genres = await listGenres(payload)
  const activeGenre = genreSlug ? genres.docs.find((genre) => genre.slug === genreSlug) : undefined

  const result = await listTenantTitles(payload, site.tenant, {
    page: 1,
    genreId: activeGenre?.id,
  })

  return (
    <>
      <Breadcrumbs
        origin={absoluteUrl(site.tenant, '')}
        crumbs={[
          { title: 'Главная', href: '/' },
          { title: HEADING, href: '/catalog/' },
        ]}
      />
      <h1>{HEADING}</h1>
      <CatalogListing
        items={result.docs.map(tenantTitleCard)}
        genres={genres.docs.map((genre) => ({ name: genre.name, slug: genre.slug }))}
        activeGenre={genreSlug}
        page={1}
        totalPages={Math.max(1, Math.ceil(result.totalDocs / PAGE_SIZE))}
        total={result.totalDocs}
      />
    </>
  )
}

export default CatalogPage
