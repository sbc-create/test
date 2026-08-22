/**
 * Правила редакционного контура проверяются на данных, которых на стенде может
 * не быть в нужный день. «Действий 0» одинаково выглядит и когда всё в порядке,
 * и когда правило сломано, поэтому каждое условие проверяется явно.
 */
import { OPPORTUNITY, decideForTitle, needsOwnText } from '../src/editorial/rules'
import { assert, assertEqual, check, summary } from './harness'

const NOW = new Date('2026-08-22T12:00:00.000Z')
const STALE = 180

await check('вышедшее по подтверждённой дате переходит в состояние «вышло»', () => {
  const decision = decideForTitle({
    releaseState: 'soon',
    releaseDate: '2026-08-21T00:00:00.000Z',
    releaseDateConfirmed: true,
  }, NOW, STALE)
  assert(decision !== null, 'решение не принято')
  assertEqual(decision!.action, 'release_state_transition', 'действие')
  assertEqual(decision!.to, 'released', 'целевое состояние')
})

await check('дата в будущем не переводит произведение в «вышло»', () => {
  const decision = decideForTitle({
    releaseState: 'soon',
    releaseDate: '2026-12-01T00:00:00.000Z',
    releaseDateConfirmed: true,
  }, NOW, STALE)
  assertEqual(String(decision), 'null', 'решение должно отсутствовать')
})

await check('неподтверждённая дата не переводит произведение в «вышло»', () => {
  // Иначе достаточно было бы вписать любую дату, чтобы страница уехала в индекс
  // профильного сайта как вышедшая.
  const decision = decideForTitle({
    releaseState: 'soon',
    releaseDate: '2026-01-01T00:00:00.000Z',
    releaseDateConfirmed: false,
  }, NOW, STALE)
  assert(decision === null || decision.action !== 'release_state_transition',
    `получено ${JSON.stringify(decision)}`)
})

await check('вышедшее уже произведение контур не трогает', () => {
  const decision = decideForTitle({
    releaseState: 'released',
    releaseDate: '2020-01-01T00:00:00.000Z',
    releaseDateConfirmed: true,
  }, NOW, STALE)
  assertEqual(String(decision), 'null', 'решение должно отсутствовать')
})

await check('просроченный анонс без даты снимается с публикации', () => {
  const decision = decideForTitle({
    releaseState: 'announced',
    releaseDate: null,
    updatedAt: '2025-01-01T00:00:00.000Z',
  }, NOW, STALE)
  assert(decision !== null, 'решение не принято')
  assertEqual(decision!.action, 'stale_announcement', 'действие')
})

await check('свежий анонс без даты не снимается', () => {
  const decision = decideForTitle({
    releaseState: 'announced',
    releaseDate: null,
    updatedAt: '2026-08-01T00:00:00.000Z',
  }, NOW, STALE)
  assertEqual(String(decision), 'null', 'решение должно отсутствовать')
})

await check('анонс с будущей датой не считается просроченным', () => {
  // Дата в будущем — признак живого анонса, сколько бы его ни не редактировали.
  const decision = decideForTitle({
    releaseState: 'announced',
    releaseDate: '2027-05-01T00:00:00.000Z',
    releaseDateConfirmed: true,
    updatedAt: '2024-01-01T00:00:00.000Z',
  }, NOW, STALE)
  assertEqual(String(decision), 'null', 'решение должно отсутствовать')
})

await check('перенос обрабатывается как ещё не вышедшее', () => {
  const decision = decideForTitle({
    releaseState: 'delayed',
    releaseDate: '2026-08-20T00:00:00.000Z',
    releaseDateConfirmed: true,
  }, NOW, STALE)
  assertEqual(decision!.action, 'release_state_transition', 'перенос с наступившей датой')
})

await check('отменённое произведение контур не воскрешает', () => {
  const decision = decideForTitle({
    releaseState: 'cancelled',
    releaseDate: '2026-01-01T00:00:00.000Z',
    releaseDateConfirmed: true,
  }, NOW, STALE)
  assertEqual(String(decision), 'null', 'отменённое остаётся отменённым')
})

await check('публикация без собственного текста попадает в отчёт', () => {
  assertEqual(needsOwnText({ editorialIntro: '' }), true, 'пустой текст')
  assertEqual(needsOwnText({ editorialIntro: '   ' }), true, 'пробелы')
  assertEqual(needsOwnText({}), true, 'поля нет')
  assertEqual(needsOwnText({ editorialIntro: 'Разбор редакции.' }), false, 'текст есть')
})

await check('срочность действий упорядочена, а не назначена случайно', () => {
  assert(OPPORTUNITY.release_state_transition! > OPPORTUNITY.stale_announcement!,
    'смена состояния срочнее снятия анонса')
  assert(OPPORTUNITY.stale_announcement! > OPPORTUNITY.missing_own_text!,
    'снятие анонса срочнее отсутствия текста')
})

process.exit(summary())
