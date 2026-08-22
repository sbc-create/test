/** Проверки контракта плеера. Ничего, кроме переданной документации. */
import {
  AGGREGATORS,
  ALLOWED_ATTRIBUTES,
  MOCK_SCRIPT_URL,
  PLAYER_ELEMENT,
  PLAYER_EVENTS,
  PLAYER_METHODS,
  PLAYER_SCRIPT_URL,
  PlayerContractError,
  buildPlayerAttributes,
  resolvePlayerMode,
  scriptUrlFor,
} from '../src/player/contract'
import { assert, assertEqual, check, summary } from './harness'

const base = { titleId: 'abc123', aggregator: 'kp', publisherId: 'publisher-1' }

await check('константы контракта не переписаны', () => {
  assertEqual(PLAYER_SCRIPT_URL, 'https://player.cdnvideohub.com/s2/stable/video-player.umd.js', 'адрес скрипта')
  assertEqual(PLAYER_ELEMENT, 'video-player', 'имя элемента')
  assertEqual(PLAYER_METHODS.join(','), 'selectSeason,selectEpisode', 'методы')
  assertEqual(PLAYER_EVENTS.join(','), 'noData', 'события')
  assertEqual(AGGREGATORS.join(','), 'kp,mali,mdl', 'агрегаторы')
})

await check('disable-licensed всегда false и не настраивается', () => {
  const attributes = buildPlayerAttributes(base)
  assertEqual(attributes['disable-licensed'], 'false', 'значение disable-licensed')
})

await check('в разметку попадают только атрибуты контракта', () => {
  const attributes = buildPlayerAttributes({ ...base, season: 2, episode: 5, priorityVoice: 'voice-a' })
  for (const key of Object.keys(attributes)) {
    assert(
      (ALLOWED_ATTRIBUTES as readonly string[]).includes(key),
      `атрибут ${key} отсутствует в контракте`,
    )
  }
  assertEqual(attributes.season, '2', 'сезон')
  assertEqual(attributes.episode, '5', 'эпизод')
  assertEqual(attributes['priority-voice'], 'voice-a', 'приоритетная озвучка')
  assertEqual(attributes['data-publisher-id'], 'publisher-1', 'publisher id')
})

await check('неизвестный агрегатор отклоняется, а не подставляется по умолчанию', () => {
  let thrown: unknown
  try {
    buildPlayerAttributes({ ...base, aggregator: 'shiki' })
  } catch (error) {
    thrown = error
  }
  assert(thrown instanceof PlayerContractError, 'ожидалась ошибка контракта')
})

await check('пустые обязательные значения не заменяются заглушкой', () => {
  for (const broken of [{ ...base, titleId: '  ' }, { ...base, publisherId: '' }]) {
    let thrown: unknown
    try {
      buildPlayerAttributes(broken)
    } catch (error) {
      thrown = error
    }
    assert(thrown instanceof PlayerContractError, `значение ${JSON.stringify(broken)} принято`)
  }
})

await check('номера сезона и серии — целые от единицы', () => {
  for (const value of [0, -1, 1.5]) {
    let thrown: unknown
    try {
      buildPlayerAttributes({ ...base, season: value })
    } catch (error) {
      thrown = error
    }
    assert(thrown instanceof PlayerContractError, `сезон ${value} принят`)
  }
})

await check('mock-режим технически запрещён в production', () => {
  assertEqual(resolvePlayerMode('staging', 'mock'), 'mock', 'на стенде mock разрешён')
  assertEqual(resolvePlayerMode('production', undefined), 'live', 'в production по умолчанию live')
  let thrown: unknown
  try {
    resolvePlayerMode('production', 'mock')
  } catch (error) {
    thrown = error
  }
  assert(thrown instanceof PlayerContractError, 'production принял mock-режим')
})

await check('адрес скрипта выбирается режимом', () => {
  assertEqual(scriptUrlFor('live'), PLAYER_SCRIPT_URL, 'live')
  assertEqual(scriptUrlFor('mock'), MOCK_SCRIPT_URL, 'mock')
})

await check('неизвестный режим не включает mock молча', () => {
  assertEqual(resolvePlayerMode('staging', 'что-то'), 'live', 'неизвестное значение трактуется как live')
})

process.exit(summary())
