import { readFileSync } from 'fs'
import { load } from 'js-yaml'

/**
 * Описание контракта Content API.
 *
 * Точные endpoint, параметры, пагинация и поля намеренно НЕ зашиты в код: в
 * переданном knowledge pack их нет, а придумывать их запрещено. Адаптер целиком
 * управляется этим описанием, и пока оно не передано, синхронизация возвращает
 * BLOCKED_INPUT вместо запроса «наугад».
 */

export class ContentApiBlocked extends Error {
  readonly status = 'BLOCKED_INPUT'
  constructor(message: string) {
    super(`BLOCKED_INPUT: ${message}`)
  }
}

export type FieldMapping = Record<string, string>

export type ContentApiDescriptor = {
  status: 'provided' | 'not_provided'
  sourceDocument?: string
  contractVersion?: string
  baseUrl?: string
  auth?: { scheme: 'bearer' | 'header'; header: string; tokenEnv: string }
  endpoints?: Record<string, { path: string; method: 'GET' | 'POST' }>
  pagination?: {
    style: 'page' | 'cursor'
    pageParam?: string
    sizeParam?: string
    size?: number
    cursorParam?: string
    cursorField?: string
    completion: string
    itemsField: string
    maxPages: number
  }
  limits?: { timeoutMs: number; maxRetries: number; backoffMs: number; cacheTtlMs?: number }
  mapping?: { title: FieldMapping; season?: FieldMapping; episode?: FieldMapping }
}

const REQUIRED_WHEN_PROVIDED = ['baseUrl', 'auth', 'endpoints', 'pagination', 'limits', 'mapping'] as const

export const parseDescriptor = (raw: unknown, origin: string): ContentApiDescriptor => {
  const data = (raw ?? {}) as Record<string, unknown>
  const status = data.status === 'provided' ? 'provided' : 'not_provided'
  if (status === 'not_provided') {
    return { status, sourceDocument: data.source_document as string | undefined }
  }

  const descriptor: ContentApiDescriptor = {
    status,
    sourceDocument: data.source_document as string | undefined,
    contractVersion: data.contract_version as string | undefined,
    baseUrl: data.base_url as string | undefined,
    auth: data.auth as ContentApiDescriptor['auth'],
    endpoints: data.endpoints as ContentApiDescriptor['endpoints'],
    pagination: data.pagination as ContentApiDescriptor['pagination'],
    limits: data.limits as ContentApiDescriptor['limits'],
    mapping: data.mapping as ContentApiDescriptor['mapping'],
  }

  const missing = REQUIRED_WHEN_PROVIDED.filter((key) => !descriptor[key])
  if (missing.length > 0) {
    throw new ContentApiBlocked(
      `описание контракта ${origin} помечено как переданное, но в нём нет разделов: ${missing.join(', ')}`,
    )
  }
  if (!descriptor.mapping?.title || Object.keys(descriptor.mapping.title).length === 0) {
    throw new ContentApiBlocked(`в описании контракта ${origin} не задано соответствие полей тайтла`)
  }
  return descriptor
}

export const loadDescriptor = (path: string): ContentApiDescriptor => {
  let raw: unknown
  try {
    raw = load(readFileSync(path, 'utf8'))
  } catch (error) {
    throw new ContentApiBlocked(
      `не удалось прочитать описание контракта ${path}: ${(error as Error).message}`,
    )
  }
  return parseDescriptor(raw, path)
}

export const assertUsable = (descriptor: ContentApiDescriptor): void => {
  if (descriptor.status !== 'provided') {
    throw new ContentApiBlocked(
      'контракт Content API не передан. Заполните knowledge/cdnvideohub/content-api.yaml ' +
        'по официальному документу провайдера; endpoint и поля не подбираются кодом.',
    )
  }
}
