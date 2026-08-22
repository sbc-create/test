import type { CollectionBeforeChangeHook, Field, PayloadRequest } from 'payload'

/**
 * Запрет межсайтовых связей.
 *
 * Доступ на чтение изолирует выборки, но не запрещает СОХРАНИТЬ ссылку на чужой
 * документ: подборка Сайта A могла бы указывать на публикацию Сайта B, и та
 * утекла бы через populate при рендере. Поэтому перед записью каждая ссылка на
 * tenant-scoped коллекцию сверяется по владельцу.
 */

/** Коллекции, у которых есть поле tenant. Держится синхронно с payload.config.ts. */
export const TENANT_SCOPED_SLUGS = new Set([
  'tenant-titles',
  'editorial-collections',
  'posts',
  'pages',
  'media',
  'redirects',
  'audit-log',
  'comments',
  'comment-reports',
  'player-profiles',
  'site-settings',
  'navigation',
  'home-layout',
])

type Reference = { relationTo: string; id: string | number }

const idOf = (value: unknown): string | number | null => {
  if (typeof value === 'string' || typeof value === 'number') return value
  if (value && typeof value === 'object' && 'id' in (value as Record<string, unknown>)) {
    const id = (value as { id: unknown }).id
    if (typeof id === 'string' || typeof id === 'number') return id
  }
  return null
}

/** Значение поля relationship/upload в любой из поддерживаемых Payload форм. */
const collectFieldReferences = (field: Field, value: unknown, out: Reference[]): void => {
  if (value === null || value === undefined) return
  const relationTo = (field as { relationTo?: string | string[] }).relationTo

  if (Array.isArray(value)) {
    for (const item of value) collectFieldReferences(field, item, out)
    return
  }

  // Полиморфная связь приходит как { relationTo, value }.
  if (value && typeof value === 'object' && 'relationTo' in (value as Record<string, unknown>)) {
    const polymorphic = value as { relationTo: string; value: unknown }
    const id = idOf(polymorphic.value)
    if (id !== null) out.push({ relationTo: polymorphic.relationTo, id })
    return
  }

  const id = idOf(value)
  if (id === null) return
  if (typeof relationTo === 'string') out.push({ relationTo, id })
}

const walkFields = (fields: Field[], data: unknown, out: Reference[]): void => {
  if (!data || typeof data !== 'object') return
  const record = data as Record<string, unknown>

  for (const field of fields) {
    switch (field.type) {
      case 'row':
      case 'collapsible':
        walkFields(field.fields, record, out)
        break
      case 'tabs':
        for (const tab of field.tabs) {
          if ('name' in tab && tab.name) walkFields(tab.fields, record[tab.name], out)
          else walkFields(tab.fields, record, out)
        }
        break
      case 'group': {
        const name = 'name' in field ? field.name : undefined
        walkFields(field.fields, name ? record[name] : record, out)
        break
      }
      case 'array': {
        const rows = record[field.name]
        if (Array.isArray(rows)) for (const row of rows) walkFields(field.fields, row, out)
        break
      }
      case 'blocks': {
        const rows = record[field.name]
        if (!Array.isArray(rows)) break
        for (const row of rows) {
          const blockType = (row as { blockType?: string })?.blockType
          const block = field.blocks.find((candidate) =>
            typeof candidate === 'string' ? candidate === blockType : candidate.slug === blockType,
          )
          if (block && typeof block !== 'string') walkFields(block.fields, row, out)
        }
        break
      }
      case 'relationship':
      case 'upload':
        collectFieldReferences(field, record[field.name], out)
        break
      default:
        break
    }
  }
}

export const collectReferences = (fields: Field[], data: unknown): Reference[] => {
  const out: Reference[] = []
  walkFields(fields, data, out)
  return out
}

/**
 * Хук ставится на все tenant-scoped коллекции. Читает связанные документы с
 * overrideAccess: true намеренно — задача проверки в том, чтобы УВИДЕТЬ чужой
 * документ и отказать, а не сделать вид, что его нет.
 */
export const enforceTenantIntegrity: CollectionBeforeChangeHook = async ({
  collection,
  data,
  originalDoc,
  req,
}) => {
  const tenant = idOf((data as Record<string, unknown>)?.tenant ?? originalDoc?.tenant)
  if (tenant === null) return data

  const references = collectReferences(collection.fields, data).filter((reference) =>
    TENANT_SCOPED_SLUGS.has(reference.relationTo),
  )
  if (references.length === 0) return data

  const payload = (req as PayloadRequest).payload
  const seen = new Set<string>()

  for (const reference of references) {
    const key = `${reference.relationTo}:${reference.id}`
    if (seen.has(key)) continue
    seen.add(key)

    const related = await payload.findByID({
      collection: reference.relationTo as never,
      id: reference.id,
      depth: 0,
      overrideAccess: true,
      disableErrors: true,
      req,
    })
    if (!related) {
      throw new Error(
        `BLOCKED_INPUT: ссылка на несуществующий документ ${reference.relationTo}#${reference.id}`,
      )
    }
    const relatedTenant = idOf((related as Record<string, unknown>).tenant)
    if (String(relatedTenant) !== String(tenant)) {
      throw new Error(
        `BLOCKED_TENANT_LEAK: ${collection.slug} сайта ${tenant} ссылается на ` +
          `${reference.relationTo}#${reference.id}, принадлежащий сайту ${relatedTenant}`,
      )
    }
  }

  return data
}
