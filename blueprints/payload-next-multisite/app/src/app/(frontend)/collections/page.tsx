import type { Metadata } from 'next'

import { Breadcrumbs } from '../../../components/Breadcrumbs'
import { CardGrid } from '../../../components/TitleCard'
import { listCollections } from '../../../lib/content'
import { collectionCard } from '../../../lib/present'
import { currentSite, payloadClient } from '../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../seo/metadata'
import { ownsListing } from '../../../seo/profiles'

export const dynamic = 'force-dynamic'

export const generateMetadata = async (): Promise<Metadata> => {
  const site = await currentSite()
  return buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'category',
      path: '/collections/',
      // Заголовок и описание берутся из профиля: разделом владеют два сайта, и
      // общий текст сделал бы их листинги дублями друг друга.
      heading: site.profile.collectionsHeading,
      description: site.profile.collectionsSummary,
      documentRobots: ownsListing(site.profile, '/collections/') ? 'inherit' : 'noindex',
    },
    site.siteName,
  )
}

const CollectionsPage = async () => {
  const site = await currentSite()
  const payload = await payloadClient()
  const result = await listCollections(payload, site.tenant, { limit: 24 })

  return (
    <>
      <Breadcrumbs
        origin={absoluteUrl(site.tenant, '')}
        crumbs={[
          { title: 'Главная', href: '/' },
          { title: site.profile.collectionsHeading, href: '/collections/' },
        ]}
      />
      <h1>{site.profile.collectionsHeading}</h1>
      <CardGrid items={result.docs.map(collectionCard)} empty={site.layout.tone.emptyList} shape={site.layout.card} />
    </>
  )
}

export default CollectionsPage
