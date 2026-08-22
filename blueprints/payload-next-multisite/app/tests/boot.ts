/** Проверка, что конфигурация действительно поднимается на реальном PostgreSQL. */
import { getPayload } from 'payload'
import config from '../src/payload.config'

const payload = await getPayload({ config })
const slugs = payload.config.collections.map((collection) => collection.slug).sort()
console.log(`collections=${slugs.length}`)
console.log(slugs.join(' '))
await payload.db.destroy?.()
process.exit(0)
