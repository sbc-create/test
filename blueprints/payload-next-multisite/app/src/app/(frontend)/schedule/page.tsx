import type { Metadata } from 'next'

import { Breadcrumbs } from '../../../components/Breadcrumbs'
import { listReleaseEvents } from '../../../lib/content'
import { currentSite, payloadClient } from '../../../lib/site'
import { absoluteUrl, buildMetadata } from '../../../seo/metadata'

export const dynamic = 'force-dynamic'

const HEADING = 'Расписание выхода серий'
const STATE_LABELS: Record<string, string> = {
  announced: 'анонсировано',
  released: 'вышло',
  delayed: 'перенесено',
  cancelled: 'отменено',
}

export const generateMetadata = async (): Promise<Metadata> => {
  const site = await currentSite()
  return buildMetadata(
    {
      tenant: site.tenant,
      pageType: 'category',
      path: '/schedule/',
      heading: HEADING,
      description: `Даты выхода серий на ближайшие две недели — ${site.siteName}.`,
    },
    site.siteName,
  )
}

const SchedulePage = async () => {
  const site = await currentSite()
  const payload = await payloadClient()
  const from = new Date()
  const to = new Date(from.getTime() + 14 * 24 * 3600 * 1000)
  const events = await listReleaseEvents(payload, { from, to })

  const byDay = new Map<string, typeof events.docs>()
  for (const event of events.docs) {
    const day = new Date(event.airsAt).toLocaleDateString('ru-RU')
    byDay.set(day, [...(byDay.get(day) ?? []), event])
  }

  return (
    <>
      <Breadcrumbs
        origin={absoluteUrl(site.tenant, '')}
        crumbs={[
          { title: 'Главная', href: '/' },
          { title: HEADING, href: '/schedule/' },
        ]}
      />
      <h1>{HEADING}</h1>
      {byDay.size === 0 ? (
        <p className="notice">На ближайшие две недели выходов не запланировано.</p>
      ) : (
        [...byDay.entries()].map(([day, items]) => (
          <section className="section" key={day}>
            <h2>{day}</h2>
            <ul className="list">
              {items.map((event) => (
                <li key={event.id} className="row">
                  <time dateTime={event.airsAt}>
                    {/* Неточную дату не показываем как точное время: это выдуманный факт. */}
                    {event.precision === 'exact'
                      ? new Date(event.airsAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
                      : 'время не указано'}
                  </time>
                  <span>{event.label}</span>
                  <span className="tag">{STATE_LABELS[event.state] ?? event.state}</span>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </>
  )
}

export default SchedulePage
