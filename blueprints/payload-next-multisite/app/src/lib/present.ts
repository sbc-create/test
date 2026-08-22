import type { CardItem } from '../components/TitleCard'

/**
 * Приведение документов к виду, который рендерит список. Ничего не выдумывает:
 * если названия или alt нет, поле остаётся пустым, а не заполняется заглушкой.
 */

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : null

export const titleNameOf = (tenantTitle: unknown): string => {
  const shared = asRecord(asRecord(tenantTitle)?.title)
  return String(shared?.primaryName ?? '').trim()
}

const imageOf = (source: unknown): CardItem['image'] => {
  const media = asRecord(source)
  if (!media) return null
  const sizes = asRecord(media.sizes)
  const card = asRecord(sizes?.card)
  const url = String(card?.url ?? media.url ?? '').trim()
  const alt = String(media.alt ?? '').trim()
  // Без alt изображение не показывается: пустой alt в публикации — дефект доступности.
  if (!url || !alt) return null
  return { url, alt }
}

export const tenantTitleCard = (doc: unknown): CardItem => {
  const record = asRecord(doc) ?? {}
  const shared = asRecord(record.title)
  const year = shared?.year
  const kind = shared?.kind
  const kindLabel = kind === 'movie' ? 'фильм' : kind === 'ova' ? 'OVA/ONA' : 'сериал'
  return {
    href: `/catalog/${String(record.slug ?? '')}/`,
    title: titleNameOf(doc) || String(record.slug ?? ''),
    meta: [kindLabel, year ? String(year) : null].filter(Boolean).join(' · '),
    image: imageOf(shared?.poster),
  }
}

export const postCard = (doc: unknown): CardItem => {
  const record = asRecord(doc) ?? {}
  const published = record.publishedAt ? new Date(String(record.publishedAt)) : null
  return {
    href: `/news/${String(record.slug ?? '')}/`,
    title: String(record.headline ?? ''),
    meta: published ? published.toLocaleDateString('ru-RU') : null,
    image: imageOf(record.cover),
  }
}

export const collectionCard = (doc: unknown): CardItem => {
  const record = asRecord(doc) ?? {}
  const items = Array.isArray(record.items) ? record.items.length : 0
  return {
    href: `/collections/${String(record.slug ?? '')}/`,
    title: String(record.name ?? ''),
    meta: items > 0 ? `${items} материалов` : null,
    image: imageOf(record.cover),
  }
}

export const plainText = (value: unknown): string => String(value ?? '').replace(/\s+/g, ' ').trim()

/** Description строится из фактического текста страницы, а не из ключевых слов. */
export const describe = (...candidates: unknown[]): string | null => {
  for (const candidate of candidates) {
    const text = plainText(candidate)
    if (text.length >= 40) return text.slice(0, 300)
  }
  return null
}
