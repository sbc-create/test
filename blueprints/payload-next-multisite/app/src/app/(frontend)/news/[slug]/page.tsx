import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { Breadcrumbs } from '../../../../components/Breadcrumbs'
import { JsonLd } from '../../../../components/JsonLd'
import { getPost } from '../../../../lib/content'
import { describe, plainText } from '../../../../lib/present'
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
  const doc = await getPost(payload, site.tenant, slug)
  if (!doc) return { robots: 'noindex,follow', title: 'Материал не найден' }

  const record = asRecord(doc)!
  return buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'article',
      path: `/news/${slug}/`,
      heading: String(record.headline ?? ''),
      description: describe(record.seoDescription, record.lead, record.body),
      ownText: plainText(record.body),
      documentRobots: (record.robots as 'inherit' | 'index' | 'noindex' | undefined) ?? 'inherit',
    },
    site.siteName,
  )
}

const PostPage = async ({ params }: { params: Params }) => {
  const site = await currentSite()
  const payload = await payloadClient()
  const { slug } = await params
  const doc = await getPost(payload, site.tenant, slug)
  if (!doc) notFound()

  const record = asRecord(doc)!
  const published = record.publishedAt ? new Date(String(record.publishedAt)) : null

  return (
    <>
      <Breadcrumbs
        origin={absoluteUrl(site.tenant, '')}
        crumbs={[
          { title: 'Главная', href: '/' },
          { title: 'Новости и статьи', href: '/news/' },
          { title: String(record.headline ?? ''), href: `/news/${slug}/` },
        ]}
      />
      <article>
        <h1>{String(record.headline ?? '')}</h1>
        {published ? (
          <p className="card__meta">
            <time dateTime={published.toISOString()}>{published.toLocaleDateString('ru-RU')}</time>
          </p>
        ) : null}
        {record.lead ? <p style={{ maxWidth: '70ch', fontWeight: 600 }}>{String(record.lead)}</p> : null}
        {record.body ? <div style={{ maxWidth: '70ch' }}>{String(record.body)}</div> : null}
      </article>
      {published ? (
        <JsonLd
          data={{
            '@context': 'https://schema.org',
            '@type': 'NewsArticle',
            headline: String(record.headline ?? ''),
            datePublished: published.toISOString(),
            inLanguage: 'ru-RU',
            mainEntityOfPage: absoluteUrl(site.tenant, `/news/${slug}/`),
            publisher: { '@type': 'Organization', name: site.siteName },
          }}
        />
      ) : null}
    </>
  )
}

export default PostPage
