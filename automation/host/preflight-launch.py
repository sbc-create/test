#!/usr/bin/env python3
"""Проверка входных данных команды запуска ДО передачи её владельцу.

    python3 automation/host/preflight-launch.py --package <пакет> --site zona-03

Смысл: команда с правами root не должна проверяться на владельце. Прошлая
команда запуска содержала два дефекта, которые проявились бы при первом же
применении, — относительный путь к реестру и круг в зависимостях nginx.
Оба нашлись чтением, а не запуском, и именно это здесь автоматизировано.

Каждая проверка отвечает на вопрос «эта команда сможет выполнить свой шаг?».
Ни одна не меняет состояние: скрипт работает без root и без записи.
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import shutil
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent.parent
if not (КОРЕНЬ / "factory" / "cell" / "executor.py").is_file():
    raise SystemExit(f"не похоже на репозиторий фабрики: {КОРЕНЬ}")

ок: list[str] = []
плохо: list[str] = []
внимание: list[str] = []


def проверка(условие: bool, текст: str, мягко: bool = False) -> bool:
    (ок if условие else (внимание if мягко else плохо)).append(текст)
    return условие


def порты_хоста() -> set[int]:
    занято: set[int] = set()
    for имя in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            for строка in Path(имя).read_text(encoding="utf-8").splitlines()[1:]:
                поля = строка.split()
                if len(поля) > 3 and поля[3] == "0A":  # LISTEN
                    занято.add(int(поля[1].split(":")[1], 16))
        except OSError:
            continue
    return занято


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--package", required=True)
    р.add_argument("--site", required=True)
    а = р.parse_args()

    пакет = Path(а.package).resolve()
    опись_п = пакет / "manifest.json"
    if not опись_п.is_file():
        print(f"это не зафиксированный пакет: нет {опись_п}")
        return 2
    опись = json.loads(опись_п.read_text(encoding="utf-8"))
    дерево = пакет / "tree"
    сайт = а.site

    print(f"пакет {опись['package_id']}, коммит {опись['commit'][:12]}, файлов {опись['file_count']}")
    print(f"проверяю запуск {сайт}\n")

    # 1. реестр ячеек внутри ПАКЕТА, а не в рабочей ветке
    реестр_п = дерево / "config" / "site-cells.json"
    if not проверка(реестр_п.is_file(), f"реестр ячеек есть в пакете: {реестр_п.name}"):
        итог()
        return 1
    реестр = json.loads(реестр_п.read_text(encoding="utf-8"))
    ячейки = {c["site_id"]: c for c in реестр.get("cells") or []}
    if not проверка(сайт in ячейки, f"{сайт} объявлен в реестре пакета"):
        итог()
        return 1
    я = ячейки[сайт]
    рв = я.get("runtime") or {}

    проверка(я.get("status") == "planned",
             f"статус в реестре 'planned' (сейчас {я.get('status')!r}) — иначе --new-site откажет")
    for поле in ("unit", "port", "account"):
        проверка(bool(рв.get(поле)), f"runtime.{поле} заполнен: {рв.get(поле)!r}")
    домен = я.get("domain") or ""
    проверка(bool(домен), f"домен объявлен: {домен!r}")

    # 2. порт свободен и не пересекается с чужой ячейкой
    порт = int(рв.get("port") or 0)
    чужие = {int((c.get("runtime") or {}).get("port") or 0): c["site_id"]
             for c in реестр.get("cells") or [] if c["site_id"] != сайт}
    проверка(порт not in чужие, f"порт {порт} не занят другой ячейкой"
             + (f" (занят {чужие.get(порт)})" if порт in чужие else ""))
    проверка(порт + 1000 not in чужие, f"порт кандидата {порт + 1000} не занят другой ячейкой")
    занято = порты_хоста()
    проверка(порт not in занято, f"на хосте никто не слушает {порт}")
    проверка(порт + 1000 not in занято, f"на хосте никто не слушает {порт + 1000}")

    # 3. заготовки nginx в пакете и их содержание
    http_п = дерево / "automation" / "host" / "nginx-site" / f"{сайт}.conf"
    tls_п = дерево / "automation" / "host" / "nginx-site" / f"{сайт}-tls.conf"
    upstream = "cell_" + re.sub(r"[.-]", "_", сайт)
    if проверка(http_п.is_file(), f"заготовка nginx в пакете: {http_п.name}"):
        текст = http_п.read_text(encoding="utf-8")
        проверка(f"proxy_pass http://{upstream}" in текст,
                 f"заготовка ходит через upstream {upstream}, а не напрямую в порт")
        проверка(f"server_name {домен}" in текст, f"server_name содержит {домен}")
        проверка("noindex" in текст, "индексация закрыта заголовком в HTTP-блоке")
        проверка("acme-challenge" in текст, "путь ACME объявлен: certbot сможет подтвердить домен")
    if проверка(tls_п.is_file(), f"заготовка HTTPS в пакете: {tls_п.name}"):
        текст = tls_п.read_text(encoding="utf-8")
        проверка(f"/etc/letsencrypt/live/{домен}/fullchain.pem" in текст,
                 "путь сертификата соответствует основному домену")
        проверка("noindex" in текст, "индексация закрыта и в блоке 443")
        проверка(f"proxy_pass http://{upstream}" in текст, f"блок 443 идёт через {upstream}")

    # 4. сценарии, которые команда вызовет
    for отн in ("automation/host/install-cell-executor.sh",
                "automation/host/install-cell-units.py",
                "automation/host/install-publisher-cell-paths.sh",
                "automation/host/launch-new-site.sh",
                "automation/host/install-site-nginx.sh",
                "automation/host/install-site-tls.sh",
                "automation/host/freeze-package.py"):
        проверка((дерево / отн).is_file(), f"в пакете есть {Path(отн).name}")

    # 5. состояние хоста: юнитов и конфигурации ещё нет — это первый запуск
    юниты = Path("/etc/systemd/system")
    основной = юниты / (рв.get("unit") or "нет")
    проверка(not основной.exists(), f"юнита {основной.name} ещё нет (шаг 1 его создаст)")
    conf = Path("/etc/nginx/lords") / f"{сайт}.conf"
    проверка(not conf.exists(), f"конфигурации {conf.name} ещё нет (шаг 2 её поставит)")
    проверка(Path("/etc/nginx/lords").is_dir(), "каталог /etc/nginx/lords существует")
    проверка(Path("/var/www/certbot").is_dir(), "webroot /var/www/certbot существует")
    проверка(shutil.which("certbot") is not None, "certbot установлен")
    проверка(shutil.which("nginx") is not None, "nginx установлен")

    # 6. рабочая копия репозитория сайта — там, куда будет смотреть исполнитель
    корень_репо = Path(опись.get("site_repos_root") or "")
    проверка(корень_репо.is_dir(), f"site_repos_root описи существует: {корень_репо}")
    путь_репо = корень_репо / ((я.get("repo") or {}).get("path") or "")
    проверка(путь_репо.is_dir(), f"репозиторий сайта на месте: {путь_репо}")
    проверка((путь_репо / "tools" / "build_release.py").is_file(),
             "в репозитории есть tools/build_release.py (исполнитель ищет именно его)")
    конфиг_п = путь_репо / "config" / "site.json"
    if проверка(конфиг_п.is_file(), "в репозитории есть config/site.json"):
        конфиг = json.loads(конфиг_п.read_text(encoding="utf-8"))
        окр = конфиг.get("environment") or {}
        ожид = ((я.get("publisher") or {}).get("publisher_id")
                or конфиг.get("publisher_id_expected"))
        проверка(str(ожид or "") == "10261" or сайт != "zona-03",
                 f"publisher_id этого сайта: {ожид!r}")
        # Чужой идентификатор издателя не должен попасть в новый домен.
        другие = {str((c.get("publisher") or {}).get("publisher_id"))
                  for c in реестр.get("cells") or [] if c["site_id"] != сайт}
        проверка(str(ожид) not in другие, f"publisher_id {ожид} не принадлежит другой ячейке")
        проверка(str(окр.get("SITE_ID") or конфиг.get("site_id") or сайт) == сайт,
                 "site_id в конфигурации репозитория совпадает с реестром")
    # Закрытая индексация проверяется по РАНТАЙМУ, а не по наличию файла:
    # robots.txt у этого шаблона не лежит на диске, его отдаёт обработчик.
    # Первая версия проверки искала static/robots.txt и объявила «не готово»
    # исправный репозиторий — искать надо было то, что действительно есть.
    рантайм = next((п for п in (путь_репо / "src").glob("*frontend*.py")), None)
    if проверка(рантайм is not None, "рантайм витрины найден в src/"):
        т = рантайм.read_text(encoding="utf-8")
        проверка('if путь == "/robots.txt"' in т, "рантайм отдаёт /robots.txt сам")
        проверка("Disallow: /" in т, "robots.txt закрывает обход целиком")
        проверка('name="robots" content="noindex, nofollow"' in т,
                 "страницы несут meta robots noindex, nofollow")
    состояние = (я.get("indexing") or {}).get("desired_state")
    проверка(состояние == "CLOSED",
             f"индексация в реестре закрыта: desired_state={состояние!r}")

    # 6b. Снимок каталога у производителя. Без него первый выпуск падает на
    # stage_snapshot «в источнике нет файлов снимка» — ровно так отказал первый
    # выпуск Yummy. Проверка добавлена после того, как этот же дефект
    # обнаружился у zona-03 уже ПОСЛЕ подготовки команды: производитель ведёт
    # свой список витрин, и новый домен в него не попадает сам.
    фронт = Path("/srv/lords/.frontend")
    снимок = фронт / f"{сайт}-catalog.json"
    if not проверка(снимок.is_file(),
                    f"снимок каталога у производителя: {снимок}"):
        издатель = Path("/srv/site-factory/repo/automation/host/nova-catalog-publish.py")
        если_есть = издатель.is_file() and сайт in издатель.read_text(encoding="utf-8", errors="replace")
        плохо.append(
            f"{сайт} {'объявлен' if если_есть else 'НЕ объявлен'} в ВИТРИНЫ издателя "
            f"({издатель}): без записи каталог для домена не собирается, и первый "
            "выпуск откажет на stage_snapshot")

    # 7. DNS: домен и псевдонимы указывают туда же, куда работающая витрина
    образец = "zonafilm.space"
    try:
        ожидаемый = socket.gethostbyname(образец)
    except OSError:
        ожидаемый = ""
        внимание.append(f"не удалось узнать адрес {образец}: DNS не сверен")
    for имя in [домен, *(я.get("aliases") or [])]:
        try:
            адрес = socket.gethostbyname(имя)
        except OSError as ош:
            плохо.append(f"{имя} не разрешается: {ош}")
            continue
        проверка(not ожидаемый or адрес == ожидаемый,
                 f"{имя} -> {адрес}" + ("" if адрес == ожидаемый else f" (ожидался {ожидаемый})"))

    итог()
    return 1 if плохо else 0


def итог() -> None:
    print(f"пройдено: {len(ок)}")
    for и in ок:
        print("   [ок]  ", и)
    if внимание:
        print(f"\nвнимание: {len(внимание)}")
        for и in внимание:
            print("   [ ! ] ", и)
    if плохо:
        print(f"\nНЕ ГОТОВО: {len(плохо)}")
        for и in плохо:
            print("   [нет] ", и)
        print("\nКоманду владельцу передавать нельзя, пока это не устранено.")
    else:
        print("\nВходные данные команды проверены: каждый её шаг выполним.")


if __name__ == "__main__":
    raise SystemExit(main())
