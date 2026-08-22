import type { Metadata } from 'next'

import type { TenantContext } from '../lib/tenant-query'
import { NON_INDEXABLE_PARAMS, PAGE_TYPES, type PageTypeId } from './matrix'
import { profileFor } from './profiles'

/**
 * Сборка метаданных страницы по матрице и профилю сайта.
 *
 * Жёсткие правила матрицы выполняются здесь, а не «по договорённости с
 * редакцией»: indexable-страница обязана иметь абсолютный self-canonical, а
 * noindex-страница не получает canonical вовсе.
 */

export type PageInput = {
  tenant: TenantContext
  pageType: PageTypeId
  /** Путь без домена и без query, всегда со слэшем на конце (кроме корня). */
  path: string
  /** Видимый заголовок страницы, из фактических данных. */
  heading: string
  description?: string | null
  /** Собственный текст сайта на этой странице (для профилей, где он обязателен). */
  ownText?: string | null
  /** Номер страницы пагинации, если это страница 2+. */
  page?: number
  /** Явное указание robots из документа (inherit | index | noindex). */
  documentRobots?: 'inherit' | 'index' | 'noindex'
  image?: { url: string; alt: string } | null
}

export type ResolvedSeo = {
  robots: string
  canonical: string | null
  title: string
  description: string | null
  indexable: boolean
  reasons: string[]
}

const origin = (tenant: TenantContext): string => `https://${tenant.domain}`

export const absoluteUrl = (tenant: TenantContext, path: string): string => {
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${origin(tenant)}${normalized}`
}

const applyTemplate = (template: string, values: Record<string, string>): string =>
  template.replace(/\{(\w+)\}/g, (_, key: string) => values[key] ?? '')

/**
 * Итоговая индексируемость. Каждое «нет» сопровождается причиной: отчёт, который
 * не может объяснить noindex, невозможно проверить.
 */
export const resolveSeo = (input: PageInput, siteName: string): ResolvedSeo => {
  const profile = profileFor(input.tenant.seoProfile)
  const rule = PAGE_TYPES[input.pageType]
  const reasons: string[] = []

  let indexable = rule.index === 'index' || rule.index === 'conditional' || rule.index === 'inherit_from_parent'
  if (!indexable) reasons.push(`матрица: тип ${input.pageType} не индексируется`)

  if (indexable && !profile.indexable[input.pageType]) {
    indexable = false
    reasons.push(`профиль ${profile.label}: тип ${input.pageType} закрыт на этом сайте`)
  }

  if (indexable && profile.requiresOwnText.includes(input.pageType) && !(input.ownText ?? '').trim()) {
    indexable = false
    reasons.push(`профиль ${profile.label}: у страницы нет собственного текста сайта`)
  }

  if (indexable && input.documentRobots === 'noindex') {
    indexable = false
    reasons.push('редакция закрыла страницу от индексации')
  }

  if (indexable && !input.tenant.indexingEnabled) {
    indexable = false
    reasons.push('индексация сайта ещё не разрешена в настройках сайта')
  }

  const template =
    (input.page && input.page > 1 ? profile.titleTemplates.paginated_page : undefined) ??
    profile.titleTemplates[input.pageType] ??
    '{page} — {site}'

  const title = applyTemplate(template, {
    page: input.heading,
    site: siteName,
    n: String(input.page ?? 1),
  }).trim()

  const canonical =
    rule.canonical === 'none_no_index' || !indexable ? null : absoluteUrl(input.tenant, input.path)

  return {
    robots: indexable ? 'index,follow' : rule.follow ? 'noindex,follow' : 'noindex,nofollow',
    canonical,
    title,
    description: input.description?.trim() || null,
    indexable,
    reasons,
  }
}

export const buildMetadata = (input: PageInput, siteName: string): Metadata => {
  const seo = resolveSeo(input, siteName)
  const metadata: Metadata = {
    title: seo.title,
    description: seo.description ?? undefined,
    robots: seo.robots,
    alternates: seo.canonical ? { canonical: seo.canonical } : undefined,
    openGraph: {
      type: 'website',
      title: seo.title,
      description: seo.description ?? undefined,
      url: seo.canonical ?? undefined,
      siteName,
      locale: 'ru_RU',
      images: input.image ? [{ url: input.image.url, alt: input.image.alt }] : undefined,
    },
  }
  return metadata
}

/** Проверка, что в URL не осталось параметров, делающих страницу дублем. */
export const hasNonIndexableParams = (search: URLSearchParams): boolean =>
  NON_INDEXABLE_PARAMS.some((param) => search.has(param))
