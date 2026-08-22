/**
 * Редакционный проход: то, что можно решить по собственным данным.
 *
 * Контур намеренно разделён на две части. Здесь — только те шаги, для которых
 * фабрике достаточно своей базы: смена состояния после выхода, снятие
 * просроченных анонсов, поиск витрин и связей, которые пора обновить. Шаги,
 * требующие внешнего источника (поиск новинок, метрики поведения), выполняются
 * отдельно и без переданного контракта возвращают BLOCKED_INPUT, а не выдумку.
 *
 * По умолчанию проход ничего не меняет: `--apply` включает запись явно.
 */
import { getPayload } from 'payload'

import config from '../src/payload.config'
import { decideForTitle, needsOwnText } from '../src/editorial/rules'
import { UPCOMING_STATES } from '../src/seo/profiles'

const apply = process.argv.includes('--apply')
/** Сколько дней анонс без обновлений считается просроченным. */
const STALE_DAYS = Number(process.env.EDITORIAL_STALE_DAYS ?? '180')

const payload = await getPayload({ config })
const now = new Date()

type Action = {
  action: string
  collection: string
  id: string | number
  title: string
  from?: string
  to?: string
  reason: string
  applied: boolean
}

const actions: Action[] = []
const blocked: { step: string; reason: string }[] = []

// --- 1. Вышедшее перестаёт быть анонсом ------------------------------------
// Дата подтверждена и уже наступила — состояние обязано смениться само.
// Иначе произведение остаётся на сайте премьер и конкурирует с профильным.
const upcoming = await payload.find({
  collection: 'titles',
  where: { releaseState: { in: [...UPCOMING_STATES] } },
  limit: 1000,
  depth: 0,
  overrideAccess: true,
})

for (const doc of upcoming.docs) {
  const record = doc as unknown as Record<string, unknown>
  const decision = decideForTitle(record, now, STALE_DAYS)
  if (!decision) continue

  if (apply) {
    // Снятие анонса — не удаление факта: удалять решает редакция, проход лишь
    // убирает просроченную запись из публичной выдачи.
    const data = decision.action === 'release_state_transition'
      ? { releaseState: 'released', status: 'ongoing' }
      : { availability: 'unavailable' }
    await payload.update({ collection: 'titles', id: doc.id, overrideAccess: true, data: data as never })
  }

  actions.push({
    action: decision.action,
    collection: 'titles',
    id: doc.id,
    title: String(record.primaryName ?? ''),
    from: decision.from,
    to: decision.to,
    reason: decision.reason,
    applied: apply,
  })
}

// --- 3. Витрины и внутренние связи ------------------------------------------
// Публикация без собственного текста не индексируется, значит витрине она
// ничего не даёт: такие карточки выносим в отчёт, а не прячем.
const publications = await payload.find({
  collection: 'tenant-titles',
  limit: 2000,
  depth: 1,
  overrideAccess: true,
})
for (const doc of publications.docs) {
  const record = doc as unknown as Record<string, unknown>
  if (needsOwnText(record)) {
    actions.push({
      action: 'missing_own_text',
      collection: 'tenant-titles',
      id: doc.id,
      title: String(record.slug ?? ''),
      reason: 'публикация без собственного текста не индексируется и не годится для витрины',
      applied: false,
    })
  }
}

// --- 4. Шаги, требующие внешнего источника ----------------------------------
// Их нельзя выполнить и нельзя изобразить: контракт Content API не передан.
blocked.push({
  step: 'discover_new_releases',
  reason:
    'BLOCKED_INPUT: контракт Content API не передан (knowledge/cdnvideohub/content-api.yaml: '
    + 'not_provided). Поиск новинок в источнике невозможен, придумывать записи запрещено.',
})
blocked.push({
  step: 'behaviour_metrics',
  reason:
    'BLOCKED_INPUT: аналитика не подключена. CTR карточки, переходы к просмотру, recirculation '
    + 'и возвраты не измерены; подставлять правдоподобные числа запрещено.',
})

console.log(JSON.stringify({
  generatedAt: now.toISOString(),
  mode: apply ? 'apply' : 'dry_run',
  staleDays: STALE_DAYS,
  actions,
  blocked,
  counts: {
    upcoming: upcoming.totalDocs,
    transitions: actions.filter((item) => item.action === 'release_state_transition').length,
    stale: actions.filter((item) => item.action === 'stale_announcement').length,
    missingOwnText: actions.filter((item) => item.action === 'missing_own_text').length,
  },
}))

await payload.db.destroy?.()
process.exit(0)
