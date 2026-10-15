#!/usr/bin/env python3
"""Готовит правку nginx: `http → https` и `www → апекс` на живых доменах.

Зачем инструмент, а не текст в документе. Оба дефекта измерены (2026-10-15):
девять опубликованных доменов отдают 200 по `http://` без перенаправления, и у
четырёх из них имя `www` стоит в `server_name` блока апекса — поисковик видит
два сайта с одним содержимым, причём теперь, когда сеть открыта к индексации,
в индекс попадают оба адреса. Правка у обоих дефектов ОДНА И ТА ЖЕ и делается
в одном файле на домен, поэтому и операция владельцу нужна одна, а не две.

Почему генератор. Владельцу нужен файл, который можно проверить `nginx -t`, а
не инструкция «добавьте блок»: прошлая правка руками уже оставила в `lords/`
блок 443 со ссылкой на несуществующий сертификат, и nginx тогда не
перезагрузился целиком — то есть ошибка одного домена роняет соседние.
Инструмент читает ДЕЙСТВУЮЩУЮ конфигурацию, применяет ровно два текстовых
преобразования и кладёт результат рядом, ничего не меняя в `/etc/nginx`.

Образец взят не из головы: ровно так устроены уже работающие домены этого же
узла (`/etc/nginx/sites-enabled/yummyani.biz.conf`) — `308` вместо `301`
(сохраняет метод и тело, POST не вырождается в GET), ACME остаётся доступен по
`http`, `www` отдельным блоком на 443 со своим сертификатом.

Запуск (ничего не меняет, только пишет в `var/staged-nginx/`):

    python3 automation/local/stage-https-www-fix.py
    python3 automation/local/stage-https-www-fix.py --domain zonafilm.cc --diff
"""
from __future__ import annotations

import argparse
import difflib
import pathlib
import re
import subprocess
import sys

КОРЕНЬ_NGINX = pathlib.Path("/etc/nginx")
КОРЕНЬ_РЕПО = pathlib.Path(__file__).resolve().parents[2]
ВЫХОД = КОРЕНЬ_РЕПО / "var" / "staged-nginx"

#: Домены, у которых дефект ИЗМЕРЕН. Список не догадка и не «все живые»:
#: восемь доменов сети уже отвечают 308 на `http://`, и трогать их файлы
#: незачем. Проверка — `scratchpad/д24-http-на-https.py` и приёмка
#: `automation/local/public-acceptance.py`.
ДОМЕНЫ_HTTP = (
    "animedia.icu", "animedia.space", "an1meg0.site", "lordserials22.info",
    "yummyani7.site", "yummyani7.info", "zonafilm.space", "zonafilm.cc",
    "zonafilm12.site",
)

#: Домены, у которых `www` ОТДАЁТ САЙТ с canonical на сам www-хост. Отдельный
#: список: у трёх доменов выше имени `www` в DNS нет вовсе, и блок для него
#: был бы конфигурацией для несуществующего имени. Измерено по 17 доменам
#: (14 — этой сессией, 3 — SEO-сессией, оба измерения сошлись).
ДОМЕНЫ_WWW = ("an1meg0.site", "lordserials22.info", "zonafilm.cc",
              "zonafilm12.site")

#: `www` отвечает 200, но canonical ведёт на апекс: сигнал поисковику верный,
#: адресов всё же два. Правка та же, срочность ниже — поэтому отдельно.
ДОМЕНЫ_WWW_МЯГКО = ("yummyani7.site", "yummyani7.info")


class НеПрименимо(RuntimeError):
    """Преобразование не подходит к этому файлу. Молча не применяется."""


def блоки(текст: str) -> list[tuple[int, int, str]]:
    """Границы каждого `server { … }` в тексте: (начало, конец, тело).

    Разбор по фигурным скобкам, а не регулярным выражением: вложенные
    `location` и `map` регулярным выражением не разбираются, а ошибка границы
    здесь означала бы испорченную конфигурацию живого домена.
    """
    итог = []
    for м in re.finditer(r"(?m)^server\s*\{", текст):
        глубина = 0
        i = м.start()
        j = текст.index("{", i)
        while j < len(текст):
            if текст[j] == "{":
                глубина += 1
            elif текст[j] == "}":
                глубина -= 1
                if глубина == 0:
                    итог.append((i, j + 1, текст[i:j + 1]))
                    break
            j += 1
    return итог


def имена(тело: str) -> list[str]:
    м = re.search(r"server_name\s+([^;]+);", тело)
    return м.group(1).split() if м else []


def порты(тело: str) -> set[str]:
    return set(re.findall(r"listen\s+(\d+)", тело))


def перенаправить_порт_80(файл: pathlib.Path, апекс: str) -> str:
    """Блок порта 80 отдаёт 308 на https, сохраняя ACME и /healthz.

    ACME остаётся доступным по `http` НЕ для удобства: подтверждение владения
    именем идёт по этому пути, и перенаправление его в https сломало бы
    продление сертификата. `/healthz` оставлен как есть — его может опрашивать
    сторонний монитор, и превращать статус в переход значило бы менять чужой
    контракт заодно с этой правкой.
    """
    текст = файл.read_text(encoding="utf-8")
    правленые = []
    for начало, _, тело in блоки(текст):
        if "80" not in порты(тело) or апекс not in имена(тело):
            continue
        if f"return 308 https://{апекс}" in тело:
            raise НеПрименимо(f"{файл.name}: блок 80 уже перенаправляет")
        м = re.search(r"(?ms)^(\s*)location / \{.*?^\1\}", тело)
        if not м:
            raise НеПрименимо(f"{файл.name}: в блоке 80 нет location /")
        отступ = м.group(1)
        новый = (
            f"{отступ}# 308, а не 301: сохраняет метод и тело запроса — POST\n"
            f"{отступ}# не вырождается в GET. Так же устроены уже работающие\n"
            f"{отступ}# домены этого узла.\n"
            f"{отступ}location / {{\n"
            f"{отступ}    return 308 https://{апекс}$request_uri;\n"
            f"{отступ}}}")
        правленые.append((начало + м.start(), начало + м.end(), новый))
    if not правленые:
        raise НеПрименимо(f"{файл.name}: блока порта 80 для {апекс} не найдено")
    for начало, конец, новый in reversed(правленые):
        текст = текст[:начало] + новый + текст[конец:]
    return текст


def www_отдельным_блоком(текст: str, файл: pathlib.Path, апекс: str) -> str:
    """Убирает `www` из блоков апекса и добавляет ему свой блок с 308.

    Сертификат обязан покрывать имя `www`, иначе блок 443 не поднимется и
    nginx не перезагрузится ВОВСЕ — то есть ошибка одного домена уронит
    соседние. Покрытие проверяется у живого хоста отдельной функцией, и без
    подтверждения блок не создаётся.
    """
    было = текст
    доб = []
    правки = []
    for начало, _, тело in блоки(текст):
        им = имена(тело)
        if f"www.{апекс}" not in им:
            continue
        if "443" not in порты(тело):
            # В блоке ПОРТА 80 имя www остаётся. Это не недоделка: проверка
            # владения именем (http-01) идёт на порт 80, и, убрав www из
            # server_name, запрос ACME для него попал бы в блок отказа по
            # умолчанию — продление сертификата, который имя www покрывает,
            # сломалось бы при следующем сроке. Содержимое по http оно всё
            # равно не отдаёт: location / отвечает 308 на апекс.
            continue
        # Правка по СМЕЩЕНИЮ блока, а не `текст.replace`: строка
        # `server_name <апекс> www.<апекс>;` у блоков 80 и 443 буква в букву
        # одна и та же, и замена по тексту сработала по первому вхождению —
        # имя www уходило из блока порта 80, ломая продление сертификата.
        м = re.search(r"server_name\s+[^;]+;", тело)
        правки.append((начало + м.start(), начало + м.end(),
                       f"server_name {апекс};"))
        серт = re.search(r"(?m)^\s*ssl_certificate\s+(\S+);", тело)
        ключ = re.search(r"(?m)^\s*ssl_certificate_key\s+(\S+);", тело)
        if not (серт and ключ):
            raise НеПрименимо(f"{файл.name}: в блоке 443 нет ssl_certificate")
        доб.append(f"""
# `www` отдельным блоком: одно каноническое имя, один сайт в индексе.
# До этой правки имя www стояло в server_name блока апекса, поэтому отдавало
# тот же сайт с canonical на сам www-хост — поисковик видел два сайта.
server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name www.{апекс};

    ssl_certificate     {серт.group(1)};
    ssl_certificate_key {ключ.group(1)};
    ssl_protocols TLSv1.2 TLSv1.3;

    server_tokens off;
    # Заголовка индексации здесь нет намеренно: блок только перенаправляет, а
    # переменная режима (`$cell_robots_*`) объявлена `map`-ом в файле витрины.
    # Сослаться на неё из файла, где её нет, значит получить «unknown
    # variable» — nginx не перезагрузится вовсе и уронит соседние домены.

    location ^~ /.well-known/acme-challenge/ {{
        root /var/www/certbot;
        default_type "text/plain";
    }}

    location / {{
        return 308 https://{апекс}$request_uri;
    }}
}}
""")
    for начало, конец, новое_имя in reversed(правки):
        текст = текст[:начало] + новое_имя + текст[конец:]
    if текст == было and not доб:
        raise НеПрименимо(f"{файл.name}: имени www.{апекс} в конфигурации нет")
    return текст + "".join(доб)


def сертификат_покрывает_www(домен: str) -> bool:
    """Покрывает ли ПРЕДЪЯВЛЯЕМЫЙ сертификат имя `www`.

    Читается у живого хоста, а не в `/etc/letsencrypt`: каталог под root, и
    догадка здесь стоила бы владельцу неперезагружаемого nginx.
    """
    try:
        г = subprocess.run(
            ["openssl", "s_client", "-connect", f"{домен}:443",
             "-servername", домен, "-showcerts"],
            input="", capture_output=True, text=True, timeout=30)
        т = subprocess.run(["openssl", "x509", "-noout", "-text"],
                           input=г.stdout, capture_output=True, text=True,
                           timeout=30).stdout
        м = re.search(r"X509v3 Subject Alternative Name:\s*\n\s*(.+)", т)
        return bool(м) and f"DNS:www.{домен}" in м.group(1)
    except Exception:  # noqa: BLE001
        return False


def файлы_домена(домен: str) -> list[pathlib.Path]:
    найдено = []
    for каталог in ("lords", "sites-enabled"):
        п = КОРЕНЬ_NGINX / каталог
        if not п.is_dir():
            continue
        for ф in sorted(п.glob("*.conf")):
            if ".bak" in ф.name:
                continue
            try:
                т = ф.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if any(домен in имена(тело) or f"www.{домен}" in имена(тело)
                   for _, _, тело in блоки(т)):
                найдено.append(ф)
    return найдено


def подготовить(домен: str, *, печатать_diff: bool = False) -> dict:
    """Готовит файлы домена и говорит, какие правки ФАКТИЧЕСКИ сделаны.

    Отчёт идёт по ДОМЕНУ, а не по файлу. У половины доменов блок 443 вынесен
    в отдельный `-tls.conf`: там нет блока порта 80, а в основном файле нет
    блока 443 — и то и другое нормально. Пока инструмент печатал это как «не
    сделано» и возвращал код 1, он сообщал о беде там, где её нет, а на
    настоящую нехватку (сертификат без имени www) владелец перестал бы
    смотреть.
    """
    итог = {"domain": домен, "files": [], "problems": [],
            "http_redirect": False, "www_block": False}
    нужен_www = домен in ДОМЕНЫ_WWW + ДОМЕНЫ_WWW_МЯГКО
    покрыт = сертификат_покрывает_www(домен) if нужен_www else False
    итог["cert_covers_www"] = покрыт
    файлы = файлы_домена(домен)
    if not файлы:
        итог["problems"].append(
            f"{домен}: конфигурации с этим именем в /etc/nginx не найдено — "
            "правка не подготовлена")
        return итог
    for ф in файлы:
        было = ф.read_text(encoding="utf-8")
        try:
            новый = перенаправить_порт_80(ф, домен)
            итог["http_redirect"] = True
        except НеПрименимо:
            новый = было          # блока 80 в этом файле нет — не его работа
        if нужен_www and покрыт:
            try:
                новый = www_отдельным_блоком(новый, ф, домен)
                итог["www_block"] = True
            except НеПрименимо:
                pass              # блока 443 с именем www в этом файле нет
        if новый == было:
            continue
        ВЫХОД.mkdir(parents=True, exist_ok=True)
        цель = ВЫХОД / ф.name
        цель.write_text(новый, encoding="utf-8")
        итог["files"].append(str(цель.relative_to(КОРЕНЬ_РЕПО)))
        if печатать_diff:
            sys.stdout.writelines(difflib.unified_diff(
                было.splitlines(keepends=True),
                новый.splitlines(keepends=True),
                fromfile=str(ф), tofile=str(цель)))
    if not итог["http_redirect"]:
        итог["problems"].append(
            f"{домен}: блок порта 80 не найден или уже перенаправляет — "
            "перенаправление http не подготовлено")
    if нужен_www and not покрыт:
        итог["problems"].append(
            f"{домен}: блок www НЕ создан — предъявляемый сертификат имени "
            f"www.{домен} не покрывает. Сначала расширить сертификат "
            f"(certbot certonly --webroot -w /var/www/certbot -d {домен} "
            f"-d www.{домен} --cert-name {домен}), иначе nginx не "
            "перезагрузится вовсе")
    elif нужен_www and not итог["www_block"]:
        итог["problems"].append(
            f"{домен}: сертификат имя www покрывает, но блок 443 с этим "
            "именем в конфигурации не найден — правка www не подготовлена")
    return итог


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domain", action="append", default=[],
                   help="только этот домен (можно повторять)")
    р.add_argument("--diff", action="store_true", help="печатать unified diff")
    а = р.parse_args()
    домены = а.domain or list(dict.fromkeys(ДОМЕНЫ_HTTP + ДОМЕНЫ_WWW
                                            + ДОМЕНЫ_WWW_МЯГКО))
    беда = 0
    for домен in домены:
        итог = подготовить(домен, печатать_diff=а.diff)
        готово = ", ".join(итог["files"]) or "ничего не изменено"
        правки = ["http → https" if итог["http_redirect"] else ""]
        if домен in ДОМЕНЫ_WWW + ДОМЕНЫ_WWW_МЯГКО:
            правки.append("www → апекс" if итог["www_block"] else "")
        print(f"{домен}: {готово} | "
              + ", ".join(п for п in правки if п))
        for с in итог["problems"]:
            print(f"    ТРЕБУЕТ ВНИМАНИЯ: {с}")
            беда = 1
    print(f"\nфайлы готовы в {ВЫХОД.relative_to(КОРЕНЬ_РЕПО)}; "
          "в /etc/nginx ничего не изменено. Порядок установки — "
          "docs/OWNER_HTTPS_WWW_20261015.md")
    return беда


if __name__ == "__main__":
    sys.exit(main())
