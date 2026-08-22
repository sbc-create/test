/**
 * Матрица индексируемости для blueprint payload-next-multisite.
 *
 * Источник правил — knowledge/SEO_INDEXABILITY_MATRIX.yaml (замороженная политика
 * фабрики). Здесь она выражена в типах, чтобы рендер не мог отдать страницу с
 * настройками «на своё усмотрение». Расхождение с YAML ловит тест seo-matrix:
 * дублирование без сверки — источник тихого дрейфа политики.
 */

export const MATRIX_POLICY_VERSION = '2026-08-21.2'

export type PageTypeId =
  | 'home'
  | 'category'
  | 'collection'
  | 'title'
  | 'season'
  | 'episode'
  | 'article'
  | 'news_index'
  | 'tag'
  | 'archive'
  | 'paginated_page'
  | 'search'
  | 'filter_non_indexable'
  | 'filter_indexable'
  | 'legal'
  | 'service'
  | 'not_found'
  | 'gone'
  | 'content_unavailable'

export type IndexRule = 'index' | 'noindex' | 'conditional' | 'inherit_from_parent'
export type CanonicalRule =
  | 'self_absolute'
  | 'canonical_to_parent_clean_url'
  | 'none_no_index'

export type PageTypeRule = {
  index: IndexRule
  follow: boolean
  canonical: CanonicalRule
  inSitemap: boolean | 'conditional' | 'inherit_from_parent'
  structuredData: string[]
  httpStatus: number[]
}

/**
 * `structuredData` перечисляет типы, РАЗРЕШЁННЫЕ матрицей, а не обязательные:
 * `*_when_applicable` и `*_when_video_available` эмитятся только при полных
 * фактических полях. Список сверяется с замороженным YAML построчно.
 */
export const PAGE_TYPES: Record<PageTypeId, PageTypeRule> = {
  home: { index: 'index', follow: true, canonical: 'self_absolute', inSitemap: true, structuredData: ['WebSite', 'Organization'], httpStatus: [200] },
  category: { index: 'index', follow: true, canonical: 'self_absolute', inSitemap: true, structuredData: ['BreadcrumbList'], httpStatus: [200, 404] },
  collection: { index: 'index', follow: true, canonical: 'self_absolute', inSitemap: true, structuredData: ['BreadcrumbList'], httpStatus: [200, 404] },
  title: { index: 'index', follow: true, canonical: 'self_absolute', inSitemap: true, structuredData: ['BreadcrumbList', 'Movie_or_TVSeries_when_applicable', 'VideoObject_when_video_available'], httpStatus: [200, 404, 410] },
  season: { index: 'index', follow: true, canonical: 'self_absolute', inSitemap: true, structuredData: ['BreadcrumbList'], httpStatus: [200, 404] },
  episode: { index: 'index', follow: true, canonical: 'self_absolute', inSitemap: true, structuredData: ['BreadcrumbList', 'TVEpisode_when_applicable', 'VideoObject_when_video_available'], httpStatus: [200, 404, 410] },
  article: { index: 'index', follow: true, canonical: 'self_absolute', inSitemap: true, structuredData: ['BreadcrumbList', 'Article_or_NewsArticle'], httpStatus: [200, 404, 410] },
  news_index: { index: 'index', follow: true, canonical: 'self_absolute', inSitemap: true, structuredData: ['BreadcrumbList'], httpStatus: [200] },
  tag: { index: 'conditional', follow: true, canonical: 'self_absolute', inSitemap: 'conditional', structuredData: ['BreadcrumbList'], httpStatus: [200, 404] },
  archive: { index: 'noindex', follow: true, canonical: 'self_absolute', inSitemap: false, structuredData: [], httpStatus: [200, 404] },
  paginated_page: { index: 'inherit_from_parent', follow: true, canonical: 'self_absolute', inSitemap: 'inherit_from_parent', structuredData: ['BreadcrumbList'], httpStatus: [200, 404] },
  search: { index: 'noindex', follow: true, canonical: 'none_no_index', inSitemap: false, structuredData: [], httpStatus: [200] },
  filter_non_indexable: { index: 'noindex', follow: true, canonical: 'canonical_to_parent_clean_url', inSitemap: false, structuredData: [], httpStatus: [200] },
  filter_indexable: { index: 'conditional', follow: true, canonical: 'self_absolute', inSitemap: 'conditional', structuredData: ['BreadcrumbList'], httpStatus: [200, 404] },
  legal: { index: 'index', follow: true, canonical: 'self_absolute', inSitemap: true, structuredData: ['BreadcrumbList'], httpStatus: [200] },
  service: { index: 'noindex', follow: true, canonical: 'none_no_index', inSitemap: false, structuredData: [], httpStatus: [200] },
  not_found: { index: 'noindex', follow: true, canonical: 'none_no_index', inSitemap: false, structuredData: [], httpStatus: [404] },
  gone: { index: 'noindex', follow: true, canonical: 'none_no_index', inSitemap: false, structuredData: [], httpStatus: [410] },
  content_unavailable: { index: 'index', follow: true, canonical: 'self_absolute', inSitemap: true, structuredData: ['BreadcrumbList'], httpStatus: [200] },
}

/** Параметры запроса, которые никогда не делают URL самостоятельным. */
export const NON_INDEXABLE_PARAMS = [
  'sort',
  'order',
  'view',
  'per_page',
  'q',
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_term',
  'utm_content',
  'gclid',
  'yclid',
  'fbclid',
]
