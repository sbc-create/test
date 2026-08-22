import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { Breadcrumbs } from '../../../../components/Breadcrumbs'
import { getPage } from '../../../../lib/content'
import { describe } from '../../../../lib/present'
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
  const doc = await getPage(payload, site.tenant, slug)
  if (!doc) return { robots: 'noindex,follow', title: 'Страница не найдена' }

  const record = asRecord(doc)!
  return buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'legal',
      path: `/legal/${slug}/`,
      heading: String(record.name ?? ''),
      description: describe(record.seoDescription, record.body),
      documentRobots: (record.robots as 'inherit' | 'index' | 'noindex' | undefined) ?? 'inherit',
    },
    site.siteName,
  )
}

const LegalPage = async ({ params }: { params: Params }) => {
  const site = await currentSite()
  const payload = await payloadClient()
  const { slug } = await params
  const doc = await getPage(payload, site.tenant, slug)
  if (!doc) notFound()

  const record = asRecord(doc)!

  return (
    <>
      <Breadcrumbs
        origin={absoluteUrl(site.tenant, '')}
        crumbs={[
          { title: 'Главная', href: '/' },
          { title: String(record.name ?? ''), href: `/legal/${slug}/` },
        ]}
      />
      <h1>{String(record.name ?? '')}</h1>
      <div style={{ maxWidth: '70ch', whiteSpace: 'pre-line' }}>{String(record.body ?? '')}</div>
    </>
  )
}

export default LegalPage
