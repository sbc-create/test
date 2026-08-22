import { NextResponse, type NextRequest } from 'next/server'

/**
 * Канонизация адресов страниц: единственный вид URL — со слэшем на конце.
 *
 * Встроенный редирект Next отключён, потому что он применяется и к /api/*,
 * где 308 на POST превращает вызов endpoint в лишний переход. Здесь редирект
 * получают только страницы.
 */

const SKIP_PREFIXES = ['/api', '/admin', '/_next', '/mock']

export const middleware = (request: NextRequest) => {
  const { pathname, search } = request.nextUrl

  if (SKIP_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))) {
    return NextResponse.next()
  }
  // Файлы отдаются как есть: /robots.txt со слэшем на конце не существует.
  if (pathname.includes('.')) return NextResponse.next()
  if (pathname.endsWith('/')) return NextResponse.next()

  const url = request.nextUrl.clone()
  url.pathname = `${pathname}/`
  url.search = search
  return NextResponse.redirect(url, 308)
}

export const config = {
  matcher: ['/((?!_next/static|_next/image).*)'],
}
