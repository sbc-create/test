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

export type SeoProfileKey =
  | 'catalog_authority'
  | 'release_pulse'
  | 'editorial_guide'
  | 'series_hub'
  | 'film_library'
  | 'premiere_radar'
  | 'curated_guide'

/**
 * Кто индексирует страницу произведения.
 *
 * Форма произведения и его релизное состояние однозначно определяют владельца:
 * вышедшие сериальные формы — у сайта сериалов, вышедшие полнометражные — у сайта
 * фильмов, ещё не вышедшее — у сайта премьер. Пересечения невозможны не потому,
 * что редакция договорилась, а потому, что множества не пересекаются. После
 * выхода произведение само уходит с сайта премьер и появляется у профильного —
 * это и есть требуемая автоматическая смена статуса.
 */
export type TitleOwnership = {
  kinds: readonly string[]
  releaseStates: readonly string[]
}

/** Формы, которые считаются сериальными и полнометражными. */
export const SERIES_KINDS = ['series', 'miniseries', 'ova'] as const
export const FILM_KINDS = ['movie', 'animated_film'] as const
/** Состояния, в которых произведение ещё не вышло. */
export const UPCOMING_STATES = ['announced', 'date_unknown', 'soon', 'delayed'] as const
export const ALL_KINDS = [...SERIES_KINDS, ...FILM_KINDS] as const
export const ALL_STATES = [...UPCOMING_STATES, 'released', 'cancelled'] as const

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
  /**
   * Какие произведения этот сайт индексирует. Пустые множества означают, что сайт
   * держит страницы произведений как навигацию и не индексирует ни одной.
   */
  titleOwnership: TitleOwnership
  /**
   * Разрешённые к индексации посадочные страницы фильтров (`tag` в матрице).
   * Всё, чего нет в списке, остаётся noindex с canonical на чистый раздел —
   * иначе комбинации фильтров порождают бесконечную индексируемую поверхность.
   */
  indexableFacets: readonly string[]
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
  // Каталожный сайт своей группы держит все формы и любое состояние: внутри
  // группы аниме-сайтов разделение проходит по типам страниц, а не по формам.
  titleOwnership: { kinds: ALL_KINDS, releaseStates: ALL_STATES },
  indexableFacets: [],
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
  titleOwnership: { kinds: ALL_KINDS, releaseStates: ALL_STATES },
  indexableFacets: [],
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
  titleOwnership: { kinds: ALL_KINDS, releaseStates: ALL_STATES },
  indexableFacets: [],
  newsHeading: 'Статьи и разборы редакции',
  newsSummary: 'Разборы, путеводители и объяснения — редакционный текст, а не пересказ аннотаций.',
  collectionsHeading: 'Подборки редакции',
  collectionsSummary: 'Несколько работ с объяснением, кому и с какого момента они подойдут.',
  episodeSummary: (name, season, episode) =>
    `Серия ${episode} сезона ${season} «${name}» в разборе редакции: о чём она и что в ней важно.`,
}

/* ------------------------------------------------------------------------- *
 * Четвёрка кинотеатров. Индексируемые поверхности не пересекаются по
 * построению: разделы-списки принадлежат одному сайту каждый, а страницы
 * произведений разведены по форме и релизному состоянию.
 * ------------------------------------------------------------------------- */

const SERIES_HUB: SeoProfile = {
  key: 'series_hub',
  label: 'SERIES_HUB',
  purpose: 'сериалы с полным составом сезонов, серий и статусом выхода',
  titleTemplates: {
    home: '{site} — сериалы по сезонам и сериям',
    category: '{page} — сериалы — {site}',
    title: '{page}: сезоны и серии — {site}',
    season: '{page} — {site}',
    episode: '{page} — {site}',
    tag: '{page} — подборка сериалов — {site}',
    news_index: 'Что нового в сериалах — {site}',
    article: '{page} — {site}',
    legal: '{page} — {site}',
    paginated_page: '{page} — страница {n} — {site}',
    search: 'Поиск по сериалам — {site}',
    not_found: 'Страница не найдена — {site}',
    gone: 'Материал удалён — {site}',
  },
  indexable: {
    home: true,
    category: true,
    title: true,
    season: true,
    episode: true,
    news_index: true,
    article: true,
    legal: true,
    paginated_page: true,
    content_unavailable: true,
  },
  requiresOwnText: ['article'],
  sitemapTypes: ['home', 'category', 'title', 'season', 'episode', 'news_index', 'article', 'legal'],
  ownedListings: ['/series/', '/news/'],
  // Вышедшие сериальные формы. Ещё не вышедший сериал живёт на сайте премьер и
  // переезжает сюда сам, когда состояние становится «вышло».
  titleOwnership: { kinds: SERIES_KINDS, releaseStates: ['released'] },
  indexableFacets: [],
  titleHeading: (name) => `${name}: сезоны, серии и статус выхода`,
  newsHeading: 'Что нового в сериалах',
  newsSummary: 'Вышедшие серии, закрытые сезоны и изменения в составе сериалов.',
  collectionsHeading: 'Сериальные подборки',
  collectionsSummary: 'Наборы сериалов, собранные по составу сезонов и статусу выхода.',
  episodeSummary: (name, season, episode) =>
    `Серия ${episode} сезона ${season} сериала «${name}»: место в порядке выхода и доступность просмотра.`,
}

const FILM_LIBRARY: SeoProfile = {
  key: 'film_library',
  label: 'FILM_LIBRARY',
  purpose: 'полнометражное кино с навигацией по жанрам, годам и странам',
  titleTemplates: {
    home: '{site} — кино по жанрам, годам и странам',
    category: '{page} — фильмы — {site}',
    title: '{page} — фильм — {site}',
    tag: '{page} — {site}',
    news_index: 'Кинообзоры — {site}',
    article: '{page} — {site}',
    legal: '{page} — {site}',
    paginated_page: '{page} — страница {n} — {site}',
    search: 'Поиск фильмов — {site}',
    not_found: 'Страница не найдена — {site}',
    gone: 'Материал удалён — {site}',
  },
  indexable: {
    home: true,
    category: true,
    title: true,
    // Посадочные страницы фильтров — единственный тип с условной индексацией:
    // индексируется только то, что перечислено в indexableFacets.
    tag: true,
    news_index: true,
    article: true,
    legal: true,
    paginated_page: true,
    content_unavailable: true,
  },
  requiresOwnText: ['article'],
  sitemapTypes: ['home', 'category', 'title', 'tag', 'news_index', 'article', 'legal'],
  ownedListings: ['/films/', '/news/'],
  titleOwnership: { kinds: FILM_KINDS, releaseStates: ['released'] },
  // Закрытый список посадочных страниц. Всё остальное — фильтр в параметрах
  // запроса: noindex и canonical на чистый раздел.
  indexableFacets: [
    '/films/genre/drama/',
    '/films/genre/thriller/',
    '/films/genre/comedy/',
    '/films/country/russia/',
    '/films/country/france/',
    '/films/year/2024/',
  ],
  titleHeading: (name) => `${name}: о фильме, жанре и годе выхода`,
  newsHeading: 'Кинообзоры редакции',
  newsSummary: 'Что посмотреть из полнометражного и почему именно это.',
  collectionsHeading: 'Кинонаборы',
  collectionsSummary: 'Фильмы, собранные по жанру, стране и году выхода.',
  episodeSummary: (name, season, episode) =>
    `Серия ${episode} сезона ${season} «${name}» — раздел сериалов, здесь страница остаётся навигацией.`,
}

const PREMIERE_RADAR: SeoProfile = {
  key: 'premiere_radar',
  label: 'PREMIERE_RADAR',
  purpose: 'подтверждённые даты премьер, переносы и недавно вышедшее',
  titleTemplates: {
    home: '{site} — календарь премьер',
    category: '{page} — премьеры — {site}',
    title: '{page}: дата выхода — {site}',
    news_index: 'Изменения дат — {site}',
    article: '{page} — {site}',
    legal: '{page} — {site}',
    paginated_page: '{page} — страница {n} — {site}',
    search: 'Поиск премьер — {site}',
    not_found: 'Страница не найдена — {site}',
    gone: 'Анонс снят — {site}',
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
  },
  requiresOwnText: ['article'],
  sitemapTypes: ['home', 'category', 'title', 'news_index', 'article', 'legal'],
  ownedListings: ['/calendar/', '/news/'],
  // Только то, что ещё не вышло, и только с подтверждённым источником — проверку
  // источника делает модель каталога, состояние проверяет профиль.
  titleOwnership: { kinds: ALL_KINDS, releaseStates: UPCOMING_STATES },
  indexableFacets: [],
  titleHeading: (name) => `${name}: когда премьера`,
  newsHeading: 'Изменения дат выхода',
  newsSummary: 'Перенесённые премьеры, подтверждённые даты и снятые анонсы.',
  collectionsHeading: 'Ожидаемое',
  collectionsSummary: 'Произведения с подтверждённой датой выхода, сгруппированные по месяцам.',
  episodeSummary: (name, season, episode) =>
    `Серия ${episode} сезона ${season} «${name}»: дата выхода и текущее состояние.`,
}

const CURATED_GUIDE: SeoProfile = {
  key: 'curated_guide',
  label: 'CURATED_GUIDE',
  purpose: 'редакционные подборки, порядок просмотра и переходы между произведениями',
  titleTemplates: {
    home: '{site} — что посмотреть',
    category: '{page} — {site}',
    collection: '{page} — подборка — {site}',
    title: '{page} — {site}',
    news_index: 'Редакционные материалы — {site}',
    article: '{page} — {site}',
    legal: '{page} — {site}',
    paginated_page: '{page} — страница {n} — {site}',
    search: 'Поиск по подборкам — {site}',
    not_found: 'Страница не найдена — {site}',
    gone: 'Подборка удалена — {site}',
  },
  indexable: {
    home: true,
    category: true,
    collection: true,
    news_index: true,
    article: true,
    legal: true,
    paginated_page: true,
    content_unavailable: true,
    // Страницы произведений здесь — переход к подборке, а не самостоятельная
    // страница: их индексируют сайты сериалов, фильмов и премьер.
  },
  requiresOwnText: ['collection', 'article'],
  sitemapTypes: ['home', 'category', 'collection', 'news_index', 'article', 'legal'],
  ownedListings: ['/collections/', '/news/'],
  titleOwnership: { kinds: [], releaseStates: [] },
  indexableFacets: [],
  titleHeading: (name) => `${name}: в каких подборках`,
  newsHeading: 'Материалы редакции',
  newsSummary: 'С чего начинать, что смотреть дальше и в каком порядке.',
  collectionsHeading: 'Подборки и маршруты просмотра',
  collectionsSummary: 'Списки с объяснением выбора и порядки просмотра с комментарием к каждому шагу.',
  episodeSummary: (name, season, episode) =>
    `Серия ${episode} сезона ${season} «${name}» — страница ведёт к подборкам, где произведение упомянуто.`,
}

export const SEO_PROFILES: Record<SeoProfileKey, SeoProfile> = {
  catalog_authority: CATALOG_AUTHORITY,
  release_pulse: RELEASE_PULSE,
  editorial_guide: EDITORIAL_GUIDE,
  series_hub: SERIES_HUB,
  film_library: FILM_LIBRARY,
  premiere_radar: PREMIERE_RADAR,
  curated_guide: CURATED_GUIDE,
}

/**
 * Группы сайтов, которые конкурируют между собой за одну и ту же выдачу.
 *
 * Сравнивать индексируемые поверхности имеет смысл внутри группы: аниме-тройка и
 * четвёрка кинотеатров работают с разными каталогами и разными запросами, а вот
 * два сайта одной группы, индексирующие один раздел, — это дубль. Ключ совпадает
 * с полем `cross_site_group` пакета сайта.
 */
export const PROFILE_GROUPS: Record<string, readonly SeoProfileKey[]> = {
  'anime-trio': ['catalog_authority', 'release_pulse', 'editorial_guide'],
  'cinema-quartet': ['series_hub', 'film_library', 'premiere_radar', 'curated_guide'],
}

/** Группа, в которой состоит профиль. Профиль без группы — ошибка конфигурации. */
export const groupOf = (key: SeoProfileKey): string => {
  const found = Object.entries(PROFILE_GROUPS).find(([, keys]) => keys.includes(key))
  if (!found) throw new Error(`BLOCKED_INPUT: профиль «${key}» не отнесён ни к одной группе сайтов`)
  return found[0]
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

/**
 * Индексирует ли этот сайт страницу конкретного произведения.
 *
 * Проверяется не «разрешён ли тип title», а совпадение формы и релизного
 * состояния с владением профиля: иначе одно и то же произведение попадает в
 * индекс сразу на двух доменах и конкурирует само с собой.
 */
export const ownsTitle = (
  profile: SeoProfile,
  title: { kind?: unknown; releaseState?: unknown } | null | undefined,
): boolean => {
  if (!profile.indexable.title) return false
  const kind = String(title?.kind ?? '')
  const state = String(title?.releaseState ?? 'released')
  return profile.titleOwnership.kinds.includes(kind)
    && profile.titleOwnership.releaseStates.includes(state)
}

/** Посадочная страница фильтра индексируется, только если она в списке профиля. */
export const ownsFacet = (profile: SeoProfile, path: string): boolean =>
  profile.indexableFacets.includes(path)

/** Раздел-список принадлежит сайту, значит может индексироваться. */
export const ownsListing = (profile: SeoProfile, path: string): boolean =>
  profile.ownedListings.includes(path)

/** Матрица разрешает тип в принципе, профиль — на конкретном сайте. */
export const matrixAllowsIndex = (pageType: PageTypeId): boolean =>
  PAGE_TYPES[pageType].index === 'index' ||
  PAGE_TYPES[pageType].index === 'conditional' ||
  PAGE_TYPES[pageType].index === 'inherit_from_parent'
