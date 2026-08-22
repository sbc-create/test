import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'

import { Breadcrumbs } from '../../../../components/Breadcrumbs'
import { Player } from '../../../../components/Player'
import { getTenantTitle, listSeasons } from '../../../../lib/content'
import { describe, plainText, titleNameOf } from '../../../../lib/present'
import { currentSite, payloadClient } from '../../../../lib/site'
import { playerConfigFor } from '../../../../player/server'
import { absoluteUrl, buildMetadata } from '../../../../seo/metadata'

export const dynamic = 'force-dynamic'

type Params = Promise<{ slug: string }>

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : null

export const generateMetadata = async ({ params }: { params: Params }): Promise<Metadata> => {
  const site = await currentSite()
  const payload = await payloadClient()
  const { slug } = await params
  const doc = await getTenantTitle(payload, site.tenant, slug)
  if (!doc) return { robots: 'noindex,follow', title: 'Материал не найден' }

  const record = asRecord(doc)!
  const shared = asRecord(record.title)
  const seo = asRecord(record.seoFields) ?? record

  return buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'title',
      path: `/catalog/${slug}/`,
      heading: titleNameOf(doc),
      description: describe(seo.seoDescription, record.editorialIntro, shared?.factualSynopsis),
      ownText: plainText(record.editorialIntro),
      documentRobots: (seo.robots as 'inherit' | 'index' | 'noindex' | undefined) ?? 'inherit',
    },
    site.siteName,
  )
}

const TitlePage = async ({ params }: { params: Params }) => {
  const site = await currentSite()
  const payload = await payloadClient()
  const { slug } = await params

  const doc = await getTenantTitle(payload, site.tenant, slug)
  if (!doc) notFound()

  const record = asRecord(doc)!
  const shared = asRecord(record.title)
  const name = titleNameOf(doc)
  const seasons = shared?.id ? await listSeasons(payload, shared.id as string | number) : { docs: [] }
  const player = await playerConfigFor(payload, site.tenant, shared)
  const intro = plainText(record.editorialIntro)

  return (
    <>
      <Breadcrumbs
        origin={absoluteUrl(site.tenant, '')}
        crumbs={[
          { title: 'Главная', href: '/' },
          { title: 'Каталог', href: '/catalog/' },
          { title: name, href: `/catalog/${slug}/` },
        ]}
      />
      <h1>{name}</h1>

      <section className="section">
        {player.attributes ? (
          <Player
            attributes={player.attributes}
            scriptUrl={player.scriptUrl}
            unavailableText="Сейчас смотреть нельзя: у этого материала нет доступного видео."
          />
        ) : (
          <p className="notice" role="status">
            {player.reason}
          </p>
        )}
      </section>

      {intro ? (
        <section className="section">
          <h2>О чём материал</h2>
          <p style={{ maxWidth: '70ch' }}>{intro}</p>
          {asRecord(record.editorialAuthor)?.name ? (
            <p className="card__meta">Автор: {String(asRecord(record.editorialAuthor)!.name)}</p>
          ) : null}
        </section>
      ) : null}

      {shared?.factualSynopsis ? (
        <section className="section">
          <h2>Описание из источника</h2>
          <p style={{ maxWidth: '70ch' }}>{String(shared.factualSynopsis)}</p>
        </section>
      ) : null}

      <section className="section">
        <h2>Сезоны и эпизоды</h2>
        {seasons.docs.length === 0 ? (
          <p className="notice">Данные о сезонах пока не переданы.</p>
        ) : (
          <ul className="list">
            {seasons.docs.map((season) => {
              const item = asRecord(season)!
              return (
                <li key={String(item.id)}>
                  <Link href={`/catalog/${slug}/season-${String(item.number)}/`}>
                    Сезон {String(item.number)}
                    {item.name ? ` — ${String(item.name)}` : ''}
                  </Link>
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </>
  )
}

export default TitlePage
