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
import { SEO_PROFILES, matrixAllowsIndex } from '../src/seo/profiles'
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

await check('три профиля различаются индексируемой поверхностью', () => {
  const surfaces = Object.values(SEO_PROFILES).map((profile) =>
    Object.entries(profile.indexable)
      .filter(([, value]) => value)
      .map(([type]) => type)
      .sort()
      .join(','),
  )
  assertEqual(new Set(surfaces).size, 3, 'различных поверхностей')
})

await check('каждый раздел-список принадлежит ровно одному сайту, кроме ленты материалов', () => {
  const owners = new Map<string, string[]>()
  for (const [key, profile] of Object.entries(SEO_PROFILES)) {
    for (const listing of profile.ownedListings) {
      owners.set(listing, [...(owners.get(listing) ?? []), key])
    }
  }
  assertEqual((owners.get('/catalog/') ?? []).join(','), 'catalog_authority', 'владелец каталога')
  assertEqual((owners.get('/schedule/') ?? []).join(','), 'release_pulse', 'владелец расписания')
  // Лента материалов есть у всех: у каждого сайта она про своё и с разным заголовком.
  // Явный ожидаемый состав владельцев: иначе смена владения проходит молча.
  const expected: Record<string, number> = {
    '/catalog/': 1, '/schedule/': 1, '/collections/': 2, '/news/': 3,
  }
  for (const [listing, count] of Object.entries(expected)) {
    assertEqual((owners.get(listing) ?? []).length, count, `владельцев раздела ${listing}`)
  }
  assertEqual([...owners.keys()].sort().join(','), Object.keys(expected).sort().join(','),
    'состав разделов-списков')
  const headings = Object.values(SEO_PROFILES).map((profile) => profile.newsHeading)
  assertEqual(new Set(headings).size, 3, 'различных заголовков ленты')
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

await check('страницу серии индексирует ровно один профиль', () => {
  const owners = Object.entries(SEO_PROFILES)
    .filter(([, profile]) => profile.indexable.episode)
    .map(([key]) => key)
  // Страница серии состоит из фактов провайдера: два владельца — это два
  // дословных дубля на разных доменах, что и показали ворота уникальности.
  assertEqual(owners.join(','), 'catalog_authority', 'владелец страниц серий')
  for (const [key, profile] of Object.entries(SEO_PROFILES)) {
    if (profile.indexable.episode) continue
    assert(!profile.sitemapTypes.includes('episode'), `${key}: серии не индексируются, но объявлены в карте`)
  }
})

await check('автоматические описания и заголовки различаются у трёх профилей', () => {
  const profiles = Object.values(SEO_PROFILES)
  for (const [field, values] of Object.entries({
    newsSummary: profiles.map((profile) => profile.newsSummary),
    collectionsHeading: profiles.map((profile) => profile.collectionsHeading),
    collectionsSummary: profiles.map((profile) => profile.collectionsSummary),
    episodeSummary: profiles.map((profile) => profile.episodeSummary('Тайтл', 1, 2)),
    titleHeading: profiles.map((profile) => profile.titleHeading('Тайтл')),
  })) {
    assertEqual(new Set(values).size, 3, `различных значений ${field}`)
  }
})

process.exit(summary())
