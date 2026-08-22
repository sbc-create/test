import type { Payload, Where } from 'payload'

import { TENANT_SCOPED_SLUGS } from '../hooks/tenant-integrity.js'

/**
 * Единственный разрешённый способ читать контент сайта при рендере.
 *
 * Публичные страницы рендерятся сервером без пользователя, поэтому обращение идёт
 * с overrideAccess: true. Само по себе это отключило бы tenant-фильтр — значит,
 * констрейнт сайта должен добавляться здесь принудительно и без возможности его
 * забыть. Прямые вызовы payload.find в коде страниц запрещены и проверяются тестом.
 */

export class TenantResolutionError extends Error {}

export type TenantContext = {
  id: string | number
  slug: string
  domain: string
  seoProfile: string
  theme: string
  indexingEnabled: boolean
  allowGuestComments: boolean
}

/** Host заголовок приходит от клиента: нормализуем и сверяем с записью в CMS. */
export const normalizeHost = (host: string | null | undefined): string => {
  if (!host) throw new TenantResolutionError('BLOCKED_INPUT: запрос без заголовка Host')
  return host.trim().toLowerCase().split(':')[0]!
}

export const resolveTenantByHost = async (
  payload: Payload,
  host: string | null | undefined,
): Promise<TenantContext> => {
  const domain = normalizeHost(host)
  const result = await payload.find({
    collection: 'tenants',
    where: { domain: { equals: domain } },
    limit: 1,
    depth: 0,
    overrideAccess: true,
  })
  const doc = result.docs[0] as Record<string, unknown> | undefined
  if (!doc) {
    // Неизвестный домен не подставляется «первым попавшимся» сайтом: иначе один
    // сайт отдавался бы под чужим адресом вместе с canonical и данными.
    throw new TenantResolutionError(`BLOCKED_INPUT: домен ${domain} не сопоставлен ни одному сайту`)
  }
  return {
    id: doc.id as string | number,
    slug: String(doc.slug ?? ''),
    domain: String(doc.domain ?? ''),
    seoProfile: String(doc.seoProfile ?? ''),
    theme: String(doc.theme ?? ''),
    indexingEnabled: Boolean(doc.indexingEnabled),
    allowGuestComments: Boolean(doc.allowGuestComments),
  }
}

const scoped = (tenant: TenantContext, where?: Where): Where => {
  const constraint: Where = { tenant: { equals: tenant.id } }
  return where ? { and: [constraint, where] } : constraint
}

const assertTenantScoped = (collection: string): void => {
  if (!TENANT_SCOPED_SLUGS.has(collection)) {
    throw new TenantResolutionError(
      `BLOCKED_INPUT: коллекция ${collection} не привязана к сайту, используйте sharedFind`,
    )
  }
}

export type TenantFindArgs = {
  collection: string
  tenant: TenantContext
  where?: Where
  limit?: number
  page?: number
  sort?: string
  depth?: number
  draft?: boolean
}

export const tenantFind = async (payload: Payload, args: TenantFindArgs) => {
  assertTenantScoped(args.collection)
  return payload.find({
    collection: args.collection as never,
    where: scoped(args.tenant, args.where),
    limit: args.limit ?? 20,
    page: args.page ?? 1,
    sort: args.sort,
    depth: args.depth ?? 1,
    draft: args.draft ?? false,
    overrideAccess: true,
  })
}

/** Один документ сайта. Возвращает null, а не документ другого сайта. */
export const tenantFindOne = async (payload: Payload, args: TenantFindArgs) => {
  const result = await tenantFind(payload, { ...args, limit: 1 })
  return result.docs[0] ?? null
}

export const tenantCount = async (
  payload: Payload,
  args: { collection: string; tenant: TenantContext; where?: Where },
) => {
  assertTenantScoped(args.collection)
  return payload.count({
    collection: args.collection as never,
    where: scoped(args.tenant, args.where),
    overrideAccess: true,
  })
}

/** «Глобал» сайта: ровно один документ на тенант. */
export const tenantGlobal = async (
  payload: Payload,
  collection: 'site-settings' | 'navigation' | 'home-layout',
  tenant: TenantContext,
  depth = 2,
) => tenantFindOne(payload, { collection, tenant, depth })
