import { Breadcrumbs } from './Breadcrumbs'
import { CatalogListing } from './CatalogListing'
import { availableYears, listTenantTitles, PAGE_SIZE } from '../lib/content'
import { buildFilterGroups, filterQuery, parseFilters, type FilterDimension } from '../lib/filters'
import { tenantTitleCard } from '../lib/present'
import type { SiteContext } from '../lib/site'
import { payloadClient } from '../lib/site'
import { absoluteUrl } from '../seo/metadata'

/**
 * Общий листинг произведений для всех разделов и всех сайтов.
 *
 * Четыре сайта показывают разные срезы одного каталога, но правила у листинга
 * одни: фильтр — констрейнт запроса, пагинация — обычные ссылки, форма карточки
 * приходит из темы. Четыре копии этого кода разошлись бы через месяц, и проверка
 * «фильтр действительно меняет выдачу» проходила бы не везде.
 */
export const TitleListing = async ({
  site,
  basePath,
  heading,
  dimensions,
  kinds,
  releaseStates,
  page = 1,
  searchParams = {},
  sort,
  showFilters = true,
}: {
  site: SiteContext
  basePath: string
  heading: string
  dimensions: readonly FilterDimension[]
  kinds?: readonly string[]
  releaseStates?: readonly string[]
  page?: number
  searchParams?: Record<string, string | string[] | undefined>
  sort?: string
  showFilters?: boolean
}) => {
  const payload = await payloadClient()
  const filters = parseFilters(searchParams)
  const query = await filterQuery(payload, filters)

  const [years, result] = await Promise.all([
    availableYears(payload, site.tenant, { kinds, releaseStates }),
    listTenantTitles(payload, site.tenant, { page, kinds, releaseStates, sort, ...query }),
  ])
  const groups = showFilters
    ? await buildFilterGroups(payload, basePath, filters, dimensions, years)
    : []

  return (
    <>
      <Breadcrumbs
        origin={absoluteUrl(site.tenant, '')}
        crumbs={[
          { title: 'Главная', href: '/' },
          { title: heading, href: basePath },
          ...(page > 1 ? [{ title: `Страница ${page}`, href: `${basePath}page/${page}/` }] : []),
        ]}
      />
      <h1>{heading}</h1>
      <CatalogListing
        items={result.docs.map(tenantTitleCard)}
        filters={groups}
        basePath={basePath}
        page={page}
        totalPages={Math.max(1, Math.ceil(result.totalDocs / PAGE_SIZE))}
        total={result.totalDocs}
        shape={site.layout.card}
        empty={site.layout.tone.emptyList}
        resetHref={basePath}
      />
    </>
  )
}

/** Число страниц раздела — нужно маршруту пагинации до рендера. */
export const listingPageCount = async (
  site: SiteContext,
  options: { kinds?: readonly string[]; releaseStates?: readonly string[] } = {},
): Promise<number> => {
  const payload = await payloadClient()
  const result = await listTenantTitles(payload, site.tenant, { ...options, page: 1 })
  return Math.max(1, Math.ceil(result.totalDocs / PAGE_SIZE))
}
