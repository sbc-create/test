import type { Metadata } from 'next'

import { TitleListing } from '../../../components/TitleListing'
import { currentSite } from '../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../seo/metadata'
import { hasActiveFilter, parseFilters } from '../../../lib/filters'
import { SERIES_KINDS, ownsListing } from '../../../seo/profiles'

export const dynamic = 'force-dynamic'

type Search = Promise<Record<string, string | string[] | undefined>>

const HEADING = 'Сериалы'
const BASE = '/series/'

export const generateMetadata = async ({ searchParams }: { searchParams: Search }): Promise<Metadata> => {
  const site = await currentSite()
  const filtered = hasActiveFilter(parseFilters(await searchParams))
  const metadata = buildMetadata(
    {
      tenant: site.tenant,
      pageType: filtered ? 'filter_non_indexable' : 'category',
      path: BASE,
      heading: HEADING,
      description: 'Сериалы с полным составом сезонов, серий и статусом выхода.',
      // Разделом владеет один сайт группы; у остальных он остаётся навигацией.
      documentRobots: ownsListing(site.profile, BASE) ? 'inherit' : 'noindex',
    },
    site.siteName,
  )
  if (filtered) metadata.alternates = { canonical: absoluteUrl(site.tenant, BASE) }
  return metadata
}

const SeriesPage = async ({ searchParams }: { searchParams: Search }) => {
  const site = await currentSite()
  return (
    <TitleListing
      site={site}
      basePath={BASE}
      heading={HEADING}
      dimensions={['genre', 'year', 'country', 'status']}
      kinds={SERIES_KINDS}
      releaseStates={['released']}
      searchParams={await searchParams}
    />
  )
}

export default SeriesPage
