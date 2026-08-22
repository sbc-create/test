/** Модульные проверки правил приёма комментариев. */
import {
  MIN_FILL_SECONDS,
  countLinks,
  fingerprint,
  isRejection,
  sanitizeBody,
  signFormToken,
  validateSubmission,
  verifyFormToken,
} from '../src/comments/policy'
import { assert, assertEqual, check, summary } from './harness'

const SECRET = 'test-secret-value'
const limits = { maxLength: 100, allowGuests: true, authenticated: false, commentsEnabled: true }

await check('разметка вырезается, а не экранируется', () => {
  const cleaned = sanitizeBody('<script>alert(1)</script>привет')
  assert(!cleaned.includes('<'), `в тексте осталась разметка: ${cleaned}`)
  assert(cleaned.includes('привет'), 'текст потерян')
})

await check('переводы строк сжимаются, пробелы нормализуются', () => {
  assertEqual(sanitizeBody('а\n\n\n\nб'), 'а\n\nб', 'переводы строк')
  assertEqual(sanitizeBody('  а   б  '), 'а б', 'пробелы')
})

await check('ссылки считаются', () => {
  assertEqual(countLinks('http://a.ru и https://b.ru и www.c.ru'), 3, 'счётчик ссылок')
})

await check('пустой комментарий и слишком длинный отклоняются', () => {
  assert(isRejection(validateSubmission({ body: ' ', guestName: 'Имя' }, limits)), 'пустой принят')
  assert(
    isRejection(validateSubmission({ body: 'я'.repeat(101), guestName: 'Имя' }, limits)),
    'слишком длинный принят',
  )
})

await check('ловушка отклоняет заполненное скрытое поле', () => {
  const result = validateSubmission({ body: 'нормальный текст', guestName: 'Имя', honeypot: 'x' }, limits)
  assert(isRejection(result) && result.code === 'HONEYPOT', 'ловушка не сработала')
})

await check('спам-ссылки отклоняются', () => {
  const result = validateSubmission(
    { body: 'http://a.ru http://b.ru http://c.ru', guestName: 'Имя' },
    limits,
  )
  assert(isRejection(result) && result.code === 'TOO_MANY_LINKS', 'ссылки пропущены')
})

await check('гостевые комментарии отключаются настройкой сайта', () => {
  const result = validateSubmission({ body: 'текст', guestName: 'Имя' }, { ...limits, allowGuests: false })
  assert(isRejection(result) && result.code === 'GUESTS_DISABLED', 'гость прошёл при запрете')
})

await check('глубина ветки ограничена', () => {
  const result = validateSubmission({ body: 'текст', guestName: 'Имя', parentDepth: 3 }, limits)
  assert(isRejection(result) && result.code === 'TOO_DEEP', 'глубина не ограничена')
})

await check('корректная отправка принимается', () => {
  const result = validateSubmission({ body: 'нормальный текст', guestName: 'Имя' }, limits)
  assert(!isRejection(result), 'корректная отправка отклонена')
})

await check('подпись формы проверяется', () => {
  const now = 1_000_000
  const token = signFormToken(SECRET, { tenant: '1', target: 'title:5', issuedAt: now })
  const good = verifyFormToken(SECRET, token, { tenant: '1', target: 'title:5' }, now + MIN_FILL_SECONDS)
  assert(!isRejection(good), 'корректный токен отклонён')

  const wrongSecret = verifyFormToken('other', token, { tenant: '1', target: 'title:5' }, now + 10)
  assert(isRejection(wrongSecret), 'токен принят с чужим секретом')

  const wrongTarget = verifyFormToken(SECRET, token, { tenant: '1', target: 'title:6' }, now + 10)
  assert(isRejection(wrongTarget), 'токен принят для другой страницы')

  const wrongTenant = verifyFormToken(SECRET, token, { tenant: '2', target: 'title:5' }, now + 10)
  assert(isRejection(wrongTenant), 'токен принят для другого сайта')

  const tooFast = verifyFormToken(SECRET, token, { tenant: '1', target: 'title:5' }, now + 1)
  assert(isRejection(tooFast) && tooFast.code === 'TOO_FAST', 'мгновенная отправка принята')

  const expired = verifyFormToken(SECRET, token, { tenant: '1', target: 'title:5' }, now + 100_000)
  assert(isRejection(expired) && expired.code === 'TOKEN_EXPIRED', 'просроченный токен принят')
})

await check('подделанная подпись той же длины не проходит', () => {
  const now = 1_000_000
  const token = signFormToken(SECRET, { tenant: '1', target: 'title:5', issuedAt: now })
  const parts = token.split('.')
  const forged = [...parts.slice(0, 3), 'a'.repeat(parts[3]!.length)].join('.')
  assert(isRejection(verifyFormToken(SECRET, forged, { tenant: '1', target: 'title:5' }, now + 10)),
    'подделка принята')
})

await check('отпечаток отправителя не содержит IP', () => {
  const value = fingerprint(SECRET, '203.0.113.7', 'Mozilla/5.0')
  assert(!value.includes('203.0.113'), 'IP попал в отпечаток')
  assertEqual(value, fingerprint(SECRET, '203.0.113.7', 'Mozilla/5.0'), 'отпечаток нестабилен')
  assert(value !== fingerprint(SECRET, '198.51.100.2', 'Mozilla/5.0'), 'отпечаток не различает отправителей')
})

process.exit(summary())
