import type { CollectionBeforeValidateHook, CollectionConfig } from 'payload'
import { hasRole, superAdminOnly } from '../access/index'

/**
 * Общий фактический каталог. Эти данные одинаковы для всех сайтов: один и тот же
 * тайтл не должен существовать в трёх несогласованных копиях. Редакционные тексты,
 * URL и SEO живут отдельно, в TenantTitles.
 */

const provenanceFields: CollectionConfig['fields'] = [
  {
    type: 'collapsible',
    label: 'Происхождение данных',
    admin: { initCollapsed: true },
    fields: [
      {
        name: 'source',
        type: 'select',
        label: 'Источник',
        defaultValue: 'manual',
        options: [
          { label: 'Ручной ввод редактора', value: 'manual' },
          { label: 'Content API провайдера', value: 'provider_api' },
          { label: 'Импорт из переданного файла', value: 'import_file' },
        ],
      },
      { name: 'sourceRef', type: 'text', label: 'Ссылка на запись источника' },
      { name: 'sourceUpdatedAt', type: 'date', label: 'Дата данных в источнике' },
    ],
  },
]

export const CatalogMedia: CollectionConfig = {
  slug: 'catalog-media',
  labels: { singular: 'Изображение каталога', plural: 'Изображения каталога' },
  admin: {
    group: 'Каталог (общий)',
    description:
      'Постеры и кадры, общие для всех сайтов. Хранятся отдельно от медиатеки сайта: ' +
      'общий тайтл не может ссылаться на файл одного сайта, иначе он утёк бы на остальные.',
  },
  upload: {
    staticDir: process.env.CATALOG_MEDIA_DIR ?? 'var/catalog-media',
    mimeTypes: ['image/png', 'image/jpeg', 'image/webp', 'image/avif'],
    imageSizes: [
      { name: 'card', width: 400, height: 600, position: 'centre' },
      { name: 'wide', width: 1200, height: 675, position: 'centre' },
    ],
  },
  access: { read: () => true, create: hasRole('site_admin'), update: hasRole('site_admin'), delete: superAdminOnly },
  fields: [
    { name: 'alt', type: 'text', required: true, label: 'Альтернативный текст',
      admin: { description: 'Обязателен: без alt изображение не публикуется.' } },
    { name: 'rightsRecord', type: 'relationship', relationTo: 'rights-records', required: true,
      label: 'Запись о правах',
      admin: { description: 'Без подтверждённых прав изображение не попадает в публикацию.' } },
    ...provenanceFields,
  ],
}

export const Genres: CollectionConfig = {
  slug: 'genres',
  labels: { singular: 'Жанр', plural: 'Жанры' },
  admin: { useAsTitle: 'name', group: 'Каталог (общий)' },
  access: { read: () => true, create: hasRole('site_admin'), update: hasRole('site_admin'), delete: superAdminOnly },
  fields: [
    { name: 'name', type: 'text', required: true, label: 'Название' },
    { name: 'slug', type: 'text', required: true, unique: true, index: true, label: 'URL-код' },
  ],
}

export const Studios: CollectionConfig = {
  slug: 'studios',
  labels: { singular: 'Студия', plural: 'Студии' },
  admin: { useAsTitle: 'name', group: 'Каталог (общий)' },
  access: { read: () => true, create: hasRole('site_admin'), update: hasRole('site_admin'), delete: superAdminOnly },
  fields: [
    { name: 'name', type: 'text', required: true, label: 'Название' },
    { name: 'slug', type: 'text', required: true, unique: true, index: true, label: 'URL-код' },
    ...provenanceFields,
  ],
}

/** Состояния, при которых произведение ещё не вышло. */
export const UPCOMING_RELEASE_STATES = ['announced', 'date_unknown', 'soon', 'delayed'] as const

/**
 * Анонс без источника — выдумка, а анонс с датой без подтверждения — выдумка с
 * подробностями. Оба случая отклоняются до записи, а не помечаются в отчёте.
 */
export const validateReleaseState: CollectionBeforeValidateHook = ({ data }) => {
  if (!data) return data
  const state = String(data.releaseState ?? 'released')
  const sourceRef = String(data.releaseSourceRef ?? '').trim()
  const confirmed = Boolean(data.releaseDateConfirmed)

  if (state !== 'released' && state !== 'cancelled' && !sourceRef) {
    throw new Error(
      `BLOCKED_INPUT: состояние «${state}» требует ссылки на подтверждение (releaseSourceRef).`,
    )
  }
  if (state === 'soon' && !(data.releaseDate && confirmed)) {
    throw new Error('BLOCKED_INPUT: состояние «скоро» требует подтверждённой даты выхода.')
  }
  if (data.releaseDate && !confirmed && state !== 'released') {
    throw new Error(
      'BLOCKED_INPUT: дата выхода указана, но не подтверждена источником. Уберите дату или подтвердите её.',
    )
  }
  if (state === 'delayed' && !data.previousReleaseDate) {
    throw new Error('BLOCKED_INPUT: перенос обязан сохранять прежнюю дату (previousReleaseDate).')
  }
  return data
}

export const Countries: CollectionConfig = {
  slug: 'countries',
  labels: { singular: 'Страна', plural: 'Страны' },
  admin: { useAsTitle: 'name', group: 'Каталог (общий)' },
  access: { read: () => true, create: hasRole('site_admin'), update: hasRole('site_admin'), delete: superAdminOnly },
  fields: [
    { name: 'name', type: 'text', required: true, label: 'Название' },
    { name: 'slug', type: 'text', required: true, unique: true, index: true, label: 'URL-код' },
  ],
}

export const Titles: CollectionConfig = {
  slug: 'titles',
  // Соответствие провайдеру обязано быть уникальным в базе, а не только в коде
  // импорта: два параллельных прогона иначе создают два тайтла на один ID, после
  // чего импорт блокируется навсегда как «неоднозначное соответствие».
  indexes: [{ fields: ['playbackAggregator', 'playbackTitleId'], unique: true }],
  labels: { singular: 'Тайтл (общие факты)', plural: 'Тайтлы (общие факты)' },
  admin: {
    useAsTitle: 'primaryName',
    group: 'Каталог (общий)',
    description: 'Проверенные факты о тайтле. Тексты и SEO конкретного сайта — в разделе «Публикации сайта».',
    defaultColumns: ['primaryName', 'kind', 'status', 'year'],
  },
  access: { read: () => true, create: hasRole('site_admin'), update: hasRole('site_admin'), delete: superAdminOnly },
  fields: [
    { name: 'primaryName', type: 'text', required: true, index: true, label: 'Основное название' },
    { name: 'englishName', type: 'text', label: 'Английское название' },
    { name: 'originalName', type: 'text', label: 'Оригинальное название' },
    {
      name: 'alternativeNames',
      type: 'array',
      label: 'Альтернативные названия',
      fields: [{ name: 'value', type: 'text', required: true, label: 'Название' }],
    },
    {
      name: 'kind',
      type: 'select',
      required: true,
      defaultValue: 'series',
      label: 'Тип',
      options: [
        { label: 'Сериал', value: 'series' },
        { label: 'Мини-сериал', value: 'miniseries' },
        { label: 'Фильм', value: 'movie' },
        { label: 'Полнометражная анимация', value: 'animated_film' },
        { label: 'OVA/ONA', value: 'ova' },
      ],
      admin: {
        description:
          'Тип определяет, какой сайт индексирует страницу произведения: сериальные формы — '
          + 'сайт сериалов, полнометражные — сайт фильмов. Двух владельцев у одной страницы не бывает.',
      },
    },
    {
      name: 'status',
      type: 'select',
      required: true,
      defaultValue: 'ongoing',
      label: 'Статус выхода',
      options: [
        { label: 'Выходит', value: 'ongoing' },
        { label: 'Завершён', value: 'completed' },
        { label: 'Анонс', value: 'announced' },
      ],
    },
    { name: 'year', type: 'number', label: 'Год выхода', min: 1900, max: 2100 },
    { name: 'factualSynopsis', type: 'textarea', label: 'Фактическое описание из источника',
      admin: { description: 'Факты из источника. Редакционный текст сайта пишется отдельно и не выдаётся за оригинальный.' } },
    {
      name: 'availability',
      type: 'select',
      required: true,
      defaultValue: 'available',
      label: 'Доступность материала',
      options: [
        { label: 'Доступен', value: 'available' },
        { label: 'Временно недоступен', value: 'unavailable' },
        { label: 'Снят с публикации', value: 'withdrawn' },
      ],
      admin: {
        description:
          'Исчезнувший из источника материал получает явное состояние. Подменять его другим тайтлом запрещено.',
      },
    },
    {
      type: 'collapsible',
      label: 'Релизное состояние',
      admin: {
        initCollapsed: true,
        description:
          'Состояние выхода и дата. Дата без подтверждённого источника не сохраняется: пустое поле '
          + 'честнее выдуманного, а страница анонса без источника не индексируется.',
      },
      fields: [
        {
          name: 'releaseState',
          type: 'select',
          required: true,
          defaultValue: 'released',
          index: true,
          label: 'Состояние выхода',
          options: [
            { label: 'Анонсировано', value: 'announced' },
            { label: 'Дата не объявлена', value: 'date_unknown' },
            { label: 'Скоро', value: 'soon' },
            { label: 'Вышло', value: 'released' },
            { label: 'Перенесено', value: 'delayed' },
            { label: 'Отменено', value: 'cancelled' },
          ],
        },
        { name: 'releaseDate', type: 'date', index: true, label: 'Дата выхода' },
        {
          name: 'releaseDateConfirmed',
          type: 'checkbox',
          defaultValue: false,
          label: 'Дата подтверждена источником',
        },
        {
          name: 'releaseSourceRef',
          type: 'text',
          label: 'Ссылка на подтверждение',
          admin: { description: 'Обязательна для любого состояния, кроме «Вышло».' },
        },
        {
          name: 'previousReleaseDate',
          type: 'date',
          label: 'Прежняя дата (при переносе)',
          admin: { description: 'История расписания не переписывается задним числом.' },
        },
      ],
    },
    { name: 'genres', type: 'relationship', relationTo: 'genres', hasMany: true, label: 'Жанры' },
    { name: 'countries', type: 'relationship', relationTo: 'countries', hasMany: true, label: 'Страны производства' },
    { name: 'studios', type: 'relationship', relationTo: 'studios', hasMany: true, label: 'Студии' },
    { name: 'poster', type: 'upload', relationTo: 'catalog-media', label: 'Постер' },
    {
      type: 'collapsible',
      label: 'Идентификаторы провайдера воспроизведения',
      admin: { initCollapsed: true, description: 'Заполняется только из разрешённого Content API или подтверждённой записи источника.' },
      fields: [
        {
          name: 'playbackAggregator',
          type: 'select',
          label: 'Агрегатор',
          options: [
            { label: 'kp', value: 'kp' },
            { label: 'mali', value: 'mali' },
            { label: 'mdl', value: 'mdl' },
          ],
        },
        { name: 'playbackTitleId', type: 'text', label: 'ID тайтла у агрегатора' },
        { name: 'rightsRecord', type: 'relationship', relationTo: 'rights-records', label: 'Запись о правах' },
      ],
    },
    {
      name: 'relatedTitles',
      type: 'relationship',
      relationTo: 'titles',
      hasMany: true,
      label: 'Связанные тайтлы',
      admin: { description: 'Только реальные связи. «Похожее» не придумывается.' },
    },
    ...provenanceFields,
  ],
  hooks: { beforeValidate: [validateReleaseState] },
}

export const Seasons: CollectionConfig = {
  slug: 'seasons',
  labels: { singular: 'Сезон', plural: 'Сезоны' },
  admin: { useAsTitle: 'label', group: 'Каталог (общий)', defaultColumns: ['label', 'title', 'number'] },
  access: { read: () => true, create: hasRole('site_admin'), update: hasRole('site_admin'), delete: superAdminOnly },
  fields: [
    { name: 'title', type: 'relationship', relationTo: 'titles', required: true, index: true, label: 'Тайтл' },
    { name: 'number', type: 'number', required: true, min: 1, label: 'Номер сезона' },
    { name: 'label', type: 'text', label: 'Название сезона' },
    ...provenanceFields,
  ],
}

export const Episodes: CollectionConfig = {
  slug: 'episodes',
  labels: { singular: 'Серия', plural: 'Серии' },
  admin: { useAsTitle: 'label', group: 'Каталог (общий)', defaultColumns: ['label', 'season', 'number', 'airedAt'] },
  access: { read: () => true, create: hasRole('site_admin'), update: hasRole('site_admin'), delete: superAdminOnly },
  fields: [
    { name: 'season', type: 'relationship', relationTo: 'seasons', required: true, index: true, label: 'Сезон' },
    { name: 'number', type: 'number', required: true, min: 1, label: 'Номер серии' },
    { name: 'label', type: 'text', label: 'Название серии' },
    { name: 'airedAt', type: 'date', label: 'Дата выхода', admin: { description: 'Только известная дата. Пустое поле лучше выдуманного.' } },
    {
      name: 'playbackAvailable',
      type: 'checkbox',
      defaultValue: false,
      label: 'Воспроизведение доступно',
      admin: { description: 'Снимается автоматически, если провайдер сообщил об отсутствии данных.' },
    },
    ...provenanceFields,
  ],
}

export const RightsRecords: CollectionConfig = {
  slug: 'rights-records',
  labels: { singular: 'Запись о правах', plural: 'Права на контент' },
  admin: { useAsTitle: 'label', group: 'Права и источники' },
  // Ссылка на договор и территория — коммерческие данные, а не публичный факт.
  // Рендер читает их на сервере через overrideAccess и от этого не страдает.
  access: { read: hasRole('analyst'), create: hasRole('site_admin'),
            update: hasRole('site_admin'), delete: superAdminOnly },
  fields: [
    { name: 'label', type: 'text', required: true, label: 'Обозначение' },
    { name: 'holder', type: 'text', required: true, label: 'Правообладатель' },
    { name: 'contractRef', type: 'text', required: true, label: 'Ссылка на договор/contract' },
    { name: 'territory', type: 'text', label: 'Территория' },
    { name: 'validUntil', type: 'date', label: 'Действует до' },
    {
      name: 'allowsPublication',
      type: 'checkbox',
      defaultValue: false,
      label: 'Разрешает публикацию',
      admin: { description: 'Без этого флага тайтл не публикуется ни на одном сайте.' },
    },
  ],
}

export const SourceRecords: CollectionConfig = {
  slug: 'source-records',
  labels: { singular: 'Запись источника', plural: 'Источники данных' },
  admin: { useAsTitle: 'label', group: 'Права и источники' },
  access: { read: () => true, create: hasRole('site_admin'), update: hasRole('site_admin'), delete: superAdminOnly },
  fields: [
    { name: 'label', type: 'text', required: true, label: 'Обозначение' },
    { name: 'kind', type: 'select', required: true, label: 'Вид источника',
      options: [
        { label: 'Content API провайдера', value: 'provider_api' },
        { label: 'Переданный файл', value: 'file' },
        { label: 'Ручная запись редактора', value: 'manual' },
      ] },
    { name: 'reference', type: 'text', required: true, label: 'Ссылка/путь' },
    { name: 'sha256', type: 'text', label: 'SHA-256 переданного файла' },
    { name: 'retrievedAt', type: 'date', label: 'Дата получения' },
  ],
}

export const Voices: CollectionConfig = {
  slug: 'voices',
  labels: { singular: 'Озвучка', plural: 'Озвучки' },
  admin: {
    useAsTitle: 'name',
    group: 'Каталог (общий)',
    description:
      'Справочник озвучек. Значения используются в атрибутах плеера only-voice / priority-voice ' +
      'строго в том виде, в каком их принимает документированный контракт плеера.',
  },
  access: { read: () => true, create: hasRole('site_admin'), update: hasRole('site_admin'), delete: superAdminOnly },
  fields: [
    { name: 'name', type: 'text', required: true, label: 'Название' },
    { name: 'slug', type: 'text', required: true, unique: true, index: true, label: 'URL-код' },
    {
      name: 'playerValue',
      type: 'text',
      label: 'Значение для контракта плеера',
      admin: {
        description:
          'Заполняется только значением, подтверждённым документацией или ответом провайдера. ' +
          'Пусто = озвучка не передаётся в плеер (BLOCKED_INPUT для сценариев, где она требуется).',
      },
    },
    ...provenanceFields,
  ],
}
