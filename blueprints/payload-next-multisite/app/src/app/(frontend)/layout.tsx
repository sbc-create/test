import type { Metadata } from 'next'
import type { ReactNode } from 'react'

import { SiteFooter } from '../../components/SiteFooter'
import { HeroSearch, SiteHeader } from '../../components/SiteHeader'
import { notFound } from 'next/navigation'

import { currentSite } from '../../lib/site'
import { TenantResolutionError } from '../../lib/tenant-query'
import '../../themes/base.css'
import '../../themes/themes.css'

export const generateMetadata = async (): Promise<Metadata> => {
  // Чужой домен, направленный на этот origin, — это 404, а не 500 в каждом логе.
  const site = await currentSite().catch((error) => {
    if (error instanceof TenantResolutionError) notFound()
    throw error
  })
  return {
    metadataBase: new URL(`https://${site.tenant.domain}`),
    title: { default: site.siteName, template: `%s` },
  }
}

const FrontendLayout = async ({ children }: { children: ReactNode }) => {
  const site = await currentSite().catch((error) => {
    if (error instanceof TenantResolutionError) notFound()
    throw error
  })

  return (
    // Тема выбирается сайтом, а не переключателем: три сайта — три разных продукта.
    <html lang="ru" data-theme={site.tenant.theme}>
      <body>
        <a className="skip-link" href="#main">
          Перейти к содержимому
        </a>
        <SiteHeader site={site} />
        <HeroSearch site={site} />
        <main id="main">
          <div className="container">{children}</div>
        </main>
        <SiteFooter site={site} />
      </body>
    </html>
  )
}

export default FrontendLayout
