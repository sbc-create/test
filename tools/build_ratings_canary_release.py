#!/usr/bin/env python3
"""Сборка неизменяемого релиза витрины animedia.icu с блоком оценок.

Основа — тот релиз, который animedia.icu исполняет прямо сейчас, а не
файл из нашей ветки. Причина простая: витрину ведёт другой терминал, и
собрать её код «как у нас в репозитории» значило бы откатить его работу.
Мы берём его байты, добавляем свои файлы и правим ровно три места.

Правки:

1. импорт адаптера и обработчика API;
2. ``деталь()`` — единственная точка, через которую витрина получает
   данные произведения;
3. страница произведения — одна фирменная оценка вместо ряда логотипов,
   плюс шкала 1–10.

Плюс маршрут ``/api/unified-ratings/*`` и отдача статики виджета.

Сборка детерминирована и проверяема: скрипт печатает SHA-256 каждого
файла и падает, если получившийся рантайм не разбирается интерпретатором.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FRONT = Path("/srv/lords/.frontend")
RELEASES = FRONT / "releases"
SITE = "animedia-01"
RUNTIME = "animedia-frontend.py"

ADAPTER_SRC = Path(__file__).resolve().parents[1] / "factory" / "animedia"
STATIC_FILES = ("unified_rating_widget.css", "unified_rating_widget.js")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# правки рантайма
# --------------------------------------------------------------------------

IMPORT_ANCHOR = "def оценки_по_источникам(деталь: dict) -> list:"
IMPORT_BLOCK = '''# --- unified ratings canary -------------------------------------------------
# Блок оценок общего модуля. Импорт защищён: витрина обязана подниматься
# и тогда, когда модуля оценок рядом нет.
try:
    import sys as _ur_sys
    _UR_CORE = "/home/claude/wt-unified-ratings-1-10-sources-01"
    if _UR_CORE not in _ur_sys.path:
        _ur_sys.path.insert(0, _UR_CORE)
    from ur_canary import unified_ratings_adapter as _ur_adapter
    from ur_canary import unified_ratings_http as _ur_http
except Exception:  # noqa: BLE001
    _ur_adapter = None
    _ur_http = None


import threading as _ur_threading

#: Признак владельца берётся из cookie текущего запроса. Витрина
#: многопоточная, поэтому значение живёт в потоке, а не в модуле: иначе
#: один владелец включал бы шкалу голосования всем остальным.
_ur_состояние = _ur_threading.local()


def _ur_владелец(handler) -> bool:
    raw = handler.headers.get("Cookie") or ""
    for часть in raw.split(";"):
        if "=" in часть:
            ключ, значение = часть.split("=", 1)
            if ключ.strip() == "ur_owner" and значение.strip():
                return True
    return False


def _ur_блок(деталь: dict) -> str:
    """Одна фирменная оценка и шкала 1–10. Пусто — если показывать нечего."""
    if _ur_adapter is None:
        return ""
    ctx = _ur_adapter.widget_context(деталь)
    if not ctx:
        return ""
    # Шкалу видит владелец канарейки; обычный посетитель видит оценки.
    ctx = dict(ctx)
    ctx["write_enabled"] = bool(
        ctx.get("write_enabled") or getattr(_ur_состояние, "владелец", False)
    )
    import html as _h

    composite = ctx.get("composite")
    community = ctx.get("community")
    внешние = ctx.get("external") or []
    части = ['<section class="ur-block" data-unified-ratings '
             f'data-space="{_h.escape(ctx["space"])}" '
             f'data-subject="{_h.escape(ctx["subject_id"])}" '
             f'data-api="{_h.escape(ctx["api_base"])}" '
             f'data-write-enabled="{"1" if ctx["write_enabled"] else "0"}" '
             'aria-labelledby="ur-heading">'
             '<h2 id="ur-heading" class="ur-heading">Оценки</h2>']
    if composite:
        части.append(
            '<div class="ur-composite">'
            f'<span class="ur-composite-label">{_h.escape(composite["label"])}</span>'
            f'<strong class="ur-composite-value">{_h.escape(str(composite["value"]))}</strong>'
            f'<span class="ur-composite-basis">На основе '
            f'{int(composite["source_count"])} источников</span>'
            '<details class="ur-composite-detail"><summary>Какие источники учтены</summary>'
            '<ul class="ur-composite-sources">'
            + "".join(f"<li>{_h.escape(str(s))}</li>" for s in composite.get("sources") or [])
            + "</ul></details></div>")
    elif внешние:
        один = внешние[0]
        части.append(
            '<div class="ur-composite">'
            f'<span class="ur-composite-label">{_h.escape(str(один.get("label") or ""))}</span>'
            f'<strong class="ur-composite-value">{_h.escape(str(один.get("score")))}</strong>'
            '<span class="ur-composite-basis">Один источник — это не сводная оценка</span>'
            "</div>")
    if ctx.get("editorial"):
        e = ctx["editorial"]
        части.append(f'<p class="ur-editorial"><span>{_h.escape(e["label"])}</span>'
                     f'<strong>{int(e["value"])}/10</strong></p>')
    части.append('<div class="ur-community">')
    if community:
        части.append('<p class="ur-community-summary">'
                     f'<span>{_h.escape(community["label"])}</span>'
                     '<strong data-role="community-average">'
                     f'{_h.escape(str(community["average"]))}</strong>'
                     '<span data-role="community-votes">'
                     f'{int(community["votes"])} голосов</span></p>')
    else:
        части.append('<p class="ur-community-summary"><span>Оценка зрителей</span> '
                     '<span data-role="community-average">Пока нет оценок</span>'
                     '<span data-role="community-votes"></span></p>')
    if ctx["write_enabled"]:
        кнопки = "".join(
            f'<button type="button" class="ur-star" role="radio" aria-checked="false" '
            f'data-score="{n}" aria-label="Поставить оценку {n} из 10">{n}</button>'
            for n in range(1, 11))
        части.append(
            '<fieldset class="ur-vote" data-role="vote">'
            '<legend class="ur-vote-legend">Ваша оценка</legend>'
            f'<div class="ur-scale" role="radiogroup" aria-label="Оценка от 1 до 10">{кнопки}</div>'
            '<p class="ur-my" data-role="my-score" aria-live="polite">Вы ещё не оценили</p>'
            '<button type="button" class="ur-retract" data-role="retract" hidden>'
            'Убрать мою оценку</button>'
            '<p class="ur-status" data-role="status" role="status" aria-live="polite"></p>'
            "</fieldset>")
    части.append("</div></section>")
    части.append('<link rel="stylesheet" href="/static/unified-ratings/unified_rating_widget.css">')
    части.append('<script src="/static/unified-ratings/unified_rating_widget.js" defer></script>')
    return "".join(части)


'''

DETAIL_OLD = """    def деталь(self, slug: str) -> dict:
        return self.п.get(slug)"""
DETAIL_NEW = """    def деталь(self, slug: str) -> dict:
        # Единственная точка, через которую витрина получает данные
        # произведения, — поэтому и подключение здесь одно.
        д = self.п.get(slug)
        if _ur_adapter is not None and isinstance(д, dict):
            try:
                return _ur_adapter.merge_into_detail(д)
            except Exception:  # noqa: BLE001
                return д
        return д"""

TRIPLE = chr(34) * 3

SCORE_OLD = (
    "    def _рейтинги_колонка_b07(self, деталь: dict) -> str:\n"
    f"        {TRIPLE}Independent source ratings: label always visible; "
    f"missing \u2260 0.{TRIPLE}\n"
    '        by_key = {о["ключ"]: о for о in оценки_по_источникам(деталь)}'
)

SCORE_NEW = (
    "    def _рейтинги_колонка_b07(self, деталь: dict) -> str:\n"
    f"        {TRIPLE}Одна фирменная оценка вместо ряда чужих логотипов.\n"
    "\n"
    "        Ряд подписей Shikimori / Кинопоиск / IMDb остаётся запасным\n"
    "        вариантом: он показывается, когда общий модуль ничего не дал.\n"
    f"        {TRIPLE}\n"
    "        _ur_html = _ur_блок(деталь)\n"
    "        if _ur_html:\n"
    "            return (\n"
    "                '<aside class=\"ztitle__rail\" data-b07=\"ratings\">'\n"
    "                + _ur_html + '</aside>'\n"
    "            )\n"
    '        by_key = {о["ключ"]: о for о in оценки_по_источникам(деталь)}'
)


CARD_OLD = (
    "    if сколько <= 0:\n"
    "        return []\n"
    "    готово = []\n"
    '    for о in оценки_по_источникам(деталь)[:сколько]:'
)

CARD_NEW = (
    "    if сколько <= 0:\n"
    "        return []\n"
    "    # Карточка показывает то же значение, что и страница произведения:\n"
    "    # разные числа под одним названием читаются как ошибка данных.\n"
    "    _ur_c = (деталь or {}).get('unified_composite') if isinstance(деталь, dict) else None\n"
    "    if _ur_c and _ur_c.get('value'):\n"
    "        return [{\n"
    "            'ключ': 'unified', 'подпись': _ur_c.get('label') or 'Сводная оценка',\n"
    "            'значение': str(_ur_c['value']), 'шкала': 10.0,\n"
    "            'голоса': None, 'пользовательская': False,\n"
    "            'на_десять': str(_ur_c['value']),\n"
    "            'исходное': str(_ur_c['value']), 'исходная_шкала': 10.0,\n"
    "        }]\n"
    "    готово = []\n"
    '    for о in оценки_по_источникам(деталь)[:сколько]:'
)


def patch_runtime(source: str) -> tuple[str, list[str]]:
    applied = []
    if IMPORT_ANCHOR not in source:
        raise SystemExit("не найден якорь импорта — рантайм изменился, сборка остановлена")
    source = source.replace(
        IMPORT_ANCHOR, IMPORT_BLOCK + ROUTE_HELPER + IMPORT_ANCHOR, 1
    )
    applied.append("import+widget")

    if DETAIL_OLD not in source:
        raise SystemExit("не найден метод деталь() — сборка остановлена")
    source = source.replace(DETAIL_OLD, DETAIL_NEW, 1)
    applied.append("деталь()")

    if SCORE_OLD not in source:
        raise SystemExit("не найдена отрисовка оценок — сборка остановлена")
    source = source.replace(SCORE_OLD, SCORE_NEW, 1)
    applied.append("страница произведения")

    if CARD_OLD not in source:
        raise SystemExit("не найдены бейджи карточки — сборка остановлена")
    source = source.replace(CARD_OLD, CARD_NEW, 1)
    applied.append("бейдж карточки")

    if DO_GET_ANCHOR not in source:
        raise SystemExit("не найден do_GET — сборка остановлена")
    source = source.replace(DO_GET_ANCHOR, DO_GET_PATCHED, 1)
    applied.append("маршруты API и статики")
    return source, applied


DO_GET_ANCHOR = """    def do_GET(self):
        д = self.данные
        разбор = urlparse(self.path)
        путь = unquote(разбор.path)
        зпр = parse_qs(разбор.query)
"""

DO_GET_PATCHED = """    def do_PUT(self):
        if not _ur_маршрут(self, "PUT"):
            self.send_response(405); self.end_headers()

    def do_DELETE(self):
        if not _ur_маршрут(self, "DELETE"):
            self.send_response(405); self.end_headers()

    def do_GET(self):
        # Маршруты блока оценок разбираются до витринных: свой префикс,
        # свой ответ, никакого пересечения с адресами страниц.
        if _ur_маршрут(self, "GET"):
            return
        _ur_состояние.владелец = _ur_владелец(self)
        д = self.данные
        разбор = urlparse(self.path)
        путь = unquote(разбор.path)
        зпр = parse_qs(разбор.query)
"""

ROUTE_HELPER = '''def _ur_маршрут(handler, метод: str) -> bool:
    """API оценок и статика виджета. True — запрос обслужен здесь."""
    if _ur_http is None:
        return False
    разбор = urlparse(handler.path)
    путь = разбор.path
    if путь.startswith("/static/unified-ratings/"):
        имя = путь.rsplit("/", 1)[-1]
        if имя not in ("unified_rating_widget.css", "unified_rating_widget.js"):
            handler.send_response(404); handler.end_headers(); return True
        файл = Path(__file__).resolve().parent / "static" / имя
        if not файл.is_file():
            handler.send_response(404); handler.end_headers(); return True
        тело = файл.read_bytes()
        тип = "text/css" if имя.endswith(".css") else "application/javascript"
        handler.send_response(200)
        handler.send_header("Content-Type", f"{тип}; charset=utf-8")
        handler.send_header("Content-Length", str(len(тело)))
        handler.send_header("Cache-Control", "public, max-age=300")
        handler.send_header("X-Robots-Tag", "noindex, nofollow")
        handler.end_headers(); handler.wfile.write(тело); return True
    if not _ur_http.handles(путь):
        return False
    код, ответ = _ur_http.dispatch(handler, метод, путь, parse_qs(разбор.query))
    полезное = json.dumps(ответ, ensure_ascii=False).encode("utf-8")
    handler.send_response(код)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(полезное)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Robots-Tag", "noindex, nofollow")
    handler.end_headers(); handler.wfile.write(полезное); return True


'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-release", default="")
    parser.add_argument("--label", default="animedia-ratings-canary")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    current = (FRONT / "sites" / SITE / "current").resolve()
    base = Path(args.base_release) if args.base_release else current
    if not (base / RUNTIME).is_file():
        raise SystemExit(f"в базовом релизе нет {RUNTIME}: {base}")

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True,
    ).stdout.strip()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    build_id = f"{stamp}-{commit[:7]}-{args.label}"
    target = RELEASES / build_id

    print(f"базовый релиз : {base.name}")
    print(f"новый релиз   : {build_id}")
    if args.dry_run:
        print("dry-run: каталог не создаётся")

    source = (base / RUNTIME).read_text(encoding="utf-8")
    patched, applied = patch_runtime(source)
    ast.parse(patched)  # рантайм обязан разбираться до того, как станет релизом
    print(f"правки        : {', '.join(applied)}")

    if args.dry_run:
        print("SHA256 нового рантайма:", hashlib.sha256(patched.encode()).hexdigest())
        return 0

    if target.exists():
        raise SystemExit(f"релиз уже существует: {target}")
    shutil.copytree(base, target)
    (target / RUNTIME).write_text(patched, encoding="utf-8")

    # Пакет называется своим именем, а не factory: каталог релиза стоит
    # первым в sys.path, и собственный factory/ перекрыл бы настоящий
    # пакет ядра — factory.unified_ratings переставал существовать.
    pkg = target / "ur_canary"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    for name in ("unified_ratings_adapter.py", "unified_ratings_http.py"):
        shutil.copy2(ADAPTER_SRC / name, pkg / name)
    static = target / "static"
    static.mkdir(exist_ok=True)
    for name in STATIC_FILES:
        shutil.copy2(ADAPTER_SRC / "frontend" / name, static / name)

    files = {}
    for path in sorted(target.rglob("*")):
        if path.is_file():
            files[str(path.relative_to(target))] = {
                "sha256": sha256(path), "bytes": path.stat().st_size
            }
    manifest = {
        "schema_version": 1,
        "tenant": "animedia",
        "site": SITE,
        "build_id": build_id,
        "stage": "UNIFIED-RATINGS-CANARY-01",
        "branch": "claude/animedia-ratings-canary-01",
        "source_commit": commit,
        "base_release": base.name,
        "base_runtime_sha256": sha256(base / RUNTIME),
        "artifact": RUNTIME,
        "artifact_sha256": sha256(target / RUNTIME),
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "patches_applied": applied,
        "rollback_target": str(current),
        "files": files,
        "public_write_enabled": False,
        "indexability_changed": False,
    }
    (target / "RELEASE.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"artifact sha  : {manifest['artifact_sha256']}")
    print(f"rollback      : {manifest['rollback_target']}")
    print(json.dumps({"build_id": build_id, "target": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
