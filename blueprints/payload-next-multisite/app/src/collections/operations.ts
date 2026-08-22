import type { CollectionConfig } from 'payload'
import { hasRole, superAdminOnly, tenantScopedAccess } from '../access/index'

/**
 * Операционные коллекции: импорт из Content API, расписание выходов и конфигурация
 * плеера. Записи создаются серверным кодом фабрики, а не руками в админке, поэтому
 * `create`/`update` из Admin UI закрыты: иначе журнал импорта перестаёт быть
 * доказательством того, что реально выполнялось.
 */

export const ImportJobs: CollectionConfig = {
  slug: 'import-jobs',
  labels: { singular: 'Задание импорта', plural: 'Задания импорта' },
  admin: {
    useAsTitle: 'reference',
    group: 'Операции',
    description:
      'Журнал обращений к Content API провайдера. Показывает, что именно было запрошено, ' +
      'сколько записей создано/обновлено/пропущено и в каком режиме (mock или live).',
    defaultColumns: ['reference', 'mode', 'status', 'startedAt'],
  },
  access: {
    read: hasRole('analyst'),
    create: () => false,
    update: () => false,
    delete: superAdminOnly,
  },
  indexes: [{ fields: ['requestDigest'] }, { fields: ['status', 'startedAt'] }],
  fields: [
    { name: 'reference', type: 'text', required: true, index: true, label: 'Идентификатор задания' },
    {
      name: 'mode',
      type: 'select',
      required: true,
      label: 'Режим',
      options: [
        { label: 'Фикстуры (mock)', value: 'mock' },
        { label: 'Живой Content API', value: 'live' },
      ],
      admin: { description: 'Production технически отвергает mock: проверка выполняется в адаптере, а не на словах.' },
    },
    {
      name: 'status',
      type: 'select',
      required: true,
      label: 'Статус',
      options: [
        { label: 'Выполняется', value: 'running' },
        { label: 'Успешно', value: 'succeeded' },
        { label: 'Ошибка', value: 'failed' },
        { label: 'Заблокировано входными данными', value: 'blocked_input' },
        { label: 'Заблокировано правами на контент', value: 'blocked_content_rights' },
        { label: 'Отказ доступа провайдера', value: 'blocked_access' },
      ],
    },
    {
      name: 'requestDigest',
      type: 'text',
      required: true,
      label: 'Отпечаток запроса',
      admin: {
        description:
          'sha256 нормализованных параметров запроса. Повторный импорт с тем же отпечатком ' +
          'обязан быть идемпотентным: те же данные не создают дублей.',
      },
    },
    { name: 'startedAt', type: 'date', required: true, label: 'Начало' },
    { name: 'finishedAt', type: 'date', label: 'Завершение' },
    {
      type: 'row',
      fields: [
        { name: 'created', type: 'number', defaultValue: 0, label: 'Создано' },
        { name: 'updated', type: 'number', defaultValue: 0, label: 'Обновлено' },
        { name: 'skipped', type: 'number', defaultValue: 0, label: 'Без изменений' },
        { name: 'blocked', type: 'number', defaultValue: 0, label: 'Заблокировано' },
      ],
    },
    {
      name: 'message',
      type: 'textarea',
      label: 'Сообщение',
      admin: { description: 'Текст ошибки после редакции секретов. Токен и заголовки авторизации сюда не попадают.' },
    },
    { name: 'artifactPath', type: 'text', label: 'Артефакт запуска' },
  ],
}

export const ReleaseEvents: CollectionConfig = {
  slug: 'release-events',
  labels: { singular: 'Событие расписания', plural: 'Расписание выходов' },
  admin: {
    useAsTitle: 'label',
    group: 'Каталог (общий)',
    description:
      'Фактические даты выхода эпизодов. Общие для всех сайтов: расписание — это факт, ' +
      'а не редакционный материал конкретного сайта.',
    defaultColumns: ['label', 'airsAt', 'state'],
  },
  access: { read: () => true, create: hasRole('editor'), update: hasRole('editor'), delete: superAdminOnly },
  indexes: [{ fields: ['airsAt', 'state'] }],
  fields: [
    { name: 'label', type: 'text', required: true, label: 'Подпись события' },
    { name: 'title', type: 'relationship', relationTo: 'titles', required: true, index: true, label: 'Тайтл' },
    { name: 'episode', type: 'relationship', relationTo: 'episodes', label: 'Эпизод' },
    { name: 'airsAt', type: 'date', required: true, index: true, label: 'Дата и время выхода (UTC)' },
    {
      name: 'state',
      type: 'select',
      required: true,
      defaultValue: 'announced',
      label: 'Состояние',
      options: [
        { label: 'Анонсировано', value: 'announced' },
        { label: 'Вышло', value: 'released' },
        { label: 'Перенесено', value: 'delayed' },
        { label: 'Отменено', value: 'cancelled' },
      ],
    },
    {
      name: 'precision',
      type: 'select',
      required: true,
      defaultValue: 'exact',
      label: 'Точность даты',
      options: [
        { label: 'Точные дата и время', value: 'exact' },
        { label: 'Только дата', value: 'day' },
        { label: 'Неделя', value: 'week' },
        { label: 'Неизвестно', value: 'unknown' },
      ],
      admin: { description: 'Неизвестную дату нельзя показывать как точную: это выдуманный факт.' },
    },
  ],
}

export const PlayerProfiles: CollectionConfig = {
  slug: 'player-profiles',
  labels: { singular: 'Профиль плеера', plural: 'Профили плеера' },
  admin: {
    useAsTitle: 'name',
    group: 'Операции',
    description:
      'Параметры встраивания плеера для этого сайта. Значения publisher ID и API-токена здесь ' +
      'НЕ хранятся: указывается только имя секрета (secret_ref), значение подставляет сервер.',
  },
  access: {
    read: tenantScopedAccess(),
    create: hasRole('site_admin'),
    update: hasRole('site_admin'),
    delete: superAdminOnly,
  },
  fields: [
    { name: 'name', type: 'text', required: true, label: 'Название профиля' },
    {
      name: 'publisherIdRef',
      type: 'text',
      required: true,
      label: 'Имя секрета с publisher ID',
      admin: {
        description:
          'Например PLAYER_PUBLISHER_ID_SITE_A. В CMS и git хранится только имя переменной; ' +
          'значение подставляет сервер. Само значение — публичный параметр встраивания: ' +
          'по контракту оно обязано быть в HTML как data-publisher-id. Секретом является ' +
          'токен Content API, а не этот идентификатор.',
      },
      validate: (value: unknown) =>
        typeof value === 'string' && /^[A-Z][A-Z0-9_]{2,63}$/.test(value)
          ? true
          : 'Укажите имя секрета в верхнем регистре, а не его значение.',
    },
    {
      name: 'aggregator',
      type: 'select',
      required: true,
      label: 'Агрегатор идентификаторов',
      options: [
        { label: 'kp', value: 'kp' },
        { label: 'mali', value: 'mali' },
        { label: 'mdl', value: 'mdl' },
      ],
      admin: { description: 'Только значения из документированного контракта плеера.' },
    },
    {
      type: 'row',
      fields: [
        { name: 'showBanner', type: 'checkbox', defaultValue: false, label: 'Показывать баннер плеера' },
        { name: 'showVoiceOnly', type: 'checkbox', defaultValue: false, label: 'Режим «только озвучка»' },
      ],
    },
    {
      name: 'priorityVoice',
      type: 'relationship',
      relationTo: 'voices',
      label: 'Приоритетная озвучка',
      admin: { description: 'Передаётся в плеер только если у озвучки заполнено значение контракта.' },
    },
    {
      name: 'contractNote',
      type: 'textarea',
      label: 'Примечание к контракту',
      admin: {
        readOnly: true,
        description:
          'disable-licensed="false" в production неизменно и задаётся кодом, а не этой формой. ' +
          'Попытка отправить иное значение — BLOCKED_PLAYER_CONTRACT.',
      },
    },
  ],
}
