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

// Не только вставка: восстановление обязано отменить и правку, и удаление.
const existing = await payload.find({
  collection: 'pages', limit: 1, depth: 0, overrideAccess: true, draft: true,
})
let updatedPageId: string | number | null = null
if (existing.docs.length > 0) {
  updatedPageId = existing.docs[0]!.id
  await payload.update({
    collection: 'pages', id: updatedPageId, overrideAccess: true,
    data: { body: 'Текст, изменённый после бэкапа.' } as never,
  })
}

const comments = await payload.find({
  collection: 'comments', limit: 1, depth: 0, overrideAccess: true,
})
let deletedCommentId: string | number | null = null
if (comments.docs.length > 0) {
  deletedCommentId = comments.docs[0]!.id
  await payload.delete({ collection: 'comments', id: deletedCommentId, overrideAccess: true })
}

console.log(JSON.stringify({ createdPostId: created.id, updatedPageId, deletedCommentId }))
await payload.db.destroy?.()
process.exit(0)
