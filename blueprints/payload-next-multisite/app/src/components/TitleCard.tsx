import Link from 'next/link'

export type CardItem = {
  href: string
  title: string
  meta?: string | null
  image?: { url: string; alt: string } | null
}

/** Карточка списка. Alt обязателен, поэтому изображение без alt не рендерится. */
export const TitleCard = ({ item }: { item: CardItem }) => (
  <article className="card">
    <Link href={item.href}>
      {item.image?.url && item.image.alt ? (
        <img className="card__poster" src={item.image.url} alt={item.image.alt} loading="lazy" />
      ) : (
        <div className="card__poster" aria-hidden="true" />
      )}
      <div className="card__body">
        <span className="card__title">{item.title}</span>
        {item.meta ? <span className="card__meta">{item.meta}</span> : null}
      </div>
    </Link>
  </article>
)

export const CardGrid = ({ items, empty }: { items: CardItem[]; empty: string }) => {
  if (items.length === 0) return <p className="notice">{empty}</p>
  return (
    <div className="grid">
      {items.map((item) => (
        <TitleCard key={item.href} item={item} />
      ))}
    </div>
  )
}
