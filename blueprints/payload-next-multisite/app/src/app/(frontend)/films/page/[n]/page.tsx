import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { TitleListing, listingPageCount } from '../../../../../components/TitleListing'
import { currentSite } from '../../../../../lib/site'
import { buildMetadata } from '../../../../../seo/metadata'
import { FILM_KINDS, ownsListing } from '../../../../../seo/profiles'

export const dynamic = 'force-dynamic'

type Params = Promise<{ n: string }>

const HEADING = 'Фильмы'
const BASE = '/films/'

/** Страница 1 живёт по адресу раздела: дубля /page/1/ не существует. */
const parsePage = (raw: string): number | null => {
  if (!/^[1-9]\d*$/.test(raw)) return null
  const value = Number(raw)
  return value >= 2 ? value : null
}

export const generateMetadata = async ({ params }: { params: Params }): Promise<Metadata> => {
  const site = await currentSite()
  const page = parsePage((await params).n)
  if (page === null) return { robots: 'noindex,follow' }
  return buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'paginated_page',
      path: `${BASE}page/${page}/`,
      heading: HEADING,
      page,
      // Страница пагинации наследует индексируемость раздела: если разделом
      // владеет другой сайт, его страницы 2+ индексировать тем более незачем.
      documentRobots: ownsListing(site.profile, BASE) ? 'inherit' : 'noindex',
    },
    site.siteName,
  )
}

const Paged = async ({ params }: { params: Params }) => {
  const site = await currentSite()
  const page = parsePage((await params).n)
  if (page === null) notFound()

  const totalPages = await listingPageCount(site, { kinds: FILM_KINDS, releaseStates: ['released'] })
  if (page > totalPages) notFound()

  return (
    <TitleListing
      site={site}
      basePath={BASE}
      heading={HEADING}
      dimensions={[]}
      showFilters={false}
      kinds={FILM_KINDS}
      releaseStates={['released']}
      page={page}
    />
  )
}

export default Paged
