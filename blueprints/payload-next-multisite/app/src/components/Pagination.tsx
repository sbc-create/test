import Link from 'next/link'

/**
 * Пагинация обычными ссылками: страница 2+ должна открываться прямым URL и быть
 * видна краулеру. Кнопка на JS вместо <a> ломает и то, и другое.
 */
export const Pagination = ({
  basePath,
  page,
  totalPages,
}: {
  basePath: string
  page: number
  totalPages: number
}) => {
  if (totalPages <= 1) return null
  const urlFor = (n: number) => (n === 1 ? basePath : `${basePath}page/${n}/`)

  return (
    <nav className="pagination" aria-label="Постраничная навигация">
      {page > 1 ? (
        <Link className="button button--ghost" href={urlFor(page - 1)} rel="prev">
          Предыдущая
        </Link>
      ) : null}
      <span>
        Страница {page} из {totalPages}
      </span>
      {page < totalPages ? (
        <Link className="button button--ghost" href={urlFor(page + 1)} rel="next">
          Следующая
        </Link>
      ) : null}
    </nav>
  )
}
