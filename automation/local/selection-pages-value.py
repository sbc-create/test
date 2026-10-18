#!/usr/bin/env python3
"""Сколько у нас индексируемых страниц ОТБОРА и насколько они наполнены.

    python3 automation/local/selection-pages-value.py zonafilm12.site country
    python3 automation/local/selection-pages-value.py zonafilm12.site year --limit 40

Зачем. Официальная рекомендация (`knowledge/FACTS.md` F7.6, F7.7, источник
SRC-YANDEX-WEBMASTER, обращение 2026-10-18): среди примеров сайтов, к которым
алгоритмы могут применить ограничения, названы малоинформативные страницы
результатов поиска и отбора, и про них сказано отдельно — «таких страниц часто
много, это увеличивает нагрузку на сайт и снижает скорость обхода полезных
страниц».

У нас таких страниц много по построению: на одной форме `/catalog/?…` витрина
Zona предлагает 165 стран, 110 годов и 98 жанров — 373 значения, и каждое даёт
индексируемый адрес. Инструмент меряет, СКОЛЬКО из них наполнены.

Что считается находкой, и почему именно это:

* **индексируемая страница отбора с нулём записей** — прямой запрет
  замороженного пакета (`SEO_KNOWLEDGE_PACK` §3 п.4: пустые категории и
  фильтры не публикуются как indexable 200). Это находка без оговорок;
* **страница с одной-двумя записями** печатается числом, но находкой НЕ
  называется: порога «малоинформативности» официальная документация не даёт, и
  выдумывать его здесь значило бы подменять рекомендацию своей меркой.

Числа берутся из того, что страница сама о себе объявляет («N записей») и из
глубины листалки; набор карточек первой страницы — для сверки формы отбора с
другой формой (`/series/?country=…` против `/catalog/?country=…`).

Только чтение публичной выдачи своих витрин.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import subprocess
import sys

ФОРМЫ = {"country": "country", "year": "year", "genre": "genre"}
#: Пустая страница отбора в индексе запрещена пакетом — это находка.
ПУСТО = 0


def взять(url: str, таймаут: int) -> tuple[str, str]:
    г = subprocess.run(["curl", "-sS", "--max-time", str(таймаут),
                        "-w", "\n%{http_code}", url],
                       capture_output=True, text=True)
    части = (г.stdout or "").rsplit("\n", 1)
    return (части[0], части[1].strip() if len(части) > 1 else "000")


def объявлено(html: str) -> int | None:
    м = re.search(r"([0-9][0-9\s ]{0,8})\s*(?:записей|записи|запись|"
                  r"тайтлов|произведени[йяе])", html)
    if not м:
        return None
    return int(re.sub(r"[^0-9]", "", м.group(1)))


def карточки(html: str) -> set[str]:
    return set(re.findall(r'href="(/(?:title|anime)/[^"/?#]+)/?"', html))


def канонический(html: str) -> str:
    м = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', html)
    return м.group(1) if м else ""


def роботы(html: str) -> str:
    м = re.search(r'<meta[^>]+name="robots"[^>]+content="([^"]+)"', html)
    return м.group(1).strip().lower() if м else ""


def индексируема(html: str) -> bool:
    return "noindex" not in роботы(html)


def коды(домен: str, вид: str, таймаут: int) -> list[str]:
    """Значения фильтра, которые витрина предлагает САМА.

    Список не придумывается: берётся со страницы каталога этой же витрины.
    """
    html, код = взять(f"https://{домен}/catalog/", таймаут)
    if код != "200":
        return []
    образец = re.escape(ФОРМЫ[вид]) + r"=([a-z0-9-]+)"
    return sorted(set(re.findall(образец, html)))


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("domain")
    р.add_argument("kind", choices=sorted(ФОРМЫ))
    р.add_argument("--limit", type=int, default=0,
                   help="проверить только первые N значений (0 — все)")
    р.add_argument("--timeout", type=int, default=25)
    р.add_argument("--json", default="")
    а = р.parse_args(аргв)

    значения = коды(а.domain, а.kind, а.timeout)
    if not значения:
        print(f"{а.domain}: страница каталога не отдала значений фильтра "
              f"«{а.kind}» — НЕ ИЗМЕРЕНО", file=sys.stderr)
        return 2
    если_предел = значения[:а.limit] if а.limit else значения
    print(f"{а.domain}: значений фильтра «{а.kind}» предложено "
          f"{len(значения)}, проверяется {len(если_предел)}")

    итоги = []
    for код_знач in если_предел:
        адрес = f"https://{а.domain}/catalog/?{ФОРМЫ[а.kind]}={код_знач}"
        html, код = взять(адрес, а.timeout)
        запись = {"value": код_знач, "url": адрес, "http": код}
        if код == "200":
            запись.update({
                "declared": объявлено(html),
                "cards_page1": len(карточки(html)),
                "indexable": индексируема(html),
                "robots": роботы(html) or "нет мета",
                "canonical_self": канонический(html).rstrip("/").endswith(
                    адрес.split("https://")[1].rstrip("/")),
            })
        итоги.append(запись)

    двести = [з for з in итоги if з["http"] == "200"]
    пустые_в_индексе = [з for з in двести
                        if з.get("indexable") and з.get("declared") == ПУСТО]
    малые = [з for з in двести
             if з.get("indexable") and (з.get("declared") or 0) in (1, 2)]
    не_двести = [з for з in итоги if з["http"] != "200"]

    корзины = collections.Counter()
    for з in двести:
        d = з.get("declared")
        корзины["не объявлено" if d is None else
                "0" if d == 0 else
                "1–2" if d <= 2 else
                "3–9" if d <= 9 else
                "10–49" if d <= 49 else "50+"] += 1

    print(f"\nответили 200: {len(двести)}; иначе: {len(не_двести)}")
    print("наполнение (по объявленному числу записей): "
          + ", ".join(f"{к}: {н}" for к, н in sorted(корзины.items())))
    print(f"\nНАХОДКИ — индексируемые страницы отбора с нулём записей: "
          f"{len(пустые_в_индексе)}")
    for з in пустые_в_индексе[:20]:
        print(f"   {з['url']}")
    print(f"\nбез вердикта (порога у документации нет) — индексируемых с одной "
          f"или двумя записями: {len(малые)}")
    for з in малые[:10]:
        print(f"   {з['declared']}: {з['url']}")
    if не_двести:
        print(f"\nне 200 (НЕ ИЗМЕРЕНО, это не «пусто»): "
              + ", ".join(f"{з['value']}={з['http']}" for з in не_двести[:12]))

    if а.json:
        pathlib.Path(а.json).write_text(
            json.dumps({"domain": а.domain, "kind": а.kind,
                        "offered": len(значения), "checked": len(если_предел),
                        "results": итоги}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print(f"\nразбор записан: {а.json}")
    return 1 if пустые_в_индексе else 0


if __name__ == "__main__":
    raise SystemExit(главная())
