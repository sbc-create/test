/**
 * Наполнение локального стенда демонстрационным контентом.
 *
 * Это ФИКСТУРЫ: названия сайтов помечены как стендовые, домены — localhost.
 * Публичные названия и домены production берутся только из пакета сайта; ничего
 * из этого файла в production попасть не должно, и фабрика это проверяет.
 */
import { getPayload } from 'payload'

import config from '../src/payload.config'
import { reset, seed, type Seeded } from './seed'

const payload = await getPayload({ config })

await reset(payload)
const base: Seeded = await seed(payload)

const rights = await payload.create({
  collection: 'rights-records',
  overrideAccess: true,
  data: {
    label: 'Стендовое соглашение',
    holder: 'Фиктивный правообладатель стенда',
    contractRef: 'STAND-FIXTURE-001',
    allowsPublication: true,
  } as never,
})

const genreNames = [
  ['Приключения', 'adventure'],
  ['Драма', 'drama'],
  ['Фэнтези', 'fantasy'],
]
const genres = []
for (const [name, slug] of genreNames) {
  genres.push(
    await payload.create({ collection: 'genres', overrideAccess: true, data: { name, slug } as never }),
  )
}

const studio = await payload.create({
  collection: 'studios',
  overrideAccess: true,
  data: { name: 'Стендовая студия', slug: 'stand-studio' } as never,
})

type SharedTitle = { id: string | number; slug: string; name: string }
const sharedTitles: SharedTitle[] = []

for (let index = 1; index <= 6; index += 1) {
  const title = await payload.create({
    collection: 'titles',
    overrideAccess: true,
    data: {
      primaryName: `Стендовый тайтл ${index}`,
      englishName: `Stand Title ${index}`,
      kind: index % 3 === 0 ? 'movie' : 'series',
      status: index % 2 === 0 ? 'completed' : 'ongoing',
      year: 2020 + (index % 5),
      factualSynopsis:
        `Фактическое описание стендового тайтла ${index}. Текст создан для проверки вёрстки и ` +
        'не описывает реальное произведение.',
      genres: [genres[index % genres.length]!.id],
      studios: [studio.id],
      rightsRecord: rights.id,
      playbackAggregator: 'kp',
      playbackTitleId: `stand-${index}`,
    } as never,
  })
  sharedTitles.push({ id: title.id, slug: `stand-title-${index}`, name: `Стендовый тайтл ${index}` })

  if (index % 3 !== 0) {
    for (let seasonNumber = 1; seasonNumber <= 2; seasonNumber += 1) {
      const season = await payload.create({
        collection: 'seasons',
        overrideAccess: true,
        data: { title: title.id, number: seasonNumber, name: `Сезон ${seasonNumber}` } as never,
      })
      for (let episodeNumber = 1; episodeNumber <= 4; episodeNumber += 1) {
        await payload.create({
          collection: 'episodes',
          overrideAccess: true,
          data: {
            season: season.id,
            number: episodeNumber,
            name: `Серия ${episodeNumber}`,
            airedAt: new Date(Date.UTC(2025, 0, episodeNumber + seasonNumber)).toISOString(),
            playbackAvailable: true,
          } as never,
        })
      }
    }
  }
}

// Расписание: события в ближайшие дни, чтобы страница расписания не была пустой.
const day = 24 * 3600 * 1000
const now = Date.now()
for (let index = 0; index < 6; index += 1) {
  const title = sharedTitles[index % sharedTitles.length]!
  await payload.create({
    collection: 'release-events',
    overrideAccess: true,
    data: {
      label: `${title.name}: серия ${index + 1}`,
      title: title.id,
      airsAt: new Date(now + (index + 1) * day).toISOString(),
      state: 'announced',
      precision: index % 4 === 3 ? 'day' : 'exact',
    } as never,
  })
}

/** У каждого сайта свой редакционный текст: одинаковый был бы дублем между сайтами. */
const editorialFor = (key: 'a' | 'b' | 'c', title: SharedTitle): string => {
  if (key === 'a') {
    return (
      `Полная карточка «${title.name}»: состав сезонов, порядок серий и статус выхода. ` +
      'Каталог собран так, чтобы за один заход было видно, что уже вышло, а что ещё ждём.'
    )
  }
  if (key === 'b') {
    return (
      `Когда выходят новые серии «${title.name}» и что уже доступно прямо сейчас. ` +
      'Страница обновляется по мере появления новых выпусков.'
    )
  }
  return (
    `Разбор редакции: чем «${title.name}» отличается от похожих тайтлов, кому подойдёт ` +
    'и с какого момента лучше начинать смотреть.'
  )
}

const legalBody =
  'Материалы сайта размещены с указанием источника и правообладателя. Если вы правообладатель ' +
  'и считаете, что материал размещён с нарушением, напишите нам через указанные контакты: ' +
  'обращение рассматривается и материал снимается до выяснения обстоятельств.'

for (const key of ['a', 'b', 'c'] as const) {
  const tenant = base.tenants[key].id
  const siteName = { a: 'Стенд A — каталог', b: 'Стенд B — расписание', c: 'Стенд C — редакция' }[key]

  const tenantTitleIds: (string | number)[] = []
  for (const title of sharedTitles) {
    const doc = await payload.create({
      collection: 'tenant-titles',
      overrideAccess: true,
      data: {
        tenant,
        title: title.id,
        slug: title.slug,
        editorialIntro: editorialFor(key, title),
        editorialAuthor: base.users.editorA.id,
        _status: 'published',
      } as never,
    })
    tenantTitleIds.push(doc.id)
  }

  const collection = await payload.create({
    collection: 'editorial-collections',
    overrideAccess: true,
    data: {
      tenant,
      name: `Подборка сайта ${key.toUpperCase()}`,
      slug: `stand-collection-${key}`,
      intro:
        `Подборка сайта ${key.toUpperCase()}: материалы отобраны редакцией стенда для проверки ` +
        'вёрстки списков и уникальности текстов между сайтами.',
      items: tenantTitleIds.slice(0, 4),
      _status: 'published',
    } as never,
  })

  for (let index = 1; index <= 3; index += 1) {
    await payload.create({
      collection: 'posts',
      overrideAccess: true,
      data: {
        tenant,
        headline: `Материал ${index} сайта ${key.toUpperCase()}`,
        slug: `stand-post-${key}-${index}`,
        lead: `Короткий лид материала ${index} сайта ${key.toUpperCase()}.`,
        body:
          `Текст материала ${index} сайта ${key.toUpperCase()}. Он написан отдельно для каждого сайта, ` +
          'потому что одинаковый текст на трёх доменах — это дубль, а не три сайта.',
        publishedAt: new Date(now - index * day).toISOString(),
        _status: 'published',
      } as never,
    })
  }

  const legal = await payload.create({
    collection: 'pages',
    overrideAccess: true,
    data: {
      tenant,
      name: 'Правообладателям',
      slug: 'rights',
      body: legalBody,
      _status: 'published',
    } as never,
  })

  // «Глобалы» сайта уже созданы базовой фикстурой — обновляем, а не плодим вторые.
  await payload.update({
    collection: 'site-settings',
    id: base.docs['site-settings']![key],
    overrideAccess: true,
    data: {
      siteName,
      tagline: { a: 'Каталог с полными данными о сезонах и сериях',
        b: 'Что выходит сегодня и на этой неделе',
        c: 'Разборы и подборки редакции' }[key],
      defaultDescription: `${siteName}: стендовый экземпляр для проверки вёрстки и SEO.`,
      commentsEnabled: true,
      premoderation: true,
      minIntervalSeconds: 30,
      maxLength: 4000,
      rulesText: 'Пишите по делу. Спойлеры прячьте, оскорбления удаляем.',
      legalPages: [legal.id],
      rightsNotice: legalBody,
    } as never,
  })

  await payload.update({
    collection: 'navigation',
    id: base.docs.navigation![key],
    overrideAccess: true,
    data: {
      label: 'Навигация',
      header: [
        { title: 'Каталог', href: '/catalog/' },
        { title: 'Расписание', href: '/schedule/' },
        { title: 'Подборки', href: '/collections/' },
        { title: 'Новости', href: '/news/' },
      ],
      footerGroups: [
        {
          title: 'О сайте',
          links: [{ title: 'Правообладателям', href: '/legal/rights/' }],
        },
      ],
    } as never,
  })

  const blocksByKey = {
    a: [
      { blockType: 'heroSpotlight', enabled: true, heading: 'Смотрят сейчас', items: tenantTitleIds.slice(0, 4) },
      { blockType: 'genreRails', enabled: true, heading: 'Жанры' },
      { blockType: 'latestUpdates', enabled: true, heading: 'Обновления каталога', limit: 12 },
      { blockType: 'editorialPicks', enabled: true, heading: 'Подборки', collections: [collection.id] },
    ],
    b: [
      { blockType: 'releaseSchedule', enabled: true, heading: 'Ближайшие выходы', days: 7 },
      { blockType: 'latestUpdates', enabled: true, heading: 'Свежие серии', limit: 12 },
      { blockType: 'newsFeed', enabled: true, heading: 'Новости выхода', limit: 6 },
    ],
    c: [
      { blockType: 'newsFeed', enabled: true, heading: 'Разборы редакции', limit: 6 },
      { blockType: 'editorialPicks', enabled: true, heading: 'Подборки', collections: [collection.id] },
      {
        blockType: 'textSection',
        enabled: true,
        heading: 'Как мы пишем',
        body: 'Каждый разбор пишется отдельно и не пересказывает карточку каталога.',
      },
    ],
  }

  await payload.update({
    collection: 'home-layout',
    id: base.docs['home-layout']![key],
    overrideAccess: true,
    data: { label: 'Главная', blocks: blocksByKey[key] } as never,
  })

  await payload.update({
    collection: 'player-profiles',
    id: base.docs['player-profiles']![key],
    overrideAccess: true,
    data: {
      name: `Плеер сайта ${key.toUpperCase()}`,
      publisherIdRef: `PLAYER_PUBLISHER_ID_${key.toUpperCase()}`,
      aggregator: 'kp',
      showBanner: false,
      showVoiceOnly: false,
    } as never,
  })

  // Индексация включается только у сайтов, где это нужно проверить: по умолчанию закрыто.
  await payload.update({
    collection: 'tenants',
    id: tenant,
    overrideAccess: true,
    data: { indexingEnabled: true } as never,
  })
}

console.log('стенд наполнен: 3 сайта, 6 тайтлов, расписание, подборки, новости, юридическая страница')
await payload.db.destroy?.()
process.exit(0)
