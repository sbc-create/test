/** Снимок состояния базы для доказательства восстановления. Только счётчики. */
import { getPayload } from 'payload'

import config from '../src/payload.config'

const payload = await getPayload({ config })
const collections = ['tenants', 'titles', 'seasons', 'episodes', 'posts', 'pages', 'comments',
  'tenant-titles', 'editorial-collections', 'users'] as const

const snapshot: Record<string, number> = {}
for (const collection of collections) {
  const result = await payload.count({ collection, overrideAccess: true })
  snapshot[collection] = result.totalDocs
}

console.log(JSON.stringify(snapshot))
await payload.db.destroy?.()
process.exit(0)
