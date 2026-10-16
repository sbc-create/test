#!/usr/bin/env python3
"""Таблица выпуска партии K2 по каждому домену — измерением, а не вручную.

Задание требует таблицу со столбцами DNS, HTTPS, служба, плеер, каталог,
индексация и остаточный блокер. Собирать её руками — значит пересобирать при
каждом изменении и однажды переписать устаревшее значение: так в документе уже
появилось «92 файла» вместо 91 и «отвечает старая копия» вместо 404.

Поэтому таблица считается. Источники по столбцам названы явно:

* **DNS** — публичный ответ (`dig @8.8.8.8`), а не план и не запись реестра;
* **HTTPS** — есть ли на узле каталог сертификата домена и покрывает ли он
  `www` (блок 443 заготовки ссылается на один каталог для обоих имён);
* **служба** — `systemctl is-active` юнита витрины НА ЕЁ УЗЛЕ;
* **плеер** — номер в установленной конфигурации ячейки;
* **каталог** — ревизия и число позиций установленного набора;
* **индексация** — заголовок, который витрина отдаёт сама, и `robots.txt`;
* **остаточный блокер** — выводится из столбцов, а не вписывается.

Узловые измерения идут одним вызовом ansible на всю партию: восемь отдельных
подключений занимали бы минуты и давали бы несогласованный по времени снимок.

    python3 automation/local/k2-release-table.py
    python3 automation/local/k2-release-table.py --json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

КОРЕНЬ_РЕПО = pathlib.Path(__file__).resolve().parents[2]
if str(КОРЕНЬ_РЕПО) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ_РЕПО))
from factory.seo.robots_scope import закрывает_весь_обход  # noqa: E402

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
УЗЕЛ = "k2-zomro-01"
ЦЕЛЕВОЙ_АДРЕС = "145.63.129.86"
ИНВЕНТАРЬ = КОРЕНЬ / "var" / "ansible" / "hosts.yml"

#: Сценарий для узла: по одной строке на витрину, поля через `|`. Печатает
#: ровно то, что можно измерить ТАМ, и ничего не домысливает.
НА_УЗЛЕ = r"""
set -u
for pair in @@ПАРЫ@@; do
  sid=${pair%%:*}; rest=${pair#*:}
  acc=${rest%%:*}; rest=${rest#*:}
  dom=${rest%%:*}; port=${rest##*:}
  unit=$(systemctl is-active "nova-$acc.service" 2>/dev/null \
         || echo "нет")
  restarts=$(systemctl show "nova-$acc.service" -p NRestarts --value 2>/dev/null)
  cert="нет"
  if [ -s "/etc/letsencrypt/live/$dom/fullchain.pem" ]; then
    san=$(openssl x509 -noout -ext subjectAltName \
            -in "/etc/letsencrypt/live/$dom/fullchain.pem" 2>/dev/null)
    if printf '%s' "$san" | grep -q "DNS:www.$dom"; then
      cert="есть, с www"
    else
      cert="есть, без www"
    fi
  fi
  tls_conf="нет"
  [ -f "/etc/nginx/lords/$sid-tls.conf" ] && tls_conf="установлен"
  pub=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['publisher_id'])" \
        "/srv/$acc/current/config/player.json" 2>/dev/null || echo "нет")
  xrobots=$(curl -s -o /dev/null -D - -H "Host: $dom" \
              "http://127.0.0.1:$port/" 2>/dev/null \
            | grep -i "^x-robots-tag" | tr -d "\r" | cut -d" " -f2- | tr -d "\n")
  robots=$(curl -s -H "Host: $dom" "http://127.0.0.1:$port/robots.txt" \
             2>/dev/null | tr "\n" " " | cut -c1-40)
  rev=$(python3 /home/k2deploy/stage/k2-catalog-state.py 2>/dev/null \
        | awk -v s="$sid" '$1==s {
            for (i = 1; i <= NF; i++) {
              if ($i ~ /^revision=/) r = substr($i, 10)
              if ($i ~ /^items=/)    n = substr($i, 7)
            }
            print r "/" n
          }')
  echo "$sid|$dom|$unit|$restarts|$cert|$tls_conf|$pub|${xrobots:-нет}|${robots:-нет}|${rev:-нет}"
done
"""


def партия() -> list[dict]:
    данные = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    ячейки = данные.get("cells") if isinstance(данные, dict) else данные
    ячейки = ячейки if isinstance(ячейки, list) else list(ячейки.values())
    итог = []
    for я in ячейки:
        if (я.get("deploy_target") or {}).get("ref") != УЗЕЛ:
            continue
        рв = я.get("runtime") or {}
        итог.append({
            "site_id": я["site_id"], "domain": я["domain"],
            "account": рв.get("account") or я["domain"].replace(".", "-"),
            "port": str(рв.get("port") or ""),
            "publisher_expected": str((я.get("publisher") or {}).get("publisher_id") or ""),
            "status": я.get("status", ""),
        })
    return sorted(итог, key=lambda з: з["site_id"])


def адрес(домен: str) -> str:
    try:
        г = subprocess.run(["dig", "+short", "A", домен, "@8.8.8.8"],
                           capture_output=True, text=True, timeout=30)
        строки = [с.strip() for с in (г.stdout or "").split() if с.strip()]
        return строки[-1] if строки else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def с_узла(витрины: list[dict]) -> dict[str, list[str]]:
    пары = " \\\n            ".join(
        f"{в['site_id']}:{в['account']}:{в['domain']}:{в['port']}" for в in витрины)
    сценарий = НА_УЗЛЕ.replace("@@ПАРЫ@@", пары)
    г = subprocess.run(
        ["ansible", "-i", str(ИНВЕНТАРЬ), УЗЕЛ, "-m", "shell", "-a", сценарий],
        capture_output=True, text=True, timeout=600, cwd=КОРЕНЬ)
    итог: dict[str, list[str]] = {}
    for строка in (г.stdout or "").splitlines():
        поля = строка.strip().split("|")
        if len(поля) == 10 and поля[0].startswith("lords-"):
            итог[поля[0]] = поля
    if not итог:
        print(f"узел не ответил разбираемыми строками (код {г.returncode}); "
              "таблица будет только с тем, что измеряется отсюда",
              file=sys.stderr)
    return итог


def блокер(строка: dict) -> str:
    if строка["dns"] != ЦЕЛЕВОЙ_АДРЕС:
        return "DNS → TLS"
    # «есть, без www» готовностью НЕ считается: блок 443 заготовки несёт имя
    # www и ссылается на тот же каталог сертификата, поэтому без www в SAN
    # nginx не поднимется вовсе — и упадёт вместе с соседними семью.
    # Поймано своей же проверкой: прежнее условие принимало любое «есть».
    if строка["https"] != "есть, с www":
        return "TLS"
    if строка["service"] != "active":
        return "служба"
    if строка["publisher"] != строка["publisher_expected"]:
        return "номер издателя"
    return "нет"


def собрать() -> list[dict]:
    витрины = партия()
    узел = с_узла(витрины)
    строки = []
    for в in витрины:
        поля = узел.get(в["site_id"], [""] * 10)
        строка = {
            "site_id": в["site_id"], "domain": в["domain"],
            "status": в["status"],
            "dns": адрес(в["domain"]) or "нет записи",
            "service": поля[2] or "не измерено",
            "restarts": поля[3] or "—",
            "https": поля[4] or "не измерено",
            "tls_conf": поля[5] or "не измерено",
            "publisher": поля[6] or "не измерено",
            "publisher_expected": в["publisher_expected"],
            "x_robots": поля[7] or "не измерено",
            "robots_txt": поля[8] or "не измерено",
            "catalog": поля[9] or "не измерено",
        }
        строка["blocker"] = блокер(строка)
        строки.append(строка)
    return строки


def напечатать(строки: list[dict]) -> None:
    print("| домен | DNS | HTTPS | служба | плеер | каталог | индексация | остаточный блокер |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for с in строки:
        dns = (f"{с['dns']} ✓" if с["dns"] == ЦЕЛЕВОЙ_АДРЕС
               else f"{с['dns']} (не цель)")
        плеер = (f"{с['publisher']} ✓"
                 if с["publisher"] and с["publisher"] == с["publisher_expected"]
                 else f"{с['publisher']} ≠ {с['publisher_expected']}")
        рев, _, поз = с["catalog"].partition("/")
        каталог = (f"{поз}, rev {рев[:8]}" if поз else с["catalog"])
        # Строкой, а не подстрокой: `"Disallow: /" in текст` совпадает с
        # `Disallow: /poster/`, и витрина с таким robots.txt считалась бы
        # закрытой при открытой индексации.
        закрыт = ("noindex" in с["x_robots"]
                  and закрывает_весь_обход(с["robots_txt"]))
        индексация = "CLOSED ✓" if закрыт else f"? {с['x_robots']}"
        print(f"| {с['domain']} | {dns} | {с['https']} | {с['service']} "
              f"| {плеер} | {каталог} | {индексация} | {с['blocker']} |")
    хорошо = [с for с in строки if с["blocker"] == "нет"]
    print(f"\nвитрин {len(строки)}, без остаточного блокера {len(хорошо)}; "
          f"перезапусков служб: "
          f"{', '.join(sorted({с['restarts'] for с in строки}))}")


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--json", action="store_true")
    а = р.parse_args()
    строки = собрать()
    if not строки:
        print("в реестре нет витрин с этим узлом выкладки", file=sys.stderr)
        return 2
    if а.json:
        print(json.dumps(строки, ensure_ascii=False, indent=2))
    else:
        напечатать(строки)
    return 0


if __name__ == "__main__":
    sys.exit(main())
