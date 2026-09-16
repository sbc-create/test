#!/usr/bin/env python3
"""Сборка архитектурных черновиков reference pack для Zona и Animedia.

Пакет собирается генератором, а не двадцатью файлами вручную. Причина та же,
по которой карты страниц выводятся из кода: структура у пакетов общая,
различия — в нескольких полях, и две руками написанные копии разойдутся на
первой же правке.

Главное свойство этих пакетов — **честность о недоступности**. Ни один
референс сейчас не открывается: guard профиля отклоняет оба хоста до сети.
Поэтому:

* `SCREENSHOT_INDEX.md` содержит `BLOCKED`, а не `PASS`;
* `VISUAL_TOKENS` пуст — токены снимают с макета, а макета нет;
* фикстуры описывают **нашу** структуру, а не чужую страницу;
* нигде нет ни логотипов, ни постеров, ни строк чужого кода.

Пакеты остаются архитектурным черновиком до завершения Lords и Yummy и
не объявляют визуального соответствия.

Запуск:
    .venv/bin/python scripts/build_reference_packs.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PACKS_DIR = ROOT / "docs" / "reference-packs"
SOURCE_PACKS = ROOT / "config" / "reference-packs"

BLOCKED_NOTE = (
    "Доступ к референсу закрыт: профиль разрешений отклоняет хост до сети "
    "(`хост не входит в переданные контракты`). Попытка сделана один раз, "
    "guard не обходился. Блокер записан как REF-EGRESS-01."
)

REFERENCES = {
    "zona-w140": {
        "title": "Zona (w140.zona.plus)",
        "url": "https://w140.zona.plus/",
        "template_id": "zona-video-portal",
        "provenance": "задание владельца потоку TEMPLATES от 04.09.2026",
        "observations": 0,
    },
    "amd-online": {
        "title": "Animedia (amd.online)",
        "url": "https://amd.online/",
        "template_id": "animedia-anime-portal",
        "provenance": "Change Request v2.0 от 22.08.2026, раздел 3",
        "observations": 8,
    },
}

#: Блоки черновика. Одинаковы для обоих пакетов: это описание НАШЕЙ структуры,
#: которую мы бы построили, а не структуры чужого сайта.
DRAFT_BLOCKS = [
    ("header", "Шапка и основная навигация", ["normal", "sticky"]),
    ("search", "Поиск по каталогу", ["idle", "suggesting", "empty"]),
    ("shelves", "Полки главной", ["normal", "empty"]),
    ("catalog-grid", "Сетка каталога", ["normal", "empty", "degraded"]),
    ("pager", "Пагинация", ["normal", "first", "last"]),
    ("title-hero", "Заголовок и факты произведения", ["normal", "no_poster", "no_rating"]),
    ("player-shell", "Посадочное место плеера", ["idle", "unavailable"]),
    ("footer", "Подвал", ["normal"]),
]

DRAFT_ROUTES = [
    ("home", "homepage", "/"),
    ("catalog", "catalog", "/catalog"),
    ("title", "title", "/title/{slug}"),
    ("search", "search", "/search"),
    ("not-found", "error", "'*'"),
]


def _readme(key: str, meta: dict) -> str:
    return f"""# {meta['title']} — reference pack (архитектурный черновик)

**Статус: черновик. Не выложен, визуальное соответствие не заявлено.**

## Что это

Описание структуры, которую мы построили бы для витрины этого класса. Это
**не** копия референса и не может ею быть: референс недоступен.

{BLOCKED_NOTE}

## Чего здесь нет и не будет

Ни логотипов, ни постеров, ни изображений, ни текстов, ни строк кода
референса. Из чужого интерфейса переносима только информационная архитектура —
какие разделы существуют и в каком порядке, — и она описана своими словами.

Политика источника: `inventory/reference-sources.yaml`.

## Состав пакета

| Файл | Назначение |
|---|---|
| `TemplateManifest.yaml` | контракт шаблона: версии, маршруты, блоки, бюджеты |
| `blocks.yaml` | блоки с разделами `mustNot` и `protectedBy` |
| `ROUTES.yaml` | маршруты и их порядок блоков |
| `PAGE_MAP.md` | страницы и их состояния |
| `BLOCK_MAP.md` | какой блок на какой странице |
| `VISUAL_TOKENS.yaml` | токены оформления — **пусты, см. ниже** |
| `VISUAL_DECISIONS.md` | принятые и отвергнутые решения |
| `SCREENSHOT_INDEX.md` | снимки — **BLOCKED** |
| `STATES.md` | состояния страниц |
| `PLAYER_SHELL.md` | посадочное место плеера |
| `RATINGS.md` | договор об оценках |
| `AD_SLOTS.md` | договор о рекламных местах |
| `ACCEPTANCE.md` | критерии приёмки |
| `PREVIEW.md` | как посмотреть локально |
| `TEST_INVENTORY.md` | какие проверки существуют |
| `CHANGELOG.md` | история пакета |
| `fixtures/` | детерминированные фикстуры состояний |

## Почему `VISUAL_TOKENS.yaml` пуст

Токены — это измеренные величины: ширина колонки, кегль, скругление,
пропорция карточки. Измерить их не на чем. Записать сюда правдоподобные числа
значило бы выдать догадку за замер, и весь пакет после этого перестал бы быть
свидетельством. Пустой файл честнее заполненного.

## Что снимет блокер

Разрешение хоста в профиле. После этого `measurement_plan` из
`config/reference-packs/reference-pack.{key}.json` запускается одной командой и
заполняет наблюдения статусом `measured_by_factory`.
"""


def _manifest(key: str, meta: dict) -> str:
    routes = "\n".join(
        f"    - routeId: {rid}\n"
        f"      pageType: {ptype}\n"
        f"      path: {path}\n"
        f"      blockOrder: [header, search, shelves, footer]"
        for rid, ptype, path in DRAFT_ROUTES
    )
    return f"""# Манифест шаблона {meta['title']} — архитектурный черновик.
#
# Черновик означает ровно одно: ни одна величина здесь не измерена на
# референсе, потому что референс недоступен. Структура — наша.

schemaVersion: 1
templateId: {meta['template_id']}
templateVersion: 0.0.1-draft
family: reference-draft

status: draft
productionEnabled: false
indexingEnabled: false

reference:
  url: {meta['url']}
  provenance: {meta['provenance']}
  access: blocked_policy
  blocker: REF-EGRESS-01
  observations: {meta['observations']}

compatibility:
  status: pending
  onIncompatibleContract: fail_build
  apiVersionRange: pending
  sdkVersionRange: pending
  seoContractVersionRange: pending
  allowLatest: false

previewCapabilities:
  requiresDatabase: false
  requiresSecrets: false
  states: [normal, empty, degraded, not_found]

performanceBudgets:
  lcpMs: 2500
  cls: 0.1
  inpMs: 200

featureFlags:
  adSlots:
    default: disabled
    onDisabled: no_dom
    onEnabled: reserve_geometry
    networkIntegration: forbidden

routes:
{routes}

blocks:
  source: blocks.yaml
"""


def _blocks(key: str) -> str:
    rows = []
    for block_id, responsibility, states in DRAFT_BLOCKS:
        rows.append(
            f"""  - blockId: {block_id}
    responsibility: "{responsibility}"
    data: описывается при подключении контракта
    states: [{', '.join(states)}]
    mustNot:
      - Показывать данные, которых нет в источнике.
      - Оставлять заголовок над пустотой.
      - Содержать ассеты или тексты референса.
    protectedBy:
      - tests/unit/test_reference_packs.py"""
        )
    return f"""# Блоки черновика {key}.
#
# У каждого блока названы `mustNot` и `protectedBy`: блок без проверки — это
# намерение, а не поведение.

schemaVersion: 1
templateId: {REFERENCES[key]['template_id']}

blocks:
{chr(10).join(rows)}
"""


def _routes(key: str) -> str:
    rows = "\n".join(
        f"  - routeId: {rid}\n"
        f"    pageType: {ptype}\n"
        f"    path: {path}\n"
        f"    blockOrder: [header, search, shelves, footer]"
        for rid, ptype, path in DRAFT_ROUTES
    )
    return f"""# Маршруты черновика {key}.
schemaVersion: 1
templateId: {REFERENCES[key]['template_id']}

routes:
{rows}
"""


def _simple(title: str, body: str) -> str:
    return f"# {title}\n\n{body}\n"


def build_pack(key: str, meta: dict) -> list[Path]:
    pack = PACKS_DIR / key
    (pack / "fixtures").mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def put(name: str, text: str) -> None:
        target = pack / name
        target.write_text(text, encoding="utf-8")
        written.append(target)

    put("README_AI.md", _readme(key, meta))
    put("TemplateManifest.yaml", _manifest(key, meta))
    put("blocks.yaml", _blocks(key))
    put("ROUTES.yaml", _routes(key))

    put("PAGE_MAP.md", _simple(
        f"Карта страниц — {meta['title']}",
        "| Маршрут | Тип | Состояния |\n|---|---|---|\n"
        + "\n".join(f"| `{path}` | {ptype} | normal, empty, degraded, not_found |"
                    for _, ptype, path in DRAFT_ROUTES)
        + "\n\nСостав снят с нашей структуры, а не с референса: референс недоступен."))

    put("BLOCK_MAP.md", _simple(
        f"Блоки по страницам — {meta['title']}",
        "| Блок | Где встречается |\n|---|---|\n"
        + "\n".join(f"| `{b}` | все маршруты, кроме `not-found` |" for b, _, _ in DRAFT_BLOCKS)))

    put("VISUAL_TOKENS.yaml", f"""# Токены оформления — {meta['title']}.
#
# ПУСТО НАМЕРЕННО. Токен — измеренная величина: ширина колонки, кегль,
# скругление, пропорция карточки. Измерить их не на чем: {BLOCKED_NOTE}
#
# Записать сюда правдоподобные числа значило бы выдать догадку за замер. После
# этого пакет перестал бы быть свидетельством, а его числа начали бы жить
# собственной жизнью в чужих отчётах.

schemaVersion: 1
status: blocked
blocker: REF-EGRESS-01
tokens: {{}}
""")

    put("VISUAL_DECISIONS.md", _simple(
        f"Визуальные решения — {meta['title']}",
        "Решений пока нет: их принимают по измерению, а измерения нет.\n\n"
        "**Отвергнуто заранее** — заполнить токены по описанию из задания или "
        "по памяти о похожих сайтах. Догадка, записанная в поле замера, "
        "неотличима от замера через неделю."))

    put("SCREENSHOT_INDEX.md", _simple(
        f"Снимки — {meta['title']}",
        "| Ширина | Состояние | Статус |\n|---|---|---|\n"
        + "\n".join(f"| {w} | normal | **BLOCKED** |" for w in (390, 768, 1024, 1440, 1920))
        + f"\n\n{BLOCKED_NOTE}\n\n"
          "Ни одна строка не помечена PASS. Снимок, которого нет, не может быть "
          "пройденной проверкой."))

    put("STATES.md", _simple(
        f"Состояния — {meta['title']}",
        "| Состояние | Что обязано быть |\n|---|---|\n"
        "| normal | содержимое из источника |\n"
        "| empty | явное объяснение пустоты |\n"
        "| degraded | честное сообщение вместо выдуманных данных |\n"
        "| not_found | код 404, заголовок, выход |\n\n"
        "Недопустим единственный исход — молчащая пустота."))

    put("PLAYER_SHELL.md", _simple(
        f"Посадочное место плеера — {meta['title']}",
        "Шаблон владеет местом: пропорция 16:9 зарезервирована до загрузки, "
        "перекрывающего слоя нет, состояние объяснено обычными словами, повтор "
        "доступен с клавиатуры.\n\n"
        "Шаблон не владеет поставщиком, резолвером, плейлистом и Publisher ID — "
        "ничего из этого в шаблоне нет.\n\n"
        "Внутренние коды отказа и имена секретов на странице не показываются "
        "никогда."))

    put("RATINGS.md", _simple(
        f"Оценки — {meta['title']}",
        "Выводятся все источники, пришедшие через контракт, и ничего сверх.\n\n"
        "Оценка без источника не выводится: число без имени источника "
        "неинтерпретируемо. Шкала, число голосов и время наблюдения "
        "показываются, только если пришли, и никогда не достраиваются.\n\n"
        "Отсутствие оценок убирает область целиком, не оставляя пустой рамки."))

    put("AD_SLOTS.md", _simple(
        f"Рекламные места — {meta['title']}",
        "Выключенный слот не оставляет контейнера в разметке.\n\n"
        "Включённый резервирует геометрию до загрузки, чтобы не сдвигать "
        "раскладку.\n\n"
        "Рекламная сеть не подключается: интеграция запрещена манифестом "
        "(`networkIntegration: forbidden`)."))

    put("ACCEPTANCE.md", _simple(
        f"Критерии приёмки — {meta['title']}",
        "Черновик считается готовым к переходу в шаблон, когда:\n\n"
        "1. доступ к референсу открыт и `measurement_plan` отработал;\n"
        "2. `VISUAL_TOKENS.yaml` заполнен измеренными величинами;\n"
        "3. `SCREENSHOT_INDEX.md` содержит снимки на пяти ширинах;\n"
        "4. манифест объявляет диапазоны версий вместо `pending`;\n"
        "5. фикстуры покрывают normal, empty, degraded и not_found;\n"
        "6. producer-тесты пакета проходят.\n\n"
        "До тех пор пакет остаётся черновиком, и объявлять визуальное "
        "соответствие запрещено."))

    put("PREVIEW.md", _simple(
        f"Локальный просмотр — {meta['title']}",
        "Просмотра пока нет: шаблон не построен, потому что не с чем сверяться.\n\n"
        "Когда доступ откроют, порядок такой:\n\n"
        "```bash\n"
        "python3 -m factory reference-audit --ref " + key + "\n"
        "```\n\n"
        "Инструмент измерения готов и не требует правки кода: "
        "`tests/tools/measure_reference.js`."))

    put("TEST_INVENTORY.md", _simple(
        f"Проверки — {meta['title']}",
        "| Проверка | Где | Статус |\n|---|---|---|\n"
        "| Схема пакета референса | `tests/unit/test_reference_packs.py` | активна |\n"
        "| Уникальность routeId и blockId | там же | активна |\n"
        "| Каждый блок документирован | там же | активна |\n"
        "| Черновик не включает production | там же | активна |\n"
        "| Черновик не включает индексацию | там же | активна |\n"
        "| Запрет `latest` | там же | активна |\n"
        "| Измерение референса | `tests/tools/measure_reference.js` | **BLOCKED** |\n"
        "| Визуальный эталон | — | **NOT_RUN** |"))

    put("CHANGELOG.md", _simple(
        f"История пакета — {meta['title']}",
        "## 0.0.1-draft — 04.09.2026\n\n"
        "Заведён архитектурный черновик. Измерений нет: референс недоступен "
        "(REF-EGRESS-01). Токены и снимки помечены BLOCKED, а не заполнены "
        "правдоподобными значениями."))

    for state in ("home.normal", "title.normal", "states"):
        (pack / "fixtures" / f"{state}.json").write_text(
            json.dumps({
                "schemaVersion": 1,
                "templateId": meta["template_id"],
                "fixtureVersion": "0.0.1-draft",
                "generatedAt": "2026-09-04T00:00:00Z",
                "deterministic": True,
                "synthetic": True,
                "note": (
                    "Фикстура описывает нашу структуру. Данных референса в ней нет "
                    "и быть не может: референс недоступен."
                ),
                "items": [],
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        written.append(pack / "fixtures" / f"{state}.json")

    return written


def main() -> int:
    total = 0
    for key, meta in REFERENCES.items():
        files = build_pack(key, meta)
        total += len(files)
        print(f"{key}: {len(files)} файлов")
    print(f"всего: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
