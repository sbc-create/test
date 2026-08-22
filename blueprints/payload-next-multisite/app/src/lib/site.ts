import { cache } from 'react'
import { headers } from 'next/headers'
import { getPayload } from 'payload'

import config from '../payload.config'
import { profileFor, type SeoProfile } from '../seo/profiles'
import { layoutFor, type ThemeLayout } from '../themes/layouts'
import { resolveTenantByHost, tenantGlobal, type TenantContext } from './tenant-query'

/**
 * Контекст запроса для публичных страниц: какой сайт обслуживаем и его настройки.
 * Кэш на время запроса — чтобы шапка, подвал и страница не ходили в базу трижды.
 */

export type SiteContext = {
  tenant: TenantContext
  profile: SeoProfile
  /** Структурная компоновка темы: шапка, поиск, форма карточки, порядок модулей. */
  layout: ThemeLayout
  settings: Record<string, unknown> | null
  navigation: Record<string, unknown> | null
  siteName: string
}

export const payloadClient = cache(async () => getPayload({ config }))

export const currentSite = cache(async (): Promise<SiteContext> => {
  const payload = await payloadClient()
  const requestHeaders = await headers()
  const tenant = await resolveTenantByHost(payload, requestHeaders.get('host'))
  const settings = (await tenantGlobal(payload, 'site-settings', tenant)) as Record<string, unknown> | null
  const navigation = (await tenantGlobal(payload, 'navigation', tenant)) as Record<string, unknown> | null

  const siteName = String(settings?.siteName ?? '').trim()
  if (!siteName) {
    // Название сайта не придумывается кодом: пустое поле — это незаполненный
    // пакет сайта, а не повод подставить «Аниме портал».
    throw new Error(`BLOCKED_INPUT: у сайта ${tenant.slug} не заполнено публичное название`)
  }

  return {
    tenant,
    profile: profileFor(tenant.seoProfile),
    layout: layoutFor(tenant.theme),
    settings,
    navigation,
    siteName,
  }
})
