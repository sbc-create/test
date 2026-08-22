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
import { readFileSync } from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

import { load } from 'js-yaml'

import { assert, assertEqual, check, summary } from './harness'

const dirname = path.dirname(fileURLToPath(import.meta.url))
const frozen = load(
  readFileSync(path.resolve(dirname, '../../../../knowledge/cdnvideohub/PLAYER_CONTRACT.yaml'), 'utf8'),
) as {
  script: { url: string }
  element: string
  public_api: { methods: { name: string }[]; events: { name: string }[] }
  attributes: { name: string; allowed?: string[]; fixed_value?: string }[]
}

const base = { titleId: 'abc123', aggregator: 'kp', publisherId: 'publisher-1' }

await check('константы контракта совпадают с замороженным документом', () => {
  // Сравнение с литералами в самом тесте ничего не доказывает: правка кода и
  // правка теста делаются одной рукой. Источник — knowledge/cdnvideohub/.
  assertEqual(PLAYER_SCRIPT_URL, frozen.script.url, 'адрес скрипта')
  assertEqual(PLAYER_ELEMENT, frozen.element, 'имя элемента')
  assertEqual(PLAYER_METHODS.join(','), frozen.public_api.methods.map((m) => m.name).join(','), 'методы')
  assertEqual(PLAYER_EVENTS.join(','), frozen.public_api.events.map((e) => e.name).join(','), 'события')

  const aggregators = frozen.attributes.find((item) => item.name === 'data-aggregator')?.allowed ?? []
  assertEqual(AGGREGATORS.join(','), aggregators.join(','), 'агрегаторы')

  const documented = frozen.attributes.map((item) => item.name).sort().join(',')
  assertEqual([...ALLOWED_ATTRIBUTES].sort().join(','), documented, 'набор атрибутов')

  const fixed = frozen.attributes.find((item) => item.name === 'disable-licensed')?.fixed_value
  assertEqual(fixed, 'false', 'зафиксированное значение disable-licensed в документе')
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

await check('конфликт озвучек отклоняется (PC-1)', () => {
  let thrown: unknown
  try {
    buildPlayerAttributes({ ...base, onlyVoice: 'voice-a', priorityVoice: 'voice-b' })
  } catch (error) {
    thrown = error
  }
  assert(thrown instanceof PlayerContractError, 'обе озвучки отправлены одновременно')

  // Только одна из них — допустимо и не меняет остальных атрибутов.
  const onlyVoice = buildPlayerAttributes({ ...base, onlyVoice: 'voice-a' })
  assertEqual(onlyVoice['only-voice'], 'voice-a', 'only-voice')
  assertEqual(onlyVoice['priority-voice'], undefined, 'priority-voice при заданном only-voice')

  const priority = buildPlayerAttributes({ ...base, priorityVoice: 'voice-b' })
  assertEqual(priority['priority-voice'], 'voice-b', 'priority-voice')
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
