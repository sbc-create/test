import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'

import { Breadcrumbs } from '../../../../../../components/Breadcrumbs'
import { Comments } from '../../../../../../components/Comments'
import { Player } from '../../../../../../components/Player'
import { getTenantTitle, listEpisodes, listSeasons } from '../../../../../../lib/content'
import { titleNameOf } from '../../../../../../lib/present'
import { currentSite, payloadClient } from '../../../../../../lib/site'
import { playerConfigFor } from '../../../../../../player/server'
import { absoluteUrl, buildMetadata } from '../../../../../../seo/metadata'
import { seasonNumberOf } from '../page'

export const dynamic = 'force-dynamic'

type Params = Promise<{ slug: string; season: string; episode: string }>

const episodeNumberOf = (segment: string): number | null => {
  const match = /^episode-([1-9]\d*)$/.exec(segment)
  return match ? Number(match[1]) : null
}

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : null

const load = async (slug: string, seasonSegment: string, episodeSegment: string) => {
  const site = await currentSite()
  const payload = await payloadClient()
  const seasonNumber = seasonNumberOf(seasonSegment)
  const episodeNumber = episodeNumberOf(episodeSegment)
  if (seasonNumber === null || episodeNumber === null) return null

  const doc = await getTenantTitle(payload, site.tenant, slug)
  if (!doc) return null

  const shared = asRecord(asRecord(doc)!.title)
  if (!shared?.id) return null

  const seasons = await listSeasons(payload, shared.id as string | number)
  const season = seasons.docs.find((item) => Number(asRecord(item)!.number) === seasonNumber)
  if (!season) return null

  const episodes = await listEpisodes(payload, asRecord(season)!.id as string | number)
  const episode = episodes.docs.find((item) => Number(asRecord(item)!.number) === episodeNumber)
  if (!episode) return null

  return { site, payload, doc, shared, season, episode, seasonNumber, episodeNumber, episodes }
}

export const generateMetadata = async ({ params }: { params: Params }): Promise<Metadata> => {
  const { slug, season, episode } = await params
  const loaded = await load(slug, season, episode)
  if (!loaded) return { robots: 'noindex,follow', title: 'Серия не найдена' }

  const name = titleNameOf(loaded.doc)
  return buildMetadata(
    {
      tenant: loaded.site.tenant,
      pageType: 'episode',
      path: `/catalog/${slug}/season-${loaded.seasonNumber}/episode-${loaded.episodeNumber}/`,
      heading: `${name}, сезон ${loaded.seasonNumber}, серия ${loaded.episodeNumber}`,
      description: `Серия ${loaded.episodeNumber} сезона ${loaded.seasonNumber} — ${name}.`,
    },
    loaded.site.siteName,
  )
}

const EpisodePage = async ({ params }: { params: Params }) => {
  const { slug, season, episode } = await params
  const loaded = await load(slug, season, episode)
  if (!loaded) notFound()

  const { site, payload, shared, seasonNumber, episodeNumber, episodes } = loaded
  const name = titleNameOf(loaded.doc)
  const episodeRecord = asRecord(loaded.episode)!
  const player = await playerConfigFor(payload, site.tenant, shared, {
    season: seasonNumber,
    episode: episodeNumber,
  })

  const numbers = episodes.docs.map((item) => Number(asRecord(item)!.number)).sort((a, b) => a - b)
  const previous = numbers.filter((value) => value < episodeNumber).pop()
  const next = numbers.find((value) => value > episodeNumber)
  const base = `/catalog/${slug}/season-${seasonNumber}`

  return (
    <>
      <Breadcrumbs
        origin={absoluteUrl(site.tenant, '')}
        crumbs={[
          { title: 'Главная', href: '/' },
          { title: 'Каталог', href: '/catalog/' },
          { title: name, href: `/catalog/${slug}/` },
          { title: `Сезон ${seasonNumber}`, href: `${base}/` },
          { title: `Серия ${episodeNumber}`, href: `${base}/episode-${episodeNumber}/` },
        ]}
      />
      <h1>
        {name}, сезон {seasonNumber}, серия {episodeNumber}
        {episodeRecord.name ? ` — ${String(episodeRecord.name)}` : ''}
      </h1>

      <section className="section">
        {player.attributes && episodeRecord.playbackAvailable !== false ? (
          <Player
            attributes={player.attributes}
            scriptUrl={player.scriptUrl}
            season={seasonNumber}
            episode={episodeNumber}
            unavailableText="Эта серия сейчас недоступна для просмотра."
          />
        ) : (
          <p className="notice" role="status">
            {player.reason ?? 'Эта серия сейчас недоступна для просмотра.'}
          </p>
        )}
      </section>

      <nav className="row" aria-label="Навигация по сериям">
        {previous ? (
          <Link className="button button--ghost" href={`${base}/episode-${previous}/`} rel="prev">
            Предыдущая серия
          </Link>
        ) : null}
        <Link className="button button--ghost" href={`${base}/`}>
          Все серии сезона
        </Link>
        {next ? (
          <Link className="button button--ghost" href={`${base}/episode-${next}/`} rel="next">
            Следующая серия
          </Link>
        ) : null}
      </nav>

      <Comments
        site={site}
        targetType="episode"
        targetId={String(episodeRecord.id)}
        targetUrl={`${base}/episode-${episodeNumber}/`}
      />
    </>
  )
}

export default EpisodePage
