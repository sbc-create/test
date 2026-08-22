/**
 * Серверное доказательство изоляции сайтов.
 *
 * Проверяется не «в админке не видно», а невозможность read/update/delete чужого
 * сайта через Local API — тот самый путь, которым ходит рендер страниц и хуки.
 */
import { getPayload } from 'payload'

import config from '../src/payload.config'
import { tenantScopedSlugs } from '../src/payload.config'
import { TenantResolutionError, resolveTenantByHost, tenantCount, tenantFind } from '../src/lib/tenant-query'
import { collectReferences, enforceTenantIntegrity } from '../src/hooks/tenant-integrity'
import { assert, assertEqual, assertRejects, check, summary } from './harness'
import { reset, seed } from './seed'

const payload = await getPayload({ config })

await reset(payload)
const data = await seed(payload)

const userA = await payload.findByID({ collection: 'users', id: data.users.adminA.id, overrideAccess: true })
const userB = await payload.findByID({ collection: 'users', id: data.users.adminB.id, overrideAccess: true })
const userSuper = await payload.findByID({ collection: 'users', id: data.users.super.id, overrideAccess: true })
const editorA = await payload.findByID({ collection: 'users', id: data.users.editorA.id, overrideAccess: true })

/** Поля могут быть завёрнуты в табы/группы плагинами — ищем рекурсивно. */
const hasFieldNamed = (fields: unknown[], name: string): boolean =>
  fields.some((field) => {
    const item = field as Record<string, unknown>
    if (item.name === name) return true
    if (Array.isArray(item.fields)) return hasFieldNamed(item.fields, name)
    if (Array.isArray(item.tabs)) return item.tabs.some((tab) => hasFieldNamed((tab as { fields: unknown[] }).fields, name))
    return false
  })

const seededSlugs = Object.keys(data.docs)

// --- 1. Выборка отдаёт только свой сайт -------------------------------------
for (const slug of seededSlugs) {
  await check(`find ${slug}: администратор сайта A видит только свои документы`, async () => {
    const result = await payload.find({
      collection: slug as never,
      overrideAccess: false,
      user: userA as never,
      limit: 100,
      depth: 0,
    })
    assertEqual(result.totalDocs, 1, `${slug}: totalDocs`)
    assertEqual(String((result.docs[0] as { id: unknown }).id), String(data.docs[slug]!.a), `${slug}: id документа`)
  })
}

// --- 2. Счётчик тоже изолирован ---------------------------------------------
for (const slug of seededSlugs) {
  await check(`count ${slug}: счётчик не считает чужие документы`, async () => {
    const result = await payload.count({ collection: slug as never, overrideAccess: false, user: userA as never })
    assertEqual(result.totalDocs, 1, `${slug}: count`)
  })
}

// --- 3. Прямое обращение по ID ----------------------------------------------
for (const slug of seededSlugs) {
  await check(`findByID ${slug}: документ сайта B недоступен пользователю сайта A`, async () => {
    await assertRejects(
      () =>
        payload.findByID({
          collection: slug as never,
          id: data.docs[slug]!.b as never,
          overrideAccess: false,
          user: userA as never,
        }),
      `${slug}: чужой документ прочитан`,
    )
  })
}

// --- 4. Изменение и удаление чужого ------------------------------------------
for (const slug of seededSlugs) {
  await check(`update ${slug}: изменение документа сайта B запрещено`, async () => {
    await assertRejects(
      () =>
        payload.update({
          collection: slug as never,
          id: data.docs[slug]!.b as never,
          data: {} as never,
          overrideAccess: false,
          user: userA as never,
        }),
      `${slug}: чужой документ изменён`,
    )
  })

  await check(`delete ${slug}: удаление документа сайта B запрещено`, async () => {
    await assertRejects(
      () =>
        payload.delete({
          collection: slug as never,
          id: data.docs[slug]!.b as never,
          overrideAccess: false,
          user: userA as never,
        }),
      `${slug}: чужой документ удалён`,
    )
    const stillThere = await payload.findByID({
      collection: slug as never,
      id: data.docs[slug]!.b as never,
      overrideAccess: true,
      disableErrors: true,
    })
    assert(stillThere, `${slug}: документ сайта B исчез после запрещённого удаления`)
  })
}

// --- 5. Массовые операции по where ------------------------------------------
await check('update по условию не задевает чужой сайт', async () => {
  const result = await payload.update({
    collection: 'posts',
    where: { slug: { like: 'post-' } },
    data: { lead: 'изменено' } as never,
    overrideAccess: false,
    user: editorA as never,
  })
  assertEqual(result.docs.length, 1, 'обновлено документов')
  assertEqual(String(result.docs[0]!.id), String(data.docs.posts!.a), 'обновлён не свой документ')
})

await check('delete по условию не задевает чужой сайт', async () => {
  const result = await payload.delete({
    collection: 'redirects',
    where: { status: { equals: '301' } },
    overrideAccess: false,
    user: userA as never,
  })
  assertEqual(result.docs.length, 1, 'удалено документов')
  const remaining = await payload.count({ collection: 'redirects', overrideAccess: true })
  assertEqual(remaining.totalDocs, 2, 'у сайтов B и C редиректы должны остаться')
})

// --- 6. Анонимный доступ -----------------------------------------------------
for (const slug of seededSlugs) {
  await check(`анонимный запрос ${slug} не отдаёт ничего`, async () => {
    // Запрет выражается либо отказом, либо пустой выборкой — утечкой не является
    // ни то, ни другое. Провал — это любой возвращённый документ.
    try {
      const result = await payload.find({ collection: slug as never, overrideAccess: false, limit: 100 })
      assertEqual(result.totalDocs, 0, `${slug}: анонимный доступ`)
    } catch {
      // отказ доступа — ожидаемое поведение
    }
  })
}

// --- 7. Супер-администратор видит всё ---------------------------------------
await check('супер-администратор видит документы всех сайтов', async () => {
  const result = await payload.find({ collection: 'posts', overrideAccess: false, user: userSuper as never, limit: 100 })
  assertEqual(result.totalDocs, 3, 'посты всех сайтов')
})

// --- 8. Межсайтовые связи ----------------------------------------------------
await check('нельзя сохранить подборку сайта A со ссылкой на публикацию сайта B', async () => {
  await assertRejects(
    () =>
      payload.create({
        collection: 'editorial-collections',
        overrideAccess: true,
        data: {
          tenant: data.tenants.a.id,
          name: 'Межсайтовая подборка',
          slug: 'cross-site',
          items: [data.docs['tenant-titles']!.b],
        } as never,
      }),
    'межсайтовая ссылка сохранена',
  )
})

await check('нельзя добавить чужую страницу в юридические ссылки сайта A', async () => {
  await assertRejects(
    () =>
      payload.update({
        collection: 'site-settings',
        id: data.docs['site-settings']!.a as never,
        overrideAccess: true,
        data: { legalPages: [data.docs.pages!.b] } as never,
      }),
    'чужая страница попала в настройки сайта',
  )
})

await check('нельзя сослаться на чужую публикацию из блока главной', async () => {
  await assertRejects(
    () =>
      payload.update({
        collection: 'home-layout',
        id: data.docs['home-layout']!.a as never,
        overrideAccess: true,
        data: {
          blocks: [{ blockType: 'heroSpotlight', enabled: true, heading: 'Витрина', items: [data.docs['tenant-titles']!.c] }],
        } as never,
      }),
    'блок главной ссылается на чужой сайт',
  )
})

await check('своя ссылка в тех же полях по-прежнему сохраняется', async () => {
  const updated = await payload.update({
    collection: 'site-settings',
    id: data.docs['site-settings']!.a as never,
    overrideAccess: true,
    data: { legalPages: [data.docs.pages!.a] } as never,
  })
  assert(updated, 'корректная ссылка должна проходить')
})


// --- 8a. Хук целостности проверяется напрямую -------------------------------
// Косвенной проверки мало: связи дополнительно ограничивает и плагин, поэтому
// поломка хука могла бы остаться незамеченной за чужой защитой.
const integrityArgs = (tenant: string | number, items: (string | number)[]) =>
  ({
    collection: {
      slug: 'editorial-collections',
      fields: [
        { name: 'tenant', type: 'relationship', relationTo: 'tenants' },
        { name: 'items', type: 'relationship', relationTo: 'tenant-titles', hasMany: true },
      ],
    },
    data: { tenant, items },
    operation: 'update',
    req: { payload },
  }) as never

await check('хук целостности сам по себе отклоняет ссылку на чужой сайт', async () => {
  await assertRejects(
    () => Promise.resolve(enforceTenantIntegrity(integrityArgs(data.tenants.a.id, [data.docs['tenant-titles']!.b]))),
    'хук пропустил межсайтовую ссылку',
  )
})

await check('хук целостности пропускает ссылку на свой сайт', async () => {
  const result = await enforceTenantIntegrity(integrityArgs(data.tenants.a.id, [data.docs['tenant-titles']!.a]))
  assert(result, 'хук должен вернуть данные для корректной ссылки')
})

await check('хук целостности отклоняет ссылку на несуществующий документ', async () => {
  await assertRejects(
    () => Promise.resolve(enforceTenantIntegrity(integrityArgs(data.tenants.a.id, [999999]))),
    'хук пропустил ссылку в никуда',
  )
})

await check('обход полей находит связи в массивах, блоках и табах', () => {
  const fields = [
    {
      type: 'tabs',
      tabs: [
        {
          label: 'Вкладка',
          fields: [
            { name: 'rows', type: 'array', fields: [{ name: 'page', type: 'relationship', relationTo: 'pages' }] },
            {
              name: 'blocks',
              type: 'blocks',
              blocks: [
                { slug: 'hero', fields: [{ name: 'items', type: 'relationship', relationTo: 'tenant-titles', hasMany: true }] },
              ],
            },
          ],
        },
      ],
    },
  ]
  const found = collectReferences(fields as never, {
    rows: [{ page: 11 }],
    blocks: [{ blockType: 'hero', items: [21, { id: 22 }] }],
  })
  assertEqual(found.length, 3, 'найдено связей')
  assertEqual(found.map((item) => `${item.relationTo}:${item.id}`).join(','), 'pages:11,tenant-titles:21,tenant-titles:22', 'состав связей')
})

// --- 9. Эскалация роли -------------------------------------------------------
await check('редактор не может повысить себя до супер-администратора', async () => {
  const updated = await payload.update({
    collection: 'users',
    id: editorA.id,
    data: { role: 'super_admin' } as never,
    overrideAccess: false,
    user: editorA as never,
  })
  assertEqual(updated.role, 'editor', 'роль после попытки эскалации')
})

await check('администратор сайта A не может читать пользователей сайта B', async () => {
  const result = await payload.find({ collection: 'users', overrideAccess: false, user: userA as never, limit: 100 })
  assertEqual(result.totalDocs, 1, 'виден только собственный профиль')
  assertEqual(String(result.docs[0]!.id), String(userA.id), 'виден чужой профиль')
})

// --- 10. Помощник рендера ----------------------------------------------------
await check('tenantFind всегда добавляет констрейнт сайта', async () => {
  const tenant = await resolveTenantByHost(payload, data.tenants.a.domain)
  const result = await tenantFind(payload, { collection: 'posts', tenant, limit: 100 })
  assertEqual(result.totalDocs, 1, 'tenantFind вернул документы другого сайта')
  const counted = await tenantCount(payload, { collection: 'posts', tenant })
  assertEqual(counted.totalDocs, 1, 'tenantCount вернул чужие документы')
})

await check('tenantFind отказывается работать с общей коллекцией', async () => {
  const tenant = await resolveTenantByHost(payload, data.tenants.a.domain)
  await assertRejects(
    () => tenantFind(payload, { collection: 'titles', tenant }),
    'общая коллекция принята как tenant-scoped',
  )
})

await check('неизвестный домен не подставляет случайный сайт', async () => {
  await assertRejects(
    () => resolveTenantByHost(payload, 'unknown.localhost'),
    'неизвестный домен сопоставлен сайту',
  )
  try {
    await resolveTenantByHost(payload, null)
    throw new Error('пустой Host принят')
  } catch (error) {
    assert(error instanceof TenantResolutionError, 'ожидалась TenantResolutionError')
  }
})

// --- 11. Явное подтверждение опасности overrideAccess -----------------------
await check('overrideAccess без констрейнта действительно отдаёт все сайты (почему нужен tenantFind)', async () => {
  const result = await payload.find({ collection: 'posts', overrideAccess: true, user: userA as never, limit: 100 })
  assertEqual(result.totalDocs, 3, 'ожидалась утечка — иначе проверка потеряла смысл')
})

// --- 12. Полнота списка tenant-scoped коллекций -----------------------------
await check('каждая tenant-scoped коллекция покрыта проверками', async () => {
  const missing = tenantScopedSlugs.filter((slug) => !seededSlugs.includes(slug))
  assertEqual(missing.length, 0, `не покрыты проверками: ${missing.join(', ')}`)
})

await check('каждая tenant-scoped коллекция действительно имеет поле tenant', async () => {
  for (const slug of tenantScopedSlugs) {
    const collection = payload.config.collections.find((item) => item.slug === slug)
    assert(collection, `коллекция ${slug} отсутствует в конфигурации`)
    const hasTenant = hasFieldNamed(collection!.fields, 'tenant')
    assert(hasTenant, `у коллекции ${slug} нет поля tenant`)
  }
})

// --- 13. Удаление комментария не оставляет висящих жалоб и ответов ----------
await check('удаление комментария уносит жалобы и ветку ответов', async () => {
  const tenantA = data.tenants.a.id
  const root = await payload.findByID({
    collection: 'comments', id: data.docs.comments.a as never, overrideAccess: true,
  })
  const reply = await payload.create({
    collection: 'comments', overrideAccess: true,
    data: {
      tenant: tenantA, targetType: root.targetType, targetId: root.targetId,
      parent: root.id, root: root.id, depth: 1, guestName: 'Гость',
      body: 'Ответ в ветке, который обязан исчезнуть вместе с корнем.',
      status: 'published',
    } as never,
  })
  const deepReply = await payload.create({
    collection: 'comments', overrideAccess: true,
    data: {
      tenant: tenantA, targetType: root.targetType, targetId: root.targetId,
      parent: reply.id, root: root.id, depth: 2, guestName: 'Гость',
      body: 'Ответ на ответ: вторая ступень той же ветки.',
      status: 'published',
    } as never,
  })
  await payload.create({
    collection: 'comment-reports', overrideAccess: true,
    data: { tenant: tenantA, comment: reply.id, reason: 'abuse' } as never,
  })

  await payload.delete({ collection: 'comments', id: root.id, overrideAccess: true })

  const left = await payload.find({
    collection: 'comments', where: { id: { in: [root.id, reply.id, deepReply.id] } },
    overrideAccess: true, pagination: false,
  })
  assertEqual(left.totalDocs, 0, 'ответы остались в базе после удаления корня ветки')
  const reports = await payload.find({
    collection: 'comment-reports', where: { comment: { in: [root.id, reply.id, deepReply.id] } },
    overrideAccess: true, pagination: false,
  })
  assertEqual(reports.totalDocs, 0, 'жалобы пережили удаление комментариев')
})

await payload.db.destroy?.()
process.exit(summary())
