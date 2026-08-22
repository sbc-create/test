import type { Metadata } from 'next'
import type { ReactNode } from 'react'

import { SiteFooter } from '../../components/SiteFooter'
import { SiteHeader } from '../../components/SiteHeader'
import { currentSite } from '../../lib/site'
import '../../themes/base.css'
import '../../themes/themes.css'

export const generateMetadata = async (): Promise<Metadata> => {
  const site = await currentSite()
  return {
    metadataBase: new URL(`https://${site.tenant.domain}`),
    title: { default: site.siteName, template: `%s` },
  }
}

const FrontendLayout = async ({ children }: { children: ReactNode }) => {
  const site = await currentSite()

  return (
    // Тема выбирается сайтом, а не переключателем: три сайта — три разных продукта.
    <html lang="ru" data-theme={site.tenant.theme}>
      <body>
        <a className="skip-link" href="#main">
          Перейти к содержимому
        </a>
        <SiteHeader site={site} />
        <main id="main">
          <div className="container">{children}</div>
        </main>
        <SiteFooter site={site} />
      </body>
    </html>
  )
}

export default FrontendLayout
