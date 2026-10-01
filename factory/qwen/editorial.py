"""Операции над редакционным материалом: подготовка, публикация, снятие, откат.

Четыре состояния, и последнее вычисляется проверкой
---------------------------------------------------

    prepared   — материал сохранён черновиком, ничего публичного не менялось
    verified   — черновик прошёл проверки качества и привязки к тайтлу
    written    — материал записан в хранилище доставки (файл на месте)
    confirmed  — материал НАЙДЕН в основном блоке публичной страницы

`written` и `confirmed` разделены намеренно. Запись файла, зелёный код возврата
и наличие отчёта публикацией не являются: это уже дважды выглядело успехом при
пустой странице. Итоговое состояние считает инструмент по фактическому HTML, а
не по тому, чем закончилась команда.

Текст не попадает в shell
-------------------------

Тело материала принимается структурированными данными (JSON через файл или
стандартный ввод) и уходит в хранилище через библиотеку. Никакой подстановки
пользовательского текста в исполняемую строку нет и не предусмотрено.

Чужую более новую правку не затираем
------------------------------------

У записи есть `expected_generation`: если в хранилище лежит не та версия, от
которой редактор отталкивался, операция отказывает и показывает фактическую.
Повтор того же задания не создаёт дубликата — ключом служит `slug`, как у
пишущей стороны.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import re
import time
import unicodedata
from typing import Any

from factory.qwen import registry

#: Черновики и история — рядом с хранилищем доставки, но отдельными файлами:
#: снятый с публикации материал обязан сохраниться, а не исчезнуть.
ЧЕРНОВИКИ = "drafts.json"
ИСТОРИЯ = "history.jsonl"
СНЯТЫЕ = "unpublished.json"


class ОперацияОтклонена(RuntimeError):
    """Отказ с названной причиной. Слепой повтор запрещён."""


def _сейчас() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def отпечаток(текст: str) -> str:
    return hashlib.sha256(
        unicodedata.normalize("NFKC", текст).encode("utf-8")).hexdigest()


def _норм(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip()


def _сайт(site: str) -> registry.Сайт:
    все = registry.собрать(опрашивать_сеть=True)
    по_домену = {s.domain: s for s in все}
    по_ид = {s.site_id: s for s in все}
    s = по_домену.get(site) or по_ид.get(site)
    if s is None:
        raise ОперацияОтклонена(
            f"сайта {site!r} нет в действующих реестрах. Список: "
            "python3 -m factory.qwen sites")
    return s


def _требует(s: registry.Сайт, операция: str) -> None:
    """Отказать, назвав КОНКРЕТНУЮ недостающую возможность адаптера."""
    нужна = registry.ТРЕБУЕТ_ВОЗМОЖНОСТИ.get(операция)
    if нужна is None:
        return
    умеет = registry.ВОЗМОЖНОСТИ_АДАПТЕРА.get(s.adapter, {})
    if нужна not in умеет:
        raise ОперацияОтклонена(
            f"{s.domain}: семейство {s.adapter or 'не определено'} не умеет "
            f"{нужна!r} — операция {операция!r} недоступна. Есть: "
            f"{sorted(умеет) or 'ничего'}. Это недостающая возможность "
            "адаптера, а не отказ по данным")


def _каталог(s: registry.Сайт) -> pathlib.Path:
    """Каталог хранилища ЭТОГО домена. Проверяется программно."""
    корень = registry.корень_хранилища(s.adapter)
    к = корень / s.domain
    if к.resolve().parent != корень.resolve():
        raise ОперацияОтклонена(
            f"каталог {к} вне корня хранилища {корень} — запись отклонена")
    return к


def _дописать_историю(к: pathlib.Path, запись: dict) -> None:
    к.mkdir(parents=True, exist_ok=True)
    with (к / ИСТОРИЯ).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(запись, ensure_ascii=False) + "\n")


def _прочитать(п: pathlib.Path, умолчание):
    try:
        return json.loads(п.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return умолчание


def _записать_атомарно(п: pathlib.Path, данные) -> None:
    п.parent.mkdir(parents=True, exist_ok=True)
    врем = п.with_name(п.name + f".tmp.{os.getpid()}")
    врем.write_text(json.dumps(данные, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    json.loads(врем.read_text(encoding="utf-8"))  # не переносим битое
    os.replace(врем, п)


# --------------------------------------------------------------- факты
def факты(site: str, slug: str | None = None) -> dict:
    """Факты о тайтле из снимка подробностей. Источник один и назван."""
    s = _сайт(site)
    _требует(s, "facts")
    sid = s.site_id
    снимок = pathlib.Path(f"/srv/lords/.frontend/{sid}-details.json")
    if not снимок.is_file():
        raise ОперацияОтклонена(
            f"снимка подробностей нет: {снимок}. Для этого сайта факты "
            "недоступны этим путём — сообщите, и адаптер будет доработан")
    данные = _прочитать(снимок, {})
    записи = данные.get("details") or {}
    if slug is None:
        без_описания = [k for k, v in записи.items()
                        if not str(v.get("description") or "").strip()
                        and v.get("playable")]
        return {"site": s.domain, "site_id": sid,
                "catalog_revision": данные.get("catalog_revision"),
                "titles_total": len(записи),
                "without_description_playable": len(без_описания),
                "sample": без_описания[:10],
                "source": str(снимок)}
    r = записи.get(slug)
    if r is None:
        raise ОперацияОтклонена(
            f"тайтла {slug!r} нет в снимке {снимок.name}. Выдумывать слаг нельзя")
    поля = ("id", "name", "original_name", "year", "type", "genres",
            "countries", "seasons", "imdb_rating", "playable",
            "description", "description_source")
    return {"site": s.domain, "site_id": sid, "slug": slug,
            "title_id": r.get("id"),
            "facts": {k: r.get(k) for k in поля},
            "source": str(снимок),
            "canonical_url": f"https://{s.domain}/title/{slug}/"}


# ------------------------------------------------- подготовка и проверки
#: Корни, а не слова. «доступн» не ловит «доступен» — именно так фраза Qwen
#: «Сериал доступен для просмотра на платформе» прошла бы проверку, из-за
#: которой проверка и появилась. Поэтому корень «доступ».
ЗАПРЕЩЁННЫЕ_ОБОРОТЫ = (
    "доступ", "смотреть все", "все серии", "озвучк", "субтитр",
    "в хорошем качестве", "бесплатно", "без регистрации",
)


def проверить_материал(тело: str, факты_тайтла: dict) -> list[str]:
    """Проверки, выросшие из НАЙДЕННЫХ ошибок, а не из общих соображений.

    Qwen уже однажды дописал «Сериал доступен для просмотра на платформе» —
    обещание доступности, которого никто не проверял. Поэтому обороты про
    доступность, озвучки и субтитры отклоняются: их нельзя подтвердить снимком.

    Чего проверка НЕ умеет: она не оценивает осмысленность текста и не ловит
    выдуманный сюжет, если он сформулирован без запрещённых оборотов. Это
    ограничение автоматической проверки, и его надо знать.
    """
    беды: list[str] = []
    т = тело.strip()
    if len(т) < 80:
        беды.append(f"текст короче 80 знаков ({len(т)}): пользы в нём нет")
    if len(т) > 1200:
        беды.append(f"текст длиннее 1200 знаков ({len(т)})")
    низ = т.lower()
    for оборот in ЗАПРЕЩЁННЫЕ_ОБОРОТЫ:
        if оборот in низ:
            беды.append(
                f"оборот {оборот!r} обещает то, чего снимок не подтверждает; "
                "доступность серий, озвучки и субтитры проверяются только на "
                "самой странице")
    ф = факты_тайтла.get("facts") or {}
    # Название сверяется по ОСНОВНОЙ части, без скобочного уточнения.
    #
    # Требовать строку целиком — ложный отказ: у снимка название
    # «7 семян (второй сезон)», а осмысленный текст пишет «7 семян» и
    # поясняет сезон словами. Проверка должна ловить текст НЕ ПРО ТОТ тайтл, а
    # не форму записи.
    имя = str(ф.get("name") or "")
    основа = re.split(r"[(\[]", имя)[0].strip().lower()
    if основа and основа not in низ:
        беды.append(f"в тексте нет названия тайтла {основа!r} (из снимка: {имя!r})")
    год = ф.get("year")
    if год and str(год) not in т:
        беды.append(f"в тексте нет года {год} — он есть в снимке и его стоит назвать")
    годы = {int(m.group(0)) for m in re.finditer(r"\b(?:19|20)\d{2}\b", т)}
    if год and годы - {int(год)}:
        беды.append(f"в тексте годы {sorted(годы)}, а в снимке только {год}: "
                    "лишние даты не подтверждены")
    return беды


def подготовить(site: str, slug: str, тело: str, *, author: str) -> dict:
    """Сохранить черновик. Публичного ничего не меняется."""
    s = _сайт(site)
    ф = факты(site, slug)
    беды = проверить_материал(тело, ф)
    к = _каталог(s)
    черновики = _прочитать(к / ЧЕРНОВИКИ, {"site": s.domain, "items": {}})
    черновики.setdefault("items", {})[slug] = {
        "slug": slug, "title_id": ф["title_id"], "body": тело,
        "body_digest": отпечаток(тело), "author": author,
        "prepared_at": _сейчас(),
        "state": "verified" if not беды else "prepared",
        "quality_problems": беды,
    }
    черновики["site"] = s.domain
    _записать_атомарно(к / ЧЕРНОВИКИ, черновики)
    _дописать_историю(к, {"at": _сейчас(), "op": "prepare", "slug": slug,
                          "author": author, "state": черновики["items"][slug]["state"],
                          "problems": беды})
    return {"site": s.domain, "slug": slug, "title_id": ф["title_id"],
            "state": черновики["items"][slug]["state"],
            "quality_problems": беды,
            "draft_store": str(к / ЧЕРНОВИКИ)}


# ------------------------------------------------------------- публикация
#: Код оператора и его интерпретатор. Хранилище живёт там, и там же 3.11:
#: `enum.StrEnum` в его моделях требует 3.11, а системный python — 3.10.
#: Поэтому запись идёт отдельным процессом, а не импортом.
ОПЕРАТОР = pathlib.Path("/home/claude/wt-seo-index-audit-20260930")
ИНТЕРПРЕТАТОР = ОПЕРАТОР / ".venv" / "bin" / "python"

_ЗАПИСЬ = r"""
import json, pathlib, sys
from seo_engine.content_operator.title_overlays import TitleOverlayStore
з = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
store = TitleOverlayStore(pathlib.Path(з["directory"]), site=з["site"])
if з["op"] == "publish":
    итог = store.publish_items(з["items"], generation_id=з["generation_id"],
                               replace=bool(з.get("replace")))
elif з["op"] == "rollback":
    итог = store.rollback_last_good()
else:
    raise SystemExit("unknown op")
print(json.dumps({"site": итог.get("site"),
                  "generation_id": итог.get("generation_id"),
                  "items": итог.get("items") or []}, ensure_ascii=False))
"""


def _вызвать_store(s: registry.Сайт, задание: dict) -> dict:
    """Запись в хранилище отдельным процессом под интерпретатором оператора.

    Текст передаётся ФАЙЛОМ с JSON, а не аргументом: в командную строку
    пользовательский текст не попадает ни при каких условиях. Проверка
    принадлежности домену остаётся внутри store и не отключается — её отказ
    `wrong_site_in_overlay_payload` доходит сюда как ошибка процесса.
    """
    import subprocess
    import tempfile
    if not ИНТЕРПРЕТАТОР.is_file():
        raise ОперацияОтклонена(
            f"нет интерпретатора оператора {ИНТЕРПРЕТАТОР}: записывать нечем")
    задание = {**задание, "directory": str(_каталог(s)), "site": s.domain}
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json",
                                     delete=False) as fh:
        json.dump(задание, fh, ensure_ascii=False)
        файл = fh.name
    try:
        r = subprocess.run([str(ИНТЕРПРЕТАТОР), "-c", _ЗАПИСЬ, файл],
                           cwd=str(ОПЕРАТОР), capture_output=True, text=True,
                           timeout=120,
                           env={"PYTHONPATH": str(ОПЕРАТОР), "PATH": "/usr/bin:/bin",
                                "HOME": os.environ.get("HOME", "/home/claude")})
    finally:
        os.unlink(файл)
    if r.returncode != 0:
        raise ОперацияОтклонена(
            f"хранилище отказало (код {r.returncode}): "
            f"{(r.stderr or r.stdout).strip()[-300:]}")
    try:
        return json.loads(r.stdout)
    except ValueError as e:
        raise ОперацияОтклонена(
            f"хранилище ответило неразборчиво: {r.stdout[:200]!r}") from e


def _текущее(s: registry.Сайт) -> dict:
    return _прочитать(_каталог(s) / "title-overlays.json",
                      {"items": [], "generation_id": None})


def публиковать(site: str, slug: str, *, author: str,
                expected_generation: str | None = None,
                тело: str | None = None) -> dict:
    """Записать материал в хранилище доставки и ПОДТВЕРДИТЬ на странице."""
    s = _сайт(site)
    _требует(s, "publish")
    if s.handover_state == "not_released":
        raise ОперацияОтклонена(
            f"{s.domain}: {s.handover_reason}. Запись отклонена, чтобы не "
            "выдать её за публикацию")
    к = _каталог(s)
    # Факты нужны для проверок качества. Семейство без источника фактов
    # (Yummy) проверяется мягче — и это сказано прямо, а не умолчано.
    умеет_факты = "facts" in registry.ВОЗМОЖНОСТИ_АДАПТЕРА.get(s.adapter, {})
    ф = факты(site, slug) if умеет_факты else {
        "title_id": None, "facts": {}, "source": "источника фактов у семейства нет"}

    if тело is None:
        черновик = (_прочитать(к / ЧЕРНОВИКИ, {}).get("items") or {}).get(slug)
        if not черновик:
            raise ОперацияОтклонена(
                f"черновика для {slug!r} нет: сначала prepare, либо передайте тело")
        тело = черновик["body"]
    беды = проверить_материал(тело, ф)
    if беды:
        raise ОперацияОтклонена(
            "материал не прошёл проверки: " + "; ".join(беды))
    предупреждения = ([] if умеет_факты else
                      ["факты не сверялись: у семейства нет источника фактов, "
                       "за достоверность отвечает автор материала"])

    текущее = _текущее(s)
    факт_ген = текущее.get("generation_id")
    if expected_generation is not None and факт_ген != expected_generation:
        raise ОперацияОтклонена(
            f"в хранилище версия {факт_ген!r}, а ожидалась {expected_generation!r}: "
            "кто-то записал новее. Перечитайте состояние и решите, что делать — "
            "слепая перезапись запрещена")

    поколение = f"qwen-{slug}-{int(time.time())}"
    итог = _вызвать_store(s, {"op": "publish", "generation_id": поколение,
        "items": [{"slug": slug, "title_id": ф.get("title_id"), "body": тело,
                   "provenance": {"author": author, "prepared_by": author,
                                  "facts_source": ф["source"],
                                  "written_at": _сейчас()}}]})
    _дописать_историю(к, {"at": _сейчас(), "op": "publish", "slug": slug,
                          "author": author, "generation_id": поколение,
                          "previous_generation": факт_ген,
                          "body_digest": отпечаток(тело)})
    подтверждение = подтвердить_с_ожиданием(site, slug, тело=тело,
                                            ждать_появления=True)
    состояние = "confirmed" if подтверждение["confirmed"] else "written"
    return {"site": s.domain, "slug": slug, "title_id": ф["title_id"],
            "generation_id": поколение, "items_in_store": len(итог["items"]),
            "state": состояние, "confirmation": подтверждение,
            "warnings": предупреждения,
            "store": str(к / "title-overlays.json")}


#: Сколько ждать появления текста на странице. Витрина перечитывает наложение
#: не мгновенно: примета смены файла проверяется опросом, затем снимок
#: пересобирается. Без ожидания `confirmed` превращался бы в орлянку — проверка
#: успевала спросить страницу раньше, чем та успевала перечитать.
ОЖИДАНИЕ_ПОДТВЕРЖДЕНИЯ_С = int(os.environ.get("QWEN_CONFIRM_WAIT", "90"))
ШАГ_ОЖИДАНИЯ_С = 10


def подтвердить_с_ожиданием(site: str, slug: str, *, тело: str | None = None,
                            ждать_появления: bool = True) -> dict:
    """Опрашивать страницу до предела, пока результат не станет ожидаемым.

    `ждать_появления=True` — ждём, пока текст ПОЯВИТСЯ (публикация);
    `False` — пока ИСЧЕЗНЕТ (снятие). Истёк предел — отдаём фактический
    результат с числом попыток, а не выдумываем успех.
    """
    предел = time.time() + ОЖИДАНИЕ_ПОДТВЕРЖДЕНИЯ_С
    попыток = 0
    итог = подтвердить(site, slug, тело=тело)
    while time.time() < предел:
        попыток += 1
        достигнуто = итог["confirmed"] if ждать_появления else not итог["confirmed"]
        if достигнуто:
            break
        time.sleep(ШАГ_ОЖИДАНИЯ_С)
        итог = подтвердить(site, slug, тело=тело)
    итог["attempts"] = попыток
    итог["waited_for"] = "появление" if ждать_появления else "исчезновение"
    return итог


def подтвердить(site: str, slug: str, *, тело: str | None = None) -> dict:
    """Есть ли ПОЛНЫЙ текст в основном блоке публичной страницы.

    Метатеги и JSON-LD считаются отдельно: они не являются основным блоком, и
    однажды «четыре вхождения» оказались тремя метатегами и одним телом.
    """
    s = _сайт(site)
    к = _каталог(s)
    if тело is None:
        запись = next((i for i in _текущее(s).get("items") or []
                       if i.get("slug") == slug), None)
        if запись is None:
            return {"confirmed": False,
                    "reason": f"в хранилище нет записи для {slug!r}"}
        тело = запись.get("body") or ""
    url = f"https://{s.domain}/title/{slug}/"
    код, страница = registry._страница(url, таймаут=25)
    if код != "200":
        return {"confirmed": False, "url": url, "http": код,
                "reason": f"страница ответила {код}"}
    import html as _html
    без_головы = re.sub(r"(?is)<head.*?</head>", "", страница)
    без_скриптов = re.sub(r"(?is)<(script|style|template)[^>]*>.*?</\1>", "",
                          без_головы)
    видимый = _норм(_html.unescape(re.sub(r"(?s)<[^>]+>", " ", без_скриптов)))
    мета = [_норм(_html.unescape(m))
            for m in re.findall(r'<meta[^>]+content="([^"]*)"', страница)]
    цель = _норм(тело)
    в_блоке = видимый.count(цель)
    return {"confirmed": в_блоке > 0, "url": url, "http": код,
            "occurrences_in_main_block": в_блоке,
            "occurrences_in_meta": sum(1 for m in мета if цель in m),
            "reason": "" if в_блоке else
                      "полного текста в основном блоке страницы нет; запись в "
                      "файл публикацией не считается"}


def снять(site: str, slug: str, *, author: str) -> dict:
    """Снять материал с публикации ОБРАТИМО: текст и история сохраняются."""
    s = _сайт(site)
    к = _каталог(s)
    текущее = _текущее(s)
    запись = next((i for i in текущее.get("items") or []
                   if i.get("slug") == slug), None)
    if запись is None:
        raise ОперацияОтклонена(
            f"в хранилище {s.domain} нет записи {slug!r}: снимать нечего")
    снятые = _прочитать(к / СНЯТЫЕ, {"site": s.domain, "items": {}})
    снятые.setdefault("items", {})[slug] = {
        **запись, "unpublished_at": _сейчас(), "unpublished_by": author}
    снятые["site"] = s.domain
    _записать_атомарно(к / СНЯТЫЕ, снятые)

    остальные = [i for i in текущее.get("items") or [] if i.get("slug") != slug]
    поколение = f"unpublish-{slug}-{int(time.time())}"
    _вызвать_store(s, {"op": "publish", "generation_id": поколение,
                       "items": остальные, "replace": True})
    _дописать_историю(к, {"at": _сейчас(), "op": "unpublish", "slug": slug,
                          "author": author, "generation_id": поколение,
                          "kept_in": str(к / СНЯТЫЕ)})
    # предусмотренное поведение: страница жива, но текста наложения на ней нет
    пров = подтвердить_с_ожиданием(site, slug,
                                   тело=запись.get("body") or "",
                                   ждать_появления=False)
    return {"site": s.domain, "slug": slug, "generation_id": поколение,
            "kept_items": len(остальные), "material_kept_at": str(к / СНЯТЫЕ),
            "page_http": пров.get("http"),
            "text_gone_from_page": not пров.get("confirmed"),
            "state": "confirmed" if not пров.get("confirmed") else "written",
            "note": "материал сохранён и восстановим: restore"}


def восстановить(site: str, slug: str, *, author: str) -> dict:
    """Вернуть ранее снятый материал из сохранённого, без переписывания текста."""
    s = _сайт(site)
    к = _каталог(s)
    снятые = _прочитать(к / СНЯТЫЕ, {"items": {}})
    запись = (снятые.get("items") or {}).get(slug)
    if запись is None:
        raise ОперацияОтклонена(
            f"снятого материала {slug!r} для {s.domain} нет: восстанавливать нечего")
    return публиковать(site, slug, author=author, тело=запись["body"])


def откатить(site: str, *, author: str) -> dict:
    """Адресный откат хранилища к последней исправной версии."""
    s = _сайт(site)
    к = _каталог(s)
    было = _текущее(s).get("generation_id")
    данные = _вызвать_store(s, {"op": "rollback"})
    _дописать_историю(к, {"at": _сейчас(), "op": "rollback", "author": author,
                          "from_generation": было,
                          "to_generation": данные.get("generation_id")})
    return {"site": s.domain, "from_generation": было,
            "to_generation": данные.get("generation_id"),
            "items": len(данные.get("items") or [])}


def состояние(site: str) -> dict:
    """Что сейчас в хранилище, черновиках и снятых, и что подтверждено."""
    s = _сайт(site)
    к = _каталог(s)
    текущее = _текущее(s)
    черновики = _прочитать(к / ЧЕРНОВИКИ, {}).get("items") or {}
    снятые = _прочитать(к / СНЯТЫЕ, {}).get("items") or {}
    записи = []
    for i in текущее.get("items") or []:
        пров = подтвердить(site, i.get("slug") or "", тело=i.get("body") or "")
        записи.append({"slug": i.get("slug"), "title_id": i.get("title_id"),
                       "state": "confirmed" if пров["confirmed"] else "written",
                       "occurrences_in_main_block": пров.get("occurrences_in_main_block"),
                       "author": (i.get("provenance") or {}).get("author")})
    return {"site": s.domain, "handover_state": s.handover_state,
            "generation_id": текущее.get("generation_id"),
            "published": записи, "drafts": sorted(черновики),
            "unpublished_kept": sorted(снятые),
            "history": str(к / ИСТОРИЯ)}
