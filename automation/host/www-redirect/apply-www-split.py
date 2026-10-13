#!/usr/bin/env python3
"""Развести www-зеркало и основной хост в четырёх конфигурациях nginx.

Правка состоит из ДВУХ частей, и вторая без первой бесполезна:

1. дописать блок `server`, который перенаправляет `www.<домен>` на основной хост
   (готовые вставки лежат рядом: `*-www.conf.add`);
2. убрать `www.<домен>` из `server_name` блока **443** основного файла.

Если забыть второе, nginx скажет `conflicting server name`, победит первый
подходящий блок, перенаправления не будет — а выглядеть будет сделанным.

Почему это сценарий, а не `sed` в руках владельца. У `zona-02.conf` **два**
блока с одинаковой строкой `server_name zonafilm.cc www.zonafilm.cc;`: порт 80 и
порт 443. Из блока 80 имя `www.` убирать НЕЛЬЗЯ — именно он перенаправляет
`http://www` на https. Глобальная замена по файлу сломала бы это молча, а
замена по номеру строки сломается при любой правке файла. Здесь правка
применяется к блоку, выбранному по его `listen`.

Что сценарий делает и чего не делает:

* делает копию каждого файла, который трогает, с отметкой времени;
* проверяет `nginx -t` ПОСЛЕ правки и ДО перезагрузки; не прошло — возвращает
  все файлы из копий и выходит с кодом 1;
* перезагружает nginx только по отдельному флагу `--reload`;
* **не** меняет сертификаты, маршруты в контейнеры, режим индексации и
  подтверждение прав в Вебмастере;
* повторный запуск ничего не меняет: обе части правки распознаются как сделанные.

    python3 automation/host/www-redirect/apply-www-split.py            # только показать
    sudo python3 automation/host/www-redirect/apply-www-split.py --apply
    sudo python3 automation/host/www-redirect/apply-www-split.py --apply --reload
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

КАТАЛОГ = Path("/etc/nginx/lords")
ВСТАВКИ = Path(__file__).resolve().parent
#: Файл → (домен, готовая вставка). Перечень равен набору вставок рядом и не
#: угадывается: лишний домен здесь означал бы правку конфигурации, которую
#: никто не готовил.
ЦЕЛИ: tuple[tuple[str, str, str], ...] = (
    ("animego-04-tls.conf", "an1meg0.site", "animego-04-www.conf.add"),
    ("lords-05-tls.conf", "lordserials22.info", "lords-05-www.conf.add"),
    ("zona-03-tls.conf", "zonafilm12.site", "zona-03-www.conf.add"),
    ("zona-02.conf", "zonafilm.cc", "zona-02-www.conf.add"),
)


def блоки(текст: str) -> list[tuple[str, int, int]]:
    """(порт, начало тела, конец тела) для каждого блока `server`."""
    итог: list[tuple[str, int, int]] = []
    for м in re.finditer(r"^server\s*\{", текст, flags=re.M):
        начало = м.end()
        конец = текст.find("\n}", начало)
        if конец == -1:
            continue
        тело = текст[начало:конец]
        порты = re.findall(r"^\s*listen\s+(?:\[::\]:)?(\d+)", тело, re.M)
        итог.append((порты[0] if порты else "?", начало, конец))
    return итог


def убрать_www(текст: str, домен: str) -> tuple[str, str]:
    """Убрать `www.<домен>` из `server_name` блока 443. (новый текст, что сделано)."""
    www = f"www.{домен}"
    for порт, начало, конец in блоки(текст):
        if порт != "443":
            continue
        тело = текст[начало:конец]
        м = re.search(r"^(\s*)server_name\s+([^;]+);", тело, re.M)
        if not м:
            continue
        перечень = м.group(2).split()
        if перечень == [www]:
            # Это сам блок перенаправления: его имя и должно быть ровно www.
            continue
        if www not in перечень:
            return текст, "блок 443 уже без www"
        остаток = [и for и in перечень if и != www]
        if not остаток:
            return текст, ("ОТКАЗ: в блоке 443 кроме www имён не осталось — "
                           "правка сделала бы основной хост недоступным")
        новое = f"{м.group(1)}server_name {' '.join(остаток)};"
        новое_тело = тело[:м.start()] + новое + тело[м.end():]
        return текст[:начало] + новое_тело + текст[конец:], (
            f"из блока 443 убрано {www}")
    return текст, "блока 443 с основным именем не найдено"


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--apply", action="store_true",
                   help="применить правку; без флага только показать")
    р.add_argument("--reload", action="store_true",
                   help="перезагрузить nginx после успешного nginx -t")
    р.add_argument("--dir", type=Path, default=КАТАЛОГ,
                   help="каталог конфигураций (для стенда)")
    а = р.parse_args()

    if not а.dir.is_dir():
        print(f"каталога конфигураций нет: {а.dir} — НЕ ИЗМЕРЕНО")
        return 2

    отметка = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    копии: list[tuple[Path, Path]] = []
    тронуто = 0
    for файл, домен, вставка in ЦЕЛИ:
        путь = а.dir / файл
        источник = ВСТАВКИ / вставка
        print(f"\n=== {файл}  ({домен})")
        if not путь.is_file():
            print(f"   файла нет: {путь} — пропуск, это НЕ «сделано»")
            continue
        if not источник.is_file():
            print(f"   вставки нет: {источник} — пропуск")
            continue
        текст = путь.read_text(encoding="utf-8")
        добавка = источник.read_text(encoding="utf-8")

        нужен_блок = f"server_name www.{домен};" not in текст
        print(f"   блок перенаправления: "
              f"{'надо дописать' if нужен_блок else 'уже есть'}")
        новый = текст + ("\n" + добавка if нужен_блок else "")
        новый, что = убрать_www(новый, домен)
        print(f"   server_name 443: {что}")
        if что.startswith("ОТКАЗ"):
            print("   файл не меняется")
            continue
        if новый == текст:
            print("   менять нечего")
            continue
        if not а.apply:
            print("   (показ; для правки нужен --apply)")
            continue
        копия = путь.with_name(f"{файл}.bak-www-{отметка}")
        shutil.copy2(путь, копия)
        копии.append((путь, копия))
        путь.write_text(новый, encoding="utf-8")
        тронуто += 1
        print(f"   правка применена, копия: {копия.name}")

    if not а.apply:
        print("\nничего не изменено: нужен --apply")
        return 0
    if not тронуто:
        print("\nправка уже на месте: файлы не менялись")
        return 0

    проверка = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
    print(f"\nnginx -t: код {проверка.returncode}")
    print((проверка.stderr or проверка.stdout or "").strip()[:600])
    if проверка.returncode != 0:
        for путь, копия in копии:
            shutil.copy2(копия, путь)
        print("\nПРОВЕРКА НЕ ПРОШЛА — все файлы возвращены из копий. "
              "nginx не перезагружался, конфигурация та же, что была.")
        return 1

    if а.reload:
        г = subprocess.run(["systemctl", "reload", "nginx"],
                           capture_output=True, text=True)
        print(f"systemctl reload nginx: код {г.returncode} "
              f"{(г.stderr or '').strip()[:200]}")
        if г.returncode != 0:
            print("перезагрузка не удалась; файлы НЕ возвращены — "
                  "конфигурация проверена, разбирайтесь с перезагрузкой")
            return 1
    else:
        print("перезагрузка не делалась: нужен --reload "
              "(до неё правка на сайте не действует)")
    print("\nпроверка результата: "
          "python3 automation/host/www-redirect/check-server-names.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
