import { issueFormToken } from '../comments/submit'
import type { SiteContext } from '../lib/site'
import { payloadClient } from '../lib/site'
import { tenantFind } from '../lib/tenant-query'
import { CommentForm } from './CommentForm'

/**
 * Обсуждение страницы. Показываются только опубликованные комментарии: то, что
 * ждёт модерации, на сайте не видно ни автору, ни поисковой системе.
 */
export const Comments = async ({
  site,
  targetType,
  targetId,
  targetUrl,
}: {
  site: SiteContext
  targetType: 'title' | 'season' | 'episode' | 'post'
  targetId: string
  targetUrl: string
}) => {
  const settings = site.settings ?? {}
  if (settings.commentsEnabled === false) return null

  const payload = await payloadClient()
  const result = await tenantFind(payload, {
    collection: 'comments',
    tenant: site.tenant,
    where: {
      and: [
        { targetType: { equals: targetType } },
        { targetId: { equals: targetId } },
        { status: { equals: 'published' } },
      ],
    },
    sort: 'createdAt',
    limit: 200,
    depth: 1,
  })

  const docs = result.docs as unknown as Record<string, unknown>[]
  const byParent = new Map<string, Record<string, unknown>[]>()
  for (const doc of docs) {
    const parentId = doc.parent ? String((doc.parent as { id?: unknown }).id ?? doc.parent) : 'root'
    byParent.set(parentId, [...(byParent.get(parentId) ?? []), doc])
  }

  const authorNameOf = (doc: Record<string, unknown>): string => {
    const author = doc.author as { name?: string; email?: string } | null
    // E-mail никогда не показывается публично, даже если имя не заполнено.
    return String(author?.name ?? doc.guestName ?? 'Аноним')
  }

  const renderBranch = (parentId: string, level: number): React.ReactNode => {
    const branch = byParent.get(parentId) ?? []
    if (branch.length === 0) return null
    return (
      <ul className="list" style={{ marginLeft: level > 0 ? '1.5rem' : 0 }}>
        {branch.map((doc) => (
          <li key={String(doc.id)} className="card" style={{ padding: '0.75rem' }}>
            <p className="card__meta">
              <strong>{authorNameOf(doc)}</strong>{' '}
              <time dateTime={String(doc.createdAt)}>
                {new Date(String(doc.createdAt)).toLocaleDateString('ru-RU')}
              </time>
            </p>
            <p style={{ whiteSpace: 'pre-line', margin: 0 }}>{String(doc.body ?? '')}</p>
            {renderBranch(String(doc.id), level + 1)}
          </li>
        ))}
      </ul>
    )
  }

  const token = issueFormToken(
    process.env.PAYLOAD_SECRET ?? '',
    site.tenant.id,
    targetType,
    targetId,
    Math.floor(Date.now() / 1000),
  )

  return (
    <section className="section" id="comments">
      <h2>Комментарии ({result.totalDocs})</h2>
      {result.totalDocs === 0 ? (
        <p className="notice">Пока никто не оставил комментарий.</p>
      ) : (
        renderBranch('root', 0)
      )}
      <h3>Оставить комментарий</h3>
      <CommentForm
        targetType={targetType}
        targetId={targetId}
        targetUrl={targetUrl}
        formToken={token}
        allowGuests={site.tenant.allowGuestComments}
        rulesText={String(settings.rulesText ?? 'Пишите по делу и уважайте собеседников.')}
        maxLength={Number(settings.maxLength ?? 4000)}
      />
    </section>
  )
}
