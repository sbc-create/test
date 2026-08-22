/**
 * Матрица индексируемости продублирована в TypeScript ради типов. Дубликат без
 * сверки — источник тихого дрейфа политики, поэтому здесь он сверяется с
 * замороженным YAML фабрики построчно.
 */
import { readFileSync } from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

import { load } from 'js-yaml'

import { MATRIX_POLICY_VERSION, NON_INDEXABLE_PARAMS, PAGE_TYPES, type PageTypeId } from '../src/seo/matrix'
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
  })
}

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
  assertEqual((owners.get('/news/') ?? []).length, 3, 'владельцы ленты материалов')
  const headings = Object.values(SEO_PROFILES).map((profile) => profile.newsHeading)
  assertEqual(new Set(headings).size, 3, 'различных заголовков ленты')
})

process.exit(summary())
