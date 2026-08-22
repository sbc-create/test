/**
 * Темы обязаны различаться, а не быть перекрашенной копией друг друга.
 *
 * Проверяется и то, и другое: набор токенов (цвет, шрифт, контейнер, плотность
 * сетки, форма карточки, скругление) и структурная компоновка (шапка, место
 * поиска, форма карточки, страница произведения, порядок модулей главной).
 * Совпадение двух тем по любому из этих срезов роняет прогон.
 */
import { readFileSync } from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

import { THEME_LAYOUTS, layoutFor } from '../src/themes/layouts'
import { SEO_PROFILES } from '../src/seo/profiles'
import { assert, assertEqual, check, summary } from './harness'

const dirname = path.dirname(fileURLToPath(import.meta.url))
const css = readFileSync(path.resolve(dirname, '../src/themes/themes.css'), 'utf8')

/** Токены темы из CSS: читаем то, что реально уедет в браузер. */
const tokensOf = (theme: string): Record<string, string> => {
  const match = new RegExp(`\\[data-theme='${theme}'\\]\\s*\\{([^}]*)\\}`, 'm').exec(css)
  if (!match) return {}
  const tokens: Record<string, string> = {}
  for (const line of match[1]!.split(';')) {
    const [name, value] = line.split(':')
    if (name && value) tokens[name.trim()] = value.trim()
  }
  return tokens
}

const CINEMA_THEMES = ['series_dark', 'film_editorial', 'premiere_signal', 'guide_warm'] as const
const ALL_THEMES = Object.keys(THEME_LAYOUTS)

const REQUIRED_TOKENS = [
  '--bg', '--surface', '--fg', '--muted', '--border', '--link', '--accent', '--focus',
  '--font-body', '--font-display', '--container', '--grid-gap', '--card-min', '--radius', '--h1',
]

await check('у каждой темы объявлен полный набор токенов', () => {
  for (const theme of ALL_THEMES) {
    const tokens = tokensOf(theme)
    assert(Object.keys(tokens).length > 0, `тема ${theme} отсутствует в themes.css`)
    const missing = REQUIRED_TOKENS.filter((token) => !(token in tokens))
    assertEqual(missing.join(','), '', `${theme}: не объявлены токены`)
  }
})

await check('четыре темы кинотеатров различаются визуальной системой', () => {
  // Сравниваем по каждому измерению отдельно: одинаковый фон при разном акценте
  // — это всё ещё одна тема в двух оттенках.
  for (const token of ['--bg', '--accent', '--font-body', '--container', '--card-min', '--radius']) {
    const values = CINEMA_THEMES.map((theme) => tokensOf(theme)[token])
    assertEqual(new Set(values).size, CINEMA_THEMES.length,
      `${token}: значения повторяются (${values.join(' | ')})`)
  }
})

await check('шрифт заголовков не одинаков у всех четырёх', () => {
  const displays = CINEMA_THEMES.map((theme) => tokensOf(theme)['--font-display'])
  assert(new Set(displays).size >= 3, `гарнитур заголовков всего ${new Set(displays).size}`)
})

await check('светлые и тёмные темы есть в обеих половинах четвёрки', () => {
  // Грубая оценка светлоты по первому каналу hex: четыре тёмных или четыре
  // светлых темы — это один визуальный класс, а не четыре самостоятельных сайта.
  const light = CINEMA_THEMES.filter((theme) => {
    const bg = tokensOf(theme)['--bg'] ?? '#000000'
    return parseInt(bg.slice(1, 3), 16) > 0x80
  })
  assert(light.length >= 1 && light.length <= 3, `светлых тем ${light.length} из ${CINEMA_THEMES.length}`)
})

await check('структурная компоновка различается у всех четырёх', () => {
  for (const field of ['header', 'search', 'card', 'titlePage'] as const) {
    const values = CINEMA_THEMES.map((theme) => layoutFor(theme)[field])
    assertEqual(new Set(values).size, CINEMA_THEMES.length,
      `${field}: повторяется (${values.join(' | ')})`)
  }
})

await check('порядок модулей главной свой у каждой темы кинотеатра', () => {
  const orders = CINEMA_THEMES.map((theme) => layoutFor(theme).homeModules.join(','))
  assertEqual(new Set(orders).size, CINEMA_THEMES.length, `порядков всего ${new Set(orders).size}`)
  for (const theme of CINEMA_THEMES) {
    assert(layoutFor(theme).homeModules.length >= 4, `${theme}: слишком мало модулей главной`)
  }
})

await check('микротексты интерфейса различаются', () => {
  for (const field of ['searchAction', 'emptyList', 'more'] as const) {
    const values = CINEMA_THEMES.map((theme) => layoutFor(theme).tone[field])
    assertEqual(new Set(values).size, CINEMA_THEMES.length, `${field}: повторяется`)
  }
})

await check('у каждой темы из профилей есть описанная компоновка', () => {
  // Тема без дескриптора получила бы чужую структуру молча.
  for (const theme of ALL_THEMES) {
    assert(Boolean(layoutFor(theme)), theme)
  }
  assert(Object.keys(SEO_PROFILES).length >= CINEMA_THEMES.length, 'профилей меньше, чем тем кинотеатров')
})

await check('неизвестная тема не подменяется похожей', () => {
  let thrown = false
  try {
    layoutFor('no_such_theme')
  } catch {
    thrown = true
  }
  assert(thrown, 'неизвестная тема принята без ошибки')
})

/** Относительная яркость по WCAG. */
const luminance = (hex: string): number => {
  const value = hex.trim().replace('#', '')
  const channels = [0, 2, 4].map((offset) => parseInt(value.slice(offset, offset + 2), 16) / 255)
  const linear = channels.map((channel) =>
    channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
  )
  return 0.2126 * linear[0]! + 0.7152 * linear[1]! + 0.0722 * linear[2]!
}

const contrast = (left: string, right: string): number => {
  const a = luminance(left)
  const b = luminance(right)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

await check('контраст каждой темы не ниже 4.5:1 на ключевых парах', () => {
  // Проверяем в тестах, а не только браузерным аудитом: axe находит нарушение
  // на конкретной странице, а тема ломает контраст сразу на всех.
  const pairs = [
    ['--fg', '--bg', 'основной текст на фоне'],
    ['--muted', '--bg', 'приглушённый текст на фоне'],
    ['--link', '--bg', 'ссылка на фоне'],
    ['--accent-fg', '--accent', 'текст кнопки на акценте'],
    ['--accent', '--surface', 'акцент как текст на поверхности'],
  ] as const
  for (const theme of ALL_THEMES) {
    const tokens = tokensOf(theme)
    for (const [left, right, label] of pairs) {
      const first = tokens[left]
      const second = tokens[right]
      if (!first?.startsWith('#') || !second?.startsWith('#')) continue
      const ratio = contrast(first, second)
      assert(ratio >= 4.5, `${theme}: ${label} — ${ratio.toFixed(2)}:1 (${first} / ${second})`)
    }
  }
})

process.exit(summary())
