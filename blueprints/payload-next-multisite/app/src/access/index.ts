import type { Access, FieldAccess, PayloadRequest } from 'payload'

/**
 * Роли фабрики. Проверка всегда серверная: значение роли из клиента не принимается.
 */
export type Role = 'super_admin' | 'site_admin' | 'editor' | 'moderator' | 'analyst'

export type FactoryUser = {
  id: string | number
  role?: Role
  tenants?: { tenant: string | number | { id: string | number } }[]
}

export const isSuperAdmin = (user: unknown): boolean =>
  Boolean(user && (user as FactoryUser).role === 'super_admin')

/** ID тенантов, к которым пользователь привязан явно. */
export const tenantIdsOf = (user: unknown): (string | number)[] => {
  const rows = (user as FactoryUser)?.tenants ?? []
  return rows
    .map((row) => (typeof row.tenant === 'object' && row.tenant !== null ? row.tenant.id : row.tenant))
    .filter((value): value is string | number => value !== undefined && value !== null)
}

export const hasRole =
  (...roles: Role[]) =>
  ({ req }: { req: PayloadRequest }): boolean => {
    const user = req.user as FactoryUser | null
    if (!user) return false
    if (user.role === 'super_admin') return true
    return Boolean(user.role && roles.includes(user.role))
  }

/**
 * Доступ к tenant-scoped коллекции.
 *
 * Super admin видит всё. Остальные — только документы своих тенантов, и это
 * выражается КОНСТРЕЙНТОМ ЗАПРОСА, а не фильтрацией после выборки: иначе чужие
 * документы утекали бы через count, Local API и связанные поля.
 */
export const tenantScopedAccess =
  (options: { roles?: Role[] } = {}): Access =>
  ({ req }) => {
    const user = req.user as FactoryUser | null
    if (!user) return false
    if (isSuperAdmin(user)) return true
    if (options.roles && user.role && !options.roles.includes(user.role)) return false
    const tenants = tenantIdsOf(user)
    if (tenants.length === 0) return false
    return { tenant: { in: tenants } }
  }

/**
 * Доступ к самой коллекции сайтов. Здесь фильтр идёт по `id`, а не по полю
 * `tenant`: у записи сайта нет ссылки на сайт — она сама и есть сайт. Попытка
 * применить общий tenant-фильтр ломает запрос (нет такого поля) и роняет любое
 * чтение, где всплывает связь на сайт.
 */
export const tenantSelfAccess: Access = ({ req }) => {
  const user = req.user as FactoryUser | null
  if (!user) return false
  if (isSuperAdmin(user)) return true
  const tenants = tenantIdsOf(user)
  if (tenants.length === 0) return false
  return { id: { in: tenants } }
}

export const superAdminOnly: Access = ({ req }) => isSuperAdmin(req.user)

export const fieldSuperAdminOnly: FieldAccess = ({ req }) => isSuperAdmin(req.user)

/** Роль назначает только super admin: иначе редактор повысит сам себя. */
export const roleFieldAccess: FieldAccess = ({ req }) => isSuperAdmin(req.user)
