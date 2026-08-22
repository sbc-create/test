import type { Metadata } from 'next'

import { TitleListing } from '../../../components/TitleListing'
import { currentSite } from '../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../seo/metadata'
import { hasActiveFilter, parseFilters } from '../../../lib/filters'
import { UPCOMING_STATES, ownsListing } from '../../../seo/profiles'

export const dynamic = 'force-dynamic'

type Search = Promise<Record<string, string | string[] | undefined>>

const HEADING = 'Календарь премьер'
const BASE = '/calendar/'

export const generateMetadata = async ({ searchParams }: { searchParams: Search }): Promise<Metadata> => {
  const site = await currentSite()
  const filtered = hasActiveFilter(parseFilters(await searchParams))
  const metadata = buildMetadata(
    {
      tenant: site.tenant,
      pageType: filtered ? 'filter_non_indexable' : 'category',
      path: BASE,
      heading: HEADING,
      description: 'Подтверждённые даты выхода, переносы и недавно вышедшее.',
      documentRobots: ownsListing(site.profile, BASE) ? 'inherit' : 'noindex',
    },
    site.siteName,
  )
  if (filtered) metadata.alternates = { canonical: absoluteUrl(site.tenant, BASE) }
  return metadata
}

const CalendarPage = async ({ searchParams }: { searchParams: Search }) => {
  const site = await currentSite()
  return (
    <TitleListing
      site={site}
      basePath={BASE}
      heading={HEADING}
      dimensions={['genre', 'year', 'country']}
      // Только то, что ещё не вышло. Вышедшее уходит на профильный сайт само —
      // здесь оно просто перестаёт попадать в выдачу.
      releaseStates={UPCOMING_STATES}
      sort="title.releaseDate"
      searchParams={await searchParams}
    />
  )
}

export default CalendarPage
