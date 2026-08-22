/**
 * Синхронизация схемы отдельным шагом выката.
 *
 * Раньше схему обновлял сам факт запуска процесса: кандидат менял её под
 * работающим релизом, а откат возвращал старую схему и удалял колонки новой.
 * Теперь это явный шаг, который выполняется после бэкапа и виден в плане, в
 * журнале и в отчёте задания.
 */
import { getPayload } from 'payload'

import config from '../src/payload.config'

if (process.env.PAYLOAD_DB_PUSH !== 'true') {
  console.error('BLOCKED_INPUT: миграция запущена без разрешения на изменение схемы')
  process.exit(2)
}

const payload = await getPayload({ config })
const result: any = await payload.db.drizzle.execute(
  "select count(*)::int as tables from information_schema.tables where table_schema = 'public'",
)
const rows = result.rows ?? result
console.log(JSON.stringify({ schema: 'synchronised', tables: rows[0]?.tables ?? null }))
await payload.db.destroy?.()
process.exit(0)
