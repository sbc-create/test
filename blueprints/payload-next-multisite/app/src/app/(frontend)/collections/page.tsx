import type { Metadata } from 'next'

import { Breadcrumbs } from '../../../components/Breadcrumbs'
import { CardGrid } from '../../../components/TitleCard'
import { listCollections } from '../../../lib/content'
import { collectionCard } from '../../../lib/present'
import { currentSite, payloadClient } from '../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../seo/metadata'

export const dynamic = 'force-dynamic'

const HEADING = 'Подборки'

export const generateMetadata = async (): Promise<Metadata> => {
  const site = await currentSite()
  return buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'category',
      path: '/collections/',
      heading: HEADING,
      description: `Тематические подборки сайта «${site.siteName}».`,
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
          { title: HEADING, href: '/collections/' },
        ]}
      />
      <h1>{HEADING}</h1>
      <CardGrid items={result.docs.map(collectionCard)} empty="Подборок пока нет." />
    </>
  )
}

export default CollectionsPage
