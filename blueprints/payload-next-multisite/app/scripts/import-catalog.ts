/**
 * Шаг выката: загрузка каталога из пакета сайта в CMS.
 *
 * Разбор пакета и запись документов живут в `src/lib/catalog-import`, чтобы
 * правила приёма проверялись тестами без базы. Здесь остаётся только то, что
 * принадлежит запуску: аргументы, тенант и отчёт шага.
 */
import { readFileSync } from 'fs'

import { getPayload } from 'payload'

import config from '../src/payload.config'
import { PackRejected, importCatalog, readPack } from '../src/lib/catalog-import'

const tenantSlug = process.argv[2]
const packPath = process.argv[3]
if (!tenantSlug || !packPath) {
  console.error('BLOCKED_INPUT: нужны slug тенанта и путь к пакету контента')
  process.exit(2)
}

let items
try {
  items = readPack(JSON.parse(readFileSync(packPath, 'utf8')))
} catch (error) {
  const detail = error instanceof PackRejected ? error.message : String(error)
  console.error(`BLOCKED_INPUT: ${detail}`)
  process.exit(2)
}

const payload = await getPayload({ config })

const tenants = await payload.find({
  collection: 'tenants',
  where: { slug: { equals: tenantSlug } },
  limit: 1,
  overrideAccess: true,
})
const tenant = tenants.docs[0]
if (!tenant) {
  console.error(`BLOCKED_INPUT: тенант «${tenantSlug}» не заведён — сначала apply-tenant`)
  process.exit(2)
}

const counters = await importCatalog(payload as never, tenant.id, items)
console.log(JSON.stringify({ tenant: tenantSlug, items: items.length, ...counters }))
await payload.db.destroy?.()
process.exit(0)
