import Link from 'next/link'

import type { SiteContext } from '../lib/site'

type FooterLink = { title?: string; href?: string; external?: boolean }
type FooterGroup = { title?: string; links?: FooterLink[] }

export const SiteFooter = ({ site }: { site: SiteContext }) => {
  const groups = ((site.navigation?.footerGroups as FooterGroup[] | undefined) ?? []).filter(
    (group) => group.title,
  )
  const rightsNotice = String(site.settings?.rightsNotice ?? '').trim()

  return (
    <footer className="site-footer">
      <div className="container">
        <div className="site-footer__groups">
          {groups.map((group) => (
            <div key={group.title}>
              <strong>{group.title}</strong>
              <ul>
                {(group.links ?? [])
                  .filter((link) => link.title && link.href)
                  .map((link) => (
                    <li key={`${link.href}-${link.title}`}>
                      <Link
                        href={link.href!}
                        {...(link.external ? { rel: 'nofollow noopener', target: '_blank' } : {})}
                      >
                        {link.title}
                      </Link>
                    </li>
                  ))}
              </ul>
            </div>
          ))}
        </div>
        {rightsNotice ? (
          <p style={{ marginTop: '1.5rem', maxWidth: '70ch' }}>{rightsNotice}</p>
        ) : null}
        <p style={{ marginTop: '1rem' }}>{site.profile.purpose}</p>
      </div>
    </footer>
  )
}
