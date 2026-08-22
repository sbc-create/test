import Link from 'next/link'

import type { SiteContext } from '../lib/site'
import { collectionCard, postCard, tenantTitleCard } from '../lib/present'
import { CardGrid } from './TitleCard'

type Block = Record<string, unknown> & { blockType?: string; enabled?: boolean; heading?: string }

export type HomeData = {
  latest: unknown[]
  posts: unknown[]
  schedule: { label: string; airsAt: string; href: string | null }[]
  genres: { id: string | number; name: string; slug: string }[]
}

const Section = ({ heading, children }: { heading?: string; children: React.ReactNode }) => (
  <section className="section">
    {heading ? (
      <div className="section__head">
        <h2>{heading}</h2>
      </div>
    ) : null}
    {children}
  </section>
)

/**
 * Главная собирается из блоков, включённых редакцией. Порядок блоков — порядок в
 * списке: сайт не решает за редакцию, что показать выше.
 */
export const HomeBlocks = ({ site, blocks, data }: { site: SiteContext; blocks: Block[]; data: HomeData }) => (
  <>
    {blocks
      .filter((block) => block.enabled !== false)
      .map((block, index) => {
        const key = `${block.blockType}-${index}`
        switch (block.blockType) {
          case 'heroSpotlight': {
            const items = Array.isArray(block.items) ? block.items : []
            return (
              <Section key={key} heading={block.heading as string | undefined}>
                <CardGrid items={items.map(tenantTitleCard)} empty="Витрина пока не заполнена." shape={site.layout.card} />
              </Section>
            )
          }
          case 'latestUpdates':
            return (
              <Section key={key} heading={block.heading as string | undefined}>
                <CardGrid items={data.latest.map(tenantTitleCard)} empty="Обновлений пока нет." shape={site.layout.card} />
              </Section>
            )
          case 'releaseSchedule':
            return (
              <Section key={key} heading={block.heading as string | undefined}>
                {data.schedule.length === 0 ? (
                  <p className="notice">На ближайшие дни выходов не запланировано.</p>
                ) : (
                  <ul className="list">
                    {data.schedule.map((event) => (
                      <li key={`${event.label}-${event.airsAt}`} className="row">
                        <time dateTime={event.airsAt}>
                          {new Date(event.airsAt).toLocaleString('ru-RU', {
                            day: '2-digit',
                            month: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </time>
                        {event.href ? <Link href={event.href}>{event.label}</Link> : <span>{event.label}</span>}
                      </li>
                    ))}
                  </ul>
                )}
                <p style={{ marginTop: '1rem' }}>
                  <Link href="/schedule/">Всё расписание</Link>
                </p>
              </Section>
            )
          case 'editorialPicks': {
            const items = Array.isArray(block.collections) ? block.collections : []
            return (
              <Section key={key} heading={block.heading as string | undefined}>
                <CardGrid items={items.map(collectionCard)} empty="Подборок пока нет." shape={site.layout.card} />
              </Section>
            )
          }
          case 'newsFeed':
            return (
              <Section key={key} heading={block.heading as string | undefined}>
                <CardGrid items={data.posts.map(postCard)} empty="Материалов пока нет." shape={site.layout.card} />
              </Section>
            )
          case 'genreRails': {
            const genres = Array.isArray(block.genres) ? (block.genres as Record<string, unknown>[]) : data.genres
            return (
              <Section key={key} heading={(block.heading as string | undefined) ?? 'Жанры'}>
                <div className="row">
                  {genres.map((genre) => (
                    <Link key={String(genre.slug)} className="tag" href={`/catalog/?genre=${String(genre.slug)}`}>
                      {String(genre.name)}
                    </Link>
                  ))}
                </div>
              </Section>
            )
          }
          case 'textSection':
            return (
              <Section key={key} heading={block.heading as string | undefined}>
                <p style={{ maxWidth: '70ch' }}>{String(block.body ?? '')}</p>
              </Section>
            )
          default:
            return null
        }
      })}
    <section className="section">
      <p className="card__meta">{site.profile.purpose}</p>
    </section>
  </>
)
