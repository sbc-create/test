import type { PayloadHandler, PayloadRequest } from 'payload'

import { resolveTenantByHost, tenantFindOne } from '../lib/tenant-query'
import {
  fingerprint,
  isRejection,
  signFormToken,
  submissionKey,
  validateSubmission,
  verifyFormToken,
  type Limits,
} from './policy'

/**
 * Приём комментария.
 *
 * Прямое создание через REST закрыто (`create: () => false`), поэтому это
 * единственный путь. Здесь же выполняются лимиты, проверка формы и модерация:
 * если бы создание было открыто, любую из этих проверок можно было бы обойти
 * обычным POST на /api/comments.
 */

const TARGET_TYPES = new Set(['title', 'season', 'episode', 'post'])

const json = (status: number, body: Record<string, unknown>): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  })

/**
 * Адрес отправителя.
 *
 * X-Forwarded-For принимается ТОЛЬКО когда явно объявлен доверенный прокси:
 * иначе клиент подставляет новый адрес на каждый запрос, и лимит частоты вместе
 * с ключом идемпотентности перестают работать вовсе. Без доверенного прокси
 * берётся адрес сокета, а при его отсутствии — общий ключ, который лимитирует
 * строже, а не слабее.
 */
const clientIp = (req: PayloadRequest): string => {
  const trustProxy = (process.env.TRUSTED_PROXY ?? '').trim() === 'true'
  if (trustProxy) {
    const forwarded = req.headers.get('x-forwarded-for') ?? ''
    const first = (forwarded.split(',')[0] ?? '').trim()
    if (first) return first
    const real = req.headers.get('x-real-ip')
    if (real) return real
  }
  const socket = (req as unknown as { socket?: { remoteAddress?: string } }).socket
  return socket?.remoteAddress || 'shared'
}

export const issueFormToken = (
  secret: string,
  tenantId: string | number,
  targetType: string,
  targetId: string,
  nowSeconds: number,
): string =>
  signFormToken(secret, {
    tenant: String(tenantId),
    target: `${targetType}:${targetId}`,
    issuedAt: nowSeconds,
  })

export const submitComment: PayloadHandler = async (req) => {
  const secret = process.env.PAYLOAD_SECRET
  if (!secret) return json(500, { error: 'BLOCKED_SECRET: приложение не настроено' })

  let input: Record<string, unknown>
  try {
    input = ((await req.json?.()) ?? {}) as Record<string, unknown>
  } catch {
    return json(400, { error: 'Некорректный запрос.' })
  }

  const targetType = String(input.targetType ?? '')
  const targetId = String(input.targetId ?? '')
  if (!TARGET_TYPES.has(targetType) || !targetId) {
    return json(400, { error: 'Неизвестный объект обсуждения.' })
  }

  let tenant
  try {
    tenant = await resolveTenantByHost(req.payload, req.headers.get('host'))
  } catch {
    return json(400, { error: 'Сайт не определён.' })
  }

  const settings = (await tenantFindOne(req.payload, {
    collection: 'site-settings',
    tenant,
    depth: 0,
  })) as Record<string, unknown> | null

  const limits: Limits = {
    maxLength: Number(settings?.maxLength ?? 4000),
    allowGuests: tenant.allowGuestComments,
    authenticated: Boolean(req.user),
    commentsEnabled: settings?.commentsEnabled !== false,
  }

  const nowSeconds = Math.floor(Date.now() / 1000)
  const tokenCheck = verifyFormToken(
    secret,
    String(input.formToken ?? ''),
    { tenant: String(tenant.id), target: `${targetType}:${targetId}` },
    nowSeconds,
  )
  if (isRejection(tokenCheck)) return json(400, { error: tokenCheck.message, code: tokenCheck.code })

  // Ответ на комментарий обязан быть в том же сайте и на том же объекте:
  // иначе ветку одного сайта можно продолжить с другого.
  let parent: Record<string, unknown> | null = null
  if (input.parent) {
    parent = (await tenantFindOne(req.payload, {
      collection: 'comments',
      tenant,
      where: {
        and: [
          { id: { equals: input.parent as string } },
          { targetType: { equals: targetType } },
          { targetId: { equals: targetId } },
          { status: { equals: 'published' } },
        ],
      },
      depth: 0,
    })) as Record<string, unknown> | null
    if (!parent) return json(400, { error: 'Комментарий, на который вы отвечаете, недоступен.' })
  }

  const validation = validateSubmission(
    {
      body: String(input.body ?? ''),
      guestName: input.guestName ? String(input.guestName) : undefined,
      guestEmail: input.guestEmail ? String(input.guestEmail) : undefined,
      honeypot: input.website ? String(input.website) : undefined,
      parentDepth: parent ? Number(parent.depth ?? 0) + 1 : 0,
    },
    limits,
  )
  if (isRejection(validation)) return json(400, { error: validation.message, code: validation.code })

  const userAgent = (req.headers.get('user-agent') ?? '').slice(0, 200)
  const authorKey = fingerprint(secret, clientIp(req), userAgent)

  // Повтор той же отправки возвращает прежний результат, а не создаёт дубль.
  const idempotencyKey = submissionKey(secret, {
    tenant: String(tenant.id),
    target: `${targetType}:${targetId}`,
    author: req.user ? `user:${req.user.id}` : authorKey,
    body: validation.body,
  })
  const duplicate = await req.payload.find({
    collection: 'comments',
    overrideAccess: true,
    limit: 1,
    depth: 0,
    where: {
      and: [{ tenant: { equals: tenant.id } }, { submissionKey: { equals: idempotencyKey } }],
    },
  })
  // Одноразовость токена обеспечивается тем же ключом: повтор с тем же токеном и
  // тем же телом возвращает прежний результат, а с другим телом упирается в лимит.
  if (duplicate.totalDocs > 0) {
    const existing = duplicate.docs[0] as unknown as Record<string, unknown>
    return json(200, {
      id: existing.id,
      status: existing.status,
      duplicate: true,
      message: 'Этот комментарий уже отправлен.',
    })
  }

  const interval = Number(settings?.minIntervalSeconds ?? 30)
  if (interval > 0) {
    const since = new Date(Date.now() - interval * 1000).toISOString()
    const recent = await req.payload.count({
      collection: 'comments',
      overrideAccess: true,
      where: {
        and: [
          { tenant: { equals: tenant.id } },
          { authorKey: { equals: authorKey } },
          { createdAt: { greater_than: since } },
        ],
      },
    })
    if (recent.totalDocs > 0) {
      return json(429, { error: `Подождите ${interval} секунд перед следующим комментарием.`, code: 'RATE_LIMIT' })
    }
  }

  // Премодерация по умолчанию включена: комментарий не появляется на сайте,
  // пока его не посмотрел модератор.
  const status = settings?.premoderation === false ? 'published' : 'pending'
  const depth = parent ? Number(parent.depth ?? 0) + 1 : 0
  const root = parent ? (parent.root ?? parent.id) : undefined

  const created = await req.payload.create({
    collection: 'comments',
    overrideAccess: true,
    data: {
      tenant: tenant.id,
      targetType,
      targetId,
      targetUrl: String(input.targetUrl ?? '').slice(0, 500),
      author: req.user?.id,
      guestName: req.user ? undefined : String(input.guestName ?? '').trim(),
      guestEmail: req.user ? undefined : String(input.guestEmail ?? '').trim() || undefined,
      parent: parent?.id,
      root,
      depth,
      body: validation.body,
      status,
      authorKey,
      submissionKey: idempotencyKey,
      submissionMeta: { userAgent, receivedAt: new Date().toISOString() },
    } as never,
  })

  return json(201, {
    id: created.id,
    status,
    message:
      status === 'pending'
        ? 'Комментарий отправлен и появится после проверки модератором.'
        : 'Комментарий опубликован.',
  })
}
