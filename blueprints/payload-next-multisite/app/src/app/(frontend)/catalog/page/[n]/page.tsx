import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { Breadcrumbs } from '../../../../../components/Breadcrumbs'
import { CatalogListing } from '../../../../../components/CatalogListing'
import { listGenres, listTenantTitles, PAGE_SIZE } from '../../../../../lib/content'
import { tenantTitleCard } from '../../../../../lib/present'
import { currentSite, payloadClient } from '../../../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../../../seo/metadata'

export const dynamic = 'force-dynamic'

type Params = Promise<{ n: string }>

/** Нечисловой или выходящий за диапазон номер — 404, а не пустая страница 200. */
const parsePage = (raw: string): number | null => {
  if (!/^[2-9]\d*$/.test(raw)) return null
  return Number(raw)
}

export const generateMetadata = async ({ params }: { params: Params }): Promise<Metadata> => {
  const site = await currentSite()
  const { n } = await params
  const page = parsePage(n)
  if (page === null) return { robots: 'noindex,follow' }
  return buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'paginated_page',
      path: `/catalog/page/${page}/`,
      heading: 'Каталог',
      page,
      description: `Каталог сайта «${site.siteName}», страница ${page}.`,
    },
    site.siteName,
  )
}

const CatalogPaged = async ({ params }: { params: Params }) => {
  const site = await currentSite()
  const payload = await payloadClient()
  const { n } = await params
  const page = parsePage(n)
  // Страница 1 живёт по адресу /catalog/ — дубля с /catalog/page/1/ не существует.
  if (page === null) notFound()

  const [genres, result] = await Promise.all([
    listGenres(payload),
    listTenantTitles(payload, site.tenant, { page }),
  ])
  const totalPages = Math.max(1, Math.ceil(result.totalDocs / PAGE_SIZE))
  if (page > totalPages) notFound()

  return (
    <>
      <Breadcrumbs
        origin={absoluteUrl(site.tenant, '')}
        crumbs={[
          { title: 'Главная', href: '/' },
          { title: 'Каталог', href: '/catalog/' },
          { title: `Страница ${page}`, href: `/catalog/page/${page}/` },
        ]}
      />
      <h1>Каталог</h1>
      <CatalogListing
        items={result.docs.map(tenantTitleCard)}
        genres={genres.docs.map((genre) => ({ name: genre.name, slug: genre.slug }))}
        activeGenre={null}
        page={page}
        totalPages={totalPages}
        total={result.totalDocs}
      />
    </>
  )
}

export default CatalogPaged
