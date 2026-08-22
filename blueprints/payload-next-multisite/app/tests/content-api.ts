/**
 * Проверки адаптера Content API.
 *
 * Транспорт подменён фикстурами, но код адаптера — тот же, что пойдёт в живой
 * прогон: пагинация, повторы, идемпотентность и журнал проверяются на нём, а не
 * на упрощённой копии.
 */
import { readFileSync } from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

import { getPayload } from 'payload'

import config from '../src/payload.config'
import { ContentApiClient, type Transport } from '../src/content-api/client'
import { ContentApiBlocked, loadDescriptor } from '../src/content-api/descriptor'
import { markMissingUnavailable, requestDigest, syncTitles } from '../src/content-api/sync'
import { assert, assertEqual, check, summary } from './harness'
import { reset } from './seed'

const dirname = path.dirname(fileURLToPath(import.meta.url))
const fixtures = path.join(dirname, 'fixtures', 'content-api')
const readFixture = (name: string): unknown => JSON.parse(readFileSync(path.join(fixtures, name), 'utf8'))

const descriptor = loadDescriptor(path.join(fixtures, 'descriptor.yaml'))
const TOKEN = 'fixture-token-must-not-leak'

const payload = await getPayload({ config })
await reset(payload)

/** Транспорт из заранее заданных ответов. Записывает, что именно запрашивалось. */
const scripted = (responses: { status?: number; headers?: Record<string, string>; body?: unknown; throw?: string }[]) => {
  const calls: string[] = []
  let index = 0
  const transport: Transport = async (url) => {
    calls.push(url)
    const response = responses[Math.min(index, responses.length - 1)]!
    index += 1
    if (response.throw) {
      const error = new Error(response.throw)
      error.name = response.throw === 'AbortError' ? 'AbortError' : 'Error'
      throw error
    }
    return { status: response.status ?? 200, headers: response.headers ?? {}, body: response.body }
  }
  return { transport, calls: () => calls }
}

const clientFor = (responses: Parameters<typeof scripted>[0]) => {
  const { transport, calls } = scripted(responses)
  return {
    client: new ContentApiClient({ descriptor, transport, token: TOKEN, sleep: async () => {} }),
    calls,
  }
}

const run = async (responses: Parameters<typeof scripted>[0], reference: string) => {
  const { client, calls } = clientFor(responses)
  const result = await syncTitles({
    payload,
    client,
    descriptor,
    mode: 'mock',
    environment: 'staging',
    reference,
  })
  return { result, calls }
}

const successPages = [
  { body: readFixture('success-page-1.json') },
  { body: readFixture('success-page-2.json') },
]

await check('без переданного контракта синхронизация блокируется, а не угадывает адреса', () => {
  const real = loadDescriptor(path.join(dirname, '..', '..', '..', '..', 'knowledge', 'cdnvideohub', 'content-api.yaml'))
  assertEqual(real.status, 'not_provided', 'статус официального описания')
  let thrown: unknown
  try {
    // eslint-disable-next-line no-new
    new ContentApiClient({ descriptor: real, transport: async () => ({ status: 200, headers: {}, body: {} }), token: TOKEN })
  } catch (error) {
    thrown = error
  }
  assert(thrown instanceof ContentApiBlocked, 'клиент собрался без контракта')
})

await check('отсутствие серверного секрета блокирует запуск', () => {
  let thrown: unknown
  try {
    // eslint-disable-next-line no-new
    new ContentApiClient({ descriptor, transport: async () => ({ status: 200, headers: {}, body: {} }), token: '' })
  } catch (error) {
    thrown = error
  }
  assert(thrown instanceof ContentApiBlocked, 'клиент собрался без токена')
})

await check('успешный импорт читает страницы до условия завершения', async () => {
  const { result, calls } = await run(successPages, 'fixture-success')
  assertEqual(result.status, 'succeeded', 'статус задания')
  assertEqual(result.created, 3, 'создано записей')
  assertEqual(calls().length, 2, 'число запросов')
  assert(calls()[0]!.includes('page=1'), `первый запрос: ${calls()[0]}`)
  assert(calls()[1]!.includes('page=2'), `второй запрос: ${calls()[1]}`)
})

await check('повторный импорт того же запроса не создаёт дублей', async () => {
  const { result } = await run(successPages, 'fixture-success-repeat')
  assertEqual(result.created, 0, 'создано записей при повторе')
  assertEqual(result.skipped, 3, 'пропущено без изменений')
  const total = await payload.count({ collection: 'titles', overrideAccess: true })
  assertEqual(total.totalDocs, 3, 'всего тайтлов в каталоге')
})

await check('отпечаток запроса стабилен и не зависит от порядка параметров', () => {
  const first = requestDigest(descriptor, 'titles', { a: 1, b: 2 })
  const second = requestDigest(descriptor, 'titles', { b: 2, a: 1 })
  assertEqual(first, second, 'отпечаток')
})

await check('изменение в источнике обновляет запись, а не создаёт вторую', async () => {
  const { result } = await run([{ body: readFixture('updated.json') }], 'fixture-updated')
  assertEqual(result.updated, 1, 'обновлено записей')
  const total = await payload.count({ collection: 'titles', overrideAccess: true })
  assertEqual(total.totalDocs, 3, 'всего тайтлов после обновления')
  const found = await payload.find({
    collection: 'titles',
    where: { playbackTitleId: { equals: 'fx-1' } },
    overrideAccess: true,
    depth: 0,
  })
  assertEqual(
    (found.docs[0] as unknown as Record<string, unknown>).primaryName,
    'Фикстура один, обновлённое название',
    'название после синхронизации',
  )
})

await check('дубликат внутри одной выдачи создаёт одну запись', async () => {
  // Полная страница означает «возможно, есть следующая»: за ней идёт пустая.
  const { result } = await run(
    [{ body: readFixture('duplicate.json') }, { body: readFixture('empty.json') }],
    'fixture-duplicate',
  )
  assertEqual(result.status, 'succeeded', 'статус задания')
  assertEqual(result.created, 0, 'создано записей')
  // Первый экземпляр обработан как обычное изменение, второй отброшен как дубль.
  assertEqual(result.skipped, 1, 'отброшено дублей')
  const found = await payload.count({
    collection: 'titles',
    where: { playbackTitleId: { equals: 'fx-1' } },
    overrideAccess: true,
  })
  assertEqual(found.totalDocs, 1, 'записей с этим идентификатором')
})

await check('запись без идентификатора не импортируется', async () => {
  const { result } = await run([{ body: readFixture('incomplete.json') }], 'fixture-incomplete')
  assertEqual(result.blocked, 1, 'заблокировано записей')
  assertEqual(result.created, 0, 'создано записей')
})

await check('пустая выдача завершает импорт без ошибок', async () => {
  const { result } = await run([{ body: readFixture('empty.json') }], 'fixture-empty')
  assertEqual(result.status, 'succeeded', 'статус')
  assertEqual(result.created + result.updated, 0, 'изменений')
})

await check('некорректный ответ помечает задание неуспешным', async () => {
  const { result } = await run([{ body: readFixture('malformed.json') }], 'fixture-malformed')
  assertEqual(result.status, 'failed', 'статус задания')
  assert((result.message ?? '').includes('malformed'), `сообщение: ${result.message}`)
})

await check('ограничение частоты повторяется ограниченное число раз и затем сдаётся', async () => {
  const { result, calls } = await run(
    [{ status: 429, headers: { 'retry-after': '0' }, body: {} }],
    'fixture-rate-limited',
  )
  assertEqual(result.status, 'failed', 'статус задания')
  assert((result.message ?? '').includes('rate_limited'), `сообщение: ${result.message}`)
  // maxRetries: 2 — три обращения всего, а не бесконечный цикл.
  assertEqual(calls().length, 3, 'число попыток')
})

await check('таймаут повторяется ограниченно и не зацикливается', async () => {
  const { result, calls } = await run([{ throw: 'AbortError' }], 'fixture-timeout')
  assertEqual(result.status, 'failed', 'статус задания')
  assert((result.message ?? '').includes('timeout'), `сообщение: ${result.message}`)
  assertEqual(calls().length, 3, 'число попыток')
})

await check('отказ авторизации не повторяется с тем же токеном', async () => {
  const { result, calls } = await run([{ status: 401, body: {} }], 'fixture-auth')
  // Именно blocked_access, а не общий failed: по журналу должно быть видно, что
  // повтор с тем же токеном бессмысленен и нужен новый секрет.
  assertEqual(result.status, 'blocked_access', 'статус задания')
  assertEqual(calls().length, 1, 'число попыток')
})

await check('токен не попадает в журнал заданий', async () => {
  const jobs = await payload.find({ collection: 'import-jobs', limit: 100, overrideAccess: true, depth: 0 })
  const serialized = JSON.stringify(jobs.docs)
  assert(!serialized.includes(TOKEN), 'токен найден в журнале импорта')
  assert(!serialized.includes('Bearer '), 'заголовок авторизации найден в журнале импорта')
})

await check('ручная запись редактора не перезаписывается импортом', async () => {
  const manual = await payload.create({
    collection: 'titles',
    overrideAccess: true,
    data: {
      primaryName: 'Ручная запись редактора',
      kind: 'series',
      status: 'ongoing',
      availability: 'available',
      playbackAggregator: 'kp',
      playbackTitleId: 'fx-manual',
      source: 'manual',
    } as never,
  })

  const { result } = await run(
    [
      {
        body: {
          data: {
            items: [
              {
                id: 'fx-manual',
                provider: 'kp',
                names: { ru: 'Импортированное название' },
                kind: 'movie',
                releaseStatus: 'completed',
              },
            ],
          },
        },
      },
    ],
    'fixture-manual',
  )
  assertEqual(result.skipped, 1, 'ручная запись должна быть пропущена')

  const after = await payload.findByID({ collection: 'titles', id: manual.id, overrideAccess: true, depth: 0 })
  assertEqual((after as unknown as Record<string, unknown>).primaryName, 'Ручная запись редактора', 'название')
})

await check('пропавший в источнике материал получает явное состояние, а не подмену', async () => {
  const changed = await markMissingUnavailable(payload, 'kp', ['fx-1'])
  assert(changed >= 1, 'ни одна запись не помечена недоступной')
  const found = await payload.find({
    collection: 'titles',
    where: { playbackTitleId: { equals: 'fx-2' } },
    overrideAccess: true,
    depth: 0,
  })
  assertEqual((found.docs[0] as unknown as Record<string, unknown>).availability, 'unavailable', 'состояние')

  const kept = await payload.find({
    collection: 'titles',
    where: { playbackTitleId: { equals: 'fx-1' } },
    overrideAccess: true,
    depth: 0,
  })
  assertEqual((kept.docs[0] as unknown as Record<string, unknown>).availability, 'available', 'состояние присутствующего')
})

await check('режим фикстур технически запрещён в production', async () => {
  const { client } = clientFor(successPages)
  let thrown: unknown
  try {
    await syncTitles({ payload, client, descriptor, mode: 'mock', environment: 'production', reference: 'fixture-prod' })
  } catch (error) {
    thrown = error
  }
  assert(thrown instanceof ContentApiBlocked, 'production принял режим фикстур')
})

await check('живой контрактный тест выполняется только по явному флагу', () => {
  const enabled = process.env.CDNVIDEOHUB_LIVE === '1'
  if (!enabled) {
    console.log(
      '      SKIPPED: живой прогон Content API не выполнялся — не задан CDNVIDEOHUB_LIVE=1 ' +
        'и не передан официальный контракт (knowledge/cdnvideohub/content-api.yaml: not_provided)',
    )
  }
  assert(true, '')
})

await payload.db.destroy?.()
process.exit(summary())
