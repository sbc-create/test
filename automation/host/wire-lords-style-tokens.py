#!/usr/bin/env python3
"""Доставить витрине Lords проверку нераскрытых токенов стилей (MOD-216, 4 из 4).

    python3 automation/host/wire-lords-style-tokens.py \
        --target var/site-repos/lordserial33-biz \
        --target var/site-repos/1lordserials1-online [--check] [--dry-run]

Что измерено
------------

`checks/style_tokens.py` есть только у `lordserials22.info`. Дефект, который
она сторожит, общий для семейства: в листе стояло `background:@ALT@`, токена
`alt` в наборе нет, подстановка оставила имя как есть, браузер отбросил
объявление целиком — у рамки превью подборки пропала подложка. В исходнике
`@ALT@` неотличим от рабочего `@INK@`; разница видна только после подстановки.

Почему доставляется не тот файл, что лежит у 22i
------------------------------------------------

Её версия зовёт подстановку ПО ИМЕНИ — `РАНТАЙМ._переменными`. Замер 28.10:
имя у витрин разное, у `lordserial33.biz` и `1lordserials1.online` функция
называется `_подставить`. Доставка файла как есть дала бы падение на
`AttributeError` — ровно то, чем уже кончилась доставка проверок режима
индексации (MOD-219).

Поэтому доставляется переформулированная через ЦЕЛЬ версия
(`automation/host/lords-checks/style_tokens.py`): подстановка выбирается
перебором известных имён и ПРОВЕРЯЕТСЯ поведением — подстановка объявленного
токена обязана убрать его имя из листа. Ни одна не подошла — исход «не
измерено» с названной причиной, а не ложный зелёный.

Ворота: сначала прогнать в копии
--------------------------------

Проверка не «сверяется по признакам», а ЗАПУСКАЕТСЯ на временной копии
витрины. Доставка идёт только если там код 0. Так ворота не дублируют логику
самой проверки и не могут от неё отстать: если проверка научится новому
исходу, ворота узнают об этом тем же прогоном.

Вызов в `checks/run.sh` обёртывается пропуском кода 2 — тем же видом, что у
`www-redirect` и прочих восьми: раннер считает любой ненулевой код провалом,
а «не измерено» провалом не является (правка кода выхода без правки
вызывающего ломает раннер — поправка владельца общего кода 28.10).

Чего инструмент не делает: не правит рантайм, не меняет листов и наборов
токенов, не перезаписывает существующую проверку.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

ИСТОЧНИК = pathlib.Path(__file__).resolve().parent / "lords-checks" / "style_tokens.py"
ИМЯ = "style_tokens.py"
РАННЕР = "checks/run.sh"
ЯКОРЬ_РАННЕРА = 'check "contrast"'
СТРОКА_РАННЕРА = (
    '# Нераскрытые имена токенов в готовой таблице стилей (MOD-216). Код 2 —\n'
    '# «не измерено» (подстановки не нашлось): пропуск, а не провал.\n'
    'check "style-tokens"            bash -c \'python3 checks/style_tokens.py; '
    'rc=$?; [ "$rc" -eq 2 ] && exit 0; exit "$rc"\'\n')


def _прогнать_в_копии(цель: pathlib.Path) -> tuple[int, str]:
    """Положить проверку во временную копию витрины и запустить там."""
    врем = pathlib.Path(tempfile.mkdtemp(prefix="style-tokens-"))
    try:
        копия = врем / "repo"
        shutil.copytree(цель, копия, symlinks=True,
                        ignore=shutil.ignore_patterns(
                            "__pycache__", ".git", "var", "artifacts"))
        (копия / "checks").mkdir(exist_ok=True)
        shutil.copyfile(ИСТОЧНИК, копия / "checks" / ИМЯ)
        готово = subprocess.run(  # noqa: S603
            [sys.executable, str(копия / "checks" / ИМЯ)],
            cwd=копия, capture_output=True, text=True, timeout=600)
        хвост = (готово.stdout + готово.stderr).strip().splitlines()
        return готово.returncode, (хвост[-1][:200] if хвост else "")
    except subprocess.TimeoutExpired:
        return 124, "не уложилась в 600 с"
    finally:
        shutil.rmtree(врем, ignore_errors=True)


def применить(цель: pathlib.Path, писать: bool) -> tuple[str, str]:
    if not ИСТОЧНИК.is_file():
        return "refuse", f"нет источника {ИСТОЧНИК}"
    каталог = цель / "checks"
    if not каталог.is_dir():
        return "refuse", f"нет каталога {каталог}"
    если = каталог / ИМЯ
    раннер = цель / РАННЕР
    уже_файл = если.is_file()
    уже_вызов = раннер.is_file() and "checks/style_tokens.py" in raw(раннер)
    if уже_файл and уже_вызов:
        return "skip", "проверка и её вызов уже на месте"
    if уже_файл and если.read_bytes() != ИСТОЧНИК.read_bytes():
        return "refuse", ("проверка уже есть и отличается от доставляемой — "
                          "чужую работу не перезаписываю")

    код, пояснение = _прогнать_в_копии(цель)
    if код != 0:
        исход = {2: "«не измерено»"}.get(код, f"код {код}")
        return "refuse", (f"прогон в копии витрины дал {исход}: {пояснение}. "
                          "Доставка остановлена: проверка, которая здесь не "
                          "измеряет, защитой не является")

    if not писать:
        что = []
        if not уже_файл:
            что.append(f"checks/{ИМЯ}")
        if not уже_вызов:
            что.append(f"вызов в {РАННЕР}")
        return "ok", ("прогон в копии зелёный; будет доставлено: "
                      + ", ".join(что))

    if not уже_файл:
        shutil.copyfile(ИСТОЧНИК, если)
    if not уже_вызов:
        текст = raw(раннер)
        if текст.count(ЯКОРЬ_РАННЕРА) != 1:
            если.unlink(missing_ok=True)
            return "refuse", (f"якорь вызова в {РАННЕР} найден "
                              f"{текст.count(ЯКОРЬ_РАННЕРА)} раз(а), ожидался 1; "
                              "файл проверки откачен")
        строка = next(с for с in текст.splitlines() if с.startswith(ЯКОРЬ_РАННЕРА))
        раннер.write_text(текст.replace(строка, СТРОКА_РАННЕРА + строка, 1),
                          encoding="utf-8")
    return "ok", f"доставлено и прогнано зелёным: checks/{ИМЯ}, вызов в {РАННЕР}"


def raw(путь: pathlib.Path) -> str:
    return путь.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--target", action="append", required=True)
    р.add_argument("--check", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args()
    отказы = правок = 0
    for путь in а.target:
        цель = pathlib.Path(путь).resolve()
        исход, пояснение = применить(цель, писать=not (а.check or а.dry_run))
        print(f"[{исход:6s}] {цель.name}: {пояснение}")
        if исход == "refuse":
            отказы += 1
        elif исход == "ok":
            правок += 1
    if отказы:
        print(f"ОТКАЗ по {отказы} витринам: причина названа выше")
        return 2
    if а.check:
        return 1 if правок else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
