/**
 * Проверки загрузки каталога из пакета сайта.
 *
 * Предмет проверок — правила приёма пакета и раскладка полей по двум сторонам:
 * общий факт против публикации сайта. Базы здесь нет намеренно: подставной
 * payload записывает вызовы, и видно не «не упало», а что именно записано.
 */
import { PackRejected, factsOf, importCatalog, readPack } from '../src/lib/catalog-import'
import { assert, assertEqual, check, summary } from './harness'

const запись = (over: Record<string, unknown> = {}) => ({
  id: 'pack-1',
  slug: 'zapis-odin',
  title: 'Запись один',
  description: 'Описание из источника',
  availability: 'available',
  updated_at: '2026-09-06',
  ...over,
})

const пакет = (...items: Record<string, unknown>[]) => ({ schema_version: 1, titles: items })

/** Подставной payload: помнит документы и все вызовы записи. */
const stub = () => {
  const store: Record<string, { id: number; data: Record<string, unknown> }[]> = {
    titles: [],
    'tenant-titles': [],
  }
  let next = 1
  const matches = (doc: Record<string, unknown>, where: Record<string, unknown>): boolean => {
    if (Array.isArray(where.and)) {
      return where.and.every((part) => matches(doc, part as Record<string, unknown>))
    }
    return Object.entries(where).every(([field, cond]) => {
      const expected = (cond as { equals?: unknown }).equals
      return doc[field] === expected
    })
  }
  return {
    store,
    find: async ({ collection, where }: never) => ({
      docs: (store[collection as unknown as string] ?? [])
        .filter((row) => matches(row.data, where as unknown as Record<string, unknown>))
        .slice(0, 1),
    }),
    create: async ({ collection, data }: never) => {
      const row = { id: next++, data: { ...(data as unknown as Record<string, unknown>) } }
      store[collection as unknown as string].push(row)
      return row
    },
    update: async ({ collection, id, data }: never) => {
      const row = store[collection as unknown as string].find((item) => item.id === id)
      if (!row) throw new Error('обновление несуществующего документа')
      row.data = { ...row.data, ...(data as unknown as Record<string, unknown>) }
      return row
    },
  }
}

await check('пустой пакет отвергается, а не импортируется как ноль записей', () => {
  let rejected = false
  try {
    readPack({ schema_version: 1, titles: [] })
  } catch (error) {
    rejected = error instanceof PackRejected
  }
  assert(rejected, 'пустой пакет принят')
})

await check('незнакомая доступность отвергается поимённо', () => {
  let message = ''
  try {
    readPack(пакет(запись({ availability: 'maybe' })))
  } catch (error) {
    message = (error as Error).message
  }
  assert(message.includes('pack-1'), `в отказе нет записи: ${message}`)
  assert(message.includes('maybe'), `в отказе нет значения: ${message}`)
})

await check('непригодный URL-код отвергается до записи в базу', () => {
  let rejected = false
  try {
    readPack(пакет(запись({ slug: 'Запись Один' })))
  } catch (error) {
    rejected = error instanceof PackRejected
  }
  assert(rejected, 'пакет с непригодным URL-кодом принят')
})

await check('повторный URL-код в одном пакете отвергается', () => {
  let rejected = false
  try {
    readPack(пакет(запись(), запись({ id: 'pack-2' })))
  } catch (error) {
    rejected = error instanceof PackRejected
  }
  assert(rejected, 'два одинаковых URL-кода приняты')
})

await check('происхождение записи сохраняется, а описание идёт в фактическое поле', () => {
  const facts = factsOf(запись() as never)
  assertEqual(facts.source, 'import_file', 'источник')
  assertEqual(facts.sourceRef, 'pack-1', 'ссылка на запись источника')
  assertEqual(facts.factualSynopsis, 'Описание из источника', 'фактическое описание')
  assert(facts.sourceUpdatedAt?.startsWith('2026-09-06'), `дата источника: ${facts.sourceUpdatedAt}`)
})

await check('редакционный текст не выдумывается', () => {
  const facts = factsOf(запись() as never) as unknown as Record<string, unknown>
  assert(!('editorialIntro' in facts), 'импорт заполняет редакционное вступление')
})

await check('факт и публикация кладутся на разные стороны', async () => {
  const payload = stub()
  const items = readPack(пакет(запись()))
  await importCatalog(payload as never, 7, items)

  assertEqual(payload.store.titles.length, 1, 'общих фактов')
  assertEqual(payload.store['tenant-titles'].length, 1, 'публикаций')
  assert(!('tenant' in payload.store.titles[0].data), 'общий факт получил тенанта')
  assertEqual(payload.store['tenant-titles'][0].data.tenant, 7, 'тенант публикации')
  assertEqual(payload.store['tenant-titles'][0].data.slug, 'zapis-odin', 'URL-код публикации')
  assertEqual(payload.store['tenant-titles'][0].data._status, 'published', 'состояние публикации')
})

await check('повторный прогон ничего не создаёт заново', async () => {
  const payload = stub()
  const items = readPack(пакет(запись()))
  await importCatalog(payload as never, 7, items)
  const second = await importCatalog(payload as never, 7, items)

  assertEqual(second.titlesCreated, 0, 'создано фактов при повторе')
  assertEqual(second.publicationsCreated, 0, 'создано публикаций при повторе')
  assertEqual(second.titlesUpdated, 1, 'обновлено фактов при повторе')
  assertEqual(payload.store.titles.length, 1, 'всего фактов')
  assertEqual(payload.store['tenant-titles'].length, 1, 'всего публикаций')
})

await check('второй сайт переиспользует общий факт и заводит свою публикацию', async () => {
  const payload = stub()
  const items = readPack(пакет(запись()))
  await importCatalog(payload as never, 7, items)
  await importCatalog(payload as never, 8, items)

  assertEqual(payload.store.titles.length, 1, 'общий факт продублирован')
  assertEqual(payload.store['tenant-titles'].length, 2, 'публикаций на два сайта')
  assertEqual(payload.store['tenant-titles'][1].data.tenant, 8, 'тенант второй публикации')
})

process.exit(summary())
