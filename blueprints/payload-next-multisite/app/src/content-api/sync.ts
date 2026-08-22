import { createHash } from 'crypto'
import type { Payload } from 'payload'

import { ContentApiClient, ContentApiError, applyMapping } from './client'
import { ContentApiBlocked, type ContentApiDescriptor } from './descriptor'

/**
 * Синхронизация общего каталога из Content API.
 *
 * Правила, которые важнее скорости импорта:
 *  - идемпотентность: повторный запуск с тем же запросом ничего не дублирует;
 *  - стабильное внешнее соответствие по паре «агрегатор + идентификатор тайтла»;
 *  - редакционные поля сайтов не трогаются вовсе — они лежат в другой коллекции;
 *  - запись, заведённая редактором вручную, не перезаписывается импортом;
 *  - пропавший в источнике тайтл получает явное состояние, а не подменяется другим.
 */

export type SyncMode = 'mock' | 'live'

export type SyncOptions = {
  payload: Payload
  client: ContentApiClient
  descriptor: ContentApiDescriptor
  mode: SyncMode
  environment: string
  endpoint?: string
  query?: Record<string, string | number>
  reference?: string
}

export type SyncCounters = { created: number; updated: number; skipped: number; blocked: number }

export type SyncResult = SyncCounters & {
  jobId: string | number
  status: 'succeeded' | 'failed' | 'blocked_input' | 'blocked_content_rights'
  requestDigest: string
  message?: string
}

/** Отпечаток нормализованного запроса: одинаковый запрос — одинаковый отпечаток. */
export const requestDigest = (
  descriptor: ContentApiDescriptor,
  endpoint: string,
  query: Record<string, string | number>,
): string => {
  const normalized = JSON.stringify({
    contract: descriptor.contractVersion ?? 'unknown',
    base: descriptor.baseUrl,
    endpoint,
    query: Object.fromEntries(Object.entries(query).sort(([a], [b]) => a.localeCompare(b))),
  })
  return createHash('sha256').update(normalized).digest('hex')
}

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : {}

/** Поля, которыми владеет импорт. Всё остальное принадлежит редакции. */
const OWNED_FIELDS = [
  'primaryName',
  'englishName',
  'originalName',
  'kind',
  'status',
  'year',
  'factualSynopsis',
  'availability',
] as const

const sameValues = (before: Record<string, unknown>, after: Record<string, unknown>): boolean =>
  OWNED_FIELDS.every((field) => {
    if (!(field in after)) return true
    return String(before[field] ?? '') === String(after[field] ?? '')
  })

export const syncTitles = async (options: SyncOptions): Promise<SyncResult> => {
  const { payload, client, descriptor, mode, environment } = options
  const endpoint = options.endpoint ?? 'titles'
  const query = options.query ?? {}

  if (mode === 'mock' && environment === 'production') {
    // Технический отказ, а не договорённость: иначе production однажды поедет на фикстурах.
    throw new ContentApiBlocked('режим фикстур запрещён в production')
  }

  const digest = requestDigest(descriptor, endpoint, query)
  const reference = options.reference ?? `sync-${endpoint}-${digest.slice(0, 12)}`
  const startedAt = new Date().toISOString()

  const job = await payload.create({
    collection: 'import-jobs',
    overrideAccess: true,
    data: {
      reference,
      mode,
      status: 'running',
      requestDigest: digest,
      startedAt,
      created: 0,
      updated: 0,
      skipped: 0,
      blocked: 0,
    } as never,
  })

  const counters: SyncCounters = { created: 0, updated: 0, skipped: 0, blocked: 0 }
  const seenExternalIds = new Set<string>()
  let status: SyncResult['status'] = 'succeeded'
  let message: string | undefined

  try {
    for await (const page of client.pages(endpoint, query)) {
      for (const item of page.items) {
        const mapped = applyMapping(item, descriptor.mapping!.title)
        const aggregator = String(mapped.playbackAggregator ?? '').trim()
        const externalId = String(mapped.playbackTitleId ?? '').trim()

        if (!aggregator || !externalId) {
          counters.blocked += 1
          continue
        }
        const key = `${aggregator}:${externalId}`
        // Дубликат внутри одной выдачи не создаёт второй записи.
        if (seenExternalIds.has(key)) {
          counters.skipped += 1
          continue
        }
        seenExternalIds.add(key)

        const existing = await payload.find({
          collection: 'titles',
          where: {
            and: [
              { playbackAggregator: { equals: aggregator } },
              { playbackTitleId: { equals: externalId } },
            ],
          },
          limit: 2,
          depth: 0,
          overrideAccess: true,
        })

        if (existing.totalDocs > 1) {
          // Неоднозначное соответствие не разрешается угадыванием.
          counters.blocked += 1
          continue
        }

        const payloadData: Record<string, unknown> = {
          ...Object.fromEntries(OWNED_FIELDS.filter((field) => field in mapped).map((field) => [field, mapped[field]])),
          playbackAggregator: aggregator,
          playbackTitleId: externalId,
          source: 'provider_api',
          sourceRef: key,
          sourceUpdatedAt: mapped.sourceUpdatedAt ?? null,
        }

        const current = existing.docs[0] as unknown as Record<string, unknown> | undefined
        if (!current) {
          if (!payloadData.primaryName) {
            counters.blocked += 1
            continue
          }
          await payload.create({
            collection: 'titles',
            overrideAccess: true,
            data: { ...payloadData, availability: payloadData.availability ?? 'available' } as never,
          })
          counters.created += 1
          continue
        }

        if (String(current.source ?? '') === 'manual') {
          // Ручная запись редактора важнее автоматической: импорт её не трогает.
          counters.skipped += 1
          continue
        }
        if (sameValues(current, payloadData)) {
          counters.skipped += 1
          continue
        }

        await payload.update({
          collection: 'titles',
          id: current.id as string | number,
          overrideAccess: true,
          data: payloadData as never,
        })
        counters.updated += 1
      }
    }
  } catch (error) {
    if (error instanceof ContentApiBlocked) {
      status = 'blocked_input'
    } else {
      status = 'failed'
    }
    message =
      error instanceof ContentApiError
        ? `${error.kind}: ${error.message}`
        : (error as Error).message
  }

  await payload.update({
    collection: 'import-jobs',
    id: job.id,
    overrideAccess: true,
    data: {
      status,
      finishedAt: new Date().toISOString(),
      ...counters,
      message: message ?? null,
    } as never,
  })

  return { ...counters, jobId: job.id, status, requestDigest: digest, message }
}

/**
 * Материалы, пропавшие из источника, помечаются недоступными. Удаления не
 * происходит: страница обязана остаться и честно сказать, что смотреть нечего.
 */
export const markMissingUnavailable = async (
  payload: Payload,
  aggregator: string,
  presentExternalIds: string[],
): Promise<number> => {
  const existing = await payload.find({
    collection: 'titles',
    where: {
      and: [
        { playbackAggregator: { equals: aggregator } },
        { source: { equals: 'provider_api' } },
        { availability: { not_equals: 'withdrawn' } },
      ],
    },
    limit: 1000,
    depth: 0,
    overrideAccess: true,
  })

  const present = new Set(presentExternalIds)
  let changed = 0
  for (const doc of existing.docs) {
    const record = asRecord(doc)
    const externalId = String(record.playbackTitleId ?? '')
    if (present.has(externalId) || record.availability === 'unavailable') continue
    await payload.update({
      collection: 'titles',
      id: record.id as string | number,
      overrideAccess: true,
      data: { availability: 'unavailable' } as never,
    })
    changed += 1
  }
  return changed
}
