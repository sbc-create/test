import type { Metadata } from 'next'

import { CardGrid } from '../../../components/TitleCard'
import { searchSite } from '../../../lib/content'
import { postCard, tenantTitleCard } from '../../../lib/present'
import { currentSite, payloadClient } from '../../../lib/site'
import { buildMetadata } from '../../../seo/metadata'

export const dynamic = 'force-dynamic'

type Search = Promise<Record<string, string | string[] | undefined>>

export const generateMetadata = async (): Promise<Metadata> => {
  const site = await currentSite()
  // Поиск — функция для посетителя, а не посадочная страница: всегда noindex,
  // canonical не выставляется вовсе.
  return buildMetadata(
    { tenant: site.tenant, pageType: 'search', path: '/search/', heading: 'Поиск' },
    site.siteName,
  )
}

const SearchPage = async ({ searchParams }: { searchParams: Search }) => {
  const site = await currentSite()
  const payload = await payloadClient()
  const params = await searchParams
  const query = typeof params.q === 'string' ? params.q : ''
  const results = await searchSite(payload, site.tenant, query)

  return (
    <>
      <h1>Поиск</h1>
      <form className="row" action="/search/" role="search" style={{ marginBottom: '1.5rem' }}>
        <label className="visually-hidden" htmlFor="q">
          Поисковый запрос
        </label>
        <input id="q" name="q" type="search" defaultValue={query} style={{ minHeight: 44, padding: '0 0.75rem' }} />
        <button className="button" type="submit">
          Найти
        </button>
      </form>

      {query.trim() === '' ? (
        <p className="notice">Введите запрос, чтобы найти материалы этого сайта.</p>
      ) : (
        <>
          <section className="section">
            <h2>Тайтлы</h2>
            <CardGrid items={results.titles.map(tenantTitleCard)} empty="Ничего не найдено." shape={site.layout.card} />
          </section>
          <section className="section">
            <h2>Материалы</h2>
            <CardGrid items={results.posts.map(postCard)} empty="Ничего не найдено." shape={site.layout.card} />
          </section>
        </>
      )}
    </>
  )
}

export default SearchPage
