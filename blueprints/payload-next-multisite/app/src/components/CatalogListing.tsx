import Link from 'next/link'

import type { CardItem } from './TitleCard'
import { CardGrid } from './TitleCard'
import { Pagination } from './Pagination'
import type { CardShape } from '../themes/layouts'

export type FilterOption = {
  label: string
  /** Адрес с применённым фильтром. Обычная ссылка: работает без JavaScript. */
  href: string
  active: boolean
}

export type FilterGroup = {
  id: string
  label: string
  options: FilterOption[]
}

/**
 * Листинг каталога с фильтрами.
 *
 * Фильтр — это обычные `<a href>`, а не переключатель на клиенте: страница
 * пересобирается на сервере и выдача действительно меняется. Комбинации фильтров
 * живут в параметрах запроса и остаются noindex с canonical на чистый раздел;
 * индексируются только посадочные страницы из списка профиля, иначе фильтры
 * порождают бесконечную индексируемую поверхность.
 */
export const CatalogListing = ({
  items,
  filters,
  basePath,
  page,
  totalPages,
  total,
  shape = 'poster',
  empty,
  resetHref,
}: {
  items: CardItem[]
  filters: FilterGroup[]
  basePath: string
  page: number
  totalPages: number
  total: number
  shape?: CardShape
  empty: string
  resetHref?: string
}) => (
  <>
    {filters.map((group) => (
      <div className="filter-group" key={group.id} data-filter={group.id}>
        <span className="filter-group__label">{group.label}</span>
        <div className="row">
          {group.options.map((option) => (
            <Link
              key={option.href}
              className="tag"
              href={option.href}
              aria-current={option.active ? 'page' : undefined}
              data-filter-option={option.active ? 'active' : 'idle'}
            >
              {option.label}
            </Link>
          ))}
        </div>
      </div>
    ))}
    <p className="card__meta" data-total={total}>
      Найдено: {total}
      {resetHref && filters.some((group) => group.options.some((option) => option.active)) ? (
        <>
          {' · '}
          <Link href={resetHref}>сбросить фильтры</Link>
        </>
      ) : null}
    </p>
    <CardGrid items={items} empty={empty} shape={shape} />
    <Pagination basePath={basePath} page={page} totalPages={totalPages} />
  </>
)
