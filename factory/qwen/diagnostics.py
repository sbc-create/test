"""Повседневная диагностика витрины и операции над режимом индексации.

Наличие плеера и проверенное воспроизведение — РАЗНЫЕ утверждения
----------------------------------------------------------------

`player_tag_present` говорит только о том, что на странице есть тег
`<video-player>`. Это не воспроизведение. Фактическое воспроизведение
проверяется отдельным инструментом с браузером
(`automation/host/publisher-id-live-check.js`), который ждёт `readyState>=2` и
прирост времени; он требует playwright и здесь не вызывается. Поле
`playback_verified` поэтому всегда `null` — и это честнее, чем выдать наличие
рамки за игру.

Режим индексации только ЧИТАЕТСЯ
--------------------------------

`индексация()` показывает robots.txt, meta robots, X-Robots-Tag и sitemap как
отдельные проверяемые величины. Менять режим эта функция не умеет намеренно:
переход открывается решением владельца либо ранее утверждённым правилом, а
передача сайта редактору открытием индексации не является.
"""
from __future__ import annotations

import json
import re

from factory.qwen import editorial, registry


def диагностика(site: str) -> dict:
    s = editorial._сайт(site)
    итог: dict = {"site": s.domain, "site_id": s.site_id,
                  "handover_state": s.handover_state}
    код, главная = registry._страница(f"https://{s.domain}/", таймаут=25)
    итог["home_http"] = код
    итог["ok"] = код == "200"
    if код != "200":
        итог["reason"] = f"главная ответила {код}"
        return итог

    итог["home_links_to_titles"] = len(re.findall(r'/title/|/anime/', главная))
    итог["posters_on_home"] = len(re.findall(r'<img[^>]+src="[^"]+"', главная))
    кодz, телоz = registry._страница(f"https://{s.domain}/healthz", таймаут=20)
    if кодz == "200" and телоz:
        try:
            h = json.loads(телоz)
            итог["build_id"] = h.get("build_id")
            итог["process_start_time"] = h.get("process_start_time")
            итог["catalog_revision"] = h.get("catalog_revision")
        except ValueError:
            итог["healthz"] = "не JSON"
    else:
        итог["healthz"] = f"ответ {кодz}"

    # свежесть каталога — из снимка, а не из обещаний
    try:
        ф = editorial.факты(site)
        итог["catalog_titles"] = ф.get("titles_total")
        итог["without_description_playable"] = ф.get("without_description_playable")
    except editorial.ОперацияОтклонена as e:
        итог["catalog"] = f"недоступен: {e}"

    # плеер: только наличие тега, и это сказано прямо
    слаг = None
    try:
        слаг = (editorial.факты(site).get("sample") or [None])[0]
    except editorial.ОперацияОтклонена:
        pass
    if слаг:
        кодт, стрт = registry._страница(f"https://{s.domain}/title/{слаг}/", таймаут=25)
        итог["title_page_http"] = кодт
        итог["player_tag_present"] = bool(re.search(r"<video-player", стрт))
        м = re.search(r'data-publisher-id="(\d+)"', стрт)
        итог["publisher_id_on_page"] = м.group(1) if м else None
        итог["playback_verified"] = None
        итог["playback_note"] = (
            "наличие тега ≠ воспроизведение; фактическая игра проверяется "
            "automation/host/publisher-id-live-check.js (нужен playwright)")
    return итог


def индексация(site: str) -> dict:
    """Показать действующий режим индексации. ТОЛЬКО ЧИТАЕТ.

    Запреты индексации — отдельные проверяемые операции владельца, и этот
    инструмент их не выполняет: смена режима не следует из передачи сайта
    редактору. Передача сайта редактору не означает открытия сети для
    индексации, поэтому здесь нет ни одной записи — `mutable: False`.

    Читается четыре независимых признака: ответ главной, `meta name="robots"`,
    `robots.txt` и наличие `sitemap.xml`, плюс `canonical`. Они расходятся
    между собой чаще, чем кажется, и сводить их в один флаг «закрыт/открыт»
    значило бы прятать расхождение.
    """
    s = editorial._сайт(site)
    итог: dict = {"site": s.domain, "ok": True, "mutable": False,
                  "note": "только чтение: смена режима — решение владельца"}
    код, главная = registry._страница(f"https://{s.domain}/", таймаут=20)
    итог["home_http"] = код
    if код == "200":
        м = re.search(r'name="robots"[^>]*content="([^"]*)"', главная)
        итог["meta_robots"] = м.group(1) if м else "не объявлен"
    крт, тело = registry._страница(f"https://{s.domain}/robots.txt", таймаут=20)
    итог["robots_txt_http"] = крт
    итог["robots_txt_head"] = [с for с in тело.strip().split("\n")[:4]] if тело else []
    кс, _ = registry._страница(f"https://{s.domain}/sitemap.xml", таймаут=20)
    итог["sitemap_http"] = кс
    # canonical
    if код == "200":
        c = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]*)"', главная)
        итог["canonical"] = c.group(1) if c else "не объявлен"
    итог["ok"] = код == "200"
    return итог
