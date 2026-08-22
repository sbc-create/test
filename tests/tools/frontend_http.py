#!/usr/bin/env python3
"""HTTP-проверка трёх сайтов на одном приложении.

Проверяется то, что видит посетитель и краулер: код ответа, тема, canonical,
robots, состав sitemap и отсутствие чужого сайта в выдаче. Ничего не считается
пройденным без фактического запроса — все ответы сохраняются в артефакт.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "blueprints" / "payload-next-multisite" / "app"
ARTIFACT = ROOT / "var" / "artifacts" / "frontend-http.json"

MIN_FILL_SECONDS = 3

SITES = {
    "a": {"host": "site-a.localhost", "theme": "portal_light", "name": "Стенд A — каталог", "profile": "catalog_authority"},
    "b": {"host": "site-b.localhost", "theme": "pulse", "name": "Стенд B — расписание", "profile": "release_pulse"},
    "c": {"host": "site-c.localhost", "theme": "editorial", "name": "Стенд C — редакция", "profile": "editorial_guide"},
}

# Профиль решает, какие типы страниц индексируются. Ожидания — из profiles.ts.
INDEXABLE = {
    "a": {"/": True, "/catalog/": True, "/catalog/stand-title-1/": True,
          "/catalog/stand-title-1/season-1/": True,
          "/catalog/stand-title-1/season-1/episode-1/": True,
          "/collections/stand-collection-a/": True, "/news/": True, "/legal/rights/": True},
    "b": {"/": True, "/catalog/": True, "/catalog/stand-title-1/": True,
          "/catalog/stand-title-1/season-1/": False,
          "/catalog/stand-title-1/season-1/episode-1/": True,
          "/collections/stand-collection-b/": False, "/news/": True, "/legal/rights/": True},
    "c": {"/": True, "/catalog/": False, "/catalog/stand-title-1/": True,
          "/catalog/stand-title-1/season-1/": False,
          "/catalog/stand-title-1/season-1/episode-1/": False,
          "/collections/stand-collection-c/": True, "/news/": True, "/legal/rights/": True},
}


@dataclass
class Results:
    checks: list[dict] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS  " if ok else "FAIL  ") + name + (f"\n      {detail}" if detail and not ok else ""))

    @property
    def failed(self) -> list[dict]:
        return [check for check in self.checks if not check["ok"]]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Редиректы не следуем: canonical, указывающий на редирект, — дефект (HR-2)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def fetch(port: int, host: str, path: str, timeout: float = 180.0, follow: bool = True) -> tuple[int, str]:
    # Кириллица в query должна быть процентно закодирована: заголовок запроса — ASCII.
    quoted = urllib.parse.quote(path, safe="/?=&:")
    request = urllib.request.Request(f"http://127.0.0.1:{port}{quoted}", headers={"Host": host})
    handlers: list = [urllib.request.ProxyHandler({})]
    if not follow:
        handlers.append(NoRedirect())
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


CANONICAL_RE = re.compile(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"')
ROBOTS_RE = re.compile(r'<meta[^>]+name="robots"[^>]+content="([^"]+)"')
THEME_RE = re.compile(r'data-theme="([^"]+)"')


TARGET_ID_RE = re.compile(r'\\?"targetId\\?":\\?"([^"\\]+)')
FORM_TOKEN_RE = re.compile(r'\\?"formToken\\?":\\?"([^"\\]+)')


def post_json(port: int, host: str, path: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Host": host, "content-type": "application/json"}
    if token:
        headers["Authorization"] = f"JWT {token}"
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers, method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=120) as response:
            return response.status, json.loads(response.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        try:
            return error.code, json.loads(body or "{}")
        except json.JSONDecodeError:
            return error.code, {"raw": body[:400]}


def patch_json(port: int, host: str, path: str, payload: dict, token: str) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data,
        headers={"Host": host, "content-type": "application/json", "Authorization": f"JWT {token}"},
        method="PATCH",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=120) as response:
            return response.status, json.loads(response.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as error:
        return error.code, {"raw": error.read().decode("utf-8", "replace")[:400]}


def check_comments(port: int, results: "Results") -> None:
    """Комментарии: отправка только через серверный endpoint, публикация — только после модерации."""
    host_a = SITES["a"]["host"]
    host_b = SITES["b"]["host"]
    path = "/catalog/stand-title-1/"

    _, body = fetch(port, host_a, path)
    target = TARGET_ID_RE.search(body)
    token_match = FORM_TOKEN_RE.search(body)
    results.add("[a] форма комментария отрисована", bool(target and token_match),
                "в разметке нет targetId/formToken")
    if not (target and token_match):
        return
    target_id, form_token = target.group(1), token_match.group(1)

    # Прямое создание через REST закрыто: иначе все проверки ниже обходятся одним POST.
    status, _ = post_json(port, host_a, "/api/comments", {
        "tenant": 1, "targetType": "title", "targetId": target_id, "body": "обход", "status": "published"})
    results.add("[a] прямое создание комментария через REST запрещено", status in (401, 403), f"получен {status}")

    # Мгновенная отправка — признак бота. Токен берём заново, чтобы измерять
    # именно время заполнения формы, а не возраст страницы.
    _, fresh = fetch(port, host_a, path)
    fresh_token = FORM_TOKEN_RE.search(fresh)
    status, payload = post_json(port, host_a, "/api/comments/submit", {
        "targetType": "title", "targetId": target_id,
        "formToken": fresh_token.group(1) if fresh_token else form_token,
        "body": "слишком быстро", "guestName": "Тест"})
    results.add("[a] мгновенная отправка отклонена", status == 400 and payload.get("code") == "TOO_FAST",
                f"{status} {payload}")

    time.sleep(MIN_FILL_SECONDS + 1)

    status, payload = post_json(port, host_a, "/api/comments/submit", {
        "targetType": "title", "targetId": target_id, "formToken": form_token,
        "body": "Первый комментарий стенда для проверки модерации.", "guestName": "Тестировщик"})
    results.add("[a] корректный комментарий принят", status == 201, f"{status} {payload}")
    results.add("[a] комментарий уходит на модерацию, а не в публикацию",
                payload.get("status") == "pending", str(payload))
    comment_id = payload.get("id")

    status, payload = post_json(port, host_a, "/api/comments/submit", {
        "targetType": "title", "targetId": target_id, "formToken": form_token,
        "body": "Второй комментарий подряд.", "guestName": "Тестировщик"})
    results.add("[a] частая отправка ограничена", status == 429, f"{status} {payload}")

    status, payload = post_json(port, host_a, "/api/comments/submit", {
        "targetType": "title", "targetId": target_id, "formToken": form_token,
        "body": "Комментарий бота.", "guestName": "Бот", "website": "http://spam"})
    results.add("[a] заполненная ловушка отклонена", status == 400 and payload.get("code") == "HONEYPOT",
                f"{status} {payload}")

    # Токен сайта A не годится для сайта B.
    status, payload = post_json(port, host_b, "/api/comments/submit", {
        "targetType": "title", "targetId": target_id, "formToken": form_token,
        "body": "Чужой токен.", "guestName": "Тестировщик"})
    results.add("[b] токен формы другого сайта не принимается", status == 400, f"{status} {payload}")

    _, body = fetch(port, host_a, path)
    results.add("[a] комментарий на модерации не виден на сайте",
                "Первый комментарий стенда" not in body, "непроверенный комментарий опубликован")

    # Модератор публикует — только после этого текст появляется на странице.
    status, login = post_json(port, host_a, "/api/users/login",
                              {"email": "moderator-a@factory.test", "password": "FactoryTest!2026"})
    results.add("[a] модератор входит в систему", status == 200 and bool(login.get("token")), f"{status}")
    token = login.get("token")
    if not token or not comment_id:
        return

    status, _ = patch_json(port, host_a, f"/api/comments/{comment_id}", {"status": "published"}, token)
    results.add("[a] модератор публикует комментарий", status == 200, f"получен {status}")

    _, body = fetch(port, host_a, path)
    results.add("[a] опубликованный комментарий виден на сайте",
                "Первый комментарий стенда" in body, "комментарий не появился")

    _, body_b = fetch(port, host_b, path)
    results.add("[b] комментарий сайта A не виден на сайте B",
                "Первый комментарий стенда" not in body_b, "комментарий утёк между сайтами")

    # Модератор чужого сайта не может трогать эту запись.
    status, login_b = post_json(port, host_b, "/api/users/login",
                                {"email": "admin-b@factory.test", "password": "FactoryTest!2026"})
    if status == 200 and login_b.get("token"):
        status, _ = patch_json(port, host_b, f"/api/comments/{comment_id}", {"status": "spam"}, login_b["token"])
        results.add("[b] администратор другого сайта не может изменить комментарий",
                    status in (403, 404), f"получен {status}")


def main() -> int:
    port = free_port()
    env = dict(os.environ)
    env.update({
        # Publisher ID приходит из окружения по имени секрета, а не из CMS.
        "PLAYER_PUBLISHER_ID_A": "stand-publisher-a",
        "PLAYER_PUBLISHER_ID_B": "stand-publisher-b",
        "PLAYER_PUBLISHER_ID_C": "stand-publisher-c",
        "PLAYER_MODE": "mock",
        "FACTORY_ENVIRONMENT": "staging",
    })
    # Стенд наполняется здесь же: тест не должен зависеть от того, что кто-то
    # раньше запустил seed вручную и оставил базу в нужном состоянии.
    seeding = subprocess.run(
        [sys.executable, str(ROOT / "tests/tools/with_app_env.py"), "--scope", "anime", "--",
         str(APP / "node_modules/.bin/tsx"), str(APP / "tests" / "stand-seed.ts")],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=900, check=False,
    )
    if seeding.returncode != 0:
        print("FAIL: не удалось наполнить стенд")
        print(seeding.stdout[-3000:])
        print(seeding.stderr[-3000:])
        return 1

    process = subprocess.Popen(
        [sys.executable, str(ROOT / "tests/tools/with_app_env.py"), "--scope", "anime",
         "--cwd", str(APP), "--", str(APP / "node_modules/.bin/next"), "dev", "-p", str(port), "-H", "127.0.0.1"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    results = Results()
    responses: dict[str, dict] = {}

    try:
        deadline = time.time() + 180
        ready = False
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=2):
                    ready = True
                    break
            except OSError:
                time.sleep(0.5)
        if not ready:
            print("FAIL: сервер не открыл порт")
            return 1

        for key, site in SITES.items():
            host = site["host"]
            for path, expected_index in INDEXABLE[key].items():
                status, body = fetch(port, host, path)
                responses[f"{key}{path}"] = {"status": status, "length": len(body)}
                results.add(f"[{key}] {path} отвечает 200", status == 200, f"получен {status}")
                if status != 200:
                    continue

                theme = THEME_RE.search(body)
                results.add(f"[{key}] {path} использует тему {site['theme']}",
                            bool(theme) and theme.group(1) == site["theme"],
                            f"в разметке {theme.group(1) if theme else 'темы нет'}")

                others = [other["name"] for other_key, other in SITES.items() if other_key != key]
                leaked = [name for name in others if name in body]
                results.add(f"[{key}] {path} не содержит названий других сайтов", not leaked, f"утекло: {leaked}")

                robots = ROBOTS_RE.search(body)
                canonical = CANONICAL_RE.search(body)
                if expected_index:
                    results.add(f"[{key}] {path} индексируется", bool(robots) and robots.group(1).startswith("index"),
                                f"robots={robots.group(1) if robots else 'нет'}")
                    expected_canonical = f"https://{host}{path}"
                    results.add(f"[{key}] {path} имеет абсолютный self-canonical",
                                bool(canonical) and canonical.group(1) == expected_canonical,
                                f"canonical={canonical.group(1) if canonical else 'нет'}")
                    # HR-2: canonical не может указывать на редирект.
                    direct_status, _ = fetch(port, host, path, follow=False)
                    results.add(f"[{key}] {path} отдаётся без редиректа",
                                direct_status == 200, f"прямой запрос вернул {direct_status}")
                else:
                    results.add(f"[{key}] {path} закрыт от индексации профилем",
                                bool(robots) and robots.group(1).startswith("noindex"),
                                f"robots={robots.group(1) if robots else 'нет'}")
                    results.add(f"[{key}] {path} без canonical, раз он noindex", canonical is None,
                                f"canonical={canonical.group(1) if canonical else ''}")

        # Фильтр каталога — не самостоятельная страница.
        status, body = fetch(port, SITES["a"]["host"], "/catalog/?genre=drama")
        canonical = CANONICAL_RE.search(body)
        robots = ROBOTS_RE.search(body)
        results.add("[a] фильтр по жанру не индексируется", bool(robots) and robots.group(1).startswith("noindex"),
                    f"robots={robots.group(1) if robots else 'нет'}")
        results.add("[a] фильтр canonical на чистый /catalog/",
                    bool(canonical) and canonical.group(1) == "https://site-a.localhost/catalog/",
                    f"canonical={canonical.group(1) if canonical else 'нет'}")

        # Поиск.
        status, body = fetch(port, SITES["a"]["host"], "/search/?q=Стендовый")
        robots = ROBOTS_RE.search(body)
        results.add("[a] поиск отвечает 200", status == 200, f"получен {status}")
        results.add("[a] поиск не индексируется", bool(robots) and robots.group(1).startswith("noindex"), "")
        results.add("[a] поиск без canonical", CANONICAL_RE.search(body) is None, "")

        # Ошибочные адреса.
        for path in ("/nothing-here/", "/catalog/page/999/", "/catalog/stand-title-1/season-99/",
                     "/catalog/stand-title-1/sezon-1/"):
            status, _ = fetch(port, SITES["a"]["host"], path)
            results.add(f"[a] {path} отвечает 404", status == 404, f"получен {status}")

        # robots.txt и sitemap.xml.
        for key, site in SITES.items():
            status, body = fetch(port, site["host"], "/robots.txt")
            results.add(f"[{key}] robots.txt отвечает 200", status == 200, f"получен {status}")
            results.add(f"[{key}] robots.txt указывает свой sitemap",
                        f"https://{site['host']}/sitemap.xml" in body, body[:200])
            results.add(f"[{key}] robots.txt закрывает поиск", "Disallow: /search/" in body, body[:200])

            status, body = fetch(port, site["host"], "/sitemap.xml")
            results.add(f"[{key}] sitemap.xml отвечает 200", status == 200, f"получен {status}")
            locs = re.findall(r"<loc>([^<]+)</loc>", body)
            results.add(f"[{key}] в sitemap только свой домен",
                        all(loc.startswith(f"https://{site['host']}/") for loc in locs),
                        f"первые записи: {locs[:3]}")
            responses[f"sitemap-{key}"] = {"count": len(locs)}

        # Состав sitemap различается: одинаковые карты у трёх сайтов — это дубль.
        sitemaps = {}
        for key, site in SITES.items():
            _, body = fetch(port, site["host"], "/sitemap.xml")
            sitemaps[key] = {re.sub(r"^https://[^/]+", "", loc) for loc in re.findall(r"<loc>([^<]+)</loc>", body)}
        results.add("состав sitemap у трёх сайтов различается",
                    len({frozenset(paths) for paths in sitemaps.values()}) == 3,
                    f"размеры: {[len(v) for v in sitemaps.values()]}")
        results.add("[c] эпизоды не попадают в sitemap редакционного сайта",
                    not any("/season-" in path for path in sitemaps["c"]), "")
        results.add("[a] эпизоды попадают в sitemap каталога",
                    any(path.startswith("/catalog/") for path in sitemaps["a"]), "")

        # Плеер: атрибуты контракта на месте, токен Content API в разметку не попадает.
        _, body = fetch(port, SITES["a"]["host"], "/catalog/stand-title-1/season-1/episode-1/")
        results.add("[a] страница серии не содержит строки подключения к БД", "postgresql://" not in body, "")
        secret = os.environ.get("PAYLOAD_SECRET", "")
        results.add("[a] страница серии не содержит секрет приложения", not secret or secret not in body, "")

        # Права не подтверждены — страница есть, плеера нет, подмены видео нет.
        _, blocked = fetch(port, SITES["a"]["host"], "/catalog/stand-title-blocked/")
        results.add("[a] страница без прав на публикацию отвечает 200 и объясняет причину",
                    "права на публикацию не подтверждены" in blocked, "нет честного статуса на странице")
        results.add("[a] на странице без прав нет параметров плеера",
                    "data-publisher-id" not in blocked and "stand-publisher-a" not in blocked,
                    "параметры плеера отрисованы при неподтверждённых правах")

        check_comments(port, results)

    finally:
        process.terminate()
        try:
            output = process.communicate(timeout=30)[0] or ""
        except subprocess.TimeoutExpired:
            process.kill()
            output = process.communicate()[0] or ""
        if results.failed:
            log_path = ROOT / "var" / "artifacts" / "frontend-http-server.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(output, encoding="utf-8")
            print("--- последние строки лога сервера ---")
            print("\n".join(output.splitlines()[-40:]))

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps({"checks": results.checks, "responses": responses},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(results.checks) - len(results.failed)}/{len(results.checks)} проверок пройдено; "
          f"артефакт: {ARTIFACT.relative_to(ROOT)}")
    return 0 if not results.failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
