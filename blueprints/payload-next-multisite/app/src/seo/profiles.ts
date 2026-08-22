import { PAGE_TYPES, type PageTypeId } from './matrix'

/**
 * Три SEO-профиля. Профиль может только СУЖАТЬ индексируемость относительно
 * матрицы — расширять запрещено, иначе сайт индексирует то, что политика
 * фабрики закрыла. Проверяется тестом seo-profiles.
 *
 * Профили различаются не косметикой: у сайтов разный набор индексируемых типов
 * страниц и разные требования к собственному тексту. Три сайта с одинаковой
 * индексируемой поверхностью — это тот самый дубль, который ловит ворота
 * cross_site_uniqueness.
 */

export type SeoProfileKey = 'catalog_authority' | 'release_pulse' | 'editorial_guide'

export type SeoProfile = {
  key: SeoProfileKey
  label: string
  /** Шаблоны заголовка. Плейсхолдеры: {page}, {site}, {n}. */
  titleTemplates: Partial<Record<PageTypeId, string>>
  /** Тип страницы индексируется на этом сайте. Отсутствие ключа = не индексируется. */
  indexable: Partial<Record<PageTypeId, boolean>>
  /**
   * Типы, которым обязателен собственный текст сайта. Без него страница отдаётся
   * с noindex: пересказ одних и тех же фактов на трёх сайтах — это дубль.
   */
  requiresOwnText: PageTypeId[]
  /** Порядок типов в sitemap: у каждого сайта своя приоритетная поверхность. */
  sitemapTypes: PageTypeId[]
  /**
   * Списочные разделы, которые этот сайт считает своими. Раздел, которым сайт не
   * владеет, остаётся навигацией и закрывается от индексации: три сайта, у
   * которых индексируется один и тот же список одних и тех же карточек, — это
   * три копии, что бы ни было написано в шапке.
   */
  ownedListings: string[]
  /**
   * Шаблон H1 карточки тайтла. Разные сайты показывают разный срез одного факта,
   * и заголовок обязан это отражать, иначе H1 совпадает на трёх доменах.
   */
  titleHeading: (name: string) => string
  /** Заголовок ленты материалов: у каждого сайта она про своё. */
  newsHeading: string
  /** Описание ленты материалов. Одинаковое описание на трёх доменах — дубль. */
  newsSummary: string
  /** Заголовок раздела подборок: разделом владеют два сайта, и он у них разный. */
  collectionsHeading: string
  /** Описание раздела подборок. */
  collectionsSummary: string
  /**
   * Описание страницы серии. Факт один и тот же, но сайты отвечают на разные
   * вопросы о нём — иначе описания серий совпадают дословно на двух доменах.
   */
  episodeSummary: (name: string, season: number, episode: number) => string
  /** Подпись назначения сайта, используется в описаниях и в footer. */
  purpose: string
}

const CATALOG_AUTHORITY: SeoProfile = {
  key: 'catalog_authority',
  label: 'CATALOG_AUTHORITY',
  purpose: 'полный и точный каталог тайтлов с сезонами и эпизодами',
  titleTemplates: {
    home: '{site} — каталог аниме',
    category: '{page} — каталог — {site}',
    title: '{page} — все сезоны и эпизоды — {site}',
    season: '{page} — {site}',
    episode: '{page} — {site}',
    collection: '{page} — подборка — {site}',
    news_index: 'Новости каталога — {site}',
    article: '{page} — {site}',
    legal: '{page} — {site}',
    paginated_page: '{page} — страница {n} — {site}',
    search: 'Поиск — {site}',
    not_found: 'Страница не найдена — {site}',
    gone: 'Материал удалён — {site}',
  },
  indexable: {
    home: true,
    category: true,
    title: true,
    season: true,
    episode: true,
    collection: true,
    news_index: true,
    article: true,
    legal: true,
    paginated_page: true,
    content_unavailable: true,
  },
  requiresOwnText: ['collection', 'article'],
  sitemapTypes: ['home', 'category', 'title', 'season', 'episode', 'collection', 'news_index', 'article', 'legal'],
  ownedListings: ['/catalog/', '/collections/', '/news/'],
  titleHeading: (name) => `${name}: все сезоны и серии`,
  newsHeading: 'Новости каталога',
  newsSummary: 'Изменения в каталоге: что добавлено, что уточнено и как сверялись данные.',
  collectionsHeading: 'Подборки каталога',
  collectionsSummary: 'Наборы тайтлов, собранные по признакам каталога: студия, жанр, завершённость.',
  episodeSummary: (name, season, episode) =>
    `Серия ${episode} сезона ${season} «${name}»: место в порядке выхода и состояние доступа к просмотру.`,
}

const RELEASE_PULSE: SeoProfile = {
  key: 'release_pulse',
  label: 'RELEASE_PULSE',
  purpose: 'что выходит сегодня и на этой неделе, с расписанием и свежими эпизодами',
  titleTemplates: {
    home: '{site} — расписание выхода серий',
    category: 'Расписание: {page} — {site}',
    title: '{page}: расписание серий — {site}',
    season: '{page} — расписание — {site}',
    episode: '{page} — когда вышла серия — {site}',
    news_index: 'Новости выхода серий — {site}',
    article: '{page} — {site}',
    legal: '{page} — {site}',
    paginated_page: '{page} — страница {n} — {site}',
    search: 'Поиск — {site}',
    not_found: 'Страница не найдена — {site}',
    gone: 'Материал удалён — {site}',
  },
  indexable: {
    home: true,
    category: true,
    title: true,
    news_index: true,
    article: true,
    legal: true,
    paginated_page: true,
    content_unavailable: true,
    // Сезоны, эпизоды и подборки закрыты. Страница серии состоит из фактов
    // провайдера и плеера: на сайте каталога и здесь она получалась дословно
    // одинаковой — ворота уникальности показали это на 384 парах страниц.
    // Серии остаются доступными и играют, но индексирует их один владелец.
  },
  requiresOwnText: ['article'],
  // Карта обязана совпадать с индексируемой поверхностью, а не быть её надмножеством.
  sitemapTypes: ['home', 'category', 'title', 'news_index', 'article', 'legal'],
  ownedListings: ['/schedule/', '/news/'],
  titleHeading: (name) => `${name}: когда выходят серии`,
  newsHeading: 'Новости выхода серий',
  newsSummary: 'Что вышло, что перенесено и что ожидается на ближайшей неделе.',
  collectionsHeading: 'Подборки к расписанию',
  collectionsSummary: 'Наборы тайтлов, сгруппированные по дням выхода серий.',
  episodeSummary: (name, season, episode) =>
    `Когда вышла серия ${episode} сезона ${season} «${name}» и доступна ли она сейчас.`,
}

const EDITORIAL_GUIDE: SeoProfile = {
  key: 'editorial_guide',
  label: 'EDITORIAL_GUIDE',
  purpose: 'редакционные разборы, подборки и путеводители по тайтлам',
  titleTemplates: {
    home: '{site} — редакционный путеводитель',
    collection: '{page} — подборка редакции — {site}',
    title: '{page}: разбор редакции — {site}',
    news_index: 'Статьи и разборы — {site}',
    article: '{page} — {site}',
    category: '{page} — {site}',
    legal: '{page} — {site}',
    paginated_page: '{page} — страница {n} — {site}',
    search: 'Поиск — {site}',
    not_found: 'Страница не найдена — {site}',
    gone: 'Материал удалён — {site}',
  },
  indexable: {
    home: true,
    // Раздел подборок — профильный листинг этого сайта, он обязан индексироваться:
    // иначе он попадал бы в sitemap, оставаясь noindex.
    category: true,
    collection: true,
    news_index: true,
    article: true,
    title: true,
    legal: true,
    paginated_page: true,
    // Каталог, сезоны и эпизоды закрыты от индексации: здесь они существуют как
    // навигация к редакционным материалам, а не как самостоятельные страницы.
  },
  requiresOwnText: ['title', 'collection', 'article'],
  sitemapTypes: ['home', 'collection', 'news_index', 'article', 'title', 'legal'],
  ownedListings: ['/collections/', '/news/'],
  titleHeading: (name) => `${name}: разбор редакции`,
  newsHeading: 'Статьи и разборы редакции',
  newsSummary: 'Разборы, путеводители и объяснения — редакционный текст, а не пересказ аннотаций.',
  collectionsHeading: 'Подборки редакции',
  collectionsSummary: 'Несколько работ с объяснением, кому и с какого момента они подойдут.',
  episodeSummary: (name, season, episode) =>
    `Серия ${episode} сезона ${season} «${name}» в разборе редакции: о чём она и что в ней важно.`,
}

export const SEO_PROFILES: Record<SeoProfileKey, SeoProfile> = {
  catalog_authority: CATALOG_AUTHORITY,
  release_pulse: RELEASE_PULSE,
  editorial_guide: EDITORIAL_GUIDE,
}

export const profileFor = (key: string): SeoProfile => {
  const profile = SEO_PROFILES[key as SeoProfileKey]
  if (!profile) {
    // Пустой или неизвестный профиль не подменяется «профилем по умолчанию»:
    // так сайт получил бы чужую политику индексации молча.
    throw new Error(`BLOCKED_INPUT: неизвестный SEO-профиль «${key}»`)
  }
  return profile
}

/** Раздел-список принадлежит сайту, значит может индексироваться. */
export const ownsListing = (profile: SeoProfile, path: string): boolean =>
  profile.ownedListings.includes(path)

/** Матрица разрешает тип в принципе, профиль — на конкретном сайте. */
export const matrixAllowsIndex = (pageType: PageTypeId): boolean =>
  PAGE_TYPES[pageType].index === 'index' ||
  PAGE_TYPES[pageType].index === 'conditional' ||
  PAGE_TYPES[pageType].index === 'inherit_from_parent'
