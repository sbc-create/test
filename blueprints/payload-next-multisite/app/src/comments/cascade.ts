import type { CollectionBeforeDeleteHook, Payload, PayloadRequest } from 'payload'

import { MAX_DEPTH } from './policy'

type CommentId = string | number

/**
 * Ветка комментария по уровням: сам комментарий, его ответы, ответы на ответы.
 *
 * Глубина ограничена политикой (`MAX_DEPTH`), поэтому обход конечный и не
 * зависит от того, что окажется в данных.
 */
export const commentThreadLevels = async (
  payload: Payload,
  req: PayloadRequest,
  id: CommentId,
): Promise<CommentId[][]> => {
  const levels: CommentId[][] = [[id]]
  const seen = new Set<string>([String(id)])
  for (let level = 0; level < MAX_DEPTH; level += 1) {
    const parents = levels[levels.length - 1]
    if (parents.length === 0) break
    const children = await payload.find({
      collection: 'comments',
      where: { parent: { in: parents } },
      limit: 1000,
      depth: 0,
      pagination: false,
      req,
      overrideAccess: true,
    })
    const next = children.docs
      .map((doc) => doc.id as CommentId)
      .filter((child) => !seen.has(String(child)))
    next.forEach((child) => seen.add(String(child)))
    if (next.length === 0) break
    levels.push(next)
  }
  return levels
}

/**
 * Удаление комментария уносит с собой жалобы и ответы.
 *
 * Без этого удаление в админке падает с 500: ссылка жалобы на комментарий
 * обязательна, а адаптер обнуляет её при удалении. Ответы же остались бы в базе
 * top-level записями — реплика на удалённое оскорбление всплывала бы отдельным
 * комментарием.
 */
export const cascadeCommentDelete: CollectionBeforeDeleteHook = async ({ req, id }) => {
  const payload = req.payload
  const levels = await commentThreadLevels(payload, req, id as CommentId)
  const all = levels.flat()

  await payload.delete({
    collection: 'comment-reports',
    where: { comment: { in: all } },
    req,
    overrideAccess: true,
  })

  // Снизу вверх: к моменту удаления родителя его ветка уже пуста, поэтому
  // рекурсивный вызов этого же хука не встречает исчезнувших документов.
  for (let level = levels.length - 1; level >= 1; level -= 1) {
    await payload.delete({
      collection: 'comments',
      where: { id: { in: levels[level] } },
      req,
      overrideAccess: true,
    })
  }
}
