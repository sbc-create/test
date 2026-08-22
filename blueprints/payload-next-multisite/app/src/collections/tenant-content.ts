import type { CollectionBeforeValidateHook, CollectionConfig } from 'payload'
import { hasRole, superAdminOnly, tenantScopedAccess } from '../access/index'

/**
 * Tenant-scoped контент: публикации, редакционные тексты, SEO, страницы и медиа.
 * Плагин multi-tenant добавляет поле `tenant` и фильтрует выборки; доступ здесь
 * дополнительно ограничен ролями.
 */

const seoFields: CollectionConfig['fields'] = [
  {
    type: 'collapsible',
    label: 'SEO',
    admin: { initCollapsed: true },
    fields: [
      { name: 'seoTitle', type: 'text', label: 'Title страницы',
        admin: { description: 'Если пусто — собирается по шаблону сайта из фактических данных.' } },
      { name: 'seoDescription', type: 'textarea', label: 'Description',
        admin: { description: 'Описывает то, что реально видно на странице. Не выдумывать факты.' } },
      {
        name: 'robots',
        type: 'select',
        defaultValue: 'inherit',
        label: 'Индексация',
        options: [
          { label: 'По правилу сайта', value: 'inherit' },
          { label: 'Индексировать', value: 'index' },
          { label: 'Не индексировать (noindex,follow)', value: 'noindex' },
        ],
      },
      { name: 'canonicalOverride', type: 'text', label: 'Canonical (только по решению)',
        admin: { description: 'Пусто = self-canonical. Заполняется только при документированном решении.' } },
    ],
  },
]

export const TenantTitles: CollectionConfig = {
  slug: 'tenant-titles',
  labels: { singular: 'Публикация тайтла', plural: 'Публикации тайтлов' },
  admin: {
    useAsTitle: 'slug',
    group: 'Контент сайта',
    description: 'Как конкретный тайтл представлен на этом сайте: URL, редакционный текст, SEO.',
    defaultColumns: ['slug', 'title', '_status'],
  },
  versions: { drafts: { autosave: { interval: 2000 }, schedulePublish: true }, maxPerDoc: 20 },
  access: {
    read: tenantScopedAccess(),
    create: hasRole('editor'),
    update: hasRole('editor'),
    delete: hasRole('site_admin'),
  },
  fields: [
    { name: 'title', type: 'relationship', relationTo: 'titles', required: true, index: true, label: 'Тайтл из общего каталога' },
    {
      name: 'slug',
      type: 'text',
      required: true,
      index: true,
      label: 'URL-код на этом сайте',
      validate: (value: unknown) =>
        typeof value === 'string' && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value)
          ? true
          : 'Строчные латинские буквы, цифры и дефис',
    },
    {
      name: 'editorialIntro',
      type: 'textarea',
      label: 'Редакционное вступление сайта',
      admin: { description: 'Оригинальный текст редакции этого сайта. Не копия описания провайдера.' },
    },
    {
      name: 'editorialAuthor',
      type: 'relationship',
      relationTo: 'users',
      label: 'Автор редакционного текста',
    },
    {
      name: 'seasonNotes',
      type: 'array',
      label: 'Заметки редакции по сезонам',
      admin: {
        description:
          'Собственный текст сайта о сезоне. Без него страница сезона остаётся списком серий, '
          + 'одинаковым на всех сайтах, и ворота уникальности закрывают её от индексации.',
      },
      fields: [
        { name: 'season', type: 'number', required: true, min: 1, label: 'Номер сезона' },
        { name: 'note', type: 'textarea', required: true, label: 'Текст редакции' },
      ],
    },
    {
      name: 'highlight',
      type: 'checkbox',
      defaultValue: false,
      label: 'Показывать в подборках на главной',
    },
    ...seoFields,
  ],
}

/**
 * У подборки ровно один источник состава: список для тематической и маршрут для
 * порядка просмотра. Два параллельных списка молча расходятся, и на странице
 * оказывается не то, что видел редактор.
 */
export const validateCollectionShape: CollectionBeforeValidateHook = ({ data }) => {
  if (!data) return data
  const kind = String(data.collectionKind ?? 'themed')
  const steps = Array.isArray(data.steps) ? data.steps : []
  const items = Array.isArray(data.items) ? data.items : []
  if (kind === 'watch_order') {
    if (steps.length === 0) {
      throw new Error('BLOCKED_INPUT: порядок просмотра без шагов не публикуется.')
    }
    if (items.length > 0) {
      throw new Error('BLOCKED_INPUT: у порядка просмотра состав задают шаги, а не список материалов.')
    }
  } else if (steps.length > 0) {
    throw new Error('BLOCKED_INPUT: шаги допустимы только у порядка просмотра.')
  }
  return data
}

export const EditorialCollections: CollectionConfig = {
  slug: 'editorial-collections',
  labels: { singular: 'Подборка', plural: 'Подборки' },
  admin: { useAsTitle: 'name', group: 'Контент сайта', defaultColumns: ['name', 'slug', '_status'] },
  versions: { drafts: { autosave: { interval: 2000 }, schedulePublish: true }, maxPerDoc: 20 },
  access: { read: tenantScopedAccess(), create: hasRole('editor'), update: hasRole('editor'), delete: hasRole('site_admin') },
  fields: [
    { name: 'name', type: 'text', required: true, label: 'Название подборки' },
    { name: 'slug', type: 'text', required: true, index: true, label: 'URL-код' },
    { name: 'intro', type: 'textarea', label: 'Вступление редакции',
      admin: { description: 'Подборка без собственного текста не индексируется.' } },
    {
      name: 'collectionKind',
      type: 'select',
      required: true,
      defaultValue: 'themed',
      index: true,
      label: 'Вид подборки',
      options: [
        { label: 'Тематическая', value: 'themed' },
        { label: 'По настроению', value: 'mood' },
        { label: 'Порядок просмотра', value: 'watch_order' },
      ],
      admin: {
        description:
          'Порядок просмотра — не список, а маршрут: у каждого шага обязателен собственный '
          + 'комментарий редакции, иначе это тот же список под другим названием.',
      },
    },
    {
      name: 'items',
      type: 'relationship',
      relationTo: 'tenant-titles',
      hasMany: true,
      label: 'Материалы подборки',
      admin: { condition: (data) => data?.collectionKind !== 'watch_order' },
    },
    {
      name: 'steps',
      type: 'array',
      label: 'Шаги порядка просмотра',
      admin: { condition: (data) => data?.collectionKind === 'watch_order' },
      fields: [
        { name: 'title', type: 'relationship', relationTo: 'tenant-titles', required: true, label: 'Произведение' },
        { name: 'note', type: 'textarea', required: true, label: 'Почему этот шаг здесь' },
      ],
    },
    ...seoFields,
  ],
  hooks: { beforeValidate: [validateCollectionShape] },
}

export const Posts: CollectionConfig = {
  slug: 'posts',
  labels: { singular: 'Материал', plural: 'Новости и статьи' },
  admin: { useAsTitle: 'headline', group: 'Контент сайта', defaultColumns: ['headline', 'slug', 'publishedAt', '_status'] },
  versions: { drafts: { autosave: { interval: 2000 }, schedulePublish: true }, maxPerDoc: 20 },
  access: { read: tenantScopedAccess(), create: hasRole('editor'), update: hasRole('editor'), delete: hasRole('site_admin') },
  fields: [
    { name: 'headline', type: 'text', required: true, label: 'Заголовок' },
    { name: 'slug', type: 'text', required: true, index: true, label: 'URL-код' },
    { name: 'lead', type: 'textarea', label: 'Лид' },
    { name: 'body', type: 'textarea', label: 'Текст материала' },
    { name: 'author', type: 'relationship', relationTo: 'users', label: 'Автор' },
    { name: 'publishedAt', type: 'date', label: 'Дата публикации' },
    { name: 'cover', type: 'upload', relationTo: 'media', label: 'Обложка' },
    ...seoFields,
  ],
}

export const Pages: CollectionConfig = {
  slug: 'pages',
  labels: { singular: 'Страница', plural: 'Страницы' },
  admin: { useAsTitle: 'name', group: 'Контент сайта', defaultColumns: ['name', 'slug', '_status'] },
  versions: { drafts: { autosave: { interval: 2000 }, schedulePublish: true }, maxPerDoc: 20 },
  access: { read: tenantScopedAccess(), create: hasRole('editor'), update: hasRole('editor'), delete: hasRole('site_admin') },
  fields: [
    { name: 'name', type: 'text', required: true, label: 'Название' },
    { name: 'slug', type: 'text', required: true, index: true, label: 'URL-код' },
    { name: 'body', type: 'textarea', label: 'Текст страницы' },
    ...seoFields,
  ],
}

export const Media: CollectionConfig = {
  slug: 'media',
  labels: { singular: 'Файл', plural: 'Медиафайлы' },
  admin: { group: 'Контент сайта', description: 'Загружайте только материалы с подтверждёнными правами.' },
  upload: {
    // Каталог загрузок задаётся окружением: он относится к состоянию стенда,
    // а не к исходникам, и не должен попадать в репозиторий.
    staticDir: process.env.MEDIA_DIR ?? 'var/media',
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp', 'image/avif'],
    imageSizes: [
      { name: 'card', width: 400, height: 600, position: 'centre' },
      { name: 'wide', width: 1200, height: 675, position: 'centre' },
    ],
  },
  access: { read: tenantScopedAccess(), create: hasRole('editor'), update: hasRole('editor'), delete: hasRole('site_admin') },
  fields: [
    { name: 'alt', type: 'text', required: true, label: 'Альтернативный текст',
      admin: { description: 'Обязателен: без alt материал не публикуется.' } },
    { name: 'rightsRecord', type: 'relationship', relationTo: 'rights-records', label: 'Права на изображение' },
  ],
}

export const Redirects: CollectionConfig = {
  slug: 'redirects',
  labels: { singular: 'Редирект', plural: 'Редиректы' },
  admin: { useAsTitle: 'from', group: 'Контент сайта' },
  access: { read: tenantScopedAccess(), create: hasRole('editor'), update: hasRole('editor'), delete: hasRole('site_admin') },
  fields: [
    { name: 'from', type: 'text', required: true, index: true, label: 'Старый путь' },
    { name: 'to', type: 'text', required: true, label: 'Новый путь' },
    { name: 'status', type: 'select', defaultValue: '301', label: 'Код', options: [{ label: '301', value: '301' }, { label: '410', value: '410' }] },
  ],
}

export const AuditLog: CollectionConfig = {
  slug: 'audit-log',
  labels: { singular: 'Запись журнала', plural: 'Журнал изменений' },
  admin: { useAsTitle: 'summary', group: 'Служебное', defaultColumns: ['summary', 'actor', 'createdAt'] },
  // Запись в журнал — только для аутентифицированных: плагин добавляет констрейнт
  // сайта лишь при наличии пользователя, поэтому `create: () => true` открывал
  // анонимную запись в журнал ЛЮБОГО сайта.
  access: { read: tenantScopedAccess(), create: hasRole('editor'), update: () => false,
            delete: superAdminOnly },
  fields: [
    { name: 'summary', type: 'text', required: true, label: 'Что произошло' },
    { name: 'actor', type: 'relationship', relationTo: 'users', label: 'Кто' },
    { name: 'collection', type: 'text', label: 'Коллекция' },
    { name: 'documentId', type: 'text', label: 'ID документа' },
    { name: 'before', type: 'json', label: 'До' },
    { name: 'after', type: 'json', label: 'После' },
  ],
}
