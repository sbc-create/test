import type { CollectionConfig } from 'payload'
import { isSuperAdmin, roleFieldAccess, superAdminOnly } from '../access/index'

export const Users: CollectionConfig = {
  slug: 'users',
  labels: { singular: 'Пользователь', plural: 'Пользователи' },
  auth: { tokenExpiration: 60 * 60 * 8, maxLoginAttempts: 10, lockTime: 10 * 60 * 1000 },
  admin: { useAsTitle: 'email', group: 'Управление сайтами' },
  access: {
    create: superAdminOnly,
    delete: superAdminOnly,
    read: ({ req }) => (isSuperAdmin(req.user) ? true : { id: { equals: (req.user as { id?: unknown })?.id } }),
    update: ({ req }) => (isSuperAdmin(req.user) ? true : { id: { equals: (req.user as { id?: unknown })?.id } }),
  },
  fields: [
    { name: 'name', type: 'text', label: 'Имя' },
    {
      name: 'role',
      type: 'select',
      required: true,
      defaultValue: 'editor',
      label: 'Роль',
      // Роль назначает только супер-администратор: иначе редактор повысит себя сам.
      access: { create: roleFieldAccess, update: roleFieldAccess },
      options: [
        { label: 'Супер-администратор', value: 'super_admin' },
        { label: 'Администратор сайта', value: 'site_admin' },
        { label: 'Редактор', value: 'editor' },
        { label: 'Модератор', value: 'moderator' },
        { label: 'Аналитик (только чтение)', value: 'analyst' },
      ],
    },
  ],
}
