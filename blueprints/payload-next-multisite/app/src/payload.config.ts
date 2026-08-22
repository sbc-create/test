import path from 'path'
import { fileURLToPath } from 'url'

import { postgresAdapter } from '@payloadcms/db-postgres'
import { lexicalEditor } from '@payloadcms/richtext-lexical'
import { multiTenantPlugin } from '@payloadcms/plugin-multi-tenant'
import { seoPlugin } from '@payloadcms/plugin-seo'
import { ru } from '@payloadcms/translations/languages/ru'
import { buildConfig } from 'payload'
import type { CollectionConfig } from 'payload'
import sharp from 'sharp'

import { isSuperAdmin } from './access/index.js'
import { Tenants } from './collections/Tenants.js'
import { Users } from './collections/Users.js'
import {
  CatalogMedia,
  Episodes,
  Genres,
  RightsRecords,
  Seasons,
  SourceRecords,
  Studios,
  Titles,
  Voices,
} from './collections/catalog.js'
import {
  AuditLog,
  EditorialCollections,
  Media,
  Pages,
  Posts,
  Redirects,
  TenantTitles,
} from './collections/tenant-content.js'
import { CommentReports, Comments } from './collections/comments.js'
import { ImportJobs, PlayerProfiles, ReleaseEvents } from './collections/operations.js'
import { HomeLayout, Navigation, SiteSettings } from './globals/index.js'
import { enforceTenantIntegrity } from './hooks/tenant-integrity.js'

const dirname = path.dirname(fileURLToPath(import.meta.url))

/**
 * Обязательные переменные окружения. Пустое значение не заменяется умолчанием:
 * тихий fallback на слабый секрет или чужую базу — это авария, а не удобство.
 */
const required = (name: string): string => {
  const value = process.env[name]
  if (!value) {
    throw new Error(`BLOCKED_INPUT: не задана переменная окружения ${name}`)
  }
  return value
}

/**
 * Коллекции, привязанные к сайту. Всё, чего здесь нет, — общий фактический каталог
 * и служебные журналы: они намеренно НЕ получают поле tenant, чтобы один и тот же
 * тайтл не размножался в трёх рассинхронизированных копиях.
 */
const SCOPED = { useTenantAccess: true, useBaseFilter: true } as const
const SCOPED_GLOBAL = { ...SCOPED, isGlobal: true } as const

const TENANT_SCOPED = {
  'tenant-titles': SCOPED,
  'editorial-collections': SCOPED,
  posts: SCOPED,
  pages: SCOPED,
  media: SCOPED,
  redirects: SCOPED,
  'audit-log': SCOPED,
  comments: SCOPED,
  'comment-reports': SCOPED,
  'player-profiles': SCOPED,
  'site-settings': SCOPED_GLOBAL,
  navigation: SCOPED_GLOBAL,
  'home-layout': SCOPED_GLOBAL,
} as const

export const tenantScopedSlugs = Object.keys(TENANT_SCOPED)

export const sharedSlugs = [
  'tenants',
  'catalog-media',
  'users',
  'genres',
  'studios',
  'titles',
  'seasons',
  'episodes',
  'voices',
  'rights-records',
  'source-records',
  'import-jobs',
  'release-events',
]

/**
 * Хук целостности ставится централизованно: если добавлять его в каждую коллекцию
 * руками, однажды коллекцию заведут и забудут — и межсайтовая ссылка пройдёт.
 */
const withTenantIntegrity = (collections: CollectionConfig[]): CollectionConfig[] =>
  collections.map((collection) => {
    if (!(collection.slug in TENANT_SCOPED)) return collection
    return {
      ...collection,
      hooks: {
        ...collection.hooks,
        beforeChange: [...(collection.hooks?.beforeChange ?? []), enforceTenantIntegrity],
      },
    }
  })

export default buildConfig({
  admin: {
    user: Users.slug,
    meta: { titleSuffix: ' — Фабрика сайтов' },
  },
  collections: withTenantIntegrity([
    Tenants,
    Users,
    CatalogMedia,
    Genres,
    Studios,
    Titles,
    Seasons,
    Episodes,
    Voices,
    RightsRecords,
    SourceRecords,
    TenantTitles,
    EditorialCollections,
    Posts,
    Pages,
    Media,
    Redirects,
    AuditLog,
    Comments,
    CommentReports,
    ImportJobs,
    ReleaseEvents,
    PlayerProfiles,
    SiteSettings,
    Navigation,
    HomeLayout,
  ]),
  db: postgresAdapter({
    pool: { connectionString: required('DATABASE_URI') },
    push: process.env.PAYLOAD_DB_PUSH === 'true',
  }),
  editor: lexicalEditor(),
  // Админка русская и не переключается на английский по языку браузера:
  // эксплуатационный интерфейс должен быть предсказуемым для редакции.
  i18n: { fallbackLanguage: 'ru', supportedLanguages: { ru } },
  secret: required('PAYLOAD_SECRET'),
  sharp,
  typescript: { outputFile: path.resolve(dirname, 'payload-types.ts') },
  plugins: [
    multiTenantPlugin({
      collections: TENANT_SCOPED as unknown as Record<string, Record<string, unknown>>,
      tenantsSlug: 'tenants',
      // Полный доступ ко всем сайтам — только у super_admin. Роль проверяется на
      // сервере по документу пользователя, а не по данным из запроса.
      userHasAccessToAllTenants: (user) => isSuperAdmin(user),
      tenantField: {
        name: 'tenant',
      },
      tenantsArrayField: {
        includeDefaultField: true,
        arrayFieldName: 'tenants',
        arrayTenantFieldName: 'tenant',
      },
      i18n: {
        translations: {
          ru: {
            'nav-tenantSelector-label': 'Сайт',
            'assign-tenant-button-label': 'Назначить сайт',
            'assign-tenant-modal-title': 'Назначить сайт для «{{title}}»',
            'field-assignedTenant-label': 'Назначенный сайт',
          },
        },
      },
    }),
    seoPlugin({
      collections: ['tenant-titles', 'posts', 'pages'],
      uploadsCollection: 'media',
      tabbedUI: true,
    }),
  ],
})
