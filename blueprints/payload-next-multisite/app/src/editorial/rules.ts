/**
 * Правила редакционного прохода — чистыми функциями.
 *
 * В маршруте или скрипте эти условия проверялись бы только живым прогоном на
 * подходящих данных, а такие данные на стенде появляются не каждый день:
 * «действий 0» одинаково выглядит и когда всё в порядке, и когда правило
 * сломано. Здесь они проверяются напрямую и мутационно.
 */

export const UPCOMING = ['announced', 'date_unknown', 'soon', 'delayed'] as const

export type TitleRecord = {
  id?: string | number
  primaryName?: unknown
  releaseState?: unknown
  releaseDate?: unknown
  releaseDateConfirmed?: unknown
  updatedAt?: unknown
}

export type EditorialAction = {
  action: 'release_state_transition' | 'stale_announcement'
  from: string
  to?: string
  reason: string
}

/** Ценность действия: чем выше, тем раньше его брать в работу. */
export const OPPORTUNITY: Record<string, number> = {
  release_state_transition: 100,
  stale_announcement: 60,
  missing_own_text: 30,
}

const asDate = (value: unknown): Date | null => {
  if (!value) return null
  const date = new Date(String(value))
  return Number.isNaN(date.getTime()) ? null : date
}

/**
 * Что контур сделал бы с этим произведением прямо сейчас.
 *
 * Возвращает одно действие или `null`. Порядок важен: вышедшее сначала
 * переезжает к профильному сайту и только потом может считаться просроченным —
 * иначе произведение с наступившей датой пометили бы мусором.
 */
export const decideForTitle = (
  record: TitleRecord,
  now: Date,
  staleDays: number,
): EditorialAction | null => {
  const state = String(record.releaseState ?? 'released')
  if (!UPCOMING.includes(state as (typeof UPCOMING)[number])) return null

  const releaseDate = asDate(record.releaseDate)
  const confirmed = Boolean(record.releaseDateConfirmed)

  // Подтверждённая дата наступила — состояние обязано смениться само, иначе
  // произведение остаётся на сайте премьер и конкурирует с профильным.
  if (releaseDate && confirmed && releaseDate.getTime() <= now.getTime()) {
    return {
      action: 'release_state_transition',
      from: state,
      to: 'released',
      reason: `подтверждённая дата ${releaseDate.toISOString().slice(0, 10)} наступила`,
    }
  }

  // Анонс без даты, который давно не трогали, — не новость, а мусор в индексе.
  // Дата в будущем защищает от снятия: у такого анонса есть смысл.
  if (!releaseDate) {
    const updatedAt = asDate(record.updatedAt)
    if (updatedAt) {
      const ageDays = (now.getTime() - updatedAt.getTime()) / 86_400_000
      if (ageDays > staleDays) {
        return {
          action: 'stale_announcement',
          from: state,
          reason: `анонс без даты не обновлялся ${Math.round(ageDays)} дней (порог ${staleDays})`,
        }
      }
    }
  }

  return null
}

/** Публикация без собственного текста не индексируется и витрине бесполезна. */
export const needsOwnText = (publication: { editorialIntro?: unknown }): boolean =>
  String(publication.editorialIntro ?? '').trim().length === 0
