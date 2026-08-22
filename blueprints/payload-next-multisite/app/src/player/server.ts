import type { Payload } from 'payload'

import { tenantFindOne, type TenantContext } from '../lib/tenant-query'
import {
  PlayerContractError,
  buildPlayerAttributes,
  resolvePlayerMode,
  scriptUrlFor,
  type PlayerAttributes,
} from './contract'

/**
 * Серверная сборка параметров плеера.
 *
 * Publisher ID берётся из переменной окружения по имени секрета, записанному в
 * CMS. В CMS хранится только имя: значение не попадает ни в базу, ни в дамп, ни
 * в экспорт контента. API-токен Content API здесь не используется вовсе — плеер
 * его не принимает.
 */

export type PlayerRenderConfig = {
  attributes: PlayerAttributes
  scriptUrl: string
  reason?: never
}

export type PlayerUnavailable = {
  reason: string
  attributes?: never
  scriptUrl?: never
}

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : null

export const playerConfigFor = async (
  payload: Payload,
  tenant: TenantContext,
  sharedTitle: unknown,
  position: { season?: number | null; episode?: number | null } = {},
): Promise<PlayerRenderConfig | PlayerUnavailable> => {
  const title = asRecord(sharedTitle)
  if (!title) return { reason: 'Данные тайтла недоступны.' }

  const rights = asRecord(title.rightsRecord)
  if (!rights || rights.allowsPublication !== true) {
    // Права не подтверждены — видео не показывается вовсе. Это не ошибка рендера,
    // а осознанное состояние страницы.
    return { reason: 'Просмотр недоступен: права на публикацию не подтверждены.' }
  }

  const titleId = String(title.playbackTitleId ?? '').trim()
  const aggregator = String(title.playbackAggregator ?? '').trim()
  if (!titleId || !aggregator) {
    return { reason: 'Просмотр недоступен: у материала нет идентификаторов воспроизведения.' }
  }

  const profile = (await tenantFindOne(payload, {
    collection: 'player-profiles',
    tenant,
    depth: 1,
  })) as Record<string, unknown> | null
  if (!profile) return { reason: 'Просмотр недоступен: для сайта не настроен профиль плеера.' }

  const publisherRef = String(profile.publisherIdRef ?? '').trim()
  const publisherId = publisherRef ? (process.env[publisherRef] ?? '').trim() : ''
  if (!publisherId) {
    // Пустой секрет не заменяется значением по умолчанию и не «пробуется наугад».
    return { reason: 'Просмотр недоступен: не задан секрет publisher ID для этого сайта.' }
  }

  const priorityVoice = asRecord(profile.priorityVoice)
  const mode = resolvePlayerMode(
    // Умолчание — production: незаданная переменная не должна открывать заглушку.
    process.env.FACTORY_ENVIRONMENT || 'production',
    process.env.PLAYER_MODE,
  )

  try {
    const attributes = buildPlayerAttributes({
      titleId,
      aggregator,
      publisherId,
      season: position.season ?? null,
      episode: position.episode ?? null,
      priorityVoice: priorityVoice ? String(priorityVoice.playerValue ?? '').trim() || null : null,
      showVoiceOnly: profile.showVoiceOnly === true,
      showBanner: profile.showBanner === true,
    })
    return { attributes, scriptUrl: scriptUrlFor(mode) }
  } catch (error) {
    if (error instanceof PlayerContractError) return { reason: error.message }
    throw error
  }
}
