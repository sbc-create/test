/**
 * Новинки — это недавно ВЫШЕДШЕЕ, а не недавно загруженное.
 *
 * Дефект, который здесь закрыт: блок обновлений главной брал тайтлы запросом
 * с сортировкой `-updatedAt`. `updatedAt` — время последней правки записи в
 * нашей базе, и массовая заливка архива, повторный импорт или правка постера
 * ставили фильм 1960 года первым в «Обновлениях». То же самое измерено на
 * снимке соседнего семейства: в окне 30 суток по дате загрузки лежало 2 973
 * записи, из них 2 473 — выпуски 2015 года и раньше.
 *
 * Правило здесь то же, что в `automation/host/collection_contract.py`, —
 * одно на фабрику, разными словами двух языков:
 *
 *   - дата выхода подтверждается ГОДОМ ВЫХОДА тайтла (`titles.year`);
 *   - анонс (`status: announced`) — будущее, а не новинка;
 *   - неизвестный год новинкой не делает и сегодняшней датой не подменяется:
 *     тайтл остаётся в каталоге, поиске и подборках, но признака новинки не
 *     получает;
 *   - граница считается от сегодня и пересчитывается сама, без зашитого года.
 */
import type { Where } from 'payload'

/** Согласованное окно новинок, в сутках. */
export const NEWNESS_WINDOW_DAYS = 365

/** Левый край окна. Год не зашит: зашитый перестаёт быть правдой 1 января. */
export const newnessBoundary = (days: number = NEWNESS_WINDOW_DAYS, today: Date = new Date()): Date => {
  const boundary = new Date(today.getTime())
  boundary.setUTCDate(boundary.getUTCDate() - days)
  return boundary
}

/** Год, начиная с которого выпуск считается новым. */
export const newnessYear = (days: number = NEWNESS_WINDOW_DAYS, today: Date = new Date()): number =>
  newnessBoundary(days, today).getUTCFullYear()

/**
 * Условие выборки новинок для общего каталога.
 *
 * Применяется в ЗАПРОСЕ, то есть до сортировки, лимита и страницы: отсеяв
 * архив после лимита, блок показал бы лимит неподходящих карточек и ноль
 * подходящих.
 */
export const freshTitlesWhere = (days: number = NEWNESS_WINDOW_DAYS, today: Date = new Date()): Where => ({
  and: [
    { 'title.year': { greater_than_equal: newnessYear(days, today) } },
    // Год не может быть больше текущего: будущий выпуск — это анонс.
    { 'title.year': { less_than_equal: today.getUTCFullYear() } },
    { 'title.status': { not_equals: 'announced' } },
  ],
})

/** Запись-кандидат для проверки в коде (тесты, предпросмотр). */
export type TitleLike = { year?: unknown; status?: unknown }

/** То же правило, но над готовой записью, а не запросом. */
export const isFresh = (title: TitleLike, days: number = NEWNESS_WINDOW_DAYS, today: Date = new Date()): boolean => {
  const year = title?.year
  if (typeof year !== 'number' || !Number.isInteger(year)) return false
  if (title?.status === 'announced') return false
  if (year > today.getUTCFullYear()) return false
  return year >= newnessYear(days, today)
}

/** Будущий релиз. */
export const isAnnouncement = (title: TitleLike, today: Date = new Date()): boolean => {
  if (title?.status === 'announced') return true
  const year = title?.year
  return typeof year === 'number' && Number.isInteger(year) && year > today.getUTCFullYear()
}
