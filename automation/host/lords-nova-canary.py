#!/usr/bin/env python3
"""Выкладка артефакта nova на ОДНУ витрину и штатный откат.

## Почему отдельная процедура

`deploy-nova-lords.sh` раскатывает витрину целиком: каталог, манифест, юнит и
nginx. Приёмщик заявок (`lords-deploy-broker`) запускает полную отрисовку
статического релиза — часы работы. Ни то, ни другое не выражает «поменять
артефакт рантайма на одной витрине и посмотреть», а именно это и есть canary.

## Что делает и чего не делает

Делает ровно три записи:

1. кладёт артефакт в `/srv/lords/.frontend/lords-frontend.py`;
2. переписывает манифест ОДНОЙ названной витрины;
3. перезапускает юнит этой витрины.

Не трогает: nginx, сертификаты, DNS, каталоги содержимого, юниты и манифесты
соседних витрин.

## Почему смена общего файла не меняет соседей

Артефакт один на шесть витрин, и подменить его — значит подменить код у всех.
Но ЧТО этот код делает, решает манифест витрины: `design_version` выбирает
ветку отрисовки. Витрина, чей манифест остался на 1.0.2, исполняет прежнюю
ветку и отдаёт прежние байты — это проверено побайтовым сличением
(`artifacts/.../legacy-byte-identity.json`), а не объявлено.

## Откат

Прежний артефакт и прежний манифест сохраняются ДО первой записи, в каталог
`.rollback/<метка>/`. Откат возвращает оба файла и перезапускает юнит. Если
сохранить точку отката не удалось, выкладка не начинается: выкладка без
возврата — это не выкладка, а замена без права передумать.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ФРОНТ = Path("/srv/lords/.frontend")
АРТЕФАКТ = ФРОНТ / "lords-frontend.py"
ОТКАТЫ = ФРОНТ / ".rollback"

#: Витрины, которые процедура согласна трогать, и всё, что о них нужно знать.
#: Расширять перечень по своей инициативе нельзя: витрина, которой здесь нет,
#: не выкатывается, а получает отказ.
ВИТРИНЫ = {
    "lords-01": {"unit": "lords-nova-01.service", "domain": "lordfilm47.space",
                 "manifest": "template-manifest.json", "family": "lords",
                 "profile": "lords-general", "port": 9110},
    "zona-01": {"unit": "nova-zona-01.service", "domain": "zonafilm.space",
                "manifest": "template-manifest-zona-01.json", "family": "zona",
                "profile": "zona-general", "port": 9120},
}

#: Каталоги, из которых разрешено брать артефакт. Путь вне этого списка —
#: отказ. Иначе привилегированный запуск с `--artifact /любой/файл` записывает
#: произвольные байты в файл, который исполняет каждая витрина парка.
РАЗРЕШЁННЫЕ_ИСТОЧНИКИ = (
    Path("/home/claude/wt-lords-r2/automation/host"),
    Path("/srv/site-factory/repo/automation/host"),
    ФРОНТ / ".rollback",
)


def проверить_источник(путь: Path) -> Path:
    """Артефакт обязан быть обычным файлом из разрешённого каталога.

    Проверки идут по РАЗРЕШЁННОМУ пути (`resolve`), а не по написанному: иначе
    `.../automation/host/../../../etc/passwd` проходит проверку префикса, а
    символическая ссылка из разрешённого каталога уводит куда угодно. Оба
    случая закрываются одним сравнением после разрешения.
    """
    if путь.is_symlink():
        raise Отказ(f"артефакт — символическая ссылка: {путь}")
    разрешённый = путь.resolve(strict=False)
    if not разрешённый.is_file():
        raise Отказ(f"артефакта нет или это не обычный файл: {разрешённый}")
    for корень in РАЗРЕШЁННЫЕ_ИСТОЧНИКИ:
        база = корень.resolve(strict=False)
        if разрешённый == база or база in разрешённый.parents:
            return разрешённый
    raise Отказ(f"артефакт вне разрешённых каталогов: {разрешённый}; "
                f"разрешены {[str(к) for к in РАЗРЕШЁННЫЕ_ИСТОЧНИКИ]}")


def доказать_цепочку(витрина: str, описание: dict) -> dict:
    """Сверка «сайт → домен → nginx → порт → юнит» с живой конфигурацией.

    Имя юнита в таблице выше — не источник истины, а ОЖИДАНИЕ. Истина лежит в
    nginx и systemd, и перед перезапуском ожидание обязано с ней совпасть.
    Догадка «сайт lords-01 обслуживается юнитом lords-01.service» выглядит
    очевидной и неверна: этот юнит слушает 9101 и публично не проксируется, а
    домен отдаёт `lords-nova-01.service` на 9110.
    """
    import importlib.util
    # parents[2], а не [1]: файл лежит в automation/host/, и один уровень вверх
    # даёт automation/, где никаких scripts/ нет. Ошибка на единицу в пути к
    # доказателю превращала бы обязательную сверку в отказ на ровном месте.
    модуль_путь = Path(__file__).resolve().parents[2] / "scripts" / "prove_serving_chain.py"
    if not модуль_путь.is_file():
        raise Отказ(f"нет доказателя цепочки: {модуль_путь}")
    спец = importlib.util.spec_from_file_location("prove_serving_chain", модуль_путь)
    доказатель = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(доказатель)
    цепь = доказатель.цепочка(описание["domain"], доказатель.юниты())
    if цепь.get("upstream_port") != описание["port"]:
        raise Отказ(f"{витрина}: nginx ведёт домен {описание['domain']} на порт "
                    f"{цепь.get('upstream_port')}, ожидался {описание['port']}")
    if цепь.get("unit") != описание["unit"]:
        raise Отказ(f"{витрина}: домен {описание['domain']} обслуживает юнит "
                    f"{цепь.get('unit')!r}, а не {описание['unit']!r}")
    ожидаемый_манифест = str(ФРОНТ / описание["manifest"])
    if цепь.get("manifest_path") != ожидаемый_манифест:
        raise Отказ(f"{витрина}: юнит читает манифест {цепь.get('manifest_path')!r}, "
                    f"ожидался {ожидаемый_манифест!r}")
    if цепь.get("executable") != str(АРТЕФАКТ):
        raise Отказ(f"{витрина}: юнит исполняет {цепь.get('executable')!r}, "
                    f"а не {АРТЕФАКТ}")
    return цепь

#: Адреса, по которым проверяется здоровье витрины после перезапуска. Пустая
#: двухсотка здоровьем не считается: у страницы обязано быть тело.
ПРОБЫ = ("/healthz", "/", "/catalog/")
МИНИМУМ_ТЕЛА = 2000

#: Пауза после перезапуска юнита, прежде чем спрашивать домен.
ПАУЗА_ПОСЛЕ_ПЕРЕЗАПУСКА = 4

#: Ограниченное ожидание схождения. Перезапущенная служба отвечает не мгновенно,
#: и первый ответ может прийти от ещё не умершего прежнего процесса — это
#: единственная задержка, которую разрешено переждать. Предел жёсткий, каждая
#: попытка записывается, а отданный ТРЕТИЙ релиз прекращает ожидание немедленно:
#: это не запаздывание, а неправильная витрина.
СХОЖДЕНИЕ_ПОПЫТОК = 6
СХОЖДЕНИЕ_ИНТЕРВАЛ = 3.0
СХОЖДЕНИЕ_ТАЙМАУТ = 30.0

#: Личность релиза, как её объявляет сам рантайм. Имена слева намеренно
#: совпадают с полями манифеста: сверка идёт с манифестом точки отката целиком,
#: а не по одному полю.
ЗАГОЛОВКИ_РЕЛИЗА = {
    "template_family": "X-Site-Factory-Template-Family",
    "design_version": "X-Site-Factory-Template-Version",
    "build_id": "X-Site-Factory-Build-Id",
    "artifact_sha256": "X-Site-Factory-Artifact-Sha256",
    "source_commit": "X-Site-Factory-Template-Revision",
}

СТИЛЬ = re.compile(rb"<style[^>]*>(.*?)</style>", re.S)
СКРИПТ = re.compile(rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S)

#: Последняя вынесенная запись: вердикт должен быть проверяем тестом, не разбором
#: печати.
ПОСЛЕДНЯЯ_ЗАПИСЬ: dict = {}


class Отказ(Exception):
    """Отказ до записи либо с уже выполненным возвратом. Всегда с причиной."""


def _sha(путь: Path) -> str:
    return hashlib.sha256(путь.read_bytes()).hexdigest()


def _сейчас() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _атомарно(цель: Path, данные: bytes) -> None:
    врем = цель.with_name(цель.name + ".tmp")
    врем.write_bytes(данные)
    врем.replace(цель)


def _юнит(действие: str, юнит: str) -> tuple[bool, str]:
    try:
        р = subprocess.run(["systemctl", действие, юнит],
                           capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as ош:
        return False, str(ош)[:200]
    return р.returncode == 0, (р.stderr or р.stdout or "").strip()[:300]


def _структура(тело: bytes) -> dict:
    """Отпечаток того, что РЕАЛЬНО пришло, а не того, что о себе объявили.

    Манифест — самоотчёт рантайма: он утверждает версию и может утверждать её
    неверно. Эти отпечатки берутся из самого ответа, поэтому манифестом их не
    подделать. Нормализуются только переводы строк: их переписывание по пути —
    свойство канала, а не релиза. Всё прочее содержимое входит как есть, и
    подмена хотя бы одного байта разметки, стиля или скрипта видна.
    """
    нормализованное = тело.replace(b"\r\n", b"\n")
    стиль = b"".join(с.group(1) for с in СТИЛЬ.finditer(нормализованное))
    скрипт = b"".join(с.group(1) for с in СКРИПТ.finditer(нормализованное))
    return {"html_sha256": hashlib.sha256(нормализованное).hexdigest(),
            "css_sha256": hashlib.sha256(стиль).hexdigest(),
            "js_sha256": hashlib.sha256(скрипт).hexdigest(),
            "bytes": len(нормализованное)}


def _релиз_манифеста(манифест: dict | None) -> dict:
    return {к: str((манифест or {}).get(к, "")) for к in ЗАГОЛОВКИ_РЕЛИЗА}


def _ключ_релиза(релиз: dict) -> tuple:
    return tuple(релиз.get(к, "") for к in sorted(ЗАГОЛОВКИ_РЕЛИЗА))


def _объявленные(проба: dict) -> set:
    """Личности релиза, объявленные доменом. Молчание — не «то же самое»."""
    return {_ключ_релиза(п["declared"]) for п in проба.get("checks", [])
            if п.get("declared")}


def _объявленные_имена(проба: dict) -> list:
    """То же, что `_объявленные`, но читаемо в отчёте: поля названы."""
    видно = {}
    for п in проба.get("checks", []):
        if п.get("declared"):
            видно[_ключ_релиза(п["declared"])] = dict(п["declared"])
    return [видно[к] for к in sorted(видно)]


def _снимок_отданного(проба: dict) -> dict:
    """Что домен отдавал: по адресу — код, конец пути, число переходов, структура."""
    return {п["path"]: {"status": п.get("status"),
                        "final_url": п.get("final_url"),
                        "redirects": п.get("redirects"),
                        "structure": п.get("structure")}
            for п in проба.get("checks", []) if п.get("structure")}


def _сверить_структуру(сейчас: dict, опорный: dict | None) -> tuple[bool, list]:
    """Измеренное против измеренного. Отсутствие опоры — не совпадение."""
    if not опорный:
        return False, []
    пусто = {"status": None, "final_url": None, "redirects": None, "structure": None}
    различия = []
    for путь in sorted(set(сейчас) | set(опорный)):
        было, стало = опорный.get(путь, пусто), сейчас.get(путь, пусто)
        if было != стало:
            различия.append({"path": путь, "expected": было, "actual": стало})
    return (not различия), различия


class _Переходы(urllib.request.HTTPRedirectHandler):
    """Переходы считаются, а не обрабатываются молча: лишний переход — дефект."""

    def __init__(self):
        self.цепочка = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.цепочка.append({"from": req.full_url, "code": code, "to": newurl})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _кэш_диагностика(домен: str) -> dict:
    """Запрос мимо кэша — ТОЛЬКО диагностика.

    Когда обычный публичный адрес отдал не то, полезно знать, кэш это или
    витрина. Но успех по адресу с обходом кэша ничего не подтверждает: зритель
    ходит по обычному адресу, и проверкой засчитывается только он. В вердикт
    этот результат не входит.
    """
    адрес = f"https://{домен}/?nova-cache-bust={_сейчас()}"
    итог = {"url": адрес, "role": "диагностика, в вердикт не входит"}
    try:
        запрос = urllib.request.Request(адрес, headers={"User-Agent": "nova-canary-diag"})
        with urllib.request.urlopen(запрос, timeout=30) as ответ:
            тело = ответ.read()
            итог["status"] = ответ.status
            итог["declared"] = {имя: (ответ.headers.get(заг) or "")
                                for имя, заг in ЗАГОЛОВКИ_РЕЛИЗА.items()}
            итог["structure"] = _структура(тело)
    except (urllib.error.HTTPError, OSError) as ош:
        итог["status"] = getattr(ош, "code", -1)
        итог["error"] = str(ош)[:120]
    return итог


def _дождаться_релиза(домен: str, ожидаемый: dict, прежний: dict) -> dict:
    """Ограниченное ожидание схождения — и ничего сверх него.

    Переждать разрешено ровно одно: доигрывающий перезапуск. Всё остальное
    ожиданием не лечится, поэтому релиз, которого здесь быть не должно,
    прекращает проверку сразу, не расходуя попытки.
    """
    ожидаемый_ключ, прежний_ключ = _ключ_релиза(ожидаемый), _ключ_релиза(прежний)
    журнал, начало, проба = [], time.monotonic(), None
    for попытка in range(1, СХОЖДЕНИЕ_ПОПЫТОК + 1):
        проба = _проба(домен)
        объявленные = _объявленные(проба)
        шаг = {"attempt": попытка,
               "elapsed_s": round(time.monotonic() - начало, 2),
               "declared": _объявленные_имена(проба),
               "health_ok": проба.get("ok", False)}
        if объявленные == {ожидаемый_ключ}:
            шаг["outcome"] = "converged"
            журнал.append(шаг)
            break
        чужие = объявленные - {ожидаемый_ключ, прежний_ключ}
        if чужие:
            шаг["outcome"] = "wrong_release"
            шаг["unexpected"] = [о for о in _объявленные_имена(проба)
                                 if _ключ_релиза(о) in чужие]
            журнал.append(шаг)
            break
        шаг["outcome"] = "not_converged"
        журнал.append(шаг)
        if (попытка == СХОЖДЕНИЕ_ПОПЫТОК
                or time.monotonic() - начало >= СХОЖДЕНИЕ_ТАЙМАУТ):
            break
        time.sleep(СХОЖДЕНИЕ_ИНТЕРВАЛ)
    return {"health": проба, "log": журнал, "attempts": len(журнал),
            "waited_s": round(time.monotonic() - начало, 2),
            "limit": {"attempts": СХОЖДЕНИЕ_ПОПЫТОК,
                      "interval_s": СХОЖДЕНИЕ_ИНТЕРВАЛ,
                      "timeout_s": СХОЖДЕНИЕ_ТАЙМАУТ}}


def _проба(домен: str) -> dict:
    """Ответ НАСТОЯЩЕГО домена по https: тот же Host и SNI, что у посетителя.

    Снимается и объявленное — заголовки, и измеренное — структура тела. Первое
    говорит, какой манифест подхватил рантайм; второе — что он на самом деле
    отрисовал. Сравнивать их между собой нельзя, требовать оба — нужно.
    """
    итог = {"domain": домен, "checks": [], "ok": True}
    for путь in ПРОБЫ:
        адрес = f"https://{домен}{путь}"
        запись = {"path": путь}
        try:
            счётчик = _Переходы()
            открыватель = urllib.request.build_opener(счётчик)
            запрос = urllib.request.Request(адрес, headers={"User-Agent": "nova-canary"})
            with открыватель.open(запрос, timeout=30) as ответ:
                тело = ответ.read()
                запись["status"] = ответ.status
                запись["bytes"] = len(тело)
                запись["final_url"] = ответ.url
                запись["redirects"] = len(счётчик.цепочка)
                запись["redirect_chain"] = счётчик.цепочка
                запись["declared"] = {имя: (ответ.headers.get(заг) or "")
                                      for имя, заг in ЗАГОЛОВКИ_РЕЛИЗА.items()}
                запись["version"] = запись["declared"]["design_version"]
                запись["artifact"] = запись["declared"]["artifact_sha256"]
                запись["structure"] = _структура(тело)
        except (urllib.error.HTTPError, OSError) as ош:
            запись["status"] = getattr(ош, "code", -1)
            запись["error"] = str(ош)[:120]
        хорошо = запись.get("status") == 200 and (
            путь == "/healthz" or запись.get("bytes", 0) >= МИНИМУМ_ТЕЛА)
        запись["ok"] = хорошо
        итог["ok"] &= хорошо
        итог["checks"].append(запись)
    return итог


def _точка_отката(метка: str, манифест: Path, домен: str = "") -> Path:
    """Точка отката — полный договор о возврате.

    Файла и манифеста мало: вернуть их и объявить успех значит поверить
    рантайму на слово. Поэтому здесь же сохраняется ИЗМЕРЕННЫЙ ответ домена до
    изменения — единственная честная опора, с которой потом сверяется откат.
    """
    каталог = ОТКАТЫ / метка
    каталог.mkdir(parents=True, exist_ok=True)
    if not АРТЕФАКТ.is_file():
        raise Отказ(f"нечего сохранять: {АРТЕФАКТ} не существует")
    снимок = _снимок_отданного(_проба(домен)) if домен else None
    if домен and not снимок:
        # Отказ ДО единственной записи: установка, откат которой потом нечем
        # будет доказать, не начинается. Молчащий домен — не мелкая помеха, а
        # отсутствие той самой опоры, ради которой точка и снимается.
        raise Отказ(f"{домен} не ответил: снимать точку отката не с чего")
    shutil.copy2(АРТЕФАКТ, каталог / "lords-frontend.py")
    if манифест.is_file():
        shutil.copy2(манифест, каталог / манифест.name)
    (каталог / "point.json").write_text(json.dumps({
        "saved_at_utc": _сейчас(),
        "artifact_sha256": _sha(каталог / "lords-frontend.py"),
        "manifest": манифест.name,
        "manifest_content": json.loads(манифест.read_text(encoding="utf-8")) if манифест.is_file() else None,
        "served_snapshot": снимок,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return каталог


def установить(арг) -> int:
    витрина = ВИТРИНЫ.get(арг.site)
    if not витрина:
        raise Отказ(f"витрина {арг.site!r} вне перечня: {sorted(ВИТРИНЫ)}")
    источник = проверить_источник(Path(арг.artifact))
    отпечаток = _sha(источник)
    # Отпечаток сверяется ДО первой записи и обязателен. Прежде проверка была
    # условной (`if арг.expect_sha256`), то есть запуск без флага устанавливал
    # что угодно: единственное, что отличало артефакт от произвольного файла,
    # можно было просто не указать.
    if арг.expect_sha256 != отпечаток:
        raise Отказ(f"отпечаток артефакта не тот: ожидался {арг.expect_sha256}, "
                    f"получен {отпечаток}")
    # Юнит определяется по живым nginx и systemd, а не по таблице. Совпадение
    # не удостоверено — выкладки не будет.
    цепь = доказать_цепочку(арг.site, витрина)
    манифест = ФРОНТ / витрина["manifest"]

    метка = f"{_сейчас()}-{арг.site}"
    точка = _точка_отката(метка, манифест, витрина["domain"])
    прежний = json.loads((точка / "point.json").read_text(encoding="utf-8"))

    новый_манифест = {
        "schema_version": 1,
        "template_family": витрина["family"],
        "design_version": арг.design_version,
        "source_commit": арг.commit,
        "build_id": арг.build_id,
        "artifact_sha256": отпечаток,
        "profile": витрина["profile"],
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # Манифест пишется ПЕРВЫМ: рантайм читает его при старте, и артефакт без
    # манифеста своей версии поднялся бы на прежней ветке отрисовки.
    _атомарно(манифест, (json.dumps(новый_манифест, ensure_ascii=False, indent=2) + "\n").encode())
    манифест.chmod(0o644)
    _атомарно(АРТЕФАКТ, источник.read_bytes())
    АРТЕФАКТ.chmod(0o755)

    ок, вывод = _юнит("restart", витрина["unit"])
    time.sleep(4)
    проба = _проба(витрина["domain"]) if ок else {"ok": False, "checks": [],
                                                  "domain": витрина["domain"]}
    запись = {
        "action": "install", "site": арг.site, "unit": витрина["unit"],
        "domain": витрина["domain"], "rollback_point": str(точка),
        "artifact_sha256": отпечаток, "previous_artifact_sha256": прежний["artifact_sha256"],
        "manifest": новый_манифест, "previous_manifest": прежний["manifest_content"],
        "restart_ok": ок, "restart_output": вывод, "health": проба,
        "proven_chain": {к: цепь.get(к) for к in
                         ("nginx_config", "upstream_port", "unit", "executable",
                          "manifest_path", "verdict")},
        "at_utc": _сейчас(),
    }
    if not ок or not проба["ok"]:
        # Возврат немедленный и до отчёта об успехе: витрина, которую подняли
        # и оставили нездоровой, хуже витрины, которую не трогали.
        _атомарно(АРТЕФАКТ, (точка / "lords-frontend.py").read_bytes())
        АРТЕФАКТ.chmod(0o755)
        if прежний["manifest_content"] is not None:
            _атомарно(манифест, (json.dumps(прежний["manifest_content"],
                                            ensure_ascii=False, indent=2) + "\n").encode())
        возврат_ок, возврат_вывод = _юнит("restart", витрина["unit"])
        time.sleep(4)
        запись["auto_rolled_back"] = True
        запись["rollback_restart_ok"] = возврат_ок
        запись["rollback_output"] = возврат_вывод
        здоровье = _проба(витрина["domain"])
        запись["health_after_rollback"] = здоровье
        отданные = {п.get("artifact") for п in здоровье["checks"] if п.get("artifact")}
        запись["served_artifact_after_rollback"] = sorted(отданные)
        # Сверяется с МАНИФЕСТОМ точки, а не с отпечатком её файла: файл в парке
        # общий на все витрины, манифест — свой у каждой.
        ожидаемый_релиз = _релиз_манифеста(прежний.get("manifest_content"))
        совпала_структура, различия = _сверить_структуру(
            _снимок_отданного(здоровье), прежний.get("served_snapshot"))
        запись["baseline_release_match"] = (
            all(ожидаемый_релиз.values())
            and _объявленные(здоровье) == {_ключ_релиза(ожидаемый_релиз)})
        запись["baseline_structure_match"] = совпала_структура
        запись["baseline_structure_diff"] = различия
        запись["baseline_fingerprint_match"] = (
            запись["baseline_release_match"] and запись["baseline_structure_match"])
        запись["verdict"] = "ROLLED_BACK_NO_CHANGE"
    else:
        запись["verdict"] = "DEPLOYED_AND_VERIFIED"
    _напечатать(запись, арг.record)
    return 0 if запись["verdict"] == "DEPLOYED_AND_VERIFIED" else 1


def откатить(арг) -> int:
    витрина = ВИТРИНЫ.get(арг.site)
    if not витрина:
        raise Отказ(f"витрина {арг.site!r} вне перечня: {sorted(ВИТРИНЫ)}")
    точка = Path(арг.point)
    if not (точка / "lords-frontend.py").is_file() or not (точка / "point.json").is_file():
        raise Отказ(f"точка отката неполна: {точка}")
    сохранено = json.loads((точка / "point.json").read_text(encoding="utf-8"))
    манифест = ФРОНТ / витрина["manifest"]
    было = _sha(АРТЕФАКТ) if АРТЕФАКТ.is_file() else ""
    прежний_релиз = _релиз_манифеста(
        json.loads(манифест.read_text(encoding="utf-8")) if манифест.is_file() else None)

    if сохранено.get("manifest_content") is not None:
        _атомарно(манифест, (json.dumps(сохранено["manifest_content"],
                                        ensure_ascii=False, indent=2) + "\n").encode())
    _атомарно(АРТЕФАКТ, (точка / "lords-frontend.py").read_bytes())
    АРТЕФАКТ.chmod(0o755)
    ок, вывод = _юнит("restart", витрина["unit"])
    time.sleep(ПАУЗА_ПОСЛЕ_ПЕРЕЗАПУСКА)

    ожидаемый_релиз = _релиз_манифеста(сохранено.get("manifest_content"))
    схождение = _дождаться_релиза(витрина["domain"], ожидаемый_релиз, прежний_релиз)
    здоровье = схождение["health"] or {"domain": витрина["domain"], "checks": [], "ok": False}

    # Отпечаток ФАЙЛА на диске и отпечаток, ОТДАННЫЙ домену, — разные величины,
    # и раньше их сравнивали друг с другом. Исполняемый файл в парке ОДИН на все
    # витрины, а манифест — свой у каждой: после выката соседней витрины файл на
    # диске законно принадлежит другой сборке, чем объявленный этой витриной
    # релиз. Их равенство было совпадением, и его отсутствие роняло полностью
    # удавшийся откат. Утверждений теперь три, и обязательны все:
    #   диск      — файл вернули;
    #   релиз     — домен объявляет ИМЕННО манифест точки отката, целиком;
    #   структура — ИЗМЕРЕННАЯ страница совпала с тем, что домен отдавал до
    #               установки; манифестом такое совпадение не подделать.
    отданные = {п.get("artifact") for п in здоровье.get("checks", []) if п.get("artifact")}
    совпала_структура, различия = _сверить_структуру(
        _снимок_отданного(здоровье), сохранено.get("served_snapshot"))
    запись = {
        "action": "rollback", "site": арг.site, "point": str(точка),
        "artifact_before_rollback": было,
        "artifact_after_rollback": _sha(АРТЕФАКТ),
        "expected_artifact": сохранено["artifact_sha256"],
        "expected_release": ожидаемый_релиз,
        "served_release": _объявленные_имена(здоровье),
        "served_artifact_after_rollback": sorted(отданные),
        "restored_manifest": сохранено.get("manifest_content"),
        "restart_ok": ок, "restart_output": вывод,
        "convergence": схождение,
        "cache_diagnostic": _кэш_диагностика(витрина["domain"]),
        "health": здоровье, "at_utc": _сейчас(),
    }
    запись["disk_fingerprint_match"] = (
        запись["artifact_after_rollback"] == сохранено["artifact_sha256"])
    # Пустое не равно пустому: точка без манифеста объявляет пустой релиз, и
    # молчащий домен «совпал» бы с ней. Ожидаемый релиз обязан быть заполнен.
    запись["served_release_match"] = (
        all(ожидаемый_релиз.values())
        and _объявленные(здоровье) == {_ключ_релиза(ожидаемый_релиз)})
    запись["served_structure_match"] = совпала_структура
    запись["structure_diff"] = различия
    if not сохранено.get("served_snapshot"):
        # Точка прежнего образца структуру доказать не может — значит не
        # доказывает. Откат при этом выполнен; недоказанным объявлен вердикт.
        запись["served_structure_reason"] = "POINT_WITHOUT_SERVED_SNAPSHOT"
    запись["served_fingerprint_match"] = (
        запись["served_release_match"] and запись["served_structure_match"])
    запись["verdict"] = (
        "ROLLED_BACK_VERIFIED"
        if (запись["disk_fingerprint_match"] and запись["served_fingerprint_match"]
            and ок and здоровье.get("ok")) else "ROLLBACK_FAILED")
    _напечатать(запись, арг.record)
    return 0 if запись["verdict"] == "ROLLED_BACK_VERIFIED" else 1


def состояние(арг) -> int:
    витрина = ВИТРИНЫ.get(арг.site) or {}
    запись = {
        "action": "status", "site": арг.site,
        "artifact_sha256": _sha(АРТЕФАКТ) if АРТЕФАКТ.is_file() else "",
        "manifest": json.loads((ФРОНТ / витрина["manifest"]).read_text(encoding="utf-8"))
        if витрина and (ФРОНТ / витрина["manifest"]).is_file() else None,
        "health": _проба(витрина["domain"]) if витрина else None,
        "rollback_points": sorted(п.name for п in ОТКАТЫ.glob("*") if п.is_dir()),
    }
    _напечатать(запись, арг.record)
    return 0


def _напечатать(запись: dict, куда: str | None) -> None:
    global ПОСЛЕДНЯЯ_ЗАПИСЬ
    ПОСЛЕДНЯЯ_ЗАПИСЬ = запись
    текст = json.dumps(запись, ensure_ascii=False, indent=1)
    if куда:
        Path(куда).parent.mkdir(parents=True, exist_ok=True)
        Path(куда).write_text(текст + "\n", encoding="utf-8")
    print(текст)


def main(argv=None) -> int:
    разбор = argparse.ArgumentParser(description=__doc__)
    под = разбор.add_subparsers(dest="команда", required=True)

    у = под.add_parser("install", help="выложить артефакт на витрину")
    у.add_argument("--site", required=True)
    у.add_argument("--artifact", required=True)
    у.add_argument("--expect-sha256", required=True,
                   help="ожидаемый sha256 артефакта; без него установка не начинается")
    у.add_argument("--design-version", required=True)
    у.add_argument("--commit", required=True)
    у.add_argument("--build-id", required=True)
    у.add_argument("--record")
    у.set_defaults(функция=установить)

    о = под.add_parser("rollback", help="вернуть сохранённую точку")
    о.add_argument("--site", required=True)
    о.add_argument("--point", required=True)
    о.add_argument("--record")
    о.set_defaults(функция=откатить)

    с = под.add_parser("status", help="что сейчас установлено")
    с.add_argument("--site", required=True)
    с.add_argument("--record")
    с.set_defaults(функция=состояние)

    арг = разбор.parse_args(argv)
    try:
        return арг.функция(арг)
    except Отказ as ош:
        print(f"ОТКАЗ: {ош}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
