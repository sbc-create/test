/**
 * Матрица индексируемости продублирована в TypeScript ради типов. Дубликат без
 * сверки — источник тихого дрейфа политики, поэтому здесь он сверяется с
 * замороженным YAML фабрики построчно.
 */
import { readFileSync } from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

import { load } from 'js-yaml'

import { inSitemap, seasonInSitemap, seasonNote } from '../src/seo/inclusion'
import { MATRIX_POLICY_VERSION, NON_INDEXABLE_PARAMS, PAGE_TYPES, type PageTypeId } from '../src/seo/matrix'
import { resolveSeo } from '../src/seo/metadata'
import {
  ALL_KINDS,
  ALL_STATES,
  FILM_KINDS,
  SEO_PROFILES,
  SERIES_KINDS,
  UPCOMING_STATES,
  PROFILE_GROUPS,
  matrixAllowsIndex,
  ownsFacet,
  ownsTitle,
} from '../src/seo/profiles'
import { assert, assertEqual, check, summary } from './harness'

const dirname = path.dirname(fileURLToPath(import.meta.url))
const yamlPath = path.resolve(dirname, '../../../../knowledge/SEO_INDEXABILITY_MATRIX.yaml')
const frozen = load(readFileSync(yamlPath, 'utf8')) as {
  policy_version: string
  query_parameters: { non_indexable: string[] }
  page_types: Record<string, unknown>[]
}

const byId = new Map(frozen.page_types.map((entry) => [String(entry.id), entry]))

const indexOf = (entry: Record<string, unknown>): string => {
  const value = entry.index
  if (value === true) return 'index'
  if (value === false) return 'noindex'
  return String(value)
}

const sitemapOf = (entry: Record<string, unknown>): boolean | string => {
  const value = entry.in_sitemap
  if (typeof value === 'boolean') return value
  if (value === 'conditional_same_as_index') return 'conditional'
  return String(value)
}

const canonicalOf = (entry: Record<string, unknown>): string => {
  const value = String(entry.canonical_rule)
  return value === 'none_no_index' ? 'none_no_index' : value
}

await check('версия политики совпадает с замороженной', () => {
  assertEqual(MATRIX_POLICY_VERSION, frozen.policy_version, 'версия политики')
})

await check('каждый тип страницы кода есть в замороженной матрице', () => {
  const missing = (Object.keys(PAGE_TYPES) as PageTypeId[]).filter((id) => !byId.has(id))
  assertEqual(missing.join(', '), '', 'типы, которых нет в матрице')
})

for (const id of Object.keys(PAGE_TYPES) as PageTypeId[]) {
  await check(`правила типа ${id} совпадают с матрицей`, () => {
    const entry = byId.get(id) as Record<string, unknown>
    const rule = PAGE_TYPES[id]
    assertEqual(rule.index, indexOf(entry), `${id}: index`)
    assertEqual(rule.follow, entry.follow !== false, `${id}: follow`)
    assertEqual(rule.canonical, canonicalOf(entry), `${id}: canonical`)
    assertEqual(String(rule.inSitemap), String(sitemapOf(entry)), `${id}: in_sitemap`)
    const statuses = (entry.http_status as number[]) ?? []
    assertEqual(rule.httpStatus.join(','), statuses.join(','), `${id}: http_status`)

    // Структурированные данные объявлены по обе стороны и раньше не сравнивались:
    // правка в YAML не роняла ничего, и политика расходилась молча.
    const declared = ((entry.structured_data as string[]) ?? []).join(',')
    assertEqual(rule.structuredData.join(','), declared, `${id}: structured_data`)
  })
}

await check('типов из матрицы, неизвестных blueprint, не остаётся без решения', () => {
  // Тип, который матрица разрешает, а blueprint не знает, — это не ошибка сама по
  // себе, но он обязан быть перечислен явно, иначе про него просто забудут.
  const notImplemented = new Set(['author', 'tag', 'archive', 'filter_indexable', 'gone', 'service'])
  const unknown = [...byId.keys()].filter(
    (id) => !(id in PAGE_TYPES) && !notImplemented.has(id),
  )
  assertEqual(unknown.join(', '), '', 'типы матрицы, не учтённые blueprint')
})

await check('список неиндексируемых параметров совпадает', () => {
  assertEqual(
    [...NON_INDEXABLE_PARAMS].sort().join(','),
    [...frozen.query_parameters.non_indexable].sort().join(','),
    'параметры',
  )
})

for (const [key, profile] of Object.entries(SEO_PROFILES)) {
  await check(`профиль ${key} только сужает матрицу, а не расширяет`, () => {
    for (const [type, allowed] of Object.entries(profile.indexable)) {
      if (!allowed) continue
      assert(
        matrixAllowsIndex(type as PageTypeId),
        `${key}: тип ${type} открыт профилем, хотя матрица его закрывает`,
      )
    }
  })
}

await check('ни один профиль не повторяет другой', () => {
  // Отпечаток профиля — что он индексирует, какими разделами владеет и какие
  // произведения считает своими. Два одинаковых отпечатка означают два зеркала.
  const fingerprints = Object.entries(SEO_PROFILES).map(([key, profile]) => [
    key,
    JSON.stringify({
      types: Object.entries(profile.indexable).filter(([, on]) => on).map(([type]) => type).sort(),
      listings: [...profile.ownedListings].sort(),
      kinds: [...profile.titleOwnership.kinds].sort(),
      states: [...profile.titleOwnership.releaseStates].sort(),
    }),
  ] as const)
  const seen = new Map<string, string>()
  for (const [key, fingerprint] of fingerprints) {
    const twin = seen.get(fingerprint)
    assert(!twin, `профили ${twin} и ${key} совпадают полностью`)
    seen.set(fingerprint, key)
  }
  assertEqual(seen.size, Object.keys(SEO_PROFILES).length, 'различных профилей')
})

// --- Владение страницами произведений в четвёрке кинотеатров ----------------

const QUARTET = ['series_hub', 'film_library', 'premiere_radar', 'curated_guide'] as const

await check('в четвёрке кинотеатров одно произведение принадлежит ровно одному сайту', () => {
  // Перебираем всё пространство: форма × состояние. Ни одна пара не должна
  // индексироваться двумя сайтами сразу и ни одна вышедшая работа не должна
  // остаться вовсе без владельца.
  for (const kind of ALL_KINDS) {
    for (const state of ALL_STATES) {
      const owners = QUARTET.filter((key) => ownsTitle(SEO_PROFILES[key], { kind, releaseState: state }))
      assert(owners.length <= 1, `${kind}/${state}: владельцев ${owners.length} (${owners.join(', ')})`)
      if (state === 'released' || UPCOMING_STATES.includes(state as never)) {
        assertEqual(owners.length, 1, `${kind}/${state}: владелец не найден`)
      }
    }
  }
})

await check('вышедший сериал уходит с сайта премьер к сайту сериалов', () => {
  const upcoming = { kind: 'series', releaseState: 'soon' }
  const released = { kind: 'series', releaseState: 'released' }
  assertEqual(ownsTitle(SEO_PROFILES.premiere_radar, upcoming), true, 'анонс у премьер')
  assertEqual(ownsTitle(SEO_PROFILES.series_hub, upcoming), false, 'анонса нет у сериалов')
  assertEqual(ownsTitle(SEO_PROFILES.premiere_radar, released), false, 'вышедшего нет у премьер')
  assertEqual(ownsTitle(SEO_PROFILES.series_hub, released), true, 'вышедшее у сериалов')
})

await check('вышедший фильм принадлежит сайту фильмов, а не сериалов', () => {
  for (const kind of FILM_KINDS) {
    assertEqual(ownsTitle(SEO_PROFILES.film_library, { kind, releaseState: 'released' }), true, kind)
    assertEqual(ownsTitle(SEO_PROFILES.series_hub, { kind, releaseState: 'released' }), false, kind)
  }
  for (const kind of SERIES_KINDS) {
    assertEqual(ownsTitle(SEO_PROFILES.film_library, { kind, releaseState: 'released' }), false, kind)
  }
})

await check('отменённое произведение не индексирует никто', () => {
  for (const key of QUARTET) {
    for (const kind of ALL_KINDS) {
      assertEqual(ownsTitle(SEO_PROFILES[key], { kind, releaseState: 'cancelled' }), false, `${key}/${kind}`)
    }
  }
})

await check('сайт подборок не индексирует ни одной страницы произведения', () => {
  for (const kind of ALL_KINDS) {
    for (const state of ALL_STATES) {
      assertEqual(ownsTitle(SEO_PROFILES.curated_guide, { kind, releaseState: state }), false, `${kind}/${state}`)
    }
  }
})

await check('посадочные страницы фильтров индексируются только по списку', () => {
  const films = SEO_PROFILES.film_library
  assert(films.indexableFacets.length > 0, 'список посадочных страниц пуст')
  for (const path of films.indexableFacets) {
    assertEqual(ownsFacet(films, path), true, path)
  }
  // Произвольная комбинация — не посадочная страница, а ловушка обхода.
  for (const path of ['/films/genre/drama/year/2024/', '/films/genre/unknown/', '/films/year/1999/']) {
    assertEqual(ownsFacet(films, path), false, path)
  }
  for (const key of ['series_hub', 'premiere_radar', 'curated_guide'] as const) {
    assertEqual(SEO_PROFILES[key].indexableFacets.length, 0, `${key}: посадочных страниц быть не должно`)
  }
})

await check('каждый раздел-список четвёрки принадлежит ровно одному сайту', () => {
  const owners = new Map<string, string[]>()
  for (const key of QUARTET) {
    for (const listing of SEO_PROFILES[key].ownedListings) {
      owners.set(listing, [...(owners.get(listing) ?? []), key])
    }
  }
  assertEqual((owners.get('/series/') ?? []).join(','), 'series_hub', 'сериалы')
  assertEqual((owners.get('/films/') ?? []).join(','), 'film_library', 'фильмы')
  assertEqual((owners.get('/calendar/') ?? []).join(','), 'premiere_radar', 'календарь')
  assertEqual((owners.get('/collections/') ?? []).join(','), 'curated_guide', 'подборки')
  assertEqual((owners.get('/news/') ?? []).length, 4, 'лента есть у каждого')
})

await check('внутри группы сайтов раздел-список принадлежит одному сайту, кроме ленты', () => {
  // Сравнение имеет смысл внутри группы: аниме-тройка и четвёрка кинотеатров
  // не конкурируют между собой, а вот два сайта одной группы с общим разделом —
  // это дубль. Ожидаемый состав владельцев задан явно, чтобы смена владения не
  // прошла молча.
  const expected: Record<string, Record<string, string[]>> = {
    'anime-trio': {
      '/catalog/': ['catalog_authority'],
      '/schedule/': ['release_pulse'],
      '/collections/': ['catalog_authority', 'editorial_guide'],
      '/news/': ['catalog_authority', 'release_pulse', 'editorial_guide'],
    },
    'cinema-quartet': {
      '/series/': ['series_hub'],
      '/films/': ['film_library'],
      '/calendar/': ['premiere_radar'],
      '/collections/': ['curated_guide'],
      '/news/': ['series_hub', 'film_library', 'premiere_radar', 'curated_guide'],
    },
  }

  for (const [group, keys] of Object.entries(PROFILE_GROUPS)) {
    const owners = new Map<string, string[]>()
    for (const key of keys) {
      for (const listing of SEO_PROFILES[key].ownedListings) {
        owners.set(listing, [...(owners.get(listing) ?? []), key])
      }
    }
    const actual = Object.fromEntries([...owners].map(([listing, list]) => [listing, [...list].sort()]))
    const wanted = Object.fromEntries(
      Object.entries(expected[group]!).map(([listing, list]) => [listing, [...list].sort()]),
    )
    assertEqual(JSON.stringify(actual, Object.keys(actual).sort()),
      JSON.stringify(wanted, Object.keys(wanted).sort()),
      `состав владельцев разделов группы ${group}`)
  }
})

await check('заголовок ленты материалов свой у каждого сайта', () => {
  const headings = Object.values(SEO_PROFILES).map((profile) => profile.newsHeading)
  assertEqual(new Set(headings).size, Object.keys(SEO_PROFILES).length, 'различных заголовков ленты')
})

// --- Поведение сборки метаданных, а не только таблица ------------------------

const TENANT = {
  id: 1,
  slug: 'site-a',
  domain: 'site-a.example',
  seoProfile: 'catalog_authority',
  indexingEnabled: true,
} as never

await check('canonical индексируемой страницы абсолютный и на своём домене', () => {
  const resolved = resolveSeo(
    { tenant: TENANT, pageType: 'title', path: '/catalog/example/', heading: 'Пример' },
    'Сайт A',
  )
  assert(resolved.indexable, 'страница должна быть индексируемой')
  assert(resolved.canonical !== null, 'canonical отсутствует')
  // Относительный canonical — это не «почти то же самое»: он не сообщает
  // поисковой системе домен и на другом хосте укажет на другой сайт.
  assert(
    resolved.canonical!.startsWith('https://site-a.example/'),
    `canonical обязан быть абсолютным и на своём домене, получено: ${resolved.canonical}`,
  )
  assertEqual(resolved.canonical, 'https://site-a.example/catalog/example/', 'canonical')
})

await check('страница поиска не получает canonical и не индексируется', () => {
  const resolved = resolveSeo(
    { tenant: TENANT, pageType: 'search', path: '/search/', heading: 'Поиск' },
    'Сайт A',
  )
  assertEqual(resolved.indexable, false, 'индексируемость')
  assertEqual(String(resolved.canonical), 'null', 'canonical')
})

// --- Состав карты сайта ------------------------------------------------------

await check('материал без собственного текста в карту сайта не попадает', () => {
  const editorial = SEO_PROFILES.editorial_guide
  assert(editorial.requiresOwnText.includes('title'), 'профиль обязан требовать собственный текст')
  assertEqual(inSitemap(editorial, 'title', { editorialIntro: '' }), false, 'пустой текст')
  assertEqual(inSitemap(editorial, 'title', {}), false, 'поля нет вовсе')
  assertEqual(inSitemap(editorial, 'title', { editorialIntro: '   ' }), false, 'только пробелы')
  assertEqual(inSitemap(editorial, 'title', { editorialIntro: 'Разбор редакции.' }), true, 'текст есть')
})

await check('профиль, не требующий собственного текста, публикует карточку и без него', () => {
  const catalog = SEO_PROFILES.catalog_authority
  assert(!catalog.requiresOwnText.includes('title'), 'у каталога свой текст не обязателен')
  assertEqual(inSitemap(catalog, 'title', {}), true, 'карточка каталога')
})

await check('тип, не объявленный в карте профиля, в неё не попадает', () => {
  const pulse = SEO_PROFILES.release_pulse
  assert(!pulse.sitemapTypes.includes('collection'), 'подборки не входят в карту этого сайта')
  assertEqual(inSitemap(pulse, 'collection', { intro: 'Текст.' }), false, 'подборка')
})

await check('сезон попадает в карту только с заметкой сайта о нём', () => {
  const catalog = SEO_PROFILES.catalog_authority
  const withNote = { seasonNotes: [{ season: 2, note: 'Заметка о втором сезоне.' }] }
  assertEqual(seasonNote(withNote, 2), 'Заметка о втором сезоне.', 'чтение заметки')
  assertEqual(String(seasonNote(withNote, 1)), 'null', 'заметки о первом сезоне нет')
  assertEqual(seasonInSitemap(catalog, withNote, 2), true, 'сезон с заметкой')
  assertEqual(seasonInSitemap(catalog, withNote, 1), false, 'сезон без заметки')
  assertEqual(seasonInSitemap(SEO_PROFILES.release_pulse, withNote, 2), false, 'чужой профиль')
})

await check('страницу серии внутри группы индексирует ровно один сайт', () => {
  // Страница серии состоит из фактов провайдера: два владельца в одной группе —
  // это два дословных дубля, что и показали ворота уникальности в CR v2.0.
  const expected: Record<string, string> = {
    'anime-trio': 'catalog_authority',
    'cinema-quartet': 'series_hub',
  }
  for (const [group, keys] of Object.entries(PROFILE_GROUPS)) {
    const owners = keys.filter((key) => SEO_PROFILES[key].indexable.episode)
    assertEqual(owners.join(','), expected[group]!, `владелец страниц серий группы ${group}`)
  }
  for (const [key, profile] of Object.entries(SEO_PROFILES)) {
    if (profile.indexable.episode) continue
    assert(!profile.sitemapTypes.includes('episode'), `${key}: серии не индексируются, но объявлены в карте`)
  }
})

await check('каждый профиль отнесён ровно к одной группе сайтов', () => {
  const assigned = Object.values(PROFILE_GROUPS).flat()
  assertEqual(assigned.length, new Set(assigned).size, 'профиль не может быть в двух группах')
  assertEqual([...assigned].sort().join(','), Object.keys(SEO_PROFILES).sort().join(','),
    'состав профилей и состав групп разошлись')
})

await check('автоматические описания и заголовки различаются у всех профилей', () => {
  const profiles = Object.values(SEO_PROFILES)
  for (const [field, values] of Object.entries({
    newsSummary: profiles.map((profile) => profile.newsSummary),
    collectionsHeading: profiles.map((profile) => profile.collectionsHeading),
    collectionsSummary: profiles.map((profile) => profile.collectionsSummary),
    episodeSummary: profiles.map((profile) => profile.episodeSummary('Тайтл', 1, 2)),
    titleHeading: profiles.map((profile) => profile.titleHeading('Тайтл')),
  })) {
    assertEqual(new Set(values).size, Object.keys(SEO_PROFILES).length, `различных значений ${field}`)
  }
})

process.exit(summary())
