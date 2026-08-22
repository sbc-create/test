import type { CollectionConfig } from 'payload'
import { hasRole, superAdminOnly, tenantScopedAccess } from '../access/index'
import { submitComment } from '../comments/submit'

/**
 * Собственные комментарии, не внешний виджет.
 *
 * Публично читаются только опубликованные: доступ выражен констрейнтом запроса,
 * поэтому pending/spam не утекают ни через список, ни через счётчик, ни через
 * связанные выборки.
 */
export const Comments: CollectionConfig = {
  slug: 'comments',
  labels: { singular: 'Комментарий', plural: 'Комментарии' },
  admin: {
    useAsTitle: 'excerpt',
    group: 'Модерация',
    description: 'Очередь модерации: новые комментарии ждут решения и не видны на сайте.',
    defaultColumns: ['excerpt', 'status', 'targetType', 'createdAt'],
  },
  access: {
    // Анонимного чтения через REST/GraphQL нет: публичная страница рендерится на
    // сервере через tenantQuery, который обязан указать сайт явно. Иначе открытый
    // /api/comments отдавал бы комментарии всех трёх сайтов сразу.
    read: tenantScopedAccess(),
    // Создание идёт через серверный endpoint с валидацией и лимитами, не напрямую.
    create: () => false,
    update: hasRole('moderator'),
    delete: hasRole('site_admin'),
  },
  // Единственный путь создания комментария: серверный обработчик с проверками.
  endpoints: [{ path: '/submit', method: 'post', handler: submitComment }],
  indexes: [
    { fields: ['tenant', 'targetType', 'targetId', 'status'] },
    { fields: ['tenant', 'status', 'createdAt'] },
    { fields: ['tenant', 'authorKey', 'createdAt'] },
  ],
  fields: [
    {
      name: 'targetType',
      type: 'select',
      required: true,
      index: true,
      label: 'Объект обсуждения',
      options: [
        { label: 'Тайтл', value: 'title' },
        { label: 'Сезон', value: 'season' },
        { label: 'Серия', value: 'episode' },
        { label: 'Материал', value: 'post' },
      ],
    },
    { name: 'targetId', type: 'text', required: true, index: true, label: 'ID объекта' },
    { name: 'targetUrl', type: 'text', label: 'Ссылка на страницу', admin: { readOnly: true } },
    { name: 'author', type: 'relationship', relationTo: 'users', label: 'Пользователь' },
    { name: 'guestName', type: 'text', label: 'Имя гостя' },
    {
      name: 'guestEmail',
      type: 'email',
      label: 'E-mail гостя (не публикуется)',
      // Адрес виден только модератору: публичный API его не отдаёт.
      access: { read: ({ req }) => Boolean(req.user), update: () => false },
    },
    { name: 'parent', type: 'relationship', relationTo: 'comments', label: 'Ответ на комментарий' },
    { name: 'root', type: 'relationship', relationTo: 'comments', label: 'Корень ветки', index: true },
    { name: 'depth', type: 'number', defaultValue: 0, min: 0, max: 3, label: 'Глубина вложенности' },
    { name: 'body', type: 'textarea', required: true, label: 'Текст (очищенный)' },
    { name: 'excerpt', type: 'text', label: 'Начало текста', admin: { readOnly: true } },
    {
      name: 'status',
      type: 'select',
      required: true,
      defaultValue: 'pending',
      index: true,
      label: 'Состояние',
      options: [
        { label: 'На модерации', value: 'pending' },
        { label: 'Опубликован', value: 'published' },
        { label: 'Отклонён', value: 'rejected' },
        { label: 'Спам', value: 'spam' },
        { label: 'Удалён', value: 'deleted' },
      ],
    },
    { name: 'moderator', type: 'relationship', relationTo: 'users', label: 'Модератор' },
    { name: 'moderatedAt', type: 'date', label: 'Когда обработан' },
    { name: 'moderatorNote', type: 'textarea', label: 'Заметка модератора',
      access: { read: ({ req }) => Boolean(req.user) } },
    { name: 'reportCount', type: 'number', defaultValue: 0, label: 'Жалоб' },
    {
      name: 'authorKey',
      type: 'text',
      index: true,
      label: 'Ключ отправителя',
      // Отпечаток отправителя (не IP) для лимитов частоты. Публично не отдаётся.
      access: { read: ({ req }) => Boolean(req.user), create: () => false, update: () => false },
      admin: { readOnly: true, description: 'Хэш отправителя для антифлуда. Исходный IP не хранится.' },
    },
    {
      name: 'submissionMeta',
      type: 'json',
      label: 'Технические данные отправки',
      // Метаданные анти-абьюза не отдаются публично и хранятся по политике ретенции.
      access: { read: ({ req }) => Boolean(req.user), update: () => false },
    },
  ],
  hooks: {
    beforeChange: [
      ({ data }) => {
        if (typeof data?.body === 'string') {
          data.excerpt = data.body.replace(/\s+/g, ' ').slice(0, 120)
        }
        return data
      },
    ],
  },
}

export const CommentReports: CollectionConfig = {
  slug: 'comment-reports',
  labels: { singular: 'Жалоба', plural: 'Жалобы на комментарии' },
  admin: { useAsTitle: 'reason', group: 'Модерация' },
  access: {
    read: tenantScopedAccess(),
    create: () => false,          // только через серверный endpoint
    update: hasRole('moderator'),
    delete: superAdminOnly,
  },
  fields: [
    { name: 'comment', type: 'relationship', relationTo: 'comments', required: true, label: 'Комментарий' },
    {
      name: 'reason',
      type: 'select',
      required: true,
      label: 'Причина',
      options: [
        { label: 'Спам', value: 'spam' },
        { label: 'Оскорбление', value: 'abuse' },
        { label: 'Спойлер', value: 'spoiler' },
        { label: 'Другое', value: 'other' },
      ],
    },
    { name: 'note', type: 'textarea', label: 'Пояснение' },
    { name: 'resolved', type: 'checkbox', defaultValue: false, label: 'Обработана' },
  ],
}
