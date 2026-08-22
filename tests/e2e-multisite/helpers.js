const PORT = process.env.FACTORY_MULTISITE_PORT || '3000';

/**
 * Семь сайтов стенда: три аниме-сайта и четыре кинотеатра.
 *
 * Маршруты у каждого свои — сайт фильмов не имеет расписания, а календарь
 * премьер не имеет каталога сериалов. Общий список маршрутов заставил бы
 * проверки ходить по чужим адресам и считать 404 нормой.
 */
const SITES = {
  a: {
    host: `http://site-a.localhost:${PORT}`,
    theme: 'portal_light',
    name: 'Стенд A — каталог',
    routes: [
      '/', '/catalog/', '/catalog/stand-title-1/', '/catalog/stand-title-1/season-1/',
      '/catalog/stand-title-1/season-1/episode-1/', '/schedule/', '/news/', '/legal/rights/',
      '/search/?q=%D0%A1%D1%82%D0%B5%D0%BD%D0%B4',
    ],
    episode: '/catalog/stand-title-1/season-1/episode-1/',
    player: { titleId: 'stand-1', publisherId: 'stand-publisher-a' },
    deeperEpisode: { path: '/catalog/stand-title-1/season-2/episode-3/', season: '2', episode: '3' },
  },
  b: {
    host: `http://site-b.localhost:${PORT}`,
    theme: 'pulse',
    name: 'Стенд B — расписание',
    routes: [
      '/', '/catalog/', '/catalog/stand-title-1/', '/schedule/', '/news/', '/legal/rights/',
      '/search/?q=%D0%A1%D1%82%D0%B5%D0%BD%D0%B4',
    ],
  },
  c: {
    host: `http://site-c.localhost:${PORT}`,
    theme: 'editorial',
    name: 'Стенд C — редакция',
    routes: [
      '/', '/collections/', '/collections/stand-collection-c/', '/catalog/stand-title-1/',
      '/news/', '/legal/rights/', '/search/?q=%D0%A1%D1%82%D0%B5%D0%BD%D0%B4',
    ],
  },
  d: {
    host: `http://site-d.localhost:${PORT}`,
    theme: 'series_dark',
    name: 'Стенд D — сериалы',
    routes: [
      '/', '/series/', '/series/?status=completed', '/catalog/severny-marshrut/',
      '/catalog/severny-marshrut/season-1/', '/catalog/severny-marshrut/season-1/episode-1/',
      '/news/', '/legal/rights/', '/search/?q=%D0%A1%D1%82%D0%B5%D0%BD%D0%B4',
    ],
    episode: '/catalog/severny-marshrut/season-1/episode-1/',
    player: { titleId: 'stand-cinema-101', publisherId: 'stand-publisher-d' },
    deeperEpisode: { path: '/catalog/severny-marshrut/season-2/episode-3/', season: '2', episode: '3' },
  },
  e: {
    host: `http://site-e.localhost:${PORT}`,
    theme: 'film_editorial',
    name: 'Стенд E — фильмы',
    routes: [
      '/', '/films/', '/films/?genre=drama', '/films/genre/drama/', '/films/year/2024/',
      '/catalog/dolgaya-pereprava/', '/news/', '/legal/rights/',
      '/search/?q=%D0%A1%D1%82%D0%B5%D0%BD%D0%B4',
    ],
  },
  f: {
    host: `http://site-f.localhost:${PORT}`,
    theme: 'premiere_signal',
    name: 'Стенд F — премьеры',
    routes: [
      '/', '/calendar/', '/catalog/obratny-otschet/', '/news/', '/legal/rights/',
      '/search/?q=%D0%A1%D1%82%D0%B5%D0%BD%D0%B4',
    ],
  },
  g: {
    host: `http://site-g.localhost:${PORT}`,
    theme: 'guide_warm',
    name: 'Стенд G — подборки',
    routes: [
      '/', '/collections/', '/collections/stand-collection-g/',
      '/collections/stand-watch-order-g/', '/news/', '/legal/rights/',
      '/search/?q=%D0%A1%D1%82%D0%B5%D0%BD%D0%B4',
    ],
  },
};

const url = (key, path) => `${SITES[key].host}${path}`;

/** Сайты, у которых есть страница серии: только там проверяется плеер. */
const EPISODE_SITES = Object.entries(SITES)
  .filter(([, site]) => Boolean(site.episode))
  .map(([key]) => key);

module.exports = { SITES, url, PORT, EPISODE_SITES };
