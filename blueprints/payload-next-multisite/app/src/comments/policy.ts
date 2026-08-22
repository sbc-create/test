import { createHash, createHmac, timingSafeEqual } from 'crypto'

/**
 * Правила приёма комментариев.
 *
 * Функции здесь чистые и проверяются модульными тестами: анти-абьюз, который
 * нельзя протестировать, на практике не работает.
 */

export const MAX_DEPTH = 3
export const MIN_LENGTH = 2
export const MAX_LINKS = 2
/** Форма, отправленная быстрее этого, заполнена не человеком. */
export const MIN_FILL_SECONDS = 3
/** Токен формы живёт ограниченное время: иначе его можно заготовить впрок. */
export const FORM_TOKEN_TTL_SECONDS = 3600

/** Управляющие символы вырезаются: в тексте комментария им делать нечего. */
const CONTROL_CHARS = /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g

export type Rejection = { code: string; message: string }

export const reject = (code: string, message: string): Rejection => ({ code, message })

/**
 * Текст приводится к простому виду: разметка не поддерживается вовсе.
 * Экранирование при выводе — не замена очистке на входе.
 */
export const sanitizeBody = (raw: string): string =>
  raw
    .replace(/\r\n?/g, '\n')
    .replace(/<[^>]*>/g, ' ')
    .replace(CONTROL_CHARS, '')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

export const countLinks = (text: string): number => (text.match(/https?:\/\/|www\./gi) ?? []).length

export type FormTokenPayload = { tenant: string; target: string; issuedAt: number }

export const signFormToken = (secret: string, payload: FormTokenPayload): string => {
  const body = `${payload.tenant}.${payload.target}.${payload.issuedAt}`
  const signature = createHmac('sha256', secret).update(body).digest('base64url')
  return `${body}.${signature}`
}

export const verifyFormToken = (
  secret: string,
  token: string,
  expected: { tenant: string; target: string },
  now: number,
): Rejection | { issuedAt: number } => {
  const parts = token.split('.')
  if (parts.length !== 4) return reject('BAD_TOKEN', 'Форма устарела, обновите страницу.')
  const [tenant, target, issuedAtRaw, signature] = parts as [string, string, string, string]
  const body = `${tenant}.${target}.${issuedAtRaw}`
  const expectedSignature = createHmac('sha256', secret).update(body).digest('base64url')

  const provided = Buffer.from(signature)
  const computed = Buffer.from(expectedSignature)
  if (provided.length !== computed.length || !timingSafeEqual(provided, computed)) {
    return reject('BAD_TOKEN', 'Форма устарела, обновите страницу.')
  }
  if (tenant !== expected.tenant || target !== expected.target) {
    // Токен, выданный для другой страницы или другого сайта, не принимается:
    // иначе одну подпись можно переиспользовать по всему приложению.
    return reject('BAD_TOKEN', 'Форма относится к другой странице.')
  }

  const issuedAt = Number(issuedAtRaw)
  if (!Number.isFinite(issuedAt)) return reject('BAD_TOKEN', 'Форма устарела, обновите страницу.')
  if (now - issuedAt > FORM_TOKEN_TTL_SECONDS) {
    return reject('TOKEN_EXPIRED', 'Форма устарела, обновите страницу.')
  }
  if (now - issuedAt < MIN_FILL_SECONDS) {
    return reject('TOO_FAST', 'Слишком быстро. Попробуйте отправить ещё раз через пару секунд.')
  }
  return { issuedAt }
}

/** IP не хранится в открытом виде: для лимитов достаточно устойчивого отпечатка. */
export const fingerprint = (secret: string, ip: string, userAgent: string): string =>
  createHash('sha256').update(`${secret}:${ip}:${userAgent}`).digest('hex').slice(0, 32)

export type SubmissionInput = {
  body: string
  guestName?: string
  guestEmail?: string
  honeypot?: string
  parentDepth?: number | null
}

export type Limits = {
  maxLength: number
  allowGuests: boolean
  authenticated: boolean
  commentsEnabled: boolean
}

export const validateSubmission = (
  input: SubmissionInput,
  limits: Limits,
): Rejection | { body: string } => {
  if (!limits.commentsEnabled) return reject('COMMENTS_DISABLED', 'Комментарии на сайте отключены.')
  if (input.honeypot && input.honeypot.trim() !== '') {
    // Поле-ловушка скрыто от человека; заполнено — значит, заполнял не человек.
    return reject('HONEYPOT', 'Не удалось отправить комментарий.')
  }
  if (!limits.authenticated && !limits.allowGuests) {
    return reject('GUESTS_DISABLED', 'Комментарии доступны только авторизованным пользователям.')
  }

  const body = sanitizeBody(input.body ?? '')
  if (body.length < MIN_LENGTH) return reject('TOO_SHORT', 'Слишком короткий комментарий.')
  if (body.length > limits.maxLength) {
    return reject('TOO_LONG', `Слишком длинный комментарий: максимум ${limits.maxLength} символов.`)
  }
  if (countLinks(body) > MAX_LINKS) {
    return reject('TOO_MANY_LINKS', 'Слишком много ссылок в комментарии.')
  }
  if (!limits.authenticated) {
    const name = (input.guestName ?? '').trim()
    if (name.length < 2 || name.length > 60) {
      return reject('BAD_NAME', 'Укажите имя длиной от 2 до 60 символов.')
    }
    const email = (input.guestEmail ?? '').trim()
    if (email && !/^[^@\s]+@[^@\s.]+\.[^@\s]+$/.test(email)) {
      return reject('BAD_EMAIL', 'Проверьте адрес электронной почты.')
    }
  }
  if ((input.parentDepth ?? 0) >= MAX_DEPTH) {
    return reject('TOO_DEEP', 'Слишком глубокая ветка обсуждения.')
  }

  return { body }
}

export const isRejection = (value: unknown): value is Rejection =>
  Boolean(value && typeof value === 'object' && 'code' in (value as Record<string, unknown>))
