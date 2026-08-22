/** Изменение данных после бэкапа: нужно, чтобы восстановление было чем проверить. */
import { getPayload } from 'payload'

import config from '../src/payload.config'

const payload = await getPayload({ config })
const tenants = await payload.find({ collection: 'tenants', limit: 1, depth: 0, overrideAccess: true })
if (tenants.docs.length === 0) {
  console.error('BLOCKED_INPUT: в базе нет ни одного сайта')
  process.exit(2)
}

const created = await payload.create({
  collection: 'posts',
  overrideAccess: true,
  data: {
    tenant: tenants.docs[0]!.id,
    headline: 'Запись, внесённая после бэкапа',
    slug: `restore-proof-${Date.now()}`,
    body: 'Эта запись должна исчезнуть после восстановления из бэкапа.',
    _status: 'published',
  } as never,
})

console.log(JSON.stringify({ createdPostId: created.id }))
await payload.db.destroy?.()
process.exit(0)
