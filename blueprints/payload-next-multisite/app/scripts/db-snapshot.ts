/**
 * Снимок состояния базы для доказательства восстановления.
 *
 * Одних счётчиков мало: восстановление, вернувшее нужное число записей с
 * испорченным содержимым или перепутанной привязкой к сайту, выглядело бы
 * успешным. Поэтому рядом со счётчиком считается отпечаток значимых полей.
 */
import { createHash } from 'crypto'

import { getPayload } from 'payload'

import config from '../src/payload.config'

const payload = await getPayload({ config })

const collections = {
  tenants: ['slug', 'domain', 'seoProfile', 'theme', 'indexingEnabled'],
  titles: ['primaryName', 'kind', 'status', 'year', 'playbackAggregator', 'playbackTitleId', 'availability'],
  seasons: ['number', 'name'],
  episodes: ['number', 'name', 'playbackAvailable'],
  posts: ['tenant', 'headline', 'slug', '_status'],
  pages: ['tenant', 'name', 'slug', '_status'],
  comments: ['tenant', 'targetType', 'targetId', 'status', 'body'],
  'tenant-titles': ['tenant', 'slug', 'editorialIntro', '_status'],
  'editorial-collections': ['tenant', 'slug', 'name', '_status'],
  users: ['email', 'role'],
} as const

const idOf = (value: unknown): string =>
  value && typeof value === 'object' && 'id' in (value as Record<string, unknown>)
    ? String((value as { id: unknown }).id)
    : String(value ?? '')

const snapshot: Record<string, unknown> = {}
for (const [collection, fields] of Object.entries(collections)) {
  const result = await payload.find({
    collection: collection as never,
    limit: 5000,
    depth: 0,
    sort: 'id',
    overrideAccess: true,
    draft: true,
  })
  const digest = createHash('sha256')
  for (const doc of result.docs) {
    const record = doc as unknown as Record<string, unknown>
    digest.update(String(record.id))
    for (const field of fields) digest.update('|' + idOf(record[field]))
    digest.update('\n')
  }
  snapshot[collection] = result.totalDocs
  snapshot[`${collection}:digest`] = digest.digest('hex').slice(0, 16)
}

console.log(JSON.stringify(snapshot))
await payload.db.destroy?.()
process.exit(0)
