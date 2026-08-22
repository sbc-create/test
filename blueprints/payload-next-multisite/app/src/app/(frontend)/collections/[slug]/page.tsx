import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { Breadcrumbs } from '../../../../components/Breadcrumbs'
import { CardGrid } from '../../../../components/TitleCard'
import { getCollection } from '../../../../lib/content'
import { describe, plainText, tenantTitleCard } from '../../../../lib/present'
import { currentSite, payloadClient } from '../../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../../seo/metadata'

export const dynamic = 'force-dynamic'

type Params = Promise<{ slug: string }>

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : null

export const generateMetadata = async ({ params }: { params: Params }): Promise<Metadata> => {
  const site = await currentSite()
  const payload = await payloadClient()
  const { slug } = await params
  const doc = await getCollection(payload, site.tenant, slug)
  if (!doc) return { robots: 'noindex,follow', title: 'Подборка не найдена' }

  const record = asRecord(doc)!
  return buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'collection',
      path: `/collections/${slug}/`,
      heading: String(record.name ?? ''),
      description: describe(record.seoDescription, record.intro),
      ownText: plainText(record.intro),
      documentRobots: (record.robots as 'inherit' | 'index' | 'noindex' | undefined) ?? 'inherit',
    },
    site.siteName,
  )
}

const CollectionPage = async ({ params }: { params: Params }) => {
  const site = await currentSite()
  const payload = await payloadClient()
  const { slug } = await params
  const doc = await getCollection(payload, site.tenant, slug)
  if (!doc) notFound()

  const record = asRecord(doc)!
  const kind = String(record.collectionKind ?? 'themed')
  const steps = Array.isArray(record.steps) ? record.steps : []
  const items = Array.isArray(record.items) ? record.items : []
  // Подборка без состава не публикуется как страница со статусом 200.
  if (kind === 'watch_order' ? steps.length === 0 : items.length === 0) notFound()

  return (
    <>
      <Breadcrumbs
        origin={absoluteUrl(site.tenant, '')}
        crumbs={[
          { title: 'Главная', href: '/' },
          { title: site.profile.collectionsHeading, href: '/collections/' },
          { title: String(record.name ?? ''), href: `/collections/${slug}/` },
        ]}
      />
      <h1>{String(record.name ?? '')}</h1>
      {record.intro ? <p style={{ maxWidth: '70ch' }}>{String(record.intro)}</p> : null}
      {kind === 'watch_order' ? (
        // Порядок просмотра — нумерованный маршрут: у каждого шага собственное
        // объяснение редакции, иначе это тот же список под другим названием.
        <ol className="watch-order" data-testid="watch-order">
          {steps.map((raw, index) => {
            const step = asRecord(raw)
            const target = asRecord(step?.title)
            if (!target) return null
            const card = tenantTitleCard(target)
            return (
              <li className="watch-order__step" key={`${card.href}-${index}`}>
                <span className="watch-order__number" aria-hidden="true">
                  {index + 1}
                </span>
                <div>
                  <a className="watch-order__title" href={card.href}>
                    {card.title}
                  </a>
                  <p className="watch-order__note">{String(step?.note ?? '')}</p>
                </div>
              </li>
            )
          })}
        </ol>
      ) : (
        <CardGrid
          items={items.map(tenantTitleCard)}
          empty={site.layout.tone.emptyList}
          shape={site.layout.card}
        />
      )}
    </>
  )
}

export default CollectionPage
