import type { Metadata } from 'next'

import { Breadcrumbs } from '../../../components/Breadcrumbs'
import { CardGrid } from '../../../components/TitleCard'
import { listPosts } from '../../../lib/content'
import { postCard } from '../../../lib/present'
import { currentSite, payloadClient } from '../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../seo/metadata'

export const dynamic = 'force-dynamic'

const HEADING = 'Новости и статьи'

export const generateMetadata = async (): Promise<Metadata> => {
  const site = await currentSite()
  return buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'news_index',
      path: '/news/',
      heading: HEADING,
      description: `Материалы редакции сайта «${site.siteName}».`,
    },
    site.siteName,
  )
}

const NewsIndex = async () => {
  const site = await currentSite()
  const payload = await payloadClient()
  const result = await listPosts(payload, site.tenant, { limit: 24 })

  return (
    <>
      <Breadcrumbs
        origin={absoluteUrl(site.tenant, '')}
        crumbs={[
          { title: 'Главная', href: '/' },
          { title: HEADING, href: '/news/' },
        ]}
      />
      <h1>{HEADING}</h1>
      <CardGrid items={result.docs.map(postCard)} empty="Материалов пока нет." />
    </>
  )
}

export default NewsIndex
