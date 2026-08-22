import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { TitleListing } from '../../../../../components/TitleListing'
import { listGenres } from '../../../../../lib/content'
import { currentSite, payloadClient } from '../../../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../../../seo/metadata'
import { FILM_KINDS, ownsFacet } from '../../../../../seo/profiles'

export const dynamic = 'force-dynamic'

type Params = Promise<{ slug: string }>

/**
 * Посадочная страница жанра.
 *
 * Индексируется только если адрес перечислен в профиле сайта. Остальные жанры
 * доступны, работают и обходятся, но остаются noindex с canonical на раздел:
 * иначе каждый новый жанр молча добавляет индексируемую страницу без ценности.
 */
const pathFor = (slug: string) => `/films/genre/${slug}/`

export const generateMetadata = async ({ params }: { params: Params }): Promise<Metadata> => {
  const site = await currentSite()
  const payload = await payloadClient()
  const { slug } = await params
  const genres = await listGenres(payload)
  const genre = genres.docs.find((item) => String(item.slug) === slug)
  if (!genre) return { robots: 'noindex,follow' }

  const path = pathFor(slug)
  const indexable = ownsFacet(site.profile, path)
  const metadata = buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'tag',
      path,
      heading: `${genre.name}: фильмы`,
      description: `Полнометражные фильмы жанра «${genre.name}» с годом выхода и страной производства.`,
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
  const genres = await listGenres(payload)
  const genre = genres.docs.find((item) => String(item.slug) === slug)
  // Несуществующий жанр — 404, а не пустая страница со статусом 200.
  if (!genre) notFound()

  return (
    <TitleListing
      site={site}
      basePath={pathFor(slug)}
      heading={`${genre.name}: фильмы`}
      dimensions={['year', 'country']}
      kinds={FILM_KINDS}
      releaseStates={['released']}
      searchParams={{ genre: slug }}
      showFilters={false}
    />
  )
}

export default GenreLanding
