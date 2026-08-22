import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { TitleListing } from '../../../../../components/TitleListing'
import { availableYears } from '../../../../../lib/content'
import { currentSite, payloadClient } from '../../../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../../../seo/metadata'
import { FILM_KINDS, ownsFacet } from '../../../../../seo/profiles'

export const dynamic = 'force-dynamic'

type Params = Promise<{ year: string }>

const pathFor = (year: number) => `/films/year/${year}/`

/** Год принимается только как четыре цифры: иначе адрес становится ловушкой обхода. */
const parseYear = (raw: string): number | null => (/^(19|20)\d{2}$/.test(raw) ? Number(raw) : null)

export const generateMetadata = async ({ params }: { params: Params }): Promise<Metadata> => {
  const site = await currentSite()
  const year = parseYear((await params).year)
  if (year === null) return { robots: 'noindex,follow' }

  const path = pathFor(year)
  const indexable = ownsFacet(site.profile, path)
  const metadata = buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'tag',
      path,
      heading: `Фильмы ${year} года`,
      description: `Полнометражные премьеры ${year} года с жанром и страной производства.`,
      documentRobots: indexable ? 'inherit' : 'noindex',
    },
    site.siteName,
  )
  if (!indexable) metadata.alternates = { canonical: absoluteUrl(site.tenant, '/films/') }
  return metadata
}

const YearLanding = async ({ params }: { params: Params }) => {
  const site = await currentSite()
  const payload = await payloadClient()
  const year = parseYear((await params).year)
  if (year === null) notFound()

  // Год без материалов — пустая страница, а пустых индексируемых страниц у нас
  // не бывает: отвечаем 404, а не 200 с пустым списком.
  const years = await availableYears(payload, site.tenant, {
    kinds: FILM_KINDS,
    releaseStates: ['released'],
  })
  if (!years.includes(year)) notFound()

  return (
    <TitleListing
      site={site}
      basePath={pathFor(year)}
      heading={`Фильмы ${year} года`}
      dimensions={['genre', 'country']}
      kinds={FILM_KINDS}
      releaseStates={['released']}
      searchParams={{ year: String(year) }}
      showFilters={false}
    />
  )
}

export default YearLanding
