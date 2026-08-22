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

// Тайтл без подтверждённых прав: страница обязана существовать, но без плеера.
const blockedRights = await payload.create({
  collection: 'rights-records',
  overrideAccess: true,
  data: {
    label: 'Права не подтверждены',
    holder: 'Правообладатель не установлен',
    contractRef: 'STAND-FIXTURE-BLOCKED',
    allowsPublication: false,
  } as never,
})

const blockedTitle = await payload.create({
  collection: 'titles',
  overrideAccess: true,
  data: {
    primaryName: 'Тайтл без прав на публикацию',
    kind: 'series',
    status: 'ongoing',
    year: 2024,
    factualSynopsis: 'Материал, для которого права на показ не подтверждены.',
    rightsRecord: blockedRights.id,
    playbackAggregator: 'kp',
    playbackTitleId: 'stand-blocked',
  } as never,
})
sharedTitles.push({ id: blockedTitle.id, slug: 'stand-title-blocked', name: 'Тайтл без прав на публикацию' })

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

/**
 * Заметка сайта о сезоне. Пишет её только каталожный сайт: он этот раздел
 * индексирует, а страница сезона без собственного текста — список серий,
 * одинаковый на любом домене.
 */
const seasonNotesFor = (key: 'a' | 'b' | 'c', title: SharedTitle): { season: number; note: string }[] => {
  if (key !== 'a') return []
  return [1, 2].map((season) => ({
    season,
    note:
      `Сезон ${season} «${title.name}»: порядок серий сверен с записями источника, включая случаи, ` +
      'когда номер выпуска в источнике и порядок выхода расходятся. Рядом с каждой серией указано, ' +
      'доступна ли она к просмотру — отсутствие видео мы показываем состоянием, а не пустой карточкой. ' +
      'Даты приведены к одному часовому поясу, поэтому список не «прыгает» между днями.',
  }))
}

const legalBodyFor = (key: 'a' | 'b' | 'c', siteName: string): string => {
  const common =
    `Страница относится к сайту «${siteName}». Если вы правообладатель и считаете, что материал ` +
    'размещён с нарушением, напишите через контакты ниже: обращение регистрируется, ' +
    'а спорный материал снимается с публикации до выяснения обстоятельств.'
  if (key === 'a') {
    return (
      `${common} Каталог хранит только фактические сведения о тайтлах: названия, годы, состав ` +
      'сезонов и серий, студии и жанры. Источник каждой записи фиксируется вместе с датой ' +
      'получения, поэтому по любому полю можно показать, откуда оно взялось. Видео размещается ' +
      'исключительно при подтверждённом договоре; при отсутствии подтверждения страница остаётся ' +
      'доступной, но проигрыватель на ней не показывается вовсе.'
    )
  }
  if (key === 'b') {
    return (
      `${common} Расписание строится из дат выхода серий и обновляется по мере поступления новых ` +
      'сведений. Неизвестное время выхода отображается как неизвестное и не заменяется ' +
      'приблизительным: неточная дата, выданная за точную, вводит читателя в заблуждение. ' +
      'Перенос или отмена выпуска отмечаются отдельным состоянием, а прежняя дата не стирается.'
    )
  }
  return (
    `${common} Редакционные материалы пишутся сотрудниками сайта и не пересказывают карточки ` +
    'каталога. Оценки и выводы принадлежат авторам, факты приводятся со ссылкой на источник. ' +
    'Цитаты из чужих материалов приводятся в объёме, оправданном разбором, с указанием автора ' +
    'и издания, и не заменяют собой самостоятельный текст.'
  )
}

const collectionIntroFor = (key: 'a' | 'b' | 'c'): string =>
  ({
    a:
      'Подборка собрана по признаку завершённости: сюда попадают тайтлы, у которых известны все ' +
      'сезоны и все серии, а даты выхода сверены с записями источника. Такой список удобен, когда ' +
      'нужно посмотреть историю целиком и не упереться в обрыв на середине сезона.',
    b:
      'Здесь собрано то, что выходит прямо сейчас: у каждого пункта есть ближайшая дата новой серии ' +
      'и отметка, вышла ли она уже. Список пересобирается по мере обновления расписания, поэтому ' +
      'порядок в нём меняется чаще, чем в остальных разделах.',
    c:
      'Редакционная подборка: не рейтинг и не топ по просмотрам, а несколько работ, о которых у нас ' +
      'есть что сказать. К каждой прилагается разбор с объяснением, кому она подойдёт и с какого ' +
      'момента её лучше смотреть.',
  })[key]

/** Материалы разных сайтов пишутся о разном: общая только фактура каталога. */
const POST_HEADLINES = {
  a: [
    'Добавлен ещё один законченный тайтл: сезоны, порядок серий и даты',
    'Как размечены студии и жанры и почему фильтр даёт предсказуемый результат',
    'Путаница с нумерацией сезонов: какой вариант показываем и почему',
  ],
  b: [
    'Неделя выхода: четыре продолжения и один финал',
    'Перенос на неделю: что изменилось в расписании и когда',
    'Что вышло за семь дней и какие серии стали доступны',
  ],
  c: [
    'Почему второй сезон смотрится иначе, хотя продолжает первый',
    'С чего начинать и что можно пропустить без потери смысла',
    'Пересмотрели спустя год и изменили часть оценок',
  ],
} as const

const postBodyFor = (key: 'a' | 'b' | 'c', index: number): string => {
  const variants = {
    a: [
      'Каталог пополнился ещё одной законченной работой: добавлены все сезоны, порядок серий и ' +
        'даты выхода, сверенные с записями источника. Для каждой серии указано, доступна ли она ' +
        'к просмотру, потому что отсутствие видео — это состояние, а не повод прятать страницу.',
      'Мы разметили студии и жанры так, чтобы фильтр каталога давал предсказуемый результат: одно ' +
        'название — один набор жанров, без дублей и без «похожих» тегов, придуманных ради страницы. ' +
        'Спорные случаи отправлены на ручную проверку и до неё в каталог не попадают.',
      'Разбор частой путаницы с нумерацией сезонов: у части тайтлов источник считает вторую часть ' +
        'продолжением, а не новым сезоном. Мы храним оба варианта нумерации и показываем тот, ' +
        'который совпадает с порядком выхода серий, а альтернативный указываем рядом.',
    ],
    b: [
      'На этой неделе выходят четыре продолжения и один финал. Ниже — время выхода по каждому дню; ' +
        'там, где источник не называет точного часа, мы честно пишем «время не указано», а не ' +
        'подставляем полночь ради ровной таблицы.',
      'Один из тайтлов перенесли на неделю: студия объявила паузу между сериями. Прежняя дата ' +
        'осталась в расписании со статусом «перенесено», чтобы было видно, что именно изменилось ' +
        'и когда. Мы не переписываем историю расписания задним числом.',
      'Короткая сводка: что уже вышло за прошедшие семь дней и какие серии стали доступны к ' +
        'просмотру. Если серия вышла, но доступа к ней нет, она отмечена отдельно — так понятнее, ' +
        'чем пустая карточка без объяснения.',
    ],
    c: [
      'Разбор: почему второй сезон смотрится иначе, хотя сюжетно продолжает первый. Дело в смене ' +
        'постановщика и в другом ритме монтажа; мы сравнили несколько сцен, где это заметнее всего, ' +
        'и объяснили, что именно поменялось в подаче.',
      'Путеводитель для тех, кто начинает: с чего заходить, какие части можно пропустить без потери ' +
        'смысла и где авторы намеренно оставляют вопросы без ответа. Мнение редакции, а не пересказ ' +
        'аннотации из каталога.',
      'Мы пересмотрели работу спустя год и изменили часть оценок. В тексте объясняем, что именно ' +
        'перестало работать, а что, наоборот, стало понятнее со временем. Прежние формулировки ' +
        'сохранены в конце материала, чтобы правку можно было проверить.',
    ],
  }
  return variants[key][(index - 1) % variants[key].length]!
}

for (const key of ['a', 'b', 'c'] as const) {
  const tenant = base.tenants[key].id
  // Документы базовой фикстуры изоляции — служебные заглушки без текста. На стенде
  // они бы стали пустыми индексируемыми страницами, поэтому удаляются.
  for (const collection of ['tenant-titles', 'pages', 'posts', 'editorial-collections'] as const) {
    await payload.delete({
      collection,
      where: { tenant: { equals: tenant } },
      overrideAccess: true,
    })
  }
  const siteName = { a: 'Стенд A — каталог', b: 'Стенд B — расписание', c: 'Стенд C — редакция' }[key]!

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
        seasonNotes: seasonNotesFor(key, title),
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
      name: { a: 'Законченные сериалы каталога', b: 'Выходят на этой неделе', c: 'С чего начать знакомство' }[key]!,
      slug: `stand-collection-${key}`,
      intro: collectionIntroFor(key),
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
        headline: POST_HEADLINES[key][(index - 1) % POST_HEADLINES[key].length]!,
        slug: `stand-post-${key}-${index}`,
        // Лид — первое предложение собственного текста, а не шаблон с номером:
        // одинаковые лиды на трёх сайтах — это дубль, который ловят ворота.
        lead: postBodyFor(key, index).split('. ')[0]! + '.',
        body: postBodyFor(key, index),
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
      name: {
        a: 'Права на данные каталога',
        b: 'Права и источники расписания',
        c: 'Права на редакционные материалы',
      }[key],
      slug: 'rights',
      body: legalBodyFor(key, siteName),
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
      defaultDescription: {
        a: 'Каталог тайтлов с сезонами, сериями и сверенными датами выхода.',
        b: 'Расписание выхода серий: что вышло сегодня и что ожидается на неделе.',
        c: 'Разборы и путеводители редакции: с чего начинать и что смотреть дальше.',
      }[key]!,
      commentsEnabled: true,
      premoderation: true,
      minIntervalSeconds: 30,
      maxLength: 4000,
      rulesText: 'Пишите по делу. Спойлеры прячьте, оскорбления удаляем.',
      legalPages: [legal.id],
      rightsNotice: legalBodyFor(key, siteName),
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
      { blockType: 'newsFeed', enabled: true, heading: 'Новости выхода', limit: 6 },
      {
        blockType: 'textSection',
        enabled: true,
        heading: 'Как читать расписание',
        body:
          'Время указано так, как его называет источник. Если точного часа нет, мы пишем «время ' +
          'не указано» и не подставляем полночь ради ровной таблицы. Перенос сохраняет прежнюю ' +
          'дату со статусом «перенесено», чтобы было видно, что именно изменилось.',
      },
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
