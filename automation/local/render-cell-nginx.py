#!/usr/bin/env python3
"""Заготовки nginx для новой витрины: HTTP и HTTPS отдельными файлами.

Зачем генератором. Заготовки в `automation/host/nginx-site/` писались по одной
на витрину, и при партии из пяти это пять шансов на опечатку в имени домена,
порте или имени включаемого файла режима индексации. Структура у всех одна и
названа в образце `lords-10.conf`; разное — домен, порт и имя ячейки.

Что генератор НЕ делает:

* не выдумывает DNS: NS и A спрашиваются у зоны ЖИВЫМ запросом (общий модуль
  `dns-probe.py`, своего разбора пакетов здесь нет) и попадают в заголовок
  файла как измерение с датой. Не ответила зона — так и написано;
* не ставит блок 443 в один файл с 80: ссылка на невыпущенный сертификат не
  даёт nginx перезагрузиться ВОВСЕ, то есть уронила бы и соседние витрины.
  Поэтому HTTPS — отдельный файл, который ставится ПОСЛЕ выпуска сертификата;
* не открывает индексацию: заголовок берётся из включаемого файла режима, и
  новая витрина рождается закрытой.

    python3 automation/local/render-cell-nginx.py --site lords-18 [--out <каталог>]
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ВЫХОД = КОРЕНЬ / "automation" / "host" / "nginx-site"


def _днс():
    спец = importlib.util.spec_from_file_location(
        "dns_probe", КОРЕНЬ / "automation" / "local" / "dns-probe.py")
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


def измерить_днс(домен: str) -> dict:
    """NS и A домена живым запросом. Неответ — честная строка, не пропуск."""
    м = _днс()
    итог = {"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}
    for тип in ("NS", "A"):
        try:
            о = м.запрос(домен, тип, м.резолверы()[0])
        except Exception as ош:  # noqa: BLE001 — зона не ответила
            итог[тип] = f"НЕ ИЗМЕРЕНО: {type(ош).__name__}"
            continue
        # Ключи ответа общего модуля — `answers` и `value`. Свои имена здесь
        # однажды дали ложное «НЕ ИЗМЕРЕНО» при исправном ответе зоны: запись
        # «не измерено» там, где измерение есть, хуже отсутствия строки, потому
        # что её читают как факт.
        if о.get("rcode") != "NOERROR" or not о.get("answers"):
            итог[тип] = (f"НЕ ИЗМЕРЕНО: rcode={о.get('rcode')}, "
                         f"ответов {len(о.get('answers') or [])}"
                         + (f", ошибка {о['error']}" if о.get("error") else ""))
            continue
        итог[тип] = ", ".join(str(з.get("value")) for з in о["answers"])
    return итог


def ячейка(site_id: str) -> dict:
    д = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))
    for з in д.get("cells") or []:
        if з.get("site_id") == site_id:
            return з
    raise SystemExit(f"ОТКАЗ: в реестре нет ячейки {site_id}")


def тело_http(site_id: str, домен: str, порт: int, днс: dict) -> str:
    имя = site_id.replace("-", "_")
    return f"""# {домен} — витрина {site_id}.
#
# Только HTTP. Блок 443 ставится отдельным файлом (`{site_id}-tls.conf`) ПОСЛЕ
# выпуска сертификата: ссылка на несуществующий сертификат не даёт nginx
# перезагрузиться вовсе, и ошибка нового домена уронила бы соседние витрины.
#
# DNS измерен {днс['at']} живым запросом к зоне:
#   NS   {днс.get('NS')}
#   A    {днс.get('A')}
#
# Порт витрины {порт} (реестр ячеек), upstream cell_{имя}. Маршрут идёт через
# upstream, а не прямо на 127.0.0.1:{порт}: это точка, которую переставляет
# исполнитель при выкладке, и прямой proxy_pass означал бы, что переключение
# трафика проходит успешно и не делает ничего.

# Значение заголовка индексации. Режим живёт во включаемом файле: менять его
# правкой конфигурации значило бы править её при каждом переключении. Файл
# создаёт install-site-nginx.sh — ЗАКРЫТЫМ.
map $uri $cell_robots_{имя} {{
    include /etc/nginx/cells/{site_id}.robots;
}}

server {{
    listen 80;
    listen [::]:80;
    server_name {домен};

    server_tokens off;

    # Индексация закрыта: у витрины `desired_state: CLOSED`, и выпуск её не
    # разрешает. Открытие — отдельная операция владельца после приёмки.
    add_header X-Robots-Tag $cell_robots_{имя} always;

    location ^~ /.well-known/acme-challenge/ {{
        root /var/www/certbot;
        default_type "text/plain";
    }}

    location / {{ return 301 https://$host$request_uri; }}

    location = /healthz {{
        proxy_pass http://cell_{имя}/healthz;
        access_log off;
    }}
}}

# www — ОТДЕЛЬНЫЙ блок с перенаправлением, а не второе имя рядом с apex: у
# lords-05 такое имя стояло в одном блоке и отдавало каталог кодом 200 с
# canonical на сам www-хост, то есть второй сайт с тем же содержимым.
server {{
    listen 80;
    listen [::]:80;
    server_name www.{домен};

    server_tokens off;
    add_header X-Robots-Tag $cell_robots_{имя} always;

    location ^~ /.well-known/acme-challenge/ {{
        root /var/www/certbot;
        default_type "text/plain";
    }}

    location / {{
        return 301 https://{домен}$request_uri;
    }}
}}
"""


def тело_tls(site_id: str, домен: str) -> str:
    имя = site_id.replace("-", "_")
    return f"""# {домен} — HTTPS. Отдельным файлом и ПОСЛЕ выпуска сертификата: блок 443
# со ссылкой на несуществующий файл не даёт nginx перезагрузиться вовсе, то
# есть роняет и соседние витрины.
#
# Сертификат обязан покрывать ОБА имени ({домен} и www.{домен}): www-блок ниже
# отвечает по HTTPS, и непокрывающий сертификат дал бы на нём ошибку TLS
# вместо перенаправления.
server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name {домен};

    ssl_certificate     /etc/letsencrypt/live/{домен}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{домен}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

    server_tokens off;

    # Тот же включаемый файл режима, что и у блока 80: два источника режима на
    # один домен расходились бы, и расхождение было бы видно только обходу.
    add_header X-Robots-Tag $cell_robots_{имя} always;

    location ^~ /.well-known/acme-challenge/ {{
        root /var/www/certbot;
        default_type "text/plain";
    }}

    location / {{
        proxy_pass http://cell_{имя};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }}

    location = /healthz {{
        proxy_pass http://cell_{имя}/healthz;
        access_log off;
    }}
}}

# www по HTTPS — перенаправление на основной адрес, причина та же.
server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name www.{домен};

    ssl_certificate     /etc/letsencrypt/live/{домен}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{домен}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

    server_tokens off;
    add_header X-Robots-Tag $cell_robots_{имя} always;

    location / {{
        return 301 https://{домен}$request_uri;
    }}
}}
"""


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--site", action="append", required=True)
    р.add_argument("--out", type=pathlib.Path, default=ВЫХОД)
    р.add_argument("--force", action="store_true",
                   help="перезаписать существующую заготовку")
    а = р.parse_args(аргв)
    а.out.mkdir(parents=True, exist_ok=True)
    for site_id in а.site:
        я = ячейка(site_id)
        домен = я["domain"]
        порт = (я.get("runtime") or {}).get("port") or (я.get("template") or {}).get("port")
        if not порт:
            # Порт берётся из паспорта; у новой ячейки он лежит в site.json
            # проекта, и подставлять «похожий» нельзя.
            проект = КОРЕНЬ / (я.get("repo") or {}).get("path", "")
            файл = проект / "config" / "site.json"
            if файл.is_file():
                порт = json.loads(файл.read_text(encoding="utf-8")).get("port")
        if not порт:
            print(f"ОТКАЗ {site_id}: порт не записан ни в паспорте, ни в проекте",
                  file=sys.stderr)
            return 2
        днс = измерить_днс(домен)
        for хвост, тело in (("", тело_http(site_id, домен, int(порт), днс)),
                            ("-tls", тело_tls(site_id, домен))):
            цель = а.out / f"{site_id}{хвост}.conf"
            if цель.exists() and not а.force:
                print(f"{цель.name}: уже есть, не перезаписываю (--force)")
                continue
            цель.write_text(тело, encoding="utf-8")
            print(f"{цель.name}: записан ({len(тело.splitlines())} строк)")
        print(f"   {site_id}: домен {домен}, порт {порт}, DNS NS={днс.get('NS')} A={днс.get('A')}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
