import type { Payload, Where } from 'payload'

import { tenantFind, tenantFindOne, type TenantContext } from './tenant-query'

/**
 * Чтение данных для публичных страниц.
 *
 * Контент сайта берётся только через tenantFind. Общий каталог (тайтлы, сезоны,
 * эпизоды, жанры) читается напрямую — он одинаков для всех сайтов и не содержит
 * ничего, что принадлежало бы одному из них.
 */

export const PAGE_SIZE = 24

export type TitleRecord = Record<string, unknown>

const publishedOnly: Where = { _status: { equals: 'published' } }

export type TitleFilter = {
  page?: number
  genreId?: string | number
  countryId?: string | number
  year?: number
  /** Формы произведения: сериальные и полнометражные разведены по сайтам. */
  kinds?: readonly string[]
  /** Релизные состояния: сайт премьер показывает только ещё не вышедшее. */
  releaseStates?: readonly string[]
  /** Статус производства: выходит, завершён, анонс. */
  statuses?: readonly string[]
  /**
   * Заведомо пустая выдача. Нужна, когда фильтр указывает на несуществующее
   * значение: подставлять туда фиктивный идентификатор нельзя — в Postgres это
   * ошибка типа, то есть 500 вместо честного «ничего не найдено».
   */
  impossible?: boolean
  sort?: string
  limit?: number
}

export const listTenantTitles = async (
  payload: Payload,
  tenant: TenantContext,
  options: TitleFilter = {},
) => {
  // Каждый фильтр — констрейнт запроса, а не отбор после выборки: иначе
  // счётчик и пагинация показывают одно, а список другое.
  const constraints: Where[] = [publishedOnly]
  // `id: { exists: false }` не выполняется никогда: идентификатор есть у каждой
  // записи. Это выражает «совпадений нет» средствами запроса, без гадания о типе.
  if (options.impossible) constraints.push({ id: { exists: false } })
  if (options.genreId) constraints.push({ 'title.genres': { in: [options.genreId] } })
  if (options.countryId) constraints.push({ 'title.countries': { in: [options.countryId] } })
  if (typeof options.year === 'number') constraints.push({ 'title.year': { equals: options.year } })
  if (options.kinds?.length) constraints.push({ 'title.kind': { in: [...options.kinds] } })
  if (options.releaseStates?.length) {
    constraints.push({ 'title.releaseState': { in: [...options.releaseStates] } })
  }
  if (options.statuses?.length) constraints.push({ 'title.status': { in: [...options.statuses] } })
  const where: Where = constraints.length === 1 ? constraints[0]! : { and: constraints }

  return tenantFind(payload, {
    collection: 'tenant-titles',
    tenant,
    where,
    page: options.page ?? 1,
    limit: options.limit ?? PAGE_SIZE,
    sort: options.sort ?? '-updatedAt',
    depth: 2,
  })
}

export const getTenantTitle = async (payload: Payload, tenant: TenantContext, slug: string) =>
  tenantFindOne(payload, {
    collection: 'tenant-titles',
    tenant,
    where: { and: [publishedOnly, { slug: { equals: slug } }] },
    depth: 2,
  })

export const listPosts = async (
  payload: Payload,
  tenant: TenantContext,
  options: { page?: number; limit?: number } = {},
) =>
  tenantFind(payload, {
    collection: 'posts',
    tenant,
    where: publishedOnly,
    page: options.page ?? 1,
    limit: options.limit ?? 12,
    sort: '-publishedAt',
    depth: 1,
  })

export const getPost = async (payload: Payload, tenant: TenantContext, slug: string) =>
  tenantFindOne(payload, {
    collection: 'posts',
    tenant,
    where: { and: [publishedOnly, { slug: { equals: slug } }] },
    depth: 1,
  })

export const listCollections = async (
  payload: Payload,
  tenant: TenantContext,
  options: { page?: number; limit?: number } = {},
) =>
  tenantFind(payload, {
    collection: 'editorial-collections',
    tenant,
    where: publishedOnly,
    page: options.page ?? 1,
    limit: options.limit ?? 12,
    depth: 2,
  })

export const getCollection = async (payload: Payload, tenant: TenantContext, slug: string) =>
  tenantFindOne(payload, {
    collection: 'editorial-collections',
    tenant,
    where: { and: [publishedOnly, { slug: { equals: slug } }] },
    depth: 2,
  })

export const getPage = async (payload: Payload, tenant: TenantContext, slug: string) =>
  tenantFindOne(payload, {
    collection: 'pages',
    tenant,
    where: { and: [publishedOnly, { slug: { equals: slug } }] },
    depth: 1,
  })

/** Общий каталог: жанры для фильтров. */
export const listGenres = async (payload: Payload) =>
  payload.find({ collection: 'genres', limit: 100, sort: 'name', depth: 0, overrideAccess: true })

export const listCountries = async (payload: Payload) =>
  payload.find({ collection: 'countries', limit: 200, sort: 'name', depth: 0, overrideAccess: true })

/**
 * Годы, по которым в каталоге сайта действительно есть материалы.
 *
 * Список строится из данных, а не из диапазона «от 1990 до текущего»: год без
 * единого произведения — это пустая страница фильтра, то есть ловушка обхода.
 */
export const availableYears = async (
  payload: Payload,
  tenant: TenantContext,
  options: { kinds?: readonly string[]; releaseStates?: readonly string[] } = {},
): Promise<number[]> => {
  const result = await listTenantTitles(payload, tenant, { ...options, limit: 500 })
  const years = new Set<number>()
  for (const doc of result.docs) {
    const shared = (doc as unknown as { title?: { year?: unknown } }).title
    const year = Number(shared?.year)
    if (Number.isInteger(year) && year > 1900) years.add(year)
  }
  return [...years].sort((left, right) => right - left)
}

export const listSeasons = async (payload: Payload, titleId: string | number) =>
  payload.find({
    collection: 'seasons',
    where: { title: { equals: titleId } },
    sort: 'number',
    limit: 100,
    depth: 0,
    overrideAccess: true,
  })

export const listEpisodes = async (payload: Payload, seasonId: string | number) =>
  payload.find({
    collection: 'episodes',
    where: { season: { equals: seasonId } },
    sort: 'number',
    limit: 500,
    depth: 0,
    overrideAccess: true,
  })

/** Расписание: факт выхода серий, общий для всех сайтов. */
export const listReleaseEvents = async (payload: Payload, options: { from: Date; to: Date }) =>
  payload.find({
    collection: 'release-events',
    where: {
      and: [
        { airsAt: { greater_than_equal: options.from.toISOString() } },
        { airsAt: { less_than: options.to.toISOString() } },
      ],
    },
    sort: 'airsAt',
    limit: 200,
    depth: 1,
    overrideAccess: true,
  })

/**
 * Поиск по материалам сайта. Поисковая выдача не индексируется, но она всё равно
 * обязана оставаться в пределах своего сайта.
 */
export const searchSite = async (payload: Payload, tenant: TenantContext, query: string) => {
  const trimmed = query.trim().slice(0, 120)
  if (!trimmed) return { titles: [], posts: [] }

  const [titles, posts] = await Promise.all([
    tenantFind(payload, {
      collection: 'tenant-titles',
      tenant,
      where: { and: [publishedOnly, { 'title.primaryName': { like: trimmed } }] },
      limit: 20,
      depth: 2,
    }),
    tenantFind(payload, {
      collection: 'posts',
      tenant,
      where: { and: [publishedOnly, { headline: { like: trimmed } }] },
      limit: 20,
      depth: 1,
    }),
  ])

  return { titles: titles.docs, posts: posts.docs }
}
