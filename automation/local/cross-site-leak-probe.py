#!/usr/bin/env python3
"""Не объявляет ли витрина чужой адрес своим. Только чтение публичных страниц.

Зачем инструментом, а не разовым замером. Определение готовности фабрики
называет cross-site утечку **блокирующей**: «обнаружена cross-site утечка» —
отдельная строка в списке причин, по которым нельзя ставить `DONE`. Значит
проверка должна быть повторяемой: её будут гонять после каждой правки шаблона,
а не один раз в отчёт.

Самый дешёвый признак утечки снаружи — **хост**: если `canonical`, `og:url` или
адрес карты сайта называют не тот домен, у которого спросили, страница
объявляет себя чужой, и вес уходит соседу. Это не единственная форма утечки
(бывает и подмена содержимого при верном хосте), и об этом сказано прямо ниже.

Проверяется по три поверхности на витрину: главная, каталог и первая карточка
каталога — то есть три разных пути сборки страницы, а не один.

    python3 automation/local/cross-site-leak-probe.py zonafilm.space
    python3 automation/local/cross-site-leak-probe.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ПАСПОРТ = Path("/home/claude/wt-portable-site-cell-01/config/site-cells.json")
#: Формы адреса карточки. Две, и это измерено, а не предположено: Yummy держит
#: карточку на `/anime/<slug>`, остальные на `/title/<slug>`.
ФОРМЫ_КАРТОЧКИ = ("/title/", "/anime/")
#: Где может оказаться чужой хост. Перечень назван: признак, который ищет в
#: одном месте, отвечает про это место, а не про страницу.
МЕСТА = (
    ("canonical", r'rel="canonical"[^>]*href="([^"]+)"'),
    ("og:url", r'property="og:url"[^>]*content="([^"]+)"'),
)


def достать(url: str, таймаут: int = 50) -> tuple[str, str]:
    with tempfile.NamedTemporaryFile(prefix="csl-", suffix=".bin") as б:
        г = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", str(таймаут), "-o", б.name,
             "-w", "%{http_code}", url],
            capture_output=True, text=True)
        тело = Path(б.name).read_text(encoding="utf-8", errors="replace")
    return (г.stdout or "").strip(), тело


def свой(хост: str, домен: str) -> bool:
    """Свой ли хост. `www.<домен>` считается своим: это тот же сайт."""
    return хост in ("", домен, f"www.{домен}")


def поверхности(домен: str) -> list[str]:
    """Главная, каталог и первая карточка каталога."""
    итог = ["/", "/catalog/"]
    код, кат = достать(f"https://{домен}/catalog/", таймаут=45)
    if код != "200":
        return итог
    for форма in ФОРМЫ_КАРТОЧКИ:
        найдено = sorted(set(re.findall(
            r'href="(' + re.escape(форма) + r'[^"#?]+)"', кат)))
        if найдено:
            итог.append(найдено[0])
            break
    return итог


def чужие_хосты(домен: str, путь: str) -> list[str]:
    код, тело = достать(f"https://{домен}{путь}")
    if код != "200":
        return []
    найдено = []
    for имя, шаблон in МЕСТА:
        for значение in re.findall(шаблон, тело):
            хост = urlsplit(значение).netloc
            if not свой(хост, домен):
                найдено.append(f"{путь} {имя} → {хост}")
    return найдено


def карта_из_robots(домен: str) -> list[str]:
    код, тело = достать(f"https://{домен}/robots.txt", таймаут=30)
    if код != "200":
        return []
    найдено = []
    for строка in тело.splitlines():
        if строка.lower().startswith("sitemap:"):
            хост = urlsplit(строка.split(":", 1)[1].strip()).netloc
            if not свой(хост, домен):
                найдено.append(f"robots.txt Sitemap → {хост}")
    return найдено


def домены() -> list[str]:
    if not ПАСПОРТ.is_file():
        return []
    ячейки = json.loads(ПАСПОРТ.read_text(encoding="utf-8")).get("cells") or []
    return [str(я["domain"]) for я in ячейки
            if я.get("domain")
            and not str(я["domain"]).endswith((".test", ".localhost"))]


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("домены", nargs="*")
    р.add_argument("--all", action="store_true")
    а = р.parse_args()
    цели = а.домены or (домены() if а.all else [])
    if not цели:
        print("не названо ни одной витрины: домен аргументом или --all")
        return 2

    замечания: list[str] = []
    не_измерено: list[str] = []
    for домен in цели:
        пути = поверхности(домен)
        чужие: list[str] = []
        for путь in пути:
            чужие.extend(чужие_хосты(домен, путь))
        чужие.extend(карта_из_robots(домен))
        if len(пути) < 3:
            не_измерено.append(f"{домен}: карточку взять не с чего "
                               f"(проверено поверхностей {len(пути)} из 3)")
        print(f"{домен:22} поверхностей {len(пути)}, чужих хостов: {len(чужие)}")
        for ч in чужие:
            замечания.append(f"{домен}: {ч}")
            print(f"{'':22}   {ч}")

    print(f"\n{'=' * 60}\nзамечаний: {len(замечания)}")
    for з in замечания:
        print(f"  • {з}")
    if не_измерено:
        print(f"\nнеполные замеры: {len(не_измерено)}")
        for н in не_измерено:
            print(f"  • {н}")
    print("\nПредел признака назван прямо: он ловит ЧУЖОЙ ХОСТ в canonical, "
          "og:url и адресе карты. Подмену СОДЕРЖИМОГО при верном хосте он не "
          "видит — для неё нужен другой замер (сравнение текста соседних "
          "витрин, см. CSU-4/B007).")
    return 1 if замечания else 0


if __name__ == "__main__":
    sys.exit(main())
