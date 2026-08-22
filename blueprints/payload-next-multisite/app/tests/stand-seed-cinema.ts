/**
 * Стендовые данные четвёрки кинотеатров.
 *
 * Это фикстуры: все названия выдуманы и помечены словом «стенд», ни одно из них
 * не описывает реальное произведение. Тексты написаны для этого репозитория;
 * ничего заимствованного здесь нет и быть не может — референсы недоступны из
 * среды, что зафиксировано в docs/reference/CINEMA_REFERENCES_UI_AUDIT.md.
 *
 * Данные подобраны так, чтобы работали правила владения: вышедшие сериальные
 * формы принадлежат сайту D, вышедшие полнометражные — сайту E, ещё не вышедшее
 * — сайту F, а сайт G живёт подборками и маршрутами просмотра.
 */
import type { Payload } from 'payload'

export type CinemaKey = 'd' | 'e' | 'f' | 'g'

type TenantRef = { id: string | number; slug: string; domain: string }

const PROFILES = {
  d: { seoProfile: 'series_hub', theme: 'series_dark', name: 'Сайт D' },
  e: { seoProfile: 'film_library', theme: 'film_editorial', name: 'Сайт E' },
  f: { seoProfile: 'premiere_radar', theme: 'premiere_signal', name: 'Сайт F' },
  g: { seoProfile: 'curated_guide', theme: 'guide_warm', name: 'Сайт G' },
} as const satisfies Record<CinemaKey, { seoProfile: string; theme: string; name: string }>

const SITE_NAMES: Record<CinemaKey, string> = {
  d: 'Стенд D — сериалы',
  e: 'Стенд E — фильмы',
  f: 'Стенд F — премьеры',
  g: 'Стенд G — подборки',
}

const SITE_DESCRIPTIONS: Record<CinemaKey, string> = {
  d: 'Сериалы с полным составом сезонов, порядком серий и статусом выхода.',
  e: 'Полнометражное кино с навигацией по жанрам, годам выхода и странам производства.',
  f: 'Подтверждённые даты премьер, переносы и произведения, вышедшие на этой неделе.',
  g: 'Редакционные подборки и маршруты просмотра с объяснением каждого шага.',
}

const TAGLINES: Record<CinemaKey, string> = {
  d: 'Сезоны и серии без пропусков',
  e: 'Кино по жанрам, годам и странам',
  f: 'Только подтверждённые даты',
  g: 'С чего начать и что дальше',
}

/** Выдуманные названия стенда. Ни одно не описывает реальное произведение. */
const SERIES_FIXTURES = [
  { name: 'Северный маршрут (стенд)', slug: 'severny-marshrut', year: 2021, kind: 'series', seasons: 2, genre: 0, country: 0, status: 'ongoing' },
  { name: 'Тихий разъезд (стенд)', slug: 'tihiy-razyezd', year: 2022, kind: 'series', seasons: 2, genre: 1, country: 0 },
  { name: 'Двенадцать писем (стенд)', slug: 'dvenadcat-pisem', year: 2023, kind: 'miniseries', seasons: 1, genre: 1, country: 1 },
]

const FILM_FIXTURES = [
  { name: 'Долгая переправа (стенд)', slug: 'dolgaya-pereprava', year: 2024, kind: 'movie', genre: 1, country: 0 },
  { name: 'Сад на крыше (стенд)', slug: 'sad-na-kryshe', year: 2024, kind: 'movie', genre: 2, country: 1 },
  { name: 'Пятый этаж (стенд)', slug: 'pyaty-etazh', year: 2023, kind: 'movie', genre: 0, country: 0 },
  { name: 'Бумажный флот (стенд)', slug: 'bumazhny-flot', year: 2022, kind: 'animated_film', genre: 2, country: 1 },
]

const UPCOMING_FIXTURES = [
  {
    name: 'Обратный отсчёт (стенд)', slug: 'obratny-otschet', year: 2026, kind: 'series',
    releaseState: 'soon', releaseDate: '2026-11-12T00:00:00.000Z', releaseDateConfirmed: true,
    releaseSourceRef: 'STAND-SOURCE-2026-11-12', genre: 0, country: 0,
  },
  {
    name: 'Второй берег (стенд)', slug: 'vtoroy-bereg', year: 2027, kind: 'movie',
    releaseState: 'announced', releaseDate: null, releaseDateConfirmed: false,
    releaseSourceRef: 'STAND-SOURCE-ANNOUNCE-02', genre: 1, country: 1,
  },
  {
    name: 'Ночная смена (стенд)', slug: 'nochnaya-smena', year: 2026, kind: 'series',
    releaseState: 'delayed', releaseDate: null, releaseDateConfirmed: false,
    releaseSourceRef: 'STAND-SOURCE-DELAY-07', previousReleaseDate: '2026-09-01T00:00:00.000Z',
    genre: 2, country: 0,
  },
  {
    name: 'Тёплый сезон (стенд)', slug: 'teply-sezon', year: 2027, kind: 'movie',
    releaseState: 'date_unknown', releaseDate: null, releaseDateConfirmed: false,
    releaseSourceRef: 'STAND-SOURCE-UNKNOWN-03', genre: 0, country: 1,
  },
]

/** Редакционное вступление сайта к произведению: у каждого сайта своё. */
const introFor = (key: CinemaKey, name: string): string => {
  if (key === 'd') {
    return (
      `Карточка «${name}» на стенде сериалов: состав сезонов, порядок серий и отметка о том, ` +
      'доступна ли серия к просмотру. Порядок сверен с записями источника, включая случаи, когда ' +
      'нумерация выпусков расходится с порядком выхода.'
    )
  }
  if (key === 'e') {
    return (
      `«${name}» в стендовой кинотеке: год выхода, страна производства и жанровые пометки. ` +
      'Описание собрано из фактических полей каталога и не пересказывает аннотацию правообладателя.'
    )
  }
  if (key === 'f') {
    return (
      `«${name}» в стендовом календаре премьер: текущее состояние выхода и ссылка на подтверждение. ` +
      'Дата без подтверждённого источника здесь не показывается вовсе.'
    )
  }
  return (
    `«${name}» на стенде подборок: страница ведёт к спискам и маршрутам просмотра, в которых ` +
    'произведение упомянуто. Отдельной страницей произведения этот сайт не занимается.'
  )
}

const LEGAL_TITLES: Record<CinemaKey, string> = {
  d: 'Права на данные о сериалах',
  e: 'Права на данные кинотеки',
  f: 'Права на данные календаря премьер',
  g: 'Права на редакционные подборки',
}

const legalBodyFor = (key: CinemaKey, siteName: string): string => {
  const common =
    `Страница относится к сайту «${siteName}». Если вы правообладатель и считаете, что материал ` +
    'размещён с нарушением, напишите через контакты в подвале: обращение регистрируется, а спорный ' +
    'материал снимается с публикации до выяснения обстоятельств.'
  const specific: Record<CinemaKey, string> = {
    d: ' Состав сезонов и порядок серий — фактические сведения, они приводятся со ссылкой на источник '
      + 'и обновляются при его изменении. Редакционные вступления написаны редакцией этого сайта.',
    e: ' Год выхода, страна производства и жанр — фактические сведения из записей источника. '
      + 'Тексты кинообзоров написаны редакцией и не являются пересказом чужих рецензий.',
    f: ' Даты выхода публикуются только при подтверждённом источнике; при переносе прежняя дата '
      + 'сохраняется, а не переписывается задним числом. Снятые анонсы удаляются вместе со страницей.',
    g: ' Подборки и маршруты просмотра — редакционный текст этого сайта. Фактические сведения о '
      + 'произведениях берутся из общего каталога и принадлежат их источникам.',
  }
  return common + specific[key]
}

const POSTS: Record<CinemaKey, { headline: string; body: string }[]> = {
  d: [
    {
      headline: 'Как на стенде считаются сезоны и серии',
      body:
        'Порядок серий на стенде хранится дважды: как номер выпуска в источнике и как позиция в '
        + 'порядке выхода. Показываем второй, а первый указываем рядом — так карточка остаётся '
        + 'понятной и тем, кто сверяется с источником. Если серия вышла, но доступа к ней нет, она '
        + 'помечается отдельно, а не пропадает из списка.',
    },
    {
      headline: 'Закрытые сериалы и продолжающиеся: чем отличается страница',
      body:
        'У завершённого сериала состав сезонов больше не меняется, поэтому страница показывает '
        + 'полный список сразу. У продолжающегося сверху остаётся отметка о ближайшей серии, а '
        + 'список дополняется по мере выхода. Никаких предположений о будущих сериях страница не '
        + 'делает: их просто нет до подтверждения.',
    },
    {
      headline: 'Почему страница сезона появляется не всегда',
      body:
        'Страница сезона на стенде индексируется только тогда, когда редакция написала о нём '
        + 'собственную заметку. Список серий сам по себе одинаков на любом сайте, и отдельная '
        + 'страница ради него означала бы дубль. Без заметки сезон остаётся навигацией внутри '
        + 'карточки сериала.',
    },
  ],
  e: [
    {
      headline: 'Что мы считаем полезной посадочной страницей жанра',
      body:
        'Страница жанра на стенде существует, только если у неё есть собственный заголовок, '
        + 'описание и входящие ссылки из раздела. Произвольная комбинация фильтров такой страницей '
        + 'не становится: она отдаётся с noindex и указывает canonical на чистый раздел. Иначе '
        + 'каждый новый фильтр добавлял бы адрес без содержания.',
    },
    {
      headline: 'Год и страна в карточке фильма: откуда берутся значения',
      body:
        'Год выхода и страна производства — фактические поля каталога, а не догадка по названию. '
        + 'Если поле пустое, карточка так и показывает: пустое поле честнее подставленного. '
        + 'Фильтр по году на стенде предлагает только те годы, в которых действительно есть '
        + 'материалы.',
    },
    {
      headline: 'Почему у кинотеки широкие кадры, а не постеры',
      body:
        'Полнометражное кино на стенде показано кадрами 16:9 в три колонки: такой список читают, '
        + 'а не пролистывают. Плотную сетку постеров мы оставили сайту сериалов, где сценарий '
        + 'другой — быстро найти нужное среди сотен карточек.',
    },
  ],
  f: [
    {
      headline: 'Правило календаря: дата только с подтверждением',
      body:
        'Состояние «скоро» на стенде требует подтверждённой даты и ссылки на источник. Анонс без '
        + 'источника создать нельзя — модель данных отклоняет запись до сохранения. Поэтому в '
        + 'календаре не бывает строк вида «ожидается осенью» без объяснения, откуда это известно.',
    },
    {
      headline: 'Перенос не стирает прежнюю дату',
      body:
        'При переносе прежняя дата остаётся в карточке рядом с новой. История расписания не '
        + 'переписывается задним числом: посетителю важно видеть, что именно изменилось, а не '
        + 'только итоговое значение. Запись без прежней даты в состоянии «перенесено» не '
        + 'сохраняется.',
    },
    {
      headline: 'Что происходит с анонсом после выхода',
      body:
        'Как только состояние меняется на «вышло», произведение перестаёт принадлежать календарю '
        + 'и появляется на профильном сайте — сериальном или кинотеке. Это не ручная операция '
        + 'редакции, а следствие правила владения: два сайта не могут индексировать одну страницу '
        + 'одновременно.',
    },
  ],
  g: [
    {
      headline: 'Чем маршрут просмотра отличается от списка',
      body:
        'В маршруте у каждого шага есть объяснение, почему он именно здесь и что даёт зрителю. '
        + 'Без такого объяснения это обычный список под другим названием, поэтому модель данных '
        + 'требует комментарий к каждому шагу и не сохраняет маршрут без него.',
    },
    {
      headline: 'Почему подборок мало и они не создаются автоматически',
      body:
        'Массовая генерация подборок даёт сотни страниц, между которыми нет разницы. На стенде '
        + 'подборка существует только с написанным редакцией вступлением, иначе она не '
        + 'индексируется. Ценность подборки — в объяснении выбора, а не в количестве карточек.',
    },
    {
      headline: 'Связи между произведениями: только настоящие',
      body:
        'Блок «похожее» на стенде строится по реальным связям каталога, а не по совпадению жанра. '
        + 'Если связей нет, блок не показывается вовсе — пустой блок с подписью «похожее» вводит '
        + 'в заблуждение сильнее, чем его отсутствие.',
    },
  ],
}

export const seedCinema = async (
  payload: Payload,
  shared: { rightsId: string | number; editorId: string | number },
): Promise<Record<CinemaKey, TenantRef>> => {
  const genreDefs = [
    ['Драма', 'drama'],
    ['Триллер', 'thriller'],
    ['Комедия', 'comedy'],
  ] as const
  const genres: (string | number)[] = []
  for (const [name, slug] of genreDefs) {
    const existing = await payload.find({
      collection: 'genres', where: { slug: { equals: slug } }, limit: 1, overrideAccess: true,
    })
    const doc = existing.docs[0]
      ?? (await payload.create({ collection: 'genres', overrideAccess: true, data: { name, slug } as never }))
    genres.push(doc.id)
  }

  const countryDefs = [
    ['Россия', 'russia'],
    ['Франция', 'france'],
  ] as const
  const countries: (string | number)[] = []
  for (const [name, slug] of countryDefs) {
    const doc = await payload.create({
      collection: 'countries', overrideAccess: true, data: { name, slug } as never,
    })
    countries.push(doc.id)
  }

  const studio = await payload.create({
    collection: 'studios',
    overrideAccess: true,
    data: { name: 'Стендовая киностудия', slug: 'stand-film-studio' } as never,
  })

  // --- Общий каталог четвёрки ---------------------------------------------
  type Made = { id: string | number; slug: string; name: string; kind: string }
  const seriesTitles: Made[] = []
  const filmTitles: Made[] = []
  const upcomingTitles: Made[] = []

  let playbackIndex = 100
  const makeTitle = async (fixture: {
    name: string; slug: string; year: number; kind: string; genre: number; country: number
    releaseState?: string; releaseDate?: string | null; releaseDateConfirmed?: boolean
    releaseSourceRef?: string; previousReleaseDate?: string; status?: string
  }): Promise<Made> => {
    playbackIndex += 1
    const doc = await payload.create({
      collection: 'titles',
      overrideAccess: true,
      data: {
        primaryName: fixture.name,
        kind: fixture.kind,
        status: fixture.status
          ?? (fixture.releaseState && fixture.releaseState !== 'released' ? 'announced' : 'completed'),
        year: fixture.year,
        factualSynopsis:
          `Фактическое описание стендовой записи «${fixture.name}». Запись создана для проверки `
          + 'вёрстки, фильтров и SEO и не описывает реальное произведение.',
        genres: [genres[fixture.genre]!],
        countries: [countries[fixture.country]!],
        studios: [studio.id],
        availability: 'available',
        releaseState: fixture.releaseState ?? 'released',
        releaseDate: fixture.releaseDate ?? null,
        releaseDateConfirmed: fixture.releaseDateConfirmed ?? false,
        releaseSourceRef: fixture.releaseSourceRef ?? null,
        previousReleaseDate: fixture.previousReleaseDate ?? null,
        rightsRecord: shared.rightsId,
        playbackAggregator: 'kp',
        playbackTitleId: `stand-cinema-${playbackIndex}`,
      } as never,
    })
    return { id: doc.id, slug: fixture.slug, name: fixture.name, kind: fixture.kind }
  }

  for (const fixture of SERIES_FIXTURES) {
    const made = await makeTitle(fixture)
    seriesTitles.push(made)
    for (let seasonNumber = 1; seasonNumber <= fixture.seasons; seasonNumber += 1) {
      const season = await payload.create({
        collection: 'seasons',
        overrideAccess: true,
        data: { title: made.id, number: seasonNumber, name: `Сезон ${seasonNumber}` } as never,
      })
      for (let episodeNumber = 1; episodeNumber <= 3; episodeNumber += 1) {
        await payload.create({
          collection: 'episodes',
          overrideAccess: true,
          data: {
            season: season.id,
            number: episodeNumber,
            name: `Серия ${episodeNumber}`,
            playbackAvailable: true,
          } as never,
        })
      }
    }
  }
  for (const fixture of FILM_FIXTURES) filmTitles.push(await makeTitle(fixture))
  for (const fixture of UPCOMING_FIXTURES) upcomingTitles.push(await makeTitle(fixture))

  // --- Арендаторы ----------------------------------------------------------
  const tenants = {} as Record<CinemaKey, TenantRef>
  for (const key of ['d', 'e', 'f', 'g'] as const) {
    const doc = await payload.create({
      collection: 'tenants',
      overrideAccess: true,
      data: {
        name: PROFILES[key].name,
        slug: `site_${key}`,
        domain: `site-${key}.localhost`,
        indexingEnabled: false,
        allowGuestComments: true,
        seoProfile: PROFILES[key].seoProfile,
        theme: PROFILES[key].theme,
      },
    })
    tenants[key] = { id: doc.id, slug: doc.slug as string, domain: doc.domain as string }
  }

  const now = Date.now()
  const day = 24 * 60 * 60 * 1000

  for (const key of ['d', 'e', 'f', 'g'] as const) {
    const tenant = tenants[key].id
    // Каждый сайт публикует свой срез каталога: сериальный, полнометражный,
    // ещё не вышедшее и — у витрины подборок — понемногу отовсюду.
    const published =
      key === 'd' ? seriesTitles
        : key === 'e' ? filmTitles
          : key === 'f' ? upcomingTitles
            : [...seriesTitles.slice(0, 2), ...filmTitles.slice(0, 2)]

    const tenantTitleIds: (string | number)[] = []
    for (const title of published) {
      const doc = await payload.create({
        collection: 'tenant-titles',
        overrideAccess: true,
        data: {
          tenant,
          title: title.id,
          slug: title.slug,
          editorialIntro: introFor(key, title.name),
          seasonNotes: key === 'd'
            ? [{
              season: 1,
              note:
                `Первый сезон «${title.name}» на стенде: порядок серий сверен с записями источника, `
                + 'у каждой серии отмечено, доступна ли она к просмотру. Даты приведены к одному '
                + 'часовому поясу, поэтому список не переставляется между днями. Расхождения '
                + 'нумерации выпуска и порядка выхода указаны рядом, а не исправлены молча.',
            }]
            : [],
          editorialAuthor: shared.editorId,
          _status: 'published',
        } as never,
      })
      tenantTitleIds.push(doc.id)
    }

    // Подборки: обычная у всех, маршрут просмотра — только у витрины подборок.
    await payload.create({
      collection: 'editorial-collections',
      overrideAccess: true,
      data: {
        tenant,
        collectionKind: 'themed',
        name: {
          d: 'Сериалы с закрытым финалом',
          e: 'Кино последних двух лет',
          f: 'Ожидается в этом сезоне',
          g: 'Короткие истории на вечер',
        }[key],
        slug: `stand-collection-${key}`,
        intro: {
          d: 'Сериалы стенда, у которых состав сезонов больше не меняется: список полон и не '
            + 'дополняется. Такой набор удобен, когда не хочется останавливаться на середине.',
          e: 'Полнометражные записи стенда за последние два года — от драм до анимации. Год выхода '
            + 'и страна производства указаны у каждой карточки.',
          f: 'Записи стенда с подтверждённой датой выхода. Как только произведение выходит, оно '
            + 'покидает этот список и появляется на профильном сайте.',
          g: 'Небольшая подборка стенда: истории, которые заканчиваются за один вечер. Выбор '
            + 'редакции, а не сортировка по длительности.',
        }[key],
        items: tenantTitleIds.slice(0, 3),
        _status: 'published',
      } as never,
    })

    if (key === 'g') {
      await payload.create({
        collection: 'editorial-collections',
        overrideAccess: true,
        data: {
          tenant,
          collectionKind: 'watch_order',
          name: 'Маршрут: с чего начать знакомство',
          slug: 'stand-watch-order-g',
          intro:
            'Маршрут стенда: порядок, в котором записи каталога складываются в связную историю. '
            + 'У каждого шага объяснено, что он добавляет и почему стоит именно здесь.',
          steps: tenantTitleIds.slice(0, 3).map((titleId, index) => ({
            title: titleId,
            note: [
              'Начинать стоит отсюда: здесь вводятся места и герои, к которым дальше возвращаются.',
              'Второй шаг объясняет то, что в первом осталось намёком, и почти не требует контекста.',
              'Третий шаг закрывает линию первых двух и добавляет взгляд со стороны.',
            ][index]!,
          })),
          _status: 'published',
        } as never,
      })
    }

    for (const [index, post] of POSTS[key].entries()) {
      await payload.create({
        collection: 'posts',
        overrideAccess: true,
        data: {
          tenant,
          headline: post.headline,
          slug: `stand-post-${key}-${index + 1}`,
          lead: post.body.split('. ')[0]! + '.',
          body: post.body,
          publishedAt: new Date(now - (index + 1) * day).toISOString(),
          _status: 'published',
        } as never,
      })
    }

    await payload.create({
      collection: 'pages',
      overrideAccess: true,
      data: {
        tenant,
        name: LEGAL_TITLES[key],
        slug: 'rights',
        body: legalBodyFor(key, SITE_NAMES[key]),
        _status: 'published',
      } as never,
    })

    await payload.create({
      collection: 'site-settings',
      overrideAccess: true,
      data: {
        tenant,
        siteName: SITE_NAMES[key],
        tagline: TAGLINES[key],
        defaultDescription: SITE_DESCRIPTIONS[key],
        commentsEnabled: true,
        premoderation: true,
        minIntervalSeconds: 30,
        maxLength: 4000,
        rulesText: 'Пишите по делу. Спойлеры прячьте, оскорбления удаляем.',
      } as never,
    })

    await payload.create({
      collection: 'player-profiles',
      overrideAccess: true,
      data: {
        tenant,
        name: `Плеер сайта ${key.toUpperCase()}`,
        publisherIdRef: `PLAYER_PUBLISHER_ID_${key.toUpperCase()}`,
        aggregator: 'kp',
        showBanner: false,
        showVoiceOnly: false,
      } as never,
    })

    const listing = { d: '/series/', e: '/films/', f: '/calendar/', g: '/collections/' }[key]
    const listingLabel = { d: 'Сериалы', e: 'Фильмы', f: 'Календарь', g: 'Подборки' }[key]
    const newsLabel = { d: 'Что нового', e: 'Кинообзоры', f: 'Изменения дат', g: 'Материалы' }[key]
    await payload.create({
      collection: 'navigation',
      overrideAccess: true,
      data: {
        tenant,
        header: [
          { title: listingLabel, href: listing },
          { title: newsLabel, href: '/news/' },
        ],
        footer: [{ title: LEGAL_TITLES[key], href: '/legal/rights/' }],
      } as never,
    })

    await payload.create({
      collection: 'home-layout',
      overrideAccess: true,
      data: {
        tenant,
        blocks: [
          { blockType: 'latestUpdates', heading: listingLabel, enabled: true },
          { blockType: 'editorialPicks', heading: 'Подборки', enabled: true },
          { blockType: 'newsFeed', heading: newsLabel, enabled: true },
        ],
      } as never,
    })
  }

  return tenants
}
