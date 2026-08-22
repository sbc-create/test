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

export const listTenantTitles = async (
  payload: Payload,
  tenant: TenantContext,
  options: { page?: number; genreId?: string | number; sort?: string; limit?: number } = {},
) => {
  const where: Where = options.genreId
    ? { and: [publishedOnly, { 'title.genres': { in: [options.genreId] } }] }
    : publishedOnly

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
