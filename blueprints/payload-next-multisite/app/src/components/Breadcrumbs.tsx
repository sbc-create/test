import Link from 'next/link'

import { JsonLd } from './JsonLd'

export type Crumb = { title: string; href: string }

/** Видимые крошки + BreadcrumbList. Разметка без видимых крошек запрещена. */
export const Breadcrumbs = ({ crumbs, origin }: { crumbs: Crumb[]; origin: string }) => {
  if (crumbs.length === 0) return null
  return (
    <>
      <nav aria-label="Хлебные крошки">
        <ol className="row" style={{ listStyle: 'none', padding: 0, margin: '0 0 1rem', gap: '0.5rem' }}>
          {crumbs.map((crumb, index) => (
            <li key={crumb.href}>
              {index < crumbs.length - 1 ? <Link href={crumb.href}>{crumb.title}</Link> : <span>{crumb.title}</span>}
              {index < crumbs.length - 1 ? <span aria-hidden="true"> / </span> : null}
            </li>
          ))}
        </ol>
      </nav>
      <JsonLd
        data={{
          '@context': 'https://schema.org',
          '@type': 'BreadcrumbList',
          itemListElement: crumbs.map((crumb, index) => ({
            '@type': 'ListItem',
            position: index + 1,
            name: crumb.title,
            item: `${origin}${crumb.href}`,
          })),
        }}
      />
    </>
  )
}
