import type { CollectionConfig } from 'payload'
import { superAdminOnly, tenantSelfAccess } from '../access/index'

/** Тенант = самостоятельный сайт: домен, бренд, SEO-профиль и состояние публикации. */
export const Tenants: CollectionConfig = {
  slug: 'tenants',
  labels: { singular: 'Сайт', plural: 'Сайты' },
  admin: {
    useAsTitle: 'name',
    group: 'Управление сайтами',
    description: 'Каждый сайт — самостоятельный бренд, домен и SEO-политика.',
  },
  access: {
    create: superAdminOnly,
    delete: superAdminOnly,
    update: superAdminOnly,
    read: tenantSelfAccess,
  },
  fields: [
    { name: 'name', type: 'text', required: true, label: 'Название сайта' },
    {
      name: 'slug',
      type: 'text',
      required: true,
      unique: true,
      index: true,
      label: 'Код сайта',
      admin: { description: 'Внутренний код: site_a, site_b, site_c. Не отображается посетителям.' },
      validate: (value: unknown) =>
        typeof value === 'string' && /^[a-z][a-z0-9_]{1,30}$/.test(value)
          ? true
          : 'Только строчные латинские буквы, цифры и подчёркивание',
    },
    {
      name: 'domain',
      type: 'text',
      required: true,
      unique: true,
      index: true,
      label: 'Домен',
      admin: { description: 'Домен без схемы. По нему запрос сопоставляется с сайтом.' },
    },
    {
      name: 'seoProfile',
      type: 'select',
      required: true,
      label: 'SEO-профиль',
      options: [
        { label: 'CATALOG_AUTHORITY — полнота каталога', value: 'catalog_authority' },
        { label: 'RELEASE_PULSE — новые серии и расписание', value: 'release_pulse' },
        { label: 'EDITORIAL_GUIDE — редакционные материалы', value: 'editorial_guide' },
        { label: 'SERIES_HUB — сериалы, сезоны и серии', value: 'series_hub' },
        { label: 'FILM_LIBRARY — полнометражное кино', value: 'film_library' },
        { label: 'PREMIERE_RADAR — даты премьер и переносы', value: 'premiere_radar' },
        { label: 'CURATED_GUIDE — подборки и маршруты просмотра', value: 'curated_guide' },
      ],
    },
    {
      name: 'theme',
      type: 'select',
      required: true,
      label: 'Тема оформления',
      options: [
        { label: 'Портальная светлая', value: 'portal_light' },
        { label: 'Динамичная лента', value: 'pulse' },
        { label: 'Редакционная спокойная', value: 'editorial' },
        { label: 'Тёмная витрина сериалов', value: 'series_dark' },
        { label: 'Светлая кинотека', value: 'film_editorial' },
        { label: 'Календарь премьер', value: 'premiere_signal' },
        { label: 'Тёплая витрина подборок', value: 'guide_warm' },
      ],
    },
    {
      name: 'indexingEnabled',
      type: 'checkbox',
      defaultValue: false,
      label: 'Разрешить индексацию поисковыми системами',
      admin: {
        description:
          'Пока выключено, сайт отдаёт noindex целиком. Включается только после проверки контента и SEO.',
      },
    },
    {
      name: 'allowGuestComments',
      type: 'checkbox',
      defaultValue: false,
      label: 'Разрешить комментарии без регистрации',
    },
  ],
}
