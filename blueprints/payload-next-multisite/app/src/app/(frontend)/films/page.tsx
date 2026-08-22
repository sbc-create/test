import type { Metadata } from 'next'

import { TitleListing } from '../../../components/TitleListing'
import { currentSite } from '../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../seo/metadata'
import { hasActiveFilter, parseFilters } from '../../../lib/filters'
import { FILM_KINDS, ownsListing } from '../../../seo/profiles'

export const dynamic = 'force-dynamic'

type Search = Promise<Record<string, string | string[] | undefined>>

const HEADING = 'Фильмы'
const BASE = '/films/'

export const generateMetadata = async ({ searchParams }: { searchParams: Search }): Promise<Metadata> => {
  const site = await currentSite()
  const filtered = hasActiveFilter(parseFilters(await searchParams))
  const metadata = buildMetadata(
    {
      tenant: site.tenant,
      pageType: filtered ? 'filter_non_indexable' : 'category',
      path: BASE,
      heading: HEADING,
      description: 'Полнометражное кино с навигацией по жанрам, годам и странам.',
      documentRobots: ownsListing(site.profile, BASE) ? 'inherit' : 'noindex',
    },
    site.siteName,
  )
  if (filtered) metadata.alternates = { canonical: absoluteUrl(site.tenant, BASE) }
  return metadata
}

const FilmsPage = async ({ searchParams }: { searchParams: Search }) => {
  const site = await currentSite()
  return (
    <TitleListing
      site={site}
      basePath={BASE}
      heading={HEADING}
      dimensions={['genre', 'year', 'country']}
      kinds={FILM_KINDS}
      releaseStates={['released']}
      searchParams={await searchParams}
    />
  )
}

export default FilmsPage
