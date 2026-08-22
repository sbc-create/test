/**
 * Контракт плеера CDNVideoHub.
 *
 * Значения здесь — только из переданной документации провайдера. Ни один
 * атрибут, метод или событие не придуман: если параметра нет в контракте, его
 * нельзя «предположить», это BLOCKED_PLAYER_CONTRACT.
 */

export const PLAYER_SCRIPT_URL = 'https://player.cdnvideohub.com/s2/stable/video-player.umd.js'
export const PLAYER_ELEMENT = 'video-player'
export const PLAYER_METHODS = ['selectSeason', 'selectEpisode'] as const
export const PLAYER_EVENTS = ['noData'] as const

export const AGGREGATORS = ['kp', 'mali', 'mdl'] as const
export type Aggregator = (typeof AGGREGATORS)[number]

/** Атрибуты, разрешённые контрактом. Всё остальное в разметку не попадает. */
export const ALLOWED_ATTRIBUTES = [
  'ident',
  'season',
  'episode',
  'data-publisher-id',
  'data-title-id',
  'data-aggregator',
  'only-voice',
  'priority-voice',
  'is-show-voice-only',
  'is-show-banner',
  'disable-licensed',
] as const

export type PlayerAttributes = Partial<Record<(typeof ALLOWED_ATTRIBUTES)[number], string>>

export class PlayerContractError extends Error {
  constructor(message: string) {
    super(`BLOCKED_PLAYER_CONTRACT: ${message}`)
  }
}

export type PlayerInput = {
  /** Идентификатор тайтла у агрегатора. */
  titleId: string
  aggregator: string
  publisherId: string
  season?: number | null
  episode?: number | null
  onlyVoice?: string | null
  priorityVoice?: string | null
  showVoiceOnly?: boolean
  showBanner?: boolean
}

const positiveInteger = (value: number, field: string): string => {
  if (!Number.isInteger(value) || value < 1) {
    throw new PlayerContractError(`${field} должен быть целым числом от 1, получено ${value}`)
  }
  return String(value)
}

/**
 * Сборка атрибутов встраивания.
 *
 * `disable-licensed` всегда "false" и не берётся из настроек: контракт не
 * допускает иного значения, а «настраиваемый» флаг рано или поздно переключат.
 */
export const buildPlayerAttributes = (input: PlayerInput): PlayerAttributes => {
  const titleId = input.titleId?.trim()
  if (!titleId) throw new PlayerContractError('не передан идентификатор тайтла')

  if (!AGGREGATORS.includes(input.aggregator as Aggregator)) {
    throw new PlayerContractError(
      `агрегатор «${input.aggregator}» отсутствует в контракте (допустимы ${AGGREGATORS.join(', ')})`,
    )
  }

  const publisherId = input.publisherId?.trim()
  if (!publisherId) throw new PlayerContractError('не передан publisher ID')

  const attributes: PlayerAttributes = {
    ident: titleId,
    'data-title-id': titleId,
    'data-publisher-id': publisherId,
    'data-aggregator': input.aggregator,
    'disable-licensed': 'false',
  }

  if (input.season !== null && input.season !== undefined) {
    attributes.season = positiveInteger(input.season, 'season')
  }
  if (input.episode !== null && input.episode !== undefined) {
    attributes.episode = positiveInteger(input.episode, 'episode')
  }
  const onlyVoice = input.onlyVoice?.trim()
  const priorityVoice = input.priorityVoice?.trim()
  if (onlyVoice) {
    // PC-1: непустой only-voice имеет приоритет, конфликтующий priority-voice
    // одновременно с ним отправлять нельзя.
    attributes['only-voice'] = onlyVoice
    if (priorityVoice && priorityVoice !== onlyVoice) {
      throw new PlayerContractError(
        `конфликт озвучек: only-voice «${onlyVoice}» и priority-voice «${priorityVoice}» одновременно`,
      )
    }
  } else if (priorityVoice) {
    attributes['priority-voice'] = priorityVoice
  }
  if (input.showVoiceOnly) attributes['is-show-voice-only'] = 'true'
  if (input.showBanner) attributes['is-show-banner'] = 'true'

  for (const key of Object.keys(attributes)) {
    if (!ALLOWED_ATTRIBUTES.includes(key as (typeof ALLOWED_ATTRIBUTES)[number])) {
      throw new PlayerContractError(`атрибут «${key}» не описан контрактом`)
    }
  }

  return attributes
}

export type PlayerMode = 'live' | 'mock'

/** Локальная заглушка для стенда. В production она технически недопустима. */
export const MOCK_SCRIPT_URL = '/mock/video-player.umd.js'

export const resolvePlayerMode = (environment: string, requested: string | undefined): PlayerMode => {
  // Незаданное окружение трактуется как production: fail-open здесь означает,
  // что забытая переменная тихо разрешает заглушку на боевом сайте.
  const mode: PlayerMode = requested === 'mock' ? 'mock' : 'live'
  if (mode === 'mock' && environment === 'production') {
    // Отказ именно технический: договорённость «в production мы не включаем mock»
    // проверить невозможно, а этот throw виден в тесте и в логе сборки.
    throw new PlayerContractError('mock-режим плеера запрещён в production')
  }
  return mode
}

export const scriptUrlFor = (mode: PlayerMode): string =>
  mode === 'mock' ? MOCK_SCRIPT_URL : PLAYER_SCRIPT_URL
