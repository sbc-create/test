import Link from 'next/link'

import type { CardShape } from '../themes/layouts'

export type CardItem = {
  href: string
  title: string
  meta?: string | null
  /** Ведущая метка: дата премьеры для календаря, номер шага для порядка просмотра. */
  lead?: string | null
  image?: { url: string; alt: string } | null
}

/**
 * Карточка списка в одной из четырёх форм.
 *
 * Форма задаётся темой, а не страницей: витрина сериалов показывает постеры,
 * кинотека — широкие кадры, календарь премьер — строки с датой слева, витрина
 * подборок — крупные плитки. Alt обязателен, поэтому изображение без alt не
 * рендерится вовсе, а не подставляет пустую строку.
 */
export const TitleCard = ({ item, shape = 'poster' }: { item: CardItem; shape?: CardShape }) => (
  <article className={`card card--${shape}`}>
    <Link href={item.href}>
      {shape === 'row' ? null : item.image?.url && item.image.alt ? (
        <img className="card__poster" src={item.image.url} alt={item.image.alt} loading="lazy" />
      ) : (
        <div className="card__poster" aria-hidden="true" />
      )}
      <div className="card__body">
        {item.lead ? <span className="card__lead">{item.lead}</span> : null}
        <span className="card__title">{item.title}</span>
        {item.meta ? <span className="card__meta">{item.meta}</span> : null}
      </div>
    </Link>
  </article>
)

export const CardGrid = ({
  items,
  empty,
  shape = 'poster',
}: {
  items: CardItem[]
  empty: string
  shape?: CardShape
}) => {
  if (items.length === 0) return <p className="notice">{empty}</p>
  return (
    <div className={`grid grid--${shape}`} data-card-shape={shape}>
      {items.map((item) => (
        <TitleCard key={item.href} item={item} shape={shape} />
      ))}
    </div>
  )
}
