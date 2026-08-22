/**
 * Структурные различия тем.
 *
 * Токены отвечают за цвет, шрифт и плотность. Но четыре темы, отличающиеся
 * только палитрой, — это одна тема в четырёх цветах. Здесь описано то, что
 * меняет саму компоновку: где стоит поиск, как собрана шапка, какой формы
 * карточка, в каком порядке идут модули главной и как устроена страница
 * произведения. Компоненты читают этот дескриптор, а не угадывают по названию.
 */

export type HeaderVariant = 'inline' | 'stacked' | 'compact' | 'split'
export type SearchPlacement = 'header' | 'below-nav' | 'hero' | 'drawer'
export type CardShape = 'poster' | 'landscape' | 'row' | 'tile'
export type TitleLayout = 'poster-left' | 'hero-cover' | 'facts-first' | 'editorial-first'

export type ThemeLayout = {
  header: HeaderVariant
  search: SearchPlacement
  card: CardShape
  titlePage: TitleLayout
  /** Порядок модулей главной по умолчанию; редактор может изменить его в CMS. */
  homeModules: readonly string[]
  /** Микротексты: пустое состояние и подпись кнопки поиска. */
  tone: { searchAction: string; emptyList: string; more: string }
}

const DEFAULT_LAYOUT: ThemeLayout = {
  header: 'inline',
  search: 'header',
  card: 'poster',
  titlePage: 'poster-left',
  homeModules: ['heroSpotlight', 'latestUpdates', 'editorialPicks', 'newsFeed'],
  tone: { searchAction: 'Найти', emptyList: 'Здесь пока пусто.', more: 'Показать ещё' },
}

export const THEME_LAYOUTS: Record<string, ThemeLayout> = {
  // --- Аниме-тройка: сохраняем то, как эти сайты уже собраны ---------------
  portal_light: DEFAULT_LAYOUT,
  pulse: {
    ...DEFAULT_LAYOUT,
    header: 'inline',
    card: 'poster',
    homeModules: ['releaseSchedule', 'latestUpdates', 'newsFeed', 'genreRails'],
  },
  editorial: {
    ...DEFAULT_LAYOUT,
    titlePage: 'editorial-first',
    homeModules: ['editorialPicks', 'heroSpotlight', 'newsFeed', 'textSection'],
  },

  // --- Четвёрка кинотеатров -----------------------------------------------

  /** Сериалы: поиск всегда под рукой в шапке, плотная сетка обложек. */
  series_dark: {
    header: 'inline',
    search: 'header',
    card: 'poster',
    titlePage: 'poster-left',
    homeModules: ['latestUpdates', 'releaseSchedule', 'genreRails', 'editorialPicks', 'newsFeed'],
    tone: {
      searchAction: 'Искать',
      emptyList: 'В этом разделе пока нет сериалов.',
      more: 'Ещё сериалы',
    },
  },

  /** Фильмы: поиск — центральный элемент первого экрана, кадры вместо постеров. */
  film_editorial: {
    header: 'split',
    search: 'hero',
    card: 'landscape',
    titlePage: 'hero-cover',
    homeModules: ['heroSpotlight', 'editorialPicks', 'genreRails', 'latestUpdates', 'newsFeed'],
    tone: {
      searchAction: 'Найти фильм',
      emptyList: 'Здесь пока нет фильмов — загляните в соседние разделы.',
      more: 'Больше фильмов',
    },
  },

  /** Премьеры: календарь читается строками, поиск уходит под навигацию. */
  premiere_signal: {
    header: 'stacked',
    search: 'below-nav',
    card: 'row',
    titlePage: 'facts-first',
    homeModules: ['releaseSchedule', 'latestUpdates', 'newsFeed', 'textSection'],
    tone: {
      searchAction: 'Найти премьеру',
      emptyList: 'На этот период подтверждённых дат нет.',
      more: 'Следующий период',
    },
  },

  /** Подборки: шапка компактная, поиск открывается по кнопке, крупные плитки. */
  guide_warm: {
    header: 'compact',
    search: 'drawer',
    card: 'tile',
    titlePage: 'editorial-first',
    homeModules: ['editorialPicks', 'heroSpotlight', 'genreRails', 'newsFeed', 'textSection'],
    tone: {
      searchAction: 'Подобрать',
      emptyList: 'Подборок в этом разделе пока нет.',
      more: 'Ещё подборки',
    },
  },
}

/**
 * Тема без описанной компоновки не подменяется «похожей»: это молча дало бы
 * сайту чужую структуру. Отсутствие дескриптора — ошибка конфигурации.
 */
export const layoutFor = (theme: string): ThemeLayout => {
  const layout = THEME_LAYOUTS[theme]
  if (!layout) throw new Error(`BLOCKED_INPUT: у темы «${theme}» не описана компоновка`)
  return layout
}
