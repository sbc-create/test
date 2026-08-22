import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { TitleListing } from '../../../../../components/TitleListing'
import { listCountries } from '../../../../../lib/content'
import { currentSite, payloadClient } from '../../../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../../../seo/metadata'
import { FILM_KINDS, ownsFacet } from '../../../../../seo/profiles'

export const dynamic = 'force-dynamic'

type Params = Promise<{ slug: string }>

/**
 * Посадочная страница страны производства.
 *
 * Индексируется только если адрес перечислен в профиле сайта. Остальные жанры
 * доступны, работают и обходятся, но остаются noindex с canonical на раздел:
 * иначе каждая новая страна молча добавляет индексируемую страницу без ценности.
 */
const pathFor = (slug: string) => `/films/country/${slug}/`

export const generateMetadata = async ({ params }: { params: Params }): Promise<Metadata> => {
  const site = await currentSite()
  const payload = await payloadClient()
  const { slug } = await params
  const countries = await listCountries(payload)
  const country = countries.docs.find((item) => String(item.slug) === slug)
  if (!country) return { robots: 'noindex,follow' }

  const path = pathFor(slug)
  const indexable = ownsFacet(site.profile, path)
  const metadata = buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'tag',
      path,
      heading: `${country.name}: фильмы`,
      description: `Полнометражные фильмы производства страны «${country.name}» с годом выхода и жанром.`,
      documentRobots: indexable ? 'inherit' : 'noindex',
    },
    site.siteName,
  )
  if (!indexable) metadata.alternates = { canonical: absoluteUrl(site.tenant, '/films/') }
  return metadata
}

const GenreLanding = async ({ params }: { params: Params }) => {
  const site = await currentSite()
  const payload = await payloadClient()
  const { slug } = await params
  const countries = await listCountries(payload)
  const country = countries.docs.find((item) => String(item.slug) === slug)
  // Несуществующая страна — 404, а не пустая страница со статусом 200.
  if (!country) notFound()

  return (
    <TitleListing
      site={site}
      basePath={pathFor(slug)}
      heading={`${country.name}: фильмы`}
      dimensions={['year', 'genre']}
      kinds={FILM_KINDS}
      releaseStates={['released']}
      searchParams={{ country: slug }}
      showFilters={false}
    />
  )
}

export default GenreLanding
