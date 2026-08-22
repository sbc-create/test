import Link from 'next/link'

import type { SiteContext } from '../lib/site'

type NavItem = { title?: string; href?: string; external?: boolean }

export const SiteHeader = ({ site }: { site: SiteContext }) => {
  const items = ((site.navigation?.header as NavItem[] | undefined) ?? []).filter(
    (item) => item.title && item.href,
  )

  return (
    <header className="site-header">
      <div className="container site-header__inner">
        <Link className="site-header__brand" href="/">
          {site.siteName}
        </Link>
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
        <form className="site-search" action="/search/" role="search">
          <label className="visually-hidden" htmlFor="site-search-input">
            Поиск по сайту
          </label>
          <input id="site-search-input" type="search" name="q" placeholder="Поиск" />
          <button className="button" type="submit">
            Найти
          </button>
        </form>
      </div>
    </header>
  )
}
