import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'

import { Breadcrumbs } from '../../../../../components/Breadcrumbs'
import { getTenantTitle, listEpisodes, listSeasons } from '../../../../../lib/content'
import { titleNameOf } from '../../../../../lib/present'
import { currentSite, payloadClient } from '../../../../../lib/site'
import { seasonNote as seasonNoteOf } from '../../../../../seo/inclusion'
import { absoluteUrl, buildMetadata } from '../../../../../seo/metadata'

export const dynamic = 'force-dynamic'

type Params = Promise<{ slug: string; season: string }>

/** URL сезона строго вида season-N. Любая другая форма — 404, а не редирект наугад. */
export const seasonNumberOf = (segment: string): number | null => {
  const match = /^season-([1-9]\d*)$/.exec(segment)
  return match ? Number(match[1]) : null
}

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : null



export const generateMetadata = async ({ params }: { params: Params }): Promise<Metadata> => {
  const site = await currentSite()
  const payload = await payloadClient()
  const { slug, season } = await params
  const number = seasonNumberOf(season)
  if (number === null) return { robots: 'noindex,follow' }

  const doc = await getTenantTitle(payload, site.tenant, slug)
  if (!doc) return { robots: 'noindex,follow' }

  return buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'season',
      path: `/catalog/${slug}/season-${number}/`,
      heading: `${titleNameOf(doc)}, сезон ${number}`,
      description: seasonNoteOf(doc, number)
        ? seasonNoteOf(doc, number)!.slice(0, 300)
        : `Список эпизодов сезона ${number} — ${titleNameOf(doc)}.`,
      // Сезон без собственного текста — список серий, одинаковый на всех сайтах.
      // Такую страницу оставляем навигацией и закрываем от индексации.
      documentRobots: seasonNoteOf(doc, number) ? 'inherit' : 'noindex',
    },
    site.siteName,
  )
}

const SeasonPage = async ({ params }: { params: Params }) => {
  const site = await currentSite()
  const payload = await payloadClient()
  const { slug, season } = await params
  const number = seasonNumberOf(season)
  if (number === null) notFound()

  const doc = await getTenantTitle(payload, site.tenant, slug)
  if (!doc) notFound()

  const shared = asRecord(asRecord(doc)!.title)
  const seasons = shared?.id ? await listSeasons(payload, shared.id as string | number) : { docs: [] }
  const current = seasons.docs.find((item) => Number(asRecord(item)!.number) === number)
  // Сезона нет — 404. Пустая страница со статусом 200 запрещена политикой.
  if (!current) notFound()

  const episodes = await listEpisodes(payload, asRecord(current)!.id as string | number)
  if (episodes.docs.length === 0) notFound()

  const name = titleNameOf(doc)

  return (
    <>
      <Breadcrumbs
        origin={absoluteUrl(site.tenant, '')}
        crumbs={[
          { title: 'Главная', href: '/' },
          { title: 'Каталог', href: '/catalog/' },
          { title: name, href: `/catalog/${slug}/` },
          { title: `Сезон ${number}`, href: `/catalog/${slug}/season-${number}/` },
        ]}
      />
      <h1>
        {name}, сезон {number}
      </h1>
      {seasonNoteOf(doc, number) ? <p className="lead">{seasonNoteOf(doc, number)}</p> : null}
      <ul className="list">
        {episodes.docs.map((episode) => {
          const item = asRecord(episode)!
          return (
            <li key={String(item.id)}>
              <Link href={`/catalog/${slug}/season-${number}/episode-${String(item.number)}/`}>
                Серия {String(item.number)}
                {item.name ? ` — ${String(item.name)}` : ''}
              </Link>
              {item.airedAt ? (
                <span className="card__meta"> · {new Date(String(item.airedAt)).toLocaleDateString('ru-RU')}</span>
              ) : null}
            </li>
          )
        })}
      </ul>
    </>
  )
}

export default SeasonPage
