/**
 * Стенд трёх семейств шаблонов: portal_light, pulse, editorial.
 *
 * Зачем он есть. Полное приложение поднимается только с базой и секретами
 * Payload, а секреты этой полосе недоступны — значит боевую витрину она
 * проверить не может и не заявляет. Но семейство шаблонов — это компоненты и
 * тема, и они принадлежат полосе целиком. Стенд отрисовывает **настоящие**
 * компоненты настоящими стилями и даёт то, чего иначе нет вовсе: измеримую
 * страницу каждого семейства.
 *
 * Чего стенд не делает и не заменяет. Он не ходит в базу, не знает тенантов,
 * не проверяет изоляцию и не является приёмкой витрины. Его предмет — слой
 * шаблонов: типографика, плотность, карточки, навигация, композиция.
 *
 * Данные фиксированные и синтетические. Никакой случайности и никакого
 * «сегодня»: два прогона в разные дни обязаны дать одну и ту же страницу,
 * иначе эталон раскладки бессмысленен.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { SiteHeader } from '../src/components/SiteHeader'
import { SiteFooter } from '../src/components/SiteFooter'
import { CardGrid, type CardItem } from '../src/components/TitleCard'
import { Pagination } from '../src/components/Pagination'
import { Breadcrumbs } from '../src/components/Breadcrumbs'
import type { SiteContext } from '../src/lib/site'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const APP = path.resolve(HERE, '..')
const OUT = path.resolve(APP, 'var', 'family-stand')

/** Три семейства и витрины, которые их несут. Соответствие — из пакетов. */
const FAMILIES = [
  { theme: 'portal_light', site: 'site-a', siteName: 'Портал', profile: 'catalog_authority' },
  { theme: 'pulse', site: 'site-b', siteName: 'Пульс', profile: 'release_pulse' },
  { theme: 'editorial', site: 'site-c', siteName: 'Журнал', profile: 'editorial_guide' },
] as const

/** Названия разной длины: короткие имена скрывают перенос и обрезку. */
const TITLES = [
  'Тихий перевал',
  'В сердце бури: охотники за штормом',
  'Соляной антракт',
  'Прошлая жизнь белой змеи',
  'Дальний переучёт: история одной переправы',
  'Медный чертёж',
  'Поздний невод',
  'Бумажный маяк: возвращение к началу',
  'Лунный полустанок',
  'Стеклянный циферблат',
  'Пепельный обжиг',
  'Северный разъезд',
]

const cards: CardItem[] = TITLES.map((title, index) => ({
  href: `/catalog/zapis-${index + 1}`,
  title,
  meta: `${2016 + (index % 10)} · ${index % 3 === 0 ? 'сериал' : 'фильм'}`,
  image: null,
}))

const context = (family: (typeof FAMILIES)[number]): SiteContext =>
  ({
    tenant: { id: family.site, slug: family.site } as never,
    profile: family.profile as never,
    settings: null,
    navigation: {
      header: [
        { title: 'Каталог', href: '/catalog' },
        { title: 'Подборки', href: '/collections' },
        { title: 'Новости', href: '/news' },
        { title: 'Поиск', href: '/search' },
      ],
      footer: [
        { title: 'О проекте', href: '/about' },
        { title: 'Правообладателям', href: '/rights' },
      ],
    },
    siteName: family.siteName,
  }) as SiteContext

const page = (family: (typeof FAMILIES)[number]): string => {
  const site = context(family)
  const body = renderToStaticMarkup(
    <>
      <SiteHeader site={site} />
      <main id="content">
        <div className="container">
          <Breadcrumbs
            crumbs={[
              { title: 'Главная', href: '/' },
              { title: 'Каталог', href: '/catalog' },
            ]}
            origin="https://stand.invalid"
          />
          <h1>Каталог</h1>
          <p className="lede">
            Раздел показывает записи витрины. Текст подзаголовка нужен стенду затем, что
            типографика семейства измеряется на настоящем абзаце, а не на заголовке.
          </p>
          <CardGrid items={cards} empty="Записей нет." />
          <Pagination basePath="/catalog" page={2} totalPages={5} />
        </div>
      </main>
      <SiteFooter site={site} />
    </>,
  )

  const base = fs.readFileSync(path.join(APP, 'src', 'themes', 'base.css'), 'utf8')
  const themes = fs.readFileSync(path.join(APP, 'src', 'themes', 'themes.css'), 'utf8')
  return [
    '<!doctype html>',
    `<html lang="ru" data-theme="${family.theme}">`,
    '<head><meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    `<title>${family.siteName} — каталог</title>`,
    `<style>${base}\n${themes}</style>`,
    '</head><body>',
    body,
    '</body></html>',
  ].join('')
}

fs.mkdirSync(OUT, { recursive: true })
for (const family of FAMILIES) {
  fs.writeFileSync(path.join(OUT, `${family.theme}.html`), page(family))
}
fs.writeFileSync(
  path.join(OUT, 'index.json'),
  `${JSON.stringify({ families: FAMILIES.map((f) => f.theme), cards: cards.length }, null, 2)}\n`,
)
console.log(`стенд семейств собран: ${FAMILIES.length} страниц в ${OUT}`)
