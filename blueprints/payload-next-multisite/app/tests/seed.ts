import sharp from 'sharp'

import type { Payload } from 'payload'

/**
 * Тестовые данные для проверки изоляции. Значения намеренно синтетические
 * (site_a/site_b/site_c, localhost-домены): выдуманный бренд и реальный домен
 * в фикстурах — это то, что потом уезжает в production.
 */

export type SeedTenant = {
  id: string | number
  slug: string
  domain: string
}

export type Seeded = {
  tenants: Record<'a' | 'b' | 'c', SeedTenant>
  users: Record<'super' | 'adminA' | 'editorA' | 'moderatorA' | 'adminB', { id: string | number; email: string }>
  docs: Record<string, Record<'a' | 'b' | 'c', string | number>>
  sharedTitle: string | number
}

const PASSWORD = 'FactoryTest!' + '2026'

/**
 * Чистое состояние перед прогоном. Список таблиц берётся из самой базы, а не
 * из захардкоженного перечня: иначе новая коллекция тихо остаётся с данными от
 * прошлого прогона и проверка изоляции начинает зависеть от истории.
 */
export const reset = async (payload: Payload): Promise<void> => {
  const result: unknown = await payload.db.drizzle.execute(
    "select table_name from information_schema.tables " +
      "where table_schema = 'public' and table_type = 'BASE TABLE' and table_name <> 'payload_migrations'",
  )
  const rows = ((result as { rows?: { table_name: string }[] }).rows ??
    (result as { table_name: string }[])) as { table_name: string }[]
  if (rows.length === 0) return
  await payload.db.drizzle.execute(
    `truncate table ${rows.map((row) => `"${row.table_name}"`).join(', ')} restart identity cascade`,
  )
}

export const seed = async (payload: Payload): Promise<Seeded> => {
  const profiles = {
    a: { seoProfile: 'catalog_authority', theme: 'portal_light' },
    b: { seoProfile: 'release_pulse', theme: 'pulse' },
    c: { seoProfile: 'editorial_guide', theme: 'editorial' },
  } as const

  const tenants = {} as Seeded['tenants']
  for (const key of ['a', 'b', 'c'] as const) {
    const doc = await payload.create({
      collection: 'tenants',
      overrideAccess: true,
      data: {
        name: `Сайт ${key.toUpperCase()}`,
        slug: `site_${key}`,
        domain: `site-${key}.localhost`,
        indexingEnabled: false,
        allowGuestComments: true,
        ...profiles[key],
      },
    })
    tenants[key] = { id: doc.id, slug: doc.slug as string, domain: doc.domain as string }
  }

  const makeUser = async (
    email: string,
    role: string,
    tenantIds: (string | number)[],
  ): Promise<{ id: string | number; email: string }> => {
    const doc = await payload.create({
      collection: 'users',
      overrideAccess: true,
      data: {
        email,
        password: PASSWORD,
        role,
        tenants: tenantIds.map((tenant) => ({ tenant })),
      } as never,
    })
    return { id: doc.id, email }
  }

  const users = {
    super: await makeUser('super@factory.test', 'super_admin', []),
    adminA: await makeUser('admin-a@factory.test', 'site_admin', [tenants.a.id]),
    editorA: await makeUser('editor-a@factory.test', 'editor', [tenants.a.id]),
    moderatorA: await makeUser('moderator-a@factory.test', 'moderator', [tenants.a.id]),
    adminB: await makeUser('admin-b@factory.test', 'site_admin', [tenants.b.id]),
  }

  // Общий каталог: один тайтл на все сайты — именно так и задумано.
  const rights = await payload.create({
    collection: 'rights-records',
    overrideAccess: true,
    data: {
      label: 'Тестовая запись о правах',
      holder: 'Тестовый правообладатель',
      contractRef: 'TEST-FIXTURE-ONLY',
      allowsPublication: true,
    } as never,
  })
  const sharedTitle = (
    await payload.create({
      collection: 'titles',
      overrideAccess: true,
      data: {
        primaryName: 'Общий тайтл каталога',
        kind: 'series',
        status: 'completed',
        year: 2024,
        rightsRecord: rights.id,
      } as never,
    })
  ).id

  const docs: Seeded['docs'] = {}
  const remember = (collection: string, key: 'a' | 'b' | 'c', id: string | number): void => {
    docs[collection] = docs[collection] ?? ({} as Record<'a' | 'b' | 'c', string | number>)
    docs[collection]![key] = id
  }

  for (const key of ['a', 'b', 'c'] as const) {
    const tenant = tenants[key].id
    const suffix = key

    const image = await sharp({
      create: { width: 8, height: 8, channels: 3, background: { r: 20, g: 20, b: 20 } },
    })
      .png()
      .toBuffer()
    const media = await payload.create({
      collection: 'media',
      overrideAccess: true,
      file: { data: image, mimetype: 'image/png', name: `fixture-${suffix}.png`, size: image.length },
      data: { tenant, alt: `Тестовое изображение ${suffix}` } as never,
    })
    remember('media', key, media.id)

    const page = await payload.create({
      collection: 'pages',
      overrideAccess: true,
      data: { tenant, name: `Страница ${suffix}`, slug: `page-${suffix}`, body: 'текст', _status: 'published' } as never,
    })
    remember('pages', key, page.id)

    const post = await payload.create({
      collection: 'posts',
      overrideAccess: true,
      data: { tenant, headline: `Материал ${suffix}`, slug: `post-${suffix}`, _status: 'published' } as never,
    })
    remember('posts', key, post.id)

    const tenantTitle = await payload.create({
      collection: 'tenant-titles',
      overrideAccess: true,
      data: { tenant, title: sharedTitle, slug: `title-${suffix}`, _status: 'published' } as never,
    })
    remember('tenant-titles', key, tenantTitle.id)

    const collection = await payload.create({
      collection: 'editorial-collections',
      overrideAccess: true,
      data: {
        tenant,
        name: `Подборка ${suffix}`,
        slug: `collection-${suffix}`,
        items: [tenantTitle.id],
        _status: 'published',
      } as never,
    })
    remember('editorial-collections', key, collection.id)

    const comment = await payload.create({
      collection: 'comments',
      overrideAccess: true,
      data: {
        tenant,
        targetType: 'post',
        targetId: String(post.id),
        body: `Комментарий ${suffix}`,
        status: 'published',
      } as never,
    })
    remember('comments', key, comment.id)

    const report = await payload.create({
      collection: 'comment-reports',
      overrideAccess: true,
      data: { tenant, comment: comment.id, reason: 'spam' } as never,
    })
    remember('comment-reports', key, report.id)

    const redirect = await payload.create({
      collection: 'redirects',
      overrideAccess: true,
      data: { tenant, from: `/old-${suffix}`, to: `/new-${suffix}`, status: '301' } as never,
    })
    remember('redirects', key, redirect.id)

    const audit = await payload.create({
      collection: 'audit-log',
      overrideAccess: true,
      data: { tenant, summary: `Событие ${suffix}` } as never,
    })
    remember('audit-log', key, audit.id)

    const profile = await payload.create({
      collection: 'player-profiles',
      overrideAccess: true,
      data: { tenant, name: `Профиль ${suffix}`, publisherIdRef: `PLAYER_PUBLISHER_ID_${suffix.toUpperCase()}`, aggregator: 'kp' } as never,
    })
    remember('player-profiles', key, profile.id)

    const settings = await payload.create({
      collection: 'site-settings',
      overrideAccess: true,
      data: { tenant, siteName: `Сайт ${suffix.toUpperCase()}`, legalPages: [page.id] } as never,
    })
    remember('site-settings', key, settings.id)

    const navigation = await payload.create({
      collection: 'navigation',
      overrideAccess: true,
      data: { tenant, label: 'Навигация', header: [{ title: 'Главная', href: '/' }] } as never,
    })
    remember('navigation', key, navigation.id)

    const home = await payload.create({
      collection: 'home-layout',
      overrideAccess: true,
      data: {
        tenant,
        label: 'Главная',
        blocks: [{ blockType: 'heroSpotlight', enabled: true, heading: 'Витрина', items: [tenantTitle.id] }],
      } as never,
    })
    remember('home-layout', key, home.id)
  }

  return { tenants, users, docs, sharedTitle }
}

export const seedPassword = PASSWORD
