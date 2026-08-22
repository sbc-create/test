import type { Metadata } from 'next'

import { Breadcrumbs } from '../../../components/Breadcrumbs'
import { CatalogListing } from '../../../components/CatalogListing'
import { availableYears, listTenantTitles, PAGE_SIZE } from '../../../lib/content'
import { buildFilterGroups, filterQuery, hasActiveFilter, parseFilters } from '../../../lib/filters'
import { tenantTitleCard } from '../../../lib/present'
import { currentSite, payloadClient } from '../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../seo/metadata'
import { ownsListing } from '../../../seo/profiles'

export const dynamic = 'force-dynamic'

type Search = Promise<Record<string, string | string[] | undefined>>

const HEADING = 'Каталог'

export const generateMetadata = async ({ searchParams }: { searchParams: Search }): Promise<Metadata> => {
  const site = await currentSite()
  const params = await searchParams
  const filters = parseFilters(params)
  const filtered = hasActiveFilter(filters)

  const metadata = buildMetadata(
    {
      tenant: site.tenant,
      // Фильтр по жанру — не самостоятельная страница: она canonical на чистый /catalog/.
      pageType: filtered ? 'filter_non_indexable' : 'category',
      path: '/catalog/',
      heading: HEADING,
      description: `Все материалы сайта «${site.siteName}»: ${site.profile.purpose}.`,
      // Раздел, которым сайт не владеет, остаётся навигацией и не индексируется.
      documentRobots: ownsListing(site.profile, '/catalog/') ? 'inherit' : 'noindex',
    },
    site.siteName,
  )
  if (filtered) {
    // Отфильтрованная выдача не самостоятельная страница: canonical ведёт на
    // чистый раздел, иначе комбинации параметров плодят индексируемые адреса.
    metadata.alternates = { canonical: absoluteUrl(site.tenant, '/catalog/') }
  }
  return metadata
}

const CatalogPage = async ({ searchParams }: { searchParams: Search }) => {
  const site = await currentSite()
  const payload = await payloadClient()
  const params = await searchParams
  const filters = parseFilters(params)

  const years = await availableYears(payload, site.tenant)
  const groups = await buildFilterGroups(payload, '/catalog/', filters, ['genre', 'year', 'status'], years)
  const query = await filterQuery(payload, filters)
  const result = await listTenantTitles(payload, site.tenant, { page: 1, ...query })

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
        filters={groups}
        basePath="/catalog/"
        page={1}
        totalPages={Math.max(1, Math.ceil(result.totalDocs / PAGE_SIZE))}
        total={result.totalDocs}
        shape={site.layout.card}
        empty={site.layout.tone.emptyList}
        resetHref="/catalog/"
      />
    </>
  )
}

export default CatalogPage
