/**
 * Применение конфигурации тенанта к CMS.
 *
 * Идемпотентно: повторный запуск с той же конфигурацией не создаёт вторых
 * записей и не затирает редакционный контент. Меняются только поля, которыми
 * владеет пакет сайта, — название, домен, профиль, тема, политика комментариев,
 * навигация и юридические тексты.
 */
import { readFileSync } from 'fs'

import { getPayload } from 'payload'

import config from '../src/payload.config'

type TenantConfig = {
  site_id: string
  environment: string
  domain: string
  tenant: Record<string, unknown>
  siteSettings: Record<string, unknown>
  navigation: Record<string, unknown>
  playerProfile: Record<string, unknown>
  legalDocuments: { slug: string; name: string; summary?: string; body: string }[]
}

const source = process.argv[2]
if (!source) {
  console.error('BLOCKED_INPUT: не передан путь к tenant-config.json')
  process.exit(2)
}

const configuration = JSON.parse(readFileSync(source, 'utf8')) as TenantConfig
const payload = await getPayload({ config })

const counters = { created: 0, updated: 0, unchanged: 0 }

const upsertGlobal = async (
  collection: 'site-settings' | 'navigation' | 'home-layout' | 'player-profiles',
  tenantId: string | number,
  data: Record<string, unknown>,
) => {
  const existing = await payload.find({
    collection,
    where: { tenant: { equals: tenantId } },
    limit: 1,
    depth: 0,
    overrideAccess: true,
  })
  if (existing.docs.length === 0) {
    await payload.create({ collection, overrideAccess: true, data: { ...data, tenant: tenantId } as never })
    counters.created += 1
    return
  }
  const current = existing.docs[0] as unknown as Record<string, unknown>
  const changed = Object.entries(data).some(
    ([key, value]) => JSON.stringify(current[key] ?? null) !== JSON.stringify(value ?? null),
  )
  if (!changed) {
    counters.unchanged += 1
    return
  }
  await payload.update({ collection, id: current.id as string | number, overrideAccess: true, data: data as never })
  counters.updated += 1
}

const slug = String(configuration.tenant.slug ?? '')
if (!slug) {
  console.error('BLOCKED_INPUT: в конфигурации нет кода сайта')
  process.exit(2)
}

const existingTenant = await payload.find({
  collection: 'tenants',
  where: { slug: { equals: slug } },
  limit: 1,
  depth: 0,
  overrideAccess: true,
})

let tenantId: string | number
if (existingTenant.docs.length === 0) {
  const created = await payload.create({
    collection: 'tenants',
    overrideAccess: true,
    data: configuration.tenant as never,
  })
  tenantId = created.id
  counters.created += 1
} else {
  const current = existingTenant.docs[0]!
  tenantId = current.id
  await payload.update({
    collection: 'tenants',
    id: tenantId,
    overrideAccess: true,
    data: configuration.tenant as never,
  })
  counters.updated += 1
}

await upsertGlobal('site-settings', tenantId, configuration.siteSettings)
await upsertGlobal('navigation', tenantId, { label: 'Навигация', ...configuration.navigation })
await upsertGlobal('player-profiles', tenantId, configuration.playerProfile)

// Главная существует всегда: без неё сайт отдаёт пустую страницу вместо блоков.
const home = await payload.find({
  collection: 'home-layout',
  where: { tenant: { equals: tenantId } },
  limit: 1,
  depth: 0,
  overrideAccess: true,
})
if (home.docs.length === 0) {
  await payload.create({
    collection: 'home-layout',
    overrideAccess: true,
    data: { tenant: tenantId, label: 'Главная', blocks: [] } as never,
  })
  counters.created += 1
}

for (const document of configuration.legalDocuments) {
  const existing = await payload.find({
    collection: 'pages',
    where: { and: [{ tenant: { equals: tenantId } }, { slug: { equals: document.slug } }] },
    limit: 1,
    depth: 0,
    overrideAccess: true,
    draft: true,
  })
  const data = { name: document.name, slug: document.slug, body: document.body, _status: 'published' }
  if (existing.docs.length === 0) {
    await payload.create({ collection: 'pages', overrideAccess: true, data: { ...data, tenant: tenantId } as never })
    counters.created += 1
  } else {
    await payload.update({
      collection: 'pages',
      id: existing.docs[0]!.id,
      overrideAccess: true,
      data: data as never,
    })
    counters.updated += 1
  }
}

console.log(JSON.stringify({ tenant: slug, tenantId, ...counters }))
await payload.db.destroy?.()
process.exit(0)
