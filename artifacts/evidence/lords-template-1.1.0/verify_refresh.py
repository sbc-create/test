#!/usr/bin/env python3
"""Автоматическое обновление содержимого нового сайта — весь путь целиком.

новый снимок → штатная доставка → загрузка приложением → изменение страниц.

Проверяется не файл на диске, а ВЕРСИЯ, КОТОРУЮ ЗАГРУЗИЛО ПРИЛОЖЕНИЕ
(`/healthz.catalog_revision`), и фактическое содержимое страниц. Файл,
лежащий рядом, обновления сайта не доказывает — именно на этом и строится
разница между «доставлено» и «показано».
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

S = Path("/tmp/claude-1001/-home-claude/9e5d5d7c-1b72-454b-9239-dbb120e73b48/scratchpad")
W = Path("/home/claude/wt-lords-template-consolidation-01")
N, D = S / "new-lords-90", S / "lords-90-data"
ОБЩИЙ = S / "producer-shared"           # изолированный «общий каталог» производителя
РЕЕСТР = S / "registry-test.json"
БАЗА = "http://127.0.0.1:9190"
МОДЕРАТОР = "test-moderator-key-9190"

итог, провалы = [], []


def проверка(имя, ок, подр=""):
    итог.append((имя, "PASS" if ок else "FAIL", подр))
    if not ок:
        провалы.append(f"{имя}: {подр}")


def get(путь, куки=""):
    """Тело ответа. Код, отличный от 200, возвращается телом, а не исключением:
    приёмка обязана дойти до конца и показать всю таблицу."""
    зпр = urllib.request.Request(БАЗА + urllib.parse.quote(путь, safe="/?=&#"),
                                 headers={"Cookie": куки} if куки else {})
    try:
        with urllib.request.urlopen(зпр, timeout=30) as о:
            return о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ош:
        return f"<!--HTTP {ош.code}-->" + ош.read().decode("utf-8", "replace")


def здоровье():
    return json.loads(get("/healthz"))


def стоп():
    for pid in subprocess.run(["pgrep", "-f", "lords-frontend.py --port 9190"],
                              capture_output=True, text=True).stdout.split():
        try:
            os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(2)


def старт(ждать=True):
    subprocess.Popen([sys.executable, str(N / "run.py"), "--port", "9190",
                      "--data-dir", str(D)], cwd=str(N),
                     env=dict(os.environ,
                              LORDS_90_COMMUNITY_MODERATOR_KEY=МОДЕРАТОР),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not ждать:
        return True
    for _ in range(60):
        try:
            get("/healthz")
            return True
        except Exception:
            time.sleep(0.5)
    return False


def доставить(**кв):
    """Штатная доставка через модуль фабрики, на изолированном реестре."""
    среда = dict(os.environ, SITE_CELLS_REGISTRY=str(РЕЕСТР))
    код = (
        "import json,sys;"
        f"sys.path.insert(0,'{W}');"
        "from factory.cell import delivery;"
        "print(json.dumps(delivery.доставить('lords-90', общий=__import__('pathlib')"
        f".Path('{ОБЩИЙ}')).as_dict(), ensure_ascii=False))"
    )
    r = subprocess.run([sys.executable, "-c", код], capture_output=True, text=True,
                       env=среда, cwd=str(W))
    if r.returncode != 0:
        return {"error": r.stderr.strip()[-300:]}
    return json.loads(r.stdout)


def засеять(куда: Path, поколение: str, добавка=()):
    subprocess.run([sys.executable, str(S / "seed.py"), str(куда), поколение,
                    json.dumps(list(добавка), ensure_ascii=False)],
                   check=True, capture_output=True)


def слаги(html):
    import re
    return re.findall(r'href="/title/([a-z0-9-]+)/"', html)


# ---------------------------------------------------------------- подготовка
НОВИНКА = [{
    "slug": "kino-svezhij-777", "title": "Свежий фильм доставки", "kind": "Фильм",
    "type": "movie", "genres": ["боевик"], "published_at": "2026-09-26T10:00:00Z",
    "rating": 9.2,
}]

ОБЩИЙ.mkdir(parents=True, exist_ok=True)
засеять(D, "rev-1")                       # исходное содержимое ячейки
for f in D.glob("*community*"):
    f.unlink()
стоп()
assert старт(), "экземпляр не поднялся"

# Голос и комментарий ДО обновления: они обязаны пережить весь путь.
import http.cookiejar
import urllib.error


class НеСледовать(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


jar = http.cookiejar.CookieJar()
клиент = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),
                                     НеСледовать())
страница = клиент.open(БАЗА + "/title/kino-000/", timeout=30).read().decode()
поля = dict(__import__("re").findall(
    r'name="(subject|slug|back|csrf)" value="([^"]*)"',
    страница.split('data-community-form="vote"', 1)[1]))
данные = urllib.parse.urlencode(dict(поля, value="9")).encode()
try:
    клиент.open(urllib.request.Request(
        БАЗА + "/community/vote", data=данные,
        headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=30)
except urllib.error.HTTPError:
    pass
голос_до = 'data-my-vote="9"' in клиент.open(
    БАЗА + "/title/kino-000/", timeout=30).read().decode()
проверка("голос поставлен до обновления", голос_до)

до = здоровье()
проверка("исходная ревизия загружена приложением", до["catalog_revision"] == "rev-1",
         до["catalog_revision"])

# --------------------------------------------- 1. новый снимок у производителя
засеять(ОБЩИЙ, "rev-2", НОВИНКА)
проверка("у производителя новый снимок",
         json.loads((ОБЩИЙ / "lords-90-catalog.json").read_text())["revision"] == "rev-2")

# --------------------------------------------------------- 2. штатная доставка
отчёт = доставить()
проверка("доставка прошла", отчёт.get("ok") is True, json.dumps(отчёт, ensure_ascii=False)[:200])
проверка("снимок и подробности доставлены",
         {"lords-90-catalog.json", "lords-90-details.json"} <= set(отчёт.get("delivered", [])),
         str(отчёт.get("delivered")))
проверка("хранилище сообщества доставке не подлежит",
         "lords-90-community.json" in отчёт.get("site_owned", []),
         str(отчёт.get("site_owned")))
проверка("файл в ячейке обновился",
         json.loads((D / "lords-90-catalog.json").read_text())["revision"] == "rev-2")

# ---------------------------- 3. файл на диске сайт ещё НЕ обновил (ключевое)
всё_ещё = здоровье()
проверка("до перезапуска приложение держит прежнюю ревизию",
         всё_ещё["catalog_revision"] == "rev-1", всё_ещё["catalog_revision"])
проверка("до перезапуска новинки на сайте нет",
         "kino-svezhij-777" not in get("/"))

# --------------------------------- 4. предусмотренный механизм подхвата
режим = json.loads(РЕЕСТР.read_text())["cells"][0]["runtime"]["reload"]
проверка("реестр объявляет режим подхвата", режим in ("restart", "mtime"), режим)
if режим == "restart":
    стоп()
    assert старт(), "витрина не поднялась после перезапуска"

после = здоровье()
проверка("приложение загрузило НОВУЮ ревизию", после["catalog_revision"] == "rev-2",
         после["catalog_revision"])
проверка("сумма снимка у приложения изменилась",
         после["catalog_digest"] != до["catalog_digest"])

# ------------------------------------------- 5. изменились сами страницы
главная = get("/")
проверка("новинка на главной", "kino-svezhij-777" in главная)
раздел = get("/movies/")
проверка("новинка в разделе фильмов", "kino-svezhij-777" in слаги(раздел))
новое = get("/new/")
проверка("новинка в «Новом»", "kino-svezhij-777" in слаги(новое))
поиск = get("/search/?q=Свежий фильм доставки")
проверка("новинка находится поиском", "kino-svezhij-777" in слаги(поиск))
карточка = get("/title/kino-svezhij-777/")
проверка("страница произведения открывается",
         "HTTP 404" not in карточка and "Свежий фильм доставки" in карточка,
         карточка[:40])
проверка("на странице новинки есть плеер", "data-player" in карточка)

# ------------------------------------------------ 6. пользовательские записи
проверка("голос пережил доставку и перезапуск",
         'data-my-vote="9"' in клиент.open(БАЗА + "/title/kino-000/",
                                           timeout=30).read().decode())

# ------------------------------------------------------- 7. повторная доставка
повтор = доставить()
проверка("повторная доставка ничего не переписывает",
         not повтор.get("delivered") and
         {"lords-90-catalog.json", "lords-90-details.json"} <= set(повтор.get("unchanged", [])),
         f"delivered={повтор.get('delivered')} unchanged={повтор.get('unchanged')}")

# --------------------------------------------------------- 8. битый снимок
целый = (D / "lords-90-catalog.json").read_bytes()
(ОБЩИЙ / "lords-90-catalog.json").write_bytes(b'{"revision": "rev-3", "items": [')
битый = доставить()
проверка("битый источник отвергнут", "lords-90-catalog.json" in битый.get("rejected", []),
         str(битый.get("rejected")))
проверка("доставка не считается состоявшейся", битый.get("ok") is False)
проверка("в ячейке остался прежний рабочий снимок",
         (D / "lords-90-catalog.json").read_bytes() == целый)
проверка("сайт продолжает работать на прежней версии",
         здоровье()["catalog_revision"] == "rev-2")
проверка("страницы целы после отвергнутой доставки",
         "kino-svezhij-777" in get("/"))

# --------------------------------- 9. запуск с битым снимком отказывает внятно
#
# Проверяется НАСТОЯЩИЙ файл ячейки, а не переменная окружения: `run.py`
# намеренно не слушает окружение и выставляет пути сам из config/site.json —
# иначе одна забытая переменная увела бы витрину на каталог соседа.
(ОБЩИЙ / "lords-90-catalog.json").write_bytes(целый)   # вернуть производителю целое
рабочий = D / "lords-90-catalog.json"
сохранён = рабочий.read_bytes()
try:
    рабочий.write_bytes(b'{"revision": "rev-x", "items": [')
    r = subprocess.run([sys.executable, str(N / "run.py"), "--check",
                        "--data-dir", str(D)], cwd=str(N), capture_output=True, text=True)
    проверка("пускатель отказывает на битом снимке словами, а не падением",
             r.returncode != 0 and "не читается как JSON" in (r.stderr + r.stdout),
             f"код {r.returncode}: {(r.stderr or r.stdout)[-120:]}")
    # И тот же файл, но не снимок вовсе: JSON читается, items нет.
    рабочий.write_bytes(b'{"revision": "rev-x"}')
    r2 = subprocess.run([sys.executable, str(N / "run.py"), "--check",
                         "--data-dir", str(D)], cwd=str(N), capture_output=True, text=True)
    проверка("пускатель отличает «не снимок» от «нет файла»",
             r2.returncode != 0 and "нет списка items" in (r2.stderr + r2.stdout),
             f"код {r2.returncode}: {(r2.stderr or r2.stdout)[-120:]}")
finally:
    рабочий.write_bytes(сохранён)

# Витрина поднимается на восстановленном снимке: проверка ничего не испортила.
стоп()
assert старт(), "витрина не поднялась на восстановленном снимке"
проверка("после проверки битого снимка витрина работает на rev-2",
         здоровье()["catalog_revision"] == "rev-2")

print(f"{'проверка':<52} итог")
print("-" * 70)
for имя, статус, подр in итог:
    print(f"{имя:<52} {статус}" + (f"  {подр}" if статус == "FAIL" and подр else ""))
print("-" * 70)
print(f"всего {len(итог)}, провалов {len(провалы)}")
sys.exit(1 if провалы else 0)
