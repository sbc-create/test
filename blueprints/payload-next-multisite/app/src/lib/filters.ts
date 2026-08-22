import type { Payload } from 'payload'

import type { FilterGroup } from '../components/CatalogListing'
import type { TitleFilter } from './content'
import { listCountries, listGenres } from './content'

/**
 * Разбор и сборка фильтров каталога.
 *
 * Один модуль на все листинги: иначе каждая страница по-своему решает, что
 * считать активным фильтром, и проверка «фильтр меняет выдачу» начинает
 * проходить на одной странице и молча ломаться на соседней.
 */

export type FilterState = {
  genre: string | null
  country: string | null
  year: number | null
  status: string | null
}

const STATUS_LABELS: Record<string, string> = {
  ongoing: 'Выходит',
  completed: 'Завершён',
  announced: 'Анонс',
}

const asString = (value: string | string[] | undefined): string | null =>
  typeof value === 'string' && value.trim() ? value.trim() : null

export const parseFilters = (params: Record<string, string | string[] | undefined>): FilterState => {
  const yearRaw = asString(params.year)
  // Год принимается только как четыре цифры в разумном диапазоне: иначе
  // произвольная строка в параметре создаёт бесконечный набор адресов.
  const year = yearRaw && /^(19|20)\d{2}$/.test(yearRaw) ? Number(yearRaw) : null
  const status = asString(params.status)
  return {
    genre: asString(params.genre),
    country: asString(params.country),
    year,
    status: status && status in STATUS_LABELS ? status : null,
  }
}

export const hasActiveFilter = (state: FilterState): boolean =>
  Boolean(state.genre || state.country || state.year || state.status)

/** Адрес с изменённым одним измерением и сохранёнными остальными. */
const hrefWith = (basePath: string, state: FilterState, key: keyof FilterState, value: string | null): string => {
  const next: Record<string, string> = {}
  const merged = { ...state, [key]: value } as FilterState
  if (merged.genre) next.genre = merged.genre
  if (merged.country) next.country = merged.country
  if (merged.year) next.year = String(merged.year)
  if (merged.status) next.status = merged.status
  const query = new URLSearchParams(next).toString()
  return query ? `${basePath}?${query}` : basePath
}

export type FilterDimension = 'genre' | 'country' | 'year' | 'status'

export const buildFilterGroups = async (
  payload: Payload,
  basePath: string,
  state: FilterState,
  dimensions: readonly FilterDimension[],
  years: readonly number[],
): Promise<FilterGroup[]> => {
  const groups: FilterGroup[] = []

  if (dimensions.includes('genre')) {
    const genres = await listGenres(payload)
    groups.push({
      id: 'genre',
      label: 'Жанр',
      options: [
        { label: 'Любой', href: hrefWith(basePath, state, 'genre', null), active: !state.genre },
        ...genres.docs.map((genre) => ({
          label: String(genre.name),
          href: hrefWith(basePath, state, 'genre', String(genre.slug)),
          active: state.genre === String(genre.slug),
        })),
      ],
    })
  }

  if (dimensions.includes('country')) {
    const countries = await listCountries(payload)
    groups.push({
      id: 'country',
      label: 'Страна',
      options: [
        { label: 'Любая', href: hrefWith(basePath, state, 'country', null), active: !state.country },
        ...countries.docs.map((country) => ({
          label: String(country.name),
          href: hrefWith(basePath, state, 'country', String(country.slug)),
          active: state.country === String(country.slug),
        })),
      ],
    })
  }

  if (dimensions.includes('year')) {
    groups.push({
      id: 'year',
      label: 'Год',
      options: [
        { label: 'Любой', href: hrefWith(basePath, state, 'year', null), active: !state.year },
        ...years.map((year) => ({
          label: String(year),
          href: hrefWith(basePath, state, 'year', String(year)),
          active: state.year === year,
        })),
      ],
    })
  }

  if (dimensions.includes('status')) {
    groups.push({
      id: 'status',
      label: 'Статус',
      options: [
        { label: 'Любой', href: hrefWith(basePath, state, 'status', null), active: !state.status },
        ...Object.entries(STATUS_LABELS).map(([value, label]) => ({
          label,
          href: hrefWith(basePath, state, 'status', value),
          active: state.status === value,
        })),
      ],
    })
  }

  return groups
}

/** Перевод состояния фильтров в констрейнты запроса. */
export const filterQuery = async (
  payload: Payload,
  state: FilterState,
): Promise<Pick<TitleFilter, 'genreId' | 'countryId' | 'year' | 'statuses'>> => {
  const query: Pick<TitleFilter, 'genreId' | 'countryId' | 'year' | 'statuses'> = {}
  if (state.genre) {
    const genres = await listGenres(payload)
    const found = genres.docs.find((genre) => String(genre.slug) === state.genre)
    // Несуществующий жанр не игнорируется: иначе фильтр «тихо не применился» и
    // страница показала бы полный список под видом отфильтрованного.
    query.genreId = found?.id ?? '__unknown__'
  }
  if (state.country) {
    const countries = await listCountries(payload)
    const found = countries.docs.find((country) => String(country.slug) === state.country)
    query.countryId = found?.id ?? '__unknown__'
  }
  if (state.year) query.year = state.year
  if (state.status) query.statuses = [state.status]
  return query
}
