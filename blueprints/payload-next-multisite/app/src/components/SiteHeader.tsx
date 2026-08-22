import Link from 'next/link'

import type { SiteContext } from '../lib/site'

type NavItem = { title?: string; href?: string; external?: boolean }

const SearchForm = ({ site, variant }: { site: SiteContext; variant: string }) => (
  <form className={`site-search site-search--${variant}`} action="/search/" role="search">
    <label className="visually-hidden" htmlFor={`site-search-${variant}`}>
      Поиск по сайту
    </label>
    <input id={`site-search-${variant}`} type="search" name="q" placeholder="Поиск" />
    <button className="button" type="submit">
      {site.layout.tone.searchAction}
    </button>
  </form>
)

const Nav = ({ items }: { items: NavItem[] }) => (
  <nav className="site-nav" aria-label="Основная навигация">
    <ul>
      {items.map((item) => (
        <li key={`${item.href}-${item.title}`}>
          <Link
            href={item.href!}
            {...(item.external ? { rel: 'nofollow noopener', target: '_blank' } : {})}
          >
            {item.title}
          </Link>
        </li>
      ))}
    </ul>
  </nav>
)

/**
 * Шапка сайта в одном из четырёх вариантов компоновки.
 *
 * Вариант берётся из дескриптора темы, а не из названия сайта: сайт с плотной
 * витриной держит поиск в шапке, календарь премьер уводит его под навигацию,
 * кинотека выносит на первый экран, а витрина подборок открывает по кнопке.
 * Разметка при этом остаётся одна и та же — поиск доступен без JavaScript в
 * любом варианте, включая «ящик»: `details` работает нативно.
 */
export const SiteHeader = ({ site }: { site: SiteContext }) => {
  const items = ((site.navigation?.header as NavItem[] | undefined) ?? []).filter(
    (item) => item.title && item.href,
  )
  const variant = site.layout.header

  const brand = (
    <Link className="site-header__brand" href="/">
      {site.siteName}
    </Link>
  )

  return (
    <header className={`site-header site-header--${variant}`} data-header={variant}>
      <div className="container site-header__inner">
        {variant === 'stacked' ? (
          <>
            <div className="site-header__row">{brand}</div>
            <div className="site-header__row site-header__row--nav">
              <Nav items={items} />
            </div>
            <div className="site-header__row">
              <SearchForm site={site} variant="below-nav" />
            </div>
          </>
        ) : null}

        {variant === 'inline' ? (
          <>
            {brand}
            <Nav items={items} />
            <SearchForm site={site} variant="header" />
          </>
        ) : null}

        {variant === 'split' ? (
          <>
            <div className="site-header__row site-header__row--brand">{brand}</div>
            <div className="site-header__row site-header__row--nav">
              <Nav items={items} />
            </div>
          </>
        ) : null}

        {variant === 'compact' ? (
          <>
            <div className="site-header__row site-header__row--brand">
              {brand}
              <details className="site-search-drawer">
                <summary className="button" aria-label="Открыть поиск">
                  {site.layout.tone.searchAction}
                </summary>
                <SearchForm site={site} variant="drawer" />
              </details>
            </div>
            <div className="site-header__row site-header__row--nav">
              <Nav items={items} />
            </div>
          </>
        ) : null}
      </div>
    </header>
  )
}

/**
 * Поиск первого экрана. Отдельный блок, потому что у кинотеки он часть контента,
 * а не служебный элемент шапки: там это главный способ навигации.
 */
export const HeroSearch = ({ site }: { site: SiteContext }) =>
  site.layout.search === 'hero' ? (
    <section className="hero-search" aria-label="Поиск по каталогу">
      <div className="container">
        <p className="hero-search__lead">{site.profile.purpose}</p>
        <SearchForm site={site} variant="hero" />
      </div>
    </section>
  ) : null
