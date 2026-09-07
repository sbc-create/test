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
import { HomeBlocks } from '../src/components/HomeBlocks'
import { Player } from '../src/components/Player'
import { PLAYER_SCRIPT_URL } from '../src/player/contract'
import type { SiteContext } from '../src/lib/site'
import { CONSUMED_SETTINGS } from '../src/lib/admin-contract'

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

/**
 * Две витрины на семейство с заведомо разными настройками.
 *
 * Нужны затем, что изоляцию нельзя проверить на одной витрине: утечка видна
 * только тогда, когда есть у кого утечь. Значения различаются в каждом поле
 * контракта — совпадающее значение не отличило бы «взяли своё» от «взяли
 * чужое и случайно совпало».
 */
const TENANTS = {
  a: {
    suffix: 'tenant-a',
    siteName: 'Первая витрина',
    rightsNotice: 'Права первой витрины',
    tagline: 'Подпись первой витрины',
    nav: ['Каталог', 'Подборки', 'Новости'],
  },
  b: {
    suffix: 'tenant-b',
    siteName: 'Вторая витрина',
    rightsNotice: 'Права второй витрины',
    tagline: 'Подпись второй витрины',
    nav: ['Расписание', 'Обзоры'],
  },
} as const

type TenantKey = keyof typeof TENANTS

const context = (
  family: (typeof FAMILIES)[number],
  tenant: TenantKey | null = null,
): SiteContext => {
  const t = tenant ? TENANTS[tenant] : null
  const navTitles = t ? t.nav : ['Каталог', 'Подборки', 'Новости', 'Поиск']
  return {
    tenant: { id: family.site, slug: family.site } as never,
    profile: family.profile as never,
    settings: t
      ? {
          // Заполняются все поля контракта: пропущенное поле проверило бы
          // поведение при пустоте, а не потребление, и это другой предмет.
          commentsEnabled: true,
          defaultDescription: `Описание витрины ${t.siteName}`,
          maxLength: 4000,
          rightsNotice: t.rightsNotice,
          rulesText: `Правила витрины ${t.siteName}`,
          tagline: t.tagline,
        }
      : null,
    navigation: {
      header: navTitles.map((title) => ({ title, href: `/${title.toLowerCase()}` })),
      footerGroups: [
        {
          title: 'О сайте',
          items: [{ title: 'О проекте', href: '/about' }],
        },
      ],
    },
    siteName: t ? t.siteName : family.siteName,
  } as SiteContext
}

/** Поверхности витрины. Каждая — отдельная страница стенда.
 *
 * Одной страницы каталога мало: требование владельца перечисляет пятнадцать
 * поверхностей, и семейство, различимое на каталоге, может совпадать с
 * соседним на главной или на странице произведения. Проверять надо то, что
 * названо, а не то, что первым собралось.
 */
const SURFACES = ['catalog', 'home', 'title', 'search', 'search-empty'] as const
type Surface = (typeof SURFACES)[number]

const HOME_BLOCKS = [
  { blockType: 'heroSpotlight', heading: 'Смотрят сейчас', items: [] },
  { blockType: 'latestUpdates', heading: 'Последние поступления' },
  { blockType: 'genreRails', heading: 'Жанры' },
  {
    blockType: 'textSection',
    heading: 'О витрине',
    text: 'Раздел собран редакцией. Текст нужен стенду затем, что типографика '
      + 'семейства измеряется на настоящем абзаце, а не на заголовке.',
  },
]

const HOME_DATA = {
  latest: [],
  posts: [],
  schedule: [
    { label: 'Соляной антракт, серия 4', airsAt: '2026-09-08', href: '/catalog/zapis-3' },
    { label: 'Медный чертёж, серия 2', airsAt: '2026-09-09', href: null },
  ],
  genres: [
    { id: 1, name: 'Драма', slug: 'drama' },
    { id: 2, name: 'Комедия', slug: 'comedy' },
    { id: 3, name: 'Детектив', slug: 'detective' },
  ],
}

const surfaceBody = (surface: Surface, site: SiteContext) => {
  if (surface === 'home') {
    return (
      <>
        <h1>{site.siteName}</h1>
        <HomeBlocks site={site} blocks={HOME_BLOCKS} data={HOME_DATA} />
      </>
    )
  }
  if (surface === 'title') {
    const item = cards[1]
    return (
      <>
        <Breadcrumbs
          crumbs={[
            { title: 'Главная', href: '/' },
            { title: 'Каталог', href: '/catalog' },
          ]}
          origin="https://stand.invalid"
        />
        <h1>{item.title}</h1>
        <p className="lede">
          Описание записи. Нужно стенду затем, что страница произведения — это прежде
          всего текст, и семейства расходятся именно на нём: шириной колонки, размером
          и интерлиньяжем.
        </p>
        <dl className="facts">
          <dt>Год</dt>
          <dd>2019</dd>
          <dt>Тип</dt>
          <dd>Сериал</dd>
          <dt>Сезонов</dt>
          <dd>2</dd>
          <dt>Серий</dt>
          <dd>16</dd>
        </dl>
        <Player
          attributes={
            {
              ident: 'player-stand',
              publisherId: '1',
              titleId: '1',
              aggregator: 'kp',
            } as never
          }
          scriptUrl={PLAYER_SCRIPT_URL}
          season={1}
          episode={1}
          unavailableText="Источник видео сейчас недоступен."
        />
      </>
    )
  }
  if (surface === 'search') {
    return (
      <>
        <h1>Поиск</h1>
        <form className="header-search" role="search" action="/search" method="get">
          <label className="visually-hidden" htmlFor="q">Строка поиска</label>
          <input id="q" name="q" type="search" defaultValue="перевал" />
          <button type="submit">Найти</button>
        </form>
        <p className="count">Найдено: {cards.length}.</p>
        <CardGrid items={cards} empty="Ничего не нашлось." />
      </>
    )
  }
  if (surface === 'search-empty') {
    return (
      <>
        <h1>Поиск</h1>
        <form className="header-search" role="search" action="/search" method="get">
          <label className="visually-hidden" htmlFor="q">Строка поиска</label>
          <input id="q" name="q" type="search" defaultValue="ыыыжжж" />
          <button type="submit">Найти</button>
        </form>
        <p className="count">По запросу «ыыыжжж» ничего не нашлось.</p>
        <CardGrid items={[]} empty="Ничего не нашлось. Попробуйте другое написание." />
      </>
    )
  }
  return (
    <>
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
    </>
  )
}

const page = (
  family: (typeof FAMILIES)[number],
  tenant: TenantKey | null = null,
  surface: Surface = 'catalog',
): string => {
  const site = context(family, tenant)
  const body = renderToStaticMarkup(
    <>
      <SiteHeader site={site} />
      <main id="content">
        <div className="container">
          {surfaceBody(surface, site)}
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
let pages = 0
for (const family of FAMILIES) {
  for (const surface of SURFACES) {
    const name = surface === 'catalog' ? `${family.theme}.html` : `${family.theme}-${surface}.html`
    fs.writeFileSync(path.join(OUT, name), page(family, null, surface))
    pages += 1
  }
  for (const key of Object.keys(TENANTS) as TenantKey[]) {
    fs.writeFileSync(
      path.join(OUT, `${family.theme}-${TENANTS[key].suffix}.html`), page(family, key))
    pages += 1
  }
}
fs.writeFileSync(
  path.join(OUT, 'index.json'),
  `${JSON.stringify(
    {
      families: FAMILIES.map((f) => f.theme),
      surfaces: SURFACES,
      tenants: Object.fromEntries(
        (Object.keys(TENANTS) as TenantKey[]).map((k) => [k, TENANTS[k]])),
      consumedSettings: CONSUMED_SETTINGS,
      cards: cards.length,
    },
    null,
    2,
  )}\n`,
)
console.log(`стенд семейств собран: ${pages} страниц в ${OUT}`)
