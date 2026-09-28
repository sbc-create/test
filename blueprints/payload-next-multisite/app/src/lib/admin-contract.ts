/**
 * Контракт потребления `site-admin/1.0.0` со стороны шаблонов.
 *
 * Единый движок админки и сам контракт принадлежат Core; сюда они не
 * копируются и копироваться не должны. Здесь объявлено ровно обратное — что
 * из отданного админкой шаблон **читает**, и это объявление нужно по двум
 * причинам.
 *
 * Первая. Имена полей сегодня разбросаны по компонентам строками: `rightsNotice`
 * в подвале, `tagline` на главной, `commentsEnabled` в обсуждениях. Переименуй
 * поле в админке — и шаблон молча покажет пустоту вместо значения. Молча:
 * ни ошибки сборки, ни падения теста, только исчезнувший текст на витрине.
 * Собранный перечень позволяет проверке заметить расхождение раньше зрителя.
 *
 * Вторая. Перечень — это граница. Всё, чего в нём нет, шаблон у админки не
 * просит, и появление нового чтения обязано начинаться с правки этого файла.
 *
 * Чего здесь нет намеренно: значений по умолчанию на случай отсутствия поля.
 * Пустое поле — это «оператор не заполнил», а не «подставь что-нибудь»;
 * решение о поведении при пустоте принимает компонент и принимает его видимо.
 */

/** Версия контракта, под которую написано потребление. */
export const ADMIN_CONTRACT_VERSION = 'site-admin/1.0.0'

/** Настройки витрины, которые читает слой шаблонов. */
export const CONSUMED_SETTINGS = [
  'commentsEnabled',
  'defaultDescription',
  'maxLength',
  'rightsNotice',
  'rulesText',
  'tagline',
] as const

/** Разделы навигации, которые читает слой шаблонов. */
export const CONSUMED_NAVIGATION = ['header', 'footerGroups'] as const

export type ConsumedSetting = (typeof CONSUMED_SETTINGS)[number]
export type ConsumedNavigation = (typeof CONSUMED_NAVIGATION)[number]

export type AdminSurface = {
  settings: Partial<Record<ConsumedSetting, unknown>> | null
  navigation: Partial<Record<ConsumedNavigation, unknown>> | null
}

/**
 * Поля, которые витрина отдала, но шаблон не читает.
 *
 * Не ошибка сама по себе: админка вправе хранить больше, чем показывает
 * витрина. Но перечень полезен — расхождение обычно означает либо
 * переименование, либо забытое потребление, и увидеть его лучше в отчёте
 * проверки, чем на боевой странице.
 */
export const unreadSettings = (settings: Record<string, unknown> | null): string[] =>
  Object.keys(settings ?? {}).filter(
    (key) => !(CONSUMED_SETTINGS as readonly string[]).includes(key),
  )

/**
 * Поля контракта, которых витрина не прислала.
 *
 * Тоже не ошибка: оператор мог не заполнить настройку. Возвращается затем,
 * чтобы отчёт мог отличить «поле пустое» от «поля нет вовсе» — это разные
 * состояния с разными владельцами.
 */
export const missingSettings = (settings: Record<string, unknown> | null): string[] =>
  CONSUMED_SETTINGS.filter((key) => !(key in (settings ?? {})))
