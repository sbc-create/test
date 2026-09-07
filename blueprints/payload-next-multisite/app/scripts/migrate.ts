/**
 * Синхронизация схемы отдельным шагом выката.
 *
 * Раньше схему обновлял сам факт запуска процесса: кандидат менял её под
 * работающим релизом, а откат возвращал старую схему и удалял колонки новой.
 * Теперь это явный шаг, который выполняется после бэкапа и виден в плане, в
 * журнале и в отчёте задания.
 */
import { getPayload } from 'payload'

if (process.env.PAYLOAD_DB_PUSH !== 'true') {
  console.error('BLOCKED_INPUT: миграция запущена без разрешения на изменение схемы')
  process.exit(2)
}

// Адаптер Postgres выполняет push только вне production-режима Node. Выкат же
// идёт именно в production-режиме, и раньше это молча превращало шаг в пустой:
// схема не создавалась, а шаг всё равно печатал «synchronised». Падал уже
// следующий шаг — стеком drizzle про «relation "tenants" does not exist».
//
// Разрешение на изменение схемы даёт не NODE_ENV, а PAYLOAD_DB_PUSH и бэкап
// перед ним, поэтому режим здесь задаётся явно и только для этого процесса.
const productionMode = process.env.NODE_ENV === 'production'
if (productionMode) {
  // Типы Next объявляют NODE_ENV только для чтения — запись идёт через
  // обычный вид окружения, каким его видит сам процесс.
  ;(process.env as Record<string, string | undefined>).NODE_ENV = 'development'
}

// Конфигурация читается после смены режима: адаптер запоминает его при сборке.
const config = (await import('../src/payload.config')).default
const payload = await getPayload({ config })

const result: any = await payload.db.drizzle.execute(
  "select count(*)::int as tables from information_schema.tables where table_schema = 'public'",
)
const rows = result.rows ?? result
const tables: number | null = rows[0]?.tables ?? null

// Пустая схема после push — это провал шага, а не «синхронизировано».
// Право напечатать отчёт о синхронизации даёт только наличие таблиц.
if (!tables) {
  const hint = productionMode ? ' (шаг запускался в production-режиме Node)' : ''
  console.error(`DEPLOY_FAILED: схема не синхронизирована — после push в базе нет таблиц${hint}`)
  await payload.db.destroy?.()
  process.exit(1)
}

console.log(JSON.stringify({ schema: 'synchronised', tables, productionMode }))
await payload.db.destroy?.()
process.exit(0)
