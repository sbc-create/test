/**
 * Правило новинок Next-шаблона — исполнением, а не разбором текста.
 *
 * Запускается без установленных зависимостей и без базы:
 *
 *   node --experimental-strip-types tests/newness.test.mts
 *
 * Это важно: обязательный прогон репозитория поднять Payload не может, и
 * правило осталось бы проверенным только на уровне исходника. Перечисленные
 * ниже случаи — те самые, из-за которых дефект возник.
 */
import assert from 'node:assert/strict'
import {
  NEWNESS_WINDOW_DAYS,
  freshTitlesWhere,
  isAnnouncement,
  isFresh,
  newnessBoundary,
  newnessYear,
} from '../src/lib/newness.ts'

const СЕГОДНЯ = new Date(Date.UTC(2026, 9, 1)) // 2026-10-01
let провалов = 0
const проверка = (имя: string, тело: () => void) => {
  try {
    тело()
    console.log(`PASS  ${имя}`)
  } catch (e) {
    провалов += 1
    console.log(`FAIL  ${имя}: ${(e as Error).message}`)
  }
}

проверка('окно по умолчанию 365 суток', () => {
  assert.equal(NEWNESS_WINDOW_DAYS, 365)
})

проверка('граница считается от сегодня, год не зашит', () => {
  assert.equal(newnessBoundary(365, СЕГОДНЯ).toISOString().slice(0, 10), '2025-10-01')
  assert.equal(newnessYear(365, СЕГОДНЯ), 2025)
  assert.equal(newnessYear(365, new Date(Date.UTC(2031, 2, 4))), 2030)
})

проверка('фильм 1960 года не новинка, чем бы его ни загрузили', () => {
  assert.equal(isFresh({ year: 1960, status: 'completed' }, 365, СЕГОДНЯ), false)
})

проверка('свежий выпуск — новинка', () => {
  assert.equal(isFresh({ year: 2026, status: 'completed' }, 365, СЕГОДНЯ), true)
  assert.equal(isFresh({ year: 2025, status: 'ongoing' }, 365, СЕГОДНЯ), true)
})

проверка('неизвестный год не становится сегодняшним', () => {
  assert.equal(isFresh({}, 365, СЕГОДНЯ), false)
  assert.equal(isFresh({ year: null }, 365, СЕГОДНЯ), false)
  assert.equal(isFresh({ year: '2026' }, 365, СЕГОДНЯ), false)
})

проверка('будущий выпуск и анонс — не новинки', () => {
  assert.equal(isFresh({ year: 2027 }, 365, СЕГОДНЯ), false)
  assert.equal(isAnnouncement({ year: 2027 }, СЕГОДНЯ), true)
  assert.equal(isFresh({ year: 2026, status: 'announced' }, 365, СЕГОДНЯ), false)
  assert.equal(isAnnouncement({ year: 2026, status: 'announced' }, СЕГОДНЯ), true)
  assert.equal(isAnnouncement({ year: 2026, status: 'completed' }, СЕГОДНЯ), false)
})

проверка('условие запроса спрашивает год, а не дату правки', () => {
  const where = freshTitlesWhere(365, СЕГОДНЯ)
  const текст = JSON.stringify(where)
  assert.ok(текст.includes('title.year'), 'в условии нет года выхода')
  assert.ok(текст.includes('2025'), 'в условии нет границы окна')
  assert.ok(!/updatedAt|createdAt/.test(текст), 'в условии дата правки записи')
  assert.ok(текст.includes('announced'), 'анонсы не исключены')
})

console.log(провалов ? `провалов ${провалов}` : 'провалов 0')
process.exit(провалов ? 1 : 0)
