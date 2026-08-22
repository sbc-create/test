import Link from 'next/link'

import type { CardItem } from './TitleCard'
import { CardGrid } from './TitleCard'
import { Pagination } from './Pagination'

export type GenreOption = { name: string; slug: string }

/**
 * Каталог: фильтр по жанру — обычные ссылки, пагинация — обычные ссылки.
 * Параметр `genre` не делает страницу самостоятельной: она canonical на чистый URL.
 */
export const CatalogListing = ({
  items,
  genres,
  activeGenre,
  page,
  totalPages,
  total,
}: {
  items: CardItem[]
  genres: GenreOption[]
  activeGenre: string | null
  page: number
  totalPages: number
  total: number
}) => (
  <>
    <div className="row" style={{ marginBottom: '1rem' }}>
      <Link className="tag" href="/catalog/" aria-current={activeGenre ? undefined : 'page'}>
        Все
      </Link>
      {genres.map((genre) => (
        <Link
          key={genre.slug}
          className="tag"
          href={`/catalog/?genre=${genre.slug}`}
          aria-current={activeGenre === genre.slug ? 'page' : undefined}
        >
          {genre.name}
        </Link>
      ))}
    </div>
    <p className="card__meta">Найдено материалов: {total}</p>
    <CardGrid items={items} empty="По этому запросу материалов нет." />
    <Pagination basePath="/catalog/" page={page} totalPages={totalPages} />
  </>
)
