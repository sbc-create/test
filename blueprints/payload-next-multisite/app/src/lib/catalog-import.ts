/**
 * Загрузка каталога из пакета сайта в CMS.
 *
 * Чего не хватало. Выкат payload-сайта применял конфигурацию тенанта и на этом
 * заканчивался: `content_package_ref` пакета не читал никто. Сайт поднимался с
 * пустым каталогом — технически живая и визуально пустая витрина, на которой
 * семейство шаблонов не на чем было увидеть.
 *
 * Разделение документов не формальность. Общий факт живёт в `titles` и виден
 * всем сайтам; URL, редакционный текст и SEO принадлежат одному сайту и живут
 * в `tenant-titles`. Импорт обязан класть каждое поле на свою сторону.
 *
 * Чего импорт не делает. Не сочиняет редакционные тексты, годы, жанры и
 * рейтинги: чего нет в пакете, того нет и в базе. `editorialIntro` остаётся
 * пустым — это текст редакции сайта, и выдумывать его импорт не вправе.
 */

/** Запись каталога в пакете сайта. */
export type PackItem = {
  id: string
  slug: string
  category?: string
  title: string
  description?: string
  availability?: string
  updated_at?: string
}

export type Pack = { schema_version?: number; kind?: string; titles?: PackItem[] }

/** Общие факты тайтла — то, что видно всем сайтам. */
export type TitleFacts = {
  primaryName: string
  kind: string
  status: string
  availability: string
  factualSynopsis: string | null
  source: string
  sourceRef: string
  sourceUpdatedAt: string | null
}

export type Counters = {
  titlesCreated: number
  titlesUpdated: number
  publicationsCreated: number
  publicationsUpdated: number
}

/** Ошибка входных данных: пакет не годится, и импорт обязан остановиться. */
export class PackRejected extends Error {}

// Доступность сверяется со словарём коллекции: незнакомое значение — это
// расхождение контрактов, а не повод тихо подставить «доступен».
const AVAILABILITY = new Set(['available', 'unavailable', 'withdrawn'])

// URL-код проверяется тем же правилом, что и поле коллекции: иначе запись
// доедет до Payload и упадёт там валидацией без указания, чья это запись.
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

/** Разбирает пакет и отвергает то, что нельзя импортировать молча. */
export const readPack = (raw: unknown): PackItem[] => {
  const pack = raw as Pack
  const items = pack?.titles
  if (!Array.isArray(items) || items.length === 0) {
    throw new PackRejected('в пакете контента нет записей каталога')
  }
  const seen = new Set<string>()
  for (const item of items) {
    if (!item?.id) throw new PackRejected('запись каталога без идентификатора источника')
    if (!item.title) throw new PackRejected(`запись ${item.id} без названия`)
    if (!SLUG.test(item.slug ?? '')) {
      throw new PackRejected(`запись ${item.id} имеет непригодный URL-код «${item.slug}»`)
    }
    if (seen.has(item.slug)) {
      throw new PackRejected(`URL-код «${item.slug}» встречается в пакете дважды`)
    }
    seen.add(item.slug)
    const availability = item.availability ?? 'available'
    if (!AVAILABILITY.has(availability)) {
      throw new PackRejected(`запись ${item.id} имеет неизвестную доступность «${availability}»`)
    }
  }
  return items
}

/** Общие факты записи. Происхождение проставляется всегда — оно и есть право. */
export const factsOf = (item: PackItem): TitleFacts => ({
  primaryName: item.title,
  kind: 'series',
  status: 'ongoing',
  availability: item.availability ?? 'available',
  factualSynopsis: item.description ?? null,
  source: 'import_file',
  sourceRef: item.id,
  sourceUpdatedAt: item.updated_at ? new Date(item.updated_at).toISOString() : null,
})

type PayloadLike = {
  find: (args: Record<string, unknown>) => Promise<{ docs: { id: number | string }[] }>
  create: (args: Record<string, unknown>) => Promise<{ id: number | string }>
  update: (args: Record<string, unknown>) => Promise<unknown>
}

/**
 * Кладёт записи пакета в CMS для одного тенанта.
 *
 * Повторный прогон находит уже созданное по происхождению (`sourceRef`) и по
 * паре «тенант + URL-код», обновляет поля пакета и ничего не создаёт заново.
 */
export const importCatalog = async (
  payload: PayloadLike,
  tenantId: number | string,
  items: PackItem[],
): Promise<Counters> => {
  const counters: Counters = {
    titlesCreated: 0,
    titlesUpdated: 0,
    publicationsCreated: 0,
    publicationsUpdated: 0,
  }

  for (const item of items) {
    const facts = factsOf(item)

    const known = await payload.find({
      collection: 'titles',
      where: { sourceRef: { equals: item.id } },
      limit: 1,
      overrideAccess: true,
    })

    let titleId: number | string
    if (known.docs[0]) {
      titleId = known.docs[0].id
      await payload.update({ collection: 'titles', id: titleId, data: facts, overrideAccess: true })
      counters.titlesUpdated += 1
    } else {
      titleId = (await payload.create({ collection: 'titles', data: facts, overrideAccess: true })).id
      counters.titlesCreated += 1
    }

    const publication = { tenant: tenantId, title: titleId, slug: item.slug, _status: 'published' }
    const existing = await payload.find({
      collection: 'tenant-titles',
      where: { and: [{ tenant: { equals: tenantId } }, { slug: { equals: item.slug } }] },
      limit: 1,
      overrideAccess: true,
    })

    if (existing.docs[0]) {
      await payload.update({
        collection: 'tenant-titles',
        id: existing.docs[0].id,
        data: publication,
        overrideAccess: true,
      })
      counters.publicationsUpdated += 1
    } else {
      await payload.create({ collection: 'tenant-titles', data: publication, overrideAccess: true })
      counters.publicationsCreated += 1
    }
  }

  return counters
}
