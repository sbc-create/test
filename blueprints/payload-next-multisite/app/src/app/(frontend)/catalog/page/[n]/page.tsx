import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { Breadcrumbs } from '../../../../../components/Breadcrumbs'
import { CatalogListing } from '../../../../../components/CatalogListing'
import { availableYears, listTenantTitles, PAGE_SIZE } from '../../../../../lib/content'
import { buildFilterGroups, parseFilters } from '../../../../../lib/filters'
import { tenantTitleCard } from '../../../../../lib/present'
import { currentSite, payloadClient } from '../../../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../../../seo/metadata'
import { ownsListing } from '../../../../../seo/profiles'

export const dynamic = 'force-dynamic'

type Params = Promise<{ n: string }>

/**
 * Нечисловой или выходящий за диапазон номер — 404, а не пустая страница 200.
 * Страница 1 живёт по адресу `/catalog/`, поэтому `/catalog/page/1/` не существует.
 * Прежняя запись `^[2-9]\d*$` отвергала ещё и страницы 10–19, 100–199 и так далее.
 */
const parsePage = (raw: string): number | null => {
  if (!/^[1-9]\d*$/.test(raw)) return null
  const value = Number(raw)
  return value >= 2 ? value : null
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
      // Пагинация наследует индексируемость родителя: раздел, которым сайт не
      // владеет, не может индексироваться со второй страницы.
      documentRobots: ownsListing(site.profile, '/catalog/') ? 'inherit' : 'noindex',
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

  // На странице пагинации фильтры показываются, но не применяются: адрес
  // /catalog/page/N/ обязан отдавать ту же выдачу при любом переходе, иначе
  // страница 2 у разных посетителей содержит разное.
  const emptyFilters = parseFilters({})
  const [years, result] = await Promise.all([
    availableYears(payload, site.tenant),
    listTenantTitles(payload, site.tenant, { page }),
  ])
  const groups = await buildFilterGroups(payload, '/catalog/', emptyFilters, ['genre', 'year', 'status'], years)
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
        filters={groups}
        basePath="/catalog/"
        page={page}
        totalPages={totalPages}
        total={result.totalDocs}
        shape={site.layout.card}
        empty={site.layout.tone.emptyList}
      />
    </>
  )
}

export default CatalogPaged
