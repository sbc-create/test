import type { PageTypeId } from './matrix'
import { ownsTitle, type SeoProfile } from './profiles'

/**
 * Правила попадания документа в карту сайта — отдельно от маршрута.
 *
 * В маршруте эти условия проверялись бы только живым прогоном всего сайта,
 * а карта, содержащая noindex-страницы, — это ровно тот дефект, который
 * незаметен глазами и виден поисковой системе.
 */

/** Поле, в котором лежит собственный текст сайта для этого типа страницы. */
const OWN_TEXT_FIELD: Partial<Record<PageTypeId, string>> = {
  title: 'editorialIntro',
  collection: 'intro',
  article: 'body',
}

export const hasOwnText = (value: unknown): boolean =>
  typeof value === 'string' && value.trim().length > 0

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : null

/** Заметка редакции сайта о конкретном сезоне, если она написана. */
export const seasonNote = (doc: unknown, season: number): string | null => {
  const notes = asRecord(doc)?.seasonNotes
  if (!Array.isArray(notes)) return null
  const found = notes.map(asRecord).find((item) => item && Number(item.season) === season)
  const note = found?.note
  return typeof note === 'string' && note.trim() ? note.trim() : null
}

/**
 * Документ попадает в карту сайта, только если профиль этот тип индексирует,
 * объявил его в составе карты и документ несёт собственный текст там, где
 * профиль его требует.
 */
export const inSitemap = (
  profile: SeoProfile,
  type: PageTypeId,
  record: Record<string, unknown>,
): boolean => {
  if (!profile.sitemapTypes.includes(type)) return false
  if (!profile.indexable[type]) return false
  if (!profile.requiresOwnText.includes(type)) return true
  const field = OWN_TEXT_FIELD[type]
  return field ? hasOwnText(record[field]) : true
}

/** Страница сезона попадает в карту только с собственной заметкой сайта. */
export const seasonInSitemap = (profile: SeoProfile, doc: unknown, season: number): boolean =>
  profile.sitemapTypes.includes('season')
  && Boolean(profile.indexable.season)
  && seasonNote(doc, season) !== null


/**
 * Страница произведения попадает в карту сайта, только если этот сайт её
 * индексирует: карта, перечисляющая noindex-страницы, вводит в заблуждение
 * поисковую систему и прячет настоящую проблему за зелёным отчётом.
 */
export const titleInSitemap = (
  profile: SeoProfile,
  record: Record<string, unknown>,
  shared: { kind?: unknown; releaseState?: unknown } | null | undefined,
): boolean => inSitemap(profile, 'title', record) && ownsTitle(profile, shared)
