<?php
/**
 * Роутер одноразового локального стенда фабрики.
 *
 * Читает routes.json, собранный рендером, и отдаёт ровно те статусы, canonical и
 * заголовки, которые описаны матрицей индексируемости. Это делает пилот настоящей
 * проверкой SEO-контура, а не осмотром статических файлов.
 *
 * Запуск: php -S 127.0.0.1:PORT -t <docroot> router.php
 */
declare(strict_types=1);

$docroot   = rtrim((string) ($_SERVER['DOCUMENT_ROOT'] ?? getcwd()), '/');
$routesFile = dirname($docroot) . '/routes.json';
$config    = is_file($routesFile) ? json_decode((string) file_get_contents($routesFile), true) : ['routes' => [], 'redirects' => []];
$environment = getenv('FACTORY_ENVIRONMENT') ?: 'staging';

$routes = [];
foreach (($config['routes'] ?? []) as $route) {
    $routes[$route['path']] = $route;
}
$redirects = [];
foreach (($config['redirects'] ?? []) as $redirect) {
    $redirects[$redirect['source']] = $redirect;
}
$nonIndexableParams = $config['non_indexable_parameters'] ?? [];

function send_common_headers(string $environment): void
{
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: SAMEORIGIN');
    header('Referrer-Policy: strict-origin-when-cross-origin');
    header('Cross-Origin-Opener-Policy: same-origin');
    header('Permissions-Policy: geolocation=(), microphone=(), camera=()');
    header("Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-src 'self' https:; object-src 'none'; base-uri 'self'; form-action 'self'");
    header_remove('X-Powered-By');
    if ($environment !== 'production') {
        header('X-Robots-Tag: noindex, nofollow');
    }
}

/** Staging закрыт авторизацией: один robots.txt защитой не считается. */
function require_staging_auth(string $environment): void
{
    if ($environment === 'production') {
        return;
    }
    $expected = getenv('FACTORY_STAGING_AUTH');   // формат user:password, приходит из окружения
    if (!$expected || !str_contains($expected, ':')) {
        // fail-closed: несконфигурированная авторизация не должна открывать стенд.
        header('X-Robots-Tag: noindex, nofollow');
        header('Retry-After: 60');
        http_response_code(503);
        echo "503 Staging authentication is not configured\n";
        exit;
    }
    [$user, $password] = explode(':', $expected, 2);
    $givenUser = $_SERVER['PHP_AUTH_USER'] ?? '';
    $givenPass = $_SERVER['PHP_AUTH_PW'] ?? '';
    if (!hash_equals($user, $givenUser) || !hash_equals($password, $givenPass)) {
        header('WWW-Authenticate: Basic realm="factory-staging"');
        header('X-Robots-Tag: noindex, nofollow');
        http_response_code(401);
        echo "401 Unauthorized\n";
        exit;
    }
}

function deny_public_path(string $path): bool
{
    $denied = ['/.env', '/.git', '/routes.json', '/build-manifest.json', '/shared/', '/backups/', '/install.php', '/engine/data/', '/.htaccess'];
    foreach ($denied as $prefix) {
        if (str_starts_with($path, $prefix)) {
            return true;
        }
    }
    return false;
}

$requestUri = (string) ($_SERVER['REQUEST_URI'] ?? '/');
$parts      = explode('?', $requestUri, 2);
$path       = $parts[0];
$query      = $parts[1] ?? '';

send_common_headers($environment);

if (deny_public_path($path)) {
    http_response_code(404);
    header('Content-Type: text/plain; charset=utf-8');
    echo "404 Not Found\n";
    return true;
}

// Авторизация staging проверяется ДО любой отдачи, включая статику: иначе
// ассеты, robots.txt и sitemap.xml доступны анонимно, и «staging закрыт» — неправда.
require_staging_auth($environment);

// Статические файлы отдаёт встроенный сервер — уже после проверки доступа.
$candidate = $docroot . $path;
if ($path !== '/' && is_file($candidate)) {
    return false;
}

// Нормализация: единый регистр и завершающий слэш.
$lower = strtolower($path);
if ($lower !== $path) {
    http_response_code(301);
    header('Location: ' . $lower . ($query !== '' ? '?' . $query : ''));
    return true;
}
if (!str_ends_with($path, '/') && !str_contains(basename($path), '.')) {
    http_response_code(301);
    header('Location: ' . $path . '/' . ($query !== '' ? '?' . $query : ''));
    return true;
}

// Явные редиректы из сборки (например /page/1/ → базовый URL).
if (isset($redirects[$path])) {
    http_response_code((int) $redirects[$path]['status']);
    header('Location: ' . $redirects[$path]['target']);
    return true;
}

$route = $routes[$path] ?? null;

// Нормализация параметров, объявленная матрицей: порядок ключей приводится к
// алфавитному, повторяющиеся и неизвестные ключи отвергаются. Без этого один и тот
// же объект доступен под множеством URL — прямой путь к комбинаторному взрыву.
$hasNonIndexableParam = false;
if ($query !== '') {
    $rawPairs = array_filter(explode('&', $query), static fn ($p) => $p !== '');
    $seenKeys = [];
    $known = array_merge($nonIndexableParams, $config['canonical_changing_parameters'] ?? []);
    $normalized = [];
    foreach ($rawPairs as $pair) {
        $key = urldecode(explode('=', $pair, 2)[0]);
        if (isset($seenKeys[$key])) {
            http_response_code(400);
            header('X-Robots-Tag: noindex, nofollow');
            echo "400 Repeated query parameter: " . htmlspecialchars($key) . "\n";
            return true;
        }
        $seenKeys[$key] = true;
        if (!in_array($key, $known, true)) {
            http_response_code(400);
            header('X-Robots-Tag: noindex, nofollow');
            echo "400 Unknown query parameter: " . htmlspecialchars($key) . "\n";
            return true;
        }
        if (in_array($key, $nonIndexableParams, true)) {
            $hasNonIndexableParam = true;
        }
        $normalized[] = $pair;
    }
    sort($normalized);
    $canonicalQuery = implode('&', $normalized);
    if ($canonicalQuery !== $query) {
        http_response_code(301);
        header('Location: ' . $path . '?' . $canonicalQuery);
        return true;
    }
}

if ($route === null) {
    // Страница пагинации вне диапазона и любой неизвестный URL — честный 404.
    $notFound = $routes['/404/'] ?? null;
    http_response_code(404);
    header('Content-Type: text/html; charset=utf-8');
    if ($notFound && is_file($docroot . '/' . $notFound['file'])) {
        readfile($docroot . '/' . $notFound['file']);
    } else {
        echo "404 Not Found\n";
    }
    return true;
}

$status = (int) ($route['status'] ?? 200);
http_response_code($status);
header('Content-Type: text/html; charset=utf-8');
if ($hasNonIndexableParam) {
    header('X-Robots-Tag: noindex, follow');
}
$file = $docroot . '/' . ($route['file'] ?? '');
if (is_file($file)) {
    readfile($file);
} else {
    echo "500 Build artifact missing\n";
    http_response_code(500);
}
return true;
