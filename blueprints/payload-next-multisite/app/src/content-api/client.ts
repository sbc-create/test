import { ContentApiBlocked, assertUsable, type ContentApiDescriptor } from './descriptor'

/**
 * Клиент Content API.
 *
 * Токен читается на сервере из переменной окружения и не передаётся ни в один
 * лог, ответ или артефакт. Транспорт подменяем: фикстуры и живой прогон
 * проходят через один и тот же код, иначе тест проверял бы не то, что работает.
 */

export type Transport = (
  url: string,
  init: { method: string; headers: Record<string, string>; signal: AbortSignal },
) => Promise<{ status: number; headers: Record<string, string>; body: unknown }>

export type ClientOptions = {
  descriptor: ContentApiDescriptor
  transport: Transport
  token?: string
  sleep?: (ms: number) => Promise<void>
  now?: () => number
}

export class ContentApiError extends Error {
  constructor(
    message: string,
    readonly kind: 'timeout' | 'http' | 'malformed' | 'rate_limited' | 'auth',
    readonly retryable: boolean,
  ) {
    super(message)
  }
}

const defaultSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

/** Секрет не печатается: в сообщении остаётся только имя переменной. */
const authHeaders = (descriptor: ContentApiDescriptor, token: string): Record<string, string> => {
  const auth = descriptor.auth!
  if (auth.scheme === 'bearer') return { [auth.header]: `Bearer ${token}` }
  return { [auth.header]: token }
}

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : {}

/** Значение по пути `a.b.c` — соответствие полей задаётся контрактом, а не кодом. */
export const pluck = (source: unknown, path: string): unknown => {
  let current: unknown = source
  for (const segment of path.split('.')) {
    if (Array.isArray(current)) {
      const index = Number(segment)
      current = Number.isInteger(index) ? current[index] : undefined
    } else {
      current = asRecord(current)[segment]
    }
    if (current === undefined || current === null) return undefined
  }
  return current
}

export const applyMapping = (
  source: unknown,
  mapping: Record<string, string>,
): Record<string, unknown> => {
  const result: Record<string, unknown> = {}
  for (const [field, path] of Object.entries(mapping)) {
    const value = pluck(source, path)
    if (value !== undefined) result[field] = value
  }
  return result
}

export class ContentApiClient {
  private readonly descriptor: ContentApiDescriptor
  private readonly transport: Transport
  private readonly token: string
  private readonly sleep: (ms: number) => Promise<void>
  private readonly cache = new Map<string, { body: unknown; expiresAt: number }>()

  constructor(options: ClientOptions) {
    assertUsable(options.descriptor)
    this.descriptor = options.descriptor
    this.transport = options.transport
    this.sleep = options.sleep ?? defaultSleep

    const tokenEnv = options.descriptor.auth!.tokenEnv
    const token = options.token ?? process.env[tokenEnv] ?? ''
    if (!token) {
      throw new ContentApiBlocked(`не задан серверный секрет ${tokenEnv} для Content API`)
    }
    this.token = token
  }

  private url(endpoint: string, params: Record<string, string | number>): string {
    const definition = this.descriptor.endpoints?.[endpoint]
    if (!definition) throw new ContentApiBlocked(`в контракте нет endpoint «${endpoint}»`)
    const url = new URL(definition.path, this.descriptor.baseUrl)
    for (const [key, value] of Object.entries(params)) url.searchParams.set(key, String(value))
    return url.toString()
  }

  /** Один запрос с таймаутом, ограниченным числом повторов и явным TTL кэша. */
  private async request(url: string, method: string): Promise<unknown> {
    const limits = this.descriptor.limits!
    const ttl = limits.cacheTtlMs ?? 0
    if (ttl > 0) {
      const cached = this.cache.get(url)
      if (cached && cached.expiresAt > Date.now()) return cached.body
    }
    let attempt = 0

    for (;;) {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), limits.timeoutMs)
      let response
      try {
        response = await this.transport(url, {
          method,
          headers: { accept: 'application/json', ...authHeaders(this.descriptor, this.token) },
          signal: controller.signal,
        })
      } catch (error) {
        clearTimeout(timer)
        const failure = new ContentApiError(
          `запрос не выполнен: ${(error as Error).message}`,
          (error as Error).name === 'AbortError' ? 'timeout' : 'http',
          true,
        )
        if (attempt >= limits.maxRetries) throw failure
        attempt += 1
        await this.sleep(limits.backoffMs * 2 ** (attempt - 1))
        continue
      }
      clearTimeout(timer)

      if (response.status === 401 || response.status === 403) {
        // Повторять запрос с тем же непринятым токеном бессмысленно.
        throw new ContentApiError('провайдер отклонил авторизацию', 'auth', false)
      }
      if (response.status === 429) {
        const retryAfter = Number(response.headers['retry-after'] ?? '')
        if (attempt >= limits.maxRetries) {
          throw new ContentApiError('превышено ограничение частоты запросов', 'rate_limited', true)
        }
        attempt += 1
        await this.sleep(Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter * 1000 : limits.backoffMs * 2 ** (attempt - 1))
        continue
      }
      if (response.status >= 500) {
        if (attempt >= limits.maxRetries) {
          throw new ContentApiError(`провайдер вернул ${response.status}`, 'http', true)
        }
        attempt += 1
        await this.sleep(limits.backoffMs * 2 ** (attempt - 1))
        continue
      }
      if (response.status >= 400) {
        throw new ContentApiError(`провайдер вернул ${response.status}`, 'http', false)
      }
      if (ttl > 0) this.cache.set(url, { body: response.body, expiresAt: Date.now() + ttl })
      return response.body
    }
  }

  /** Сброс кэша: после импорта данные читаются заново, а не из прошлого прогона. */
  invalidate(): void {
    this.cache.clear()
  }

  /**
   * Постраничное чтение до условия завершения из контракта. Ограничение
   * `maxPages` — защита от бесконечного цикла, а не «столько и хватит»:
   * при его достижении вызывающий код обязан считать выборку неполной.
   */
  async *pages(endpoint: string, query: Record<string, string | number> = {}) {
    const pagination = this.descriptor.pagination!
    let page = 1
    let cursor: string | undefined
    let seen = 0

    for (;;) {
      const params: Record<string, string | number> = { ...query }
      if (pagination.style === 'page') {
        params[pagination.pageParam ?? 'page'] = page
        if (pagination.sizeParam) params[pagination.sizeParam] = pagination.size ?? 50
      } else if (cursor) {
        params[pagination.cursorParam ?? 'cursor'] = cursor
      }

      const body = await this.request(this.url(endpoint, params), this.descriptor.endpoints![endpoint]!.method)
      const items = pluck(body, pagination.itemsField)
      if (!Array.isArray(items)) {
        throw new ContentApiError(
          `ответ не содержит списка по пути «${pagination.itemsField}»`,
          'malformed',
          false,
        )
      }

      yield { items, body, page, complete: false }
      seen += 1

      if (pagination.completion === 'empty_page' && items.length === 0) return
      if (pagination.completion === 'short_page' && items.length < (pagination.size ?? 50)) return
      if (pagination.completion === 'cursor_absent') {
        const next = pagination.cursorField ? pluck(body, pagination.cursorField) : undefined
        if (!next) return
        cursor = String(next)
      }
      page += 1
      if (seen >= pagination.maxPages) {
        throw new ContentApiError(
          `достигнут предел в ${pagination.maxPages} страниц: выборка неполная`,
          'http',
          false,
        )
      }
    }
  }
}
