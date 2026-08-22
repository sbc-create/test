import type { CollectionConfig } from 'payload'
import { hasRole, superAdminOnly, tenantScopedAccess } from '../access/index'

/**
 * «Глобалы» сайта. В мультитенантной установке настоящий Payload global был бы один
 * на все три сайта, поэтому это коллекции, объявленные плагином как isGlobal: по
 * одному документу на тенант. Так настройки Сайта A физически не могут прочитаться
 * при рендере Сайта B.
 */

const globalAccess = {
  read: tenantScopedAccess(),
  create: hasRole('site_admin'),
  update: hasRole('site_admin'),
  delete: superAdminOnly,
}

export const SiteSettings: CollectionConfig = {
  slug: 'site-settings',
  labels: { singular: 'Настройки сайта', plural: 'Настройки сайта' },
  admin: {
    useAsTitle: 'siteName',
    group: 'Настройки сайта',
    description: 'Название, контакты, правила комментариев и SEO-умолчания одного сайта.',
  },
  access: globalAccess,
  fields: [
    {
      name: 'siteName',
      type: 'text',
      required: true,
      label: 'Публичное название сайта',
      admin: {
        description:
          'Заполняется из пакета сайта. Пустое поле не заменяется придуманным брендом: ' +
          'это BLOCKED_INPUT, а не повод сочинить название.',
      },
    },
    { name: 'tagline', type: 'text', label: 'Короткое описание' },
    {
      name: 'seoTitleTemplate',
      type: 'text',
      label: 'Шаблон title',
      admin: { description: 'Например: «{page} — {site}». Подставляются только фактические значения страницы.' },
    },
    { name: 'defaultDescription', type: 'textarea', label: 'Description по умолчанию' },
    { name: 'defaultOgImage', type: 'upload', relationTo: 'media', label: 'Картинка для соцсетей' },
    {
      type: 'collapsible',
      label: 'Комментарии',
      admin: { initCollapsed: false },
      fields: [
        { name: 'commentsEnabled', type: 'checkbox', defaultValue: true, label: 'Комментарии включены' },
        {
          name: 'premoderation',
          type: 'checkbox',
          defaultValue: true,
          label: 'Премодерация (комментарий публикуется после проверки)',
          admin: { description: 'Выключение премодерации — решение владельца сайта, оно фиксируется в пакете сайта.' },
        },
        {
          name: 'minIntervalSeconds',
          type: 'number',
          defaultValue: 30,
          min: 0,
          label: 'Минимальный интервал между отправками, сек',
        },
        { name: 'maxLength', type: 'number', defaultValue: 4000, min: 1, label: 'Максимальная длина комментария' },
        {
          name: 'rulesText',
          type: 'textarea',
          label: 'Правила комментирования',
          admin: { description: 'Показывается рядом с формой. Текст собственный, не скопированный.' },
        },
      ],
    },
    {
      type: 'collapsible',
      label: 'Юридические страницы',
      admin: { initCollapsed: true },
      fields: [
        { name: 'legalPages', type: 'relationship', relationTo: 'pages', hasMany: true, label: 'Страницы' },
        {
          name: 'rightsNotice',
          type: 'textarea',
          label: 'Уведомление о правах и источниках',
          admin: { description: 'Обязательно описывает происхождение материалов и порядок обращения правообладателя.' },
        },
      ],
    },
  ],
}

export const Navigation: CollectionConfig = {
  slug: 'navigation',
  labels: { singular: 'Навигация', plural: 'Навигация' },
  admin: {
    useAsTitle: 'label',
    group: 'Настройки сайта',
    description: 'Меню в шапке и подвале. Ссылки ведут только на страницы этого сайта или явно помеченные внешние.',
  },
  access: globalAccess,
  fields: [
    { name: 'label', type: 'text', defaultValue: 'Навигация', label: 'Служебное имя' },
    {
      name: 'header',
      type: 'array',
      label: 'Меню в шапке',
      labels: { singular: 'Пункт', plural: 'Пункты' },
      fields: [
        { name: 'title', type: 'text', required: true, label: 'Подпись' },
        { name: 'href', type: 'text', required: true, label: 'Адрес' },
        { name: 'external', type: 'checkbox', defaultValue: false, label: 'Внешняя ссылка (rel=nofollow noopener)' },
      ],
    },
    {
      name: 'footerGroups',
      type: 'array',
      label: 'Колонки в подвале',
      labels: { singular: 'Колонка', plural: 'Колонки' },
      fields: [
        { name: 'title', type: 'text', required: true, label: 'Заголовок колонки' },
        {
          name: 'links',
          type: 'array',
          label: 'Ссылки',
          fields: [
            { name: 'title', type: 'text', required: true, label: 'Подпись' },
            { name: 'href', type: 'text', required: true, label: 'Адрес' },
            { name: 'external', type: 'checkbox', defaultValue: false, label: 'Внешняя ссылка' },
          ],
        },
      ],
    },
  ],
}

export const HomeLayout: CollectionConfig = {
  slug: 'home-layout',
  labels: { singular: 'Главная страница', plural: 'Главная страница' },
  admin: {
    useAsTitle: 'label',
    group: 'Настройки сайта',
    description:
      'Состав и порядок блоков главной. Блоки включаются флажком и переставляются перетаскиванием: ' +
      'порядок в списке — это порядок на странице.',
  },
  access: globalAccess,
  fields: [
    { name: 'label', type: 'text', defaultValue: 'Главная', label: 'Служебное имя' },
    {
      name: 'blocks',
      type: 'blocks',
      label: 'Блоки главной',
      labels: { singular: 'Блок', plural: 'Блоки' },
      blocks: [
        {
          slug: 'heroSpotlight',
          labels: { singular: 'Витрина', plural: 'Витрины' },
          fields: [
            { name: 'enabled', type: 'checkbox', defaultValue: true, label: 'Показывать' },
            { name: 'heading', type: 'text', label: 'Заголовок' },
            { name: 'items', type: 'relationship', relationTo: 'tenant-titles', hasMany: true, label: 'Материалы' },
          ],
        },
        {
          slug: 'releaseSchedule',
          labels: { singular: 'Расписание', plural: 'Расписания' },
          fields: [
            { name: 'enabled', type: 'checkbox', defaultValue: true, label: 'Показывать' },
            { name: 'heading', type: 'text', label: 'Заголовок' },
            { name: 'days', type: 'number', defaultValue: 7, min: 1, max: 31, label: 'Горизонт, дней' },
          ],
        },
        {
          slug: 'latestUpdates',
          labels: { singular: 'Обновления', plural: 'Обновления' },
          fields: [
            { name: 'enabled', type: 'checkbox', defaultValue: true, label: 'Показывать' },
            { name: 'heading', type: 'text', label: 'Заголовок' },
            { name: 'limit', type: 'number', defaultValue: 12, min: 1, max: 60, label: 'Сколько показывать' },
          ],
        },
        {
          slug: 'editorialPicks',
          labels: { singular: 'Подборки', plural: 'Подборки' },
          fields: [
            { name: 'enabled', type: 'checkbox', defaultValue: true, label: 'Показывать' },
            { name: 'heading', type: 'text', label: 'Заголовок' },
            { name: 'collections', type: 'relationship', relationTo: 'editorial-collections', hasMany: true, label: 'Подборки' },
          ],
        },
        {
          slug: 'newsFeed',
          labels: { singular: 'Новости', plural: 'Новости' },
          fields: [
            { name: 'enabled', type: 'checkbox', defaultValue: true, label: 'Показывать' },
            { name: 'heading', type: 'text', label: 'Заголовок' },
            { name: 'limit', type: 'number', defaultValue: 6, min: 1, max: 30, label: 'Сколько показывать' },
          ],
        },
        {
          slug: 'genreRails',
          labels: { singular: 'Полки по жанрам', plural: 'Полки по жанрам' },
          fields: [
            { name: 'enabled', type: 'checkbox', defaultValue: true, label: 'Показывать' },
            { name: 'genres', type: 'relationship', relationTo: 'genres', hasMany: true, label: 'Жанры' },
          ],
        },
        {
          slug: 'textSection',
          labels: { singular: 'Текстовый блок', plural: 'Текстовые блоки' },
          fields: [
            { name: 'enabled', type: 'checkbox', defaultValue: true, label: 'Показывать' },
            { name: 'heading', type: 'text', label: 'Заголовок' },
            { name: 'body', type: 'textarea', label: 'Текст' },
          ],
        },
      ],
    },
  ],
}
