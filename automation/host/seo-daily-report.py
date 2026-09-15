#!/usr/bin/env python3
"""Ежедневный бесплатный отчёт о состоянии SEO-контура витрин.

Платного здесь нет ничего: съём позиций не запускается, баланс не тратится.
Отчёт отвечает на один вопрос — осталось ли всё на своих местах со вчера.

Почему отчёт, а не только тесты. Тег Метрики уже однажды исчез из рендерера
при переработке шаблонов, и страницы продолжали отдаваться как ни в чём не
бывало. Такую пропажу не видно ни по кодам ответа, ни по внешнему виду —
видно только по отчёту, и то через сутки. Этот отчёт сокращает сутки до
одного прогона.

Идемпотентность: отчёт за один день перезаписывает сам себя и не плодит
файлов. Сравнение со вчера ведётся по сохранённому отчёту, а не по памяти.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

#: Домен → счётчик Метрики и проект Topvisor. Публичные идентификаторы.
ВИТРИНЫ = {
    "lordfilm47.space": {"counter": 112010269, "topvisor": 32531504, "site_id": "lords-01"},
    "lordserial33.biz": {"counter": 112010274, "topvisor": 32531521, "site_id": "lords-02"},
    "1lordserials1.online": {"counter": 112010277, "topvisor": 32531542, "site_id": "lords-03"},
    "zonafilm.space": {"counter": 112582938, "topvisor": 33238820, "site_id": "zona-01"},
}

#: Ожидаемая политика индексации. Её неожиданное снятие — повод для тревоги,
#: а не для молчаливого принятия: индексация закрытого сайта откатывается
#: месяцами.
ОЖИДАЕМЫЙ_ROBOTS = "noindex"


def _взять(url: str, timeout: int = 25) -> tuple[str, str, int]:
    """Заголовки, тело и код ответа. Без внешних библиотек: отчёт обязан
    работать и там, где ничего не установлено."""
    r = subprocess.run(
        ["curl", "-sSL", "-m", str(timeout), "-D", "-", "-o", "-", url],
        capture_output=True, text=True)
    txt = r.stdout
    зг, _, тело = txt.partition("\r\n\r\n") if "\r\n\r\n" in txt else txt.partition("\n\n")
    коды = re.findall(r"HTTP/[\d.]+ (\d+)", зг)
    return зг, тело, int(коды[-1]) if коды else 0


def осмотреть(домен: str, данные: dict) -> dict:
    счёт = данные["counter"]
    зг, тело, код = _взять(f"https://{домен}/")
    теги = тело.count("metrika/tag.js")
    свой = len(re.findall(rf'ym\({счёт},', тело))
    чужие = sorted({int(x) for x in re.findall(r"ym\((\d+),", тело) if int(x) != счёт})
    canon = re.findall(r'<link rel="canonical" href="([^"]*)"', тело)
    _, sm, sm_код = _взять(f"https://{домен}/sitemap.xml")
    _, rb, rb_код = _взять(f"https://{домен}/robots.txt")
    _, _, нет_код = _взять(f"https://{домен}/заведомо-нет-такой-страницы/")
    return {
        "domain": домен, "site_id": данные["site_id"],
        "http": код,
        "metrika_counter_id": счёт,
        "metrika_tag_present": теги == 1,
        "metrika_tag_occurrences": теги,
        "metrika_init_calls": свой,
        "metrika_foreign_counters": чужие,
        "topvisor_project_id": данные["topvisor"],
        "x_robots_tag": (re.findall(r"(?im)^x-robots-tag:\s*(.+)$", зг) or [""])[0].strip(),
        "meta_robots": (re.findall(r'<meta name="robots" content="([^"]*)"', тело) or [""])[0],
        "robots_txt_http": rb_код,
        "robots_txt_disallow_all": "Disallow: /" in rb,
        "sitemap_http": sm_код,
        "sitemap_url_count": len(re.findall(r"<loc>", sm)),
        "canonical_present": bool(canon),
        "canonical_absolute": bool(canon) and canon[0].startswith("https://"),
        "json_ld_blocks": тело.count("application/ld+json"),
        "soft_404": нет_код == 200,
        "renderer_build_id": (re.findall(
            r'<meta name="site-factory-build-id" content="([^"]*)"', тело) or [""])[0],
        "renderer_template_revision": (re.findall(
            r'<meta name="site-factory-template-revision" content="([^"]*)"', тело) or [""])[0],
    }


#: Правила тревог. Каждое отвечает на вопрос «что сломалось», а не «что
#: выглядит непривычно»: тревога, которую нельзя починить, учит её не читать.
ПРАВИЛА = (
    ("METRIKA_TAG_MISSING", lambda с: not с["metrika_tag_present"],
     "тег Метрики исчез со страницы"),
    ("METRIKA_WRONG_COUNTER", lambda с: bool(с["metrika_foreign_counters"]),
     "на странице чужой счётчик"),
    ("METRIKA_DUPLICATE_INIT", lambda с: с["metrika_init_calls"] > 1,
     "счётчик инициализируется больше одного раза"),
    ("HTTP_NOT_OK", lambda с: с["http"] != 200, "витрина не отвечает 200"),
    ("INDEXING_UNEXPECTEDLY_OPEN",
     lambda с: ОЖИДАЕМЫЙ_ROBOTS not in (с["x_robots_tag"] + с["meta_robots"]).lower(),
     "noindex снят, а решения об этом не было"),
    ("ROBOTS_TXT_LOST", lambda с: с["robots_txt_http"] != 200,
     "robots.txt недоступен"),
    ("SITEMAP_EMPTY", lambda с: с["sitemap_url_count"] == 0,
     "sitemap пуст или не отдаётся"),
    ("CANONICAL_MISSING", lambda с: not с["canonical_present"],
     "на главной нет canonical"),
    ("SOFT_404", lambda с: с["soft_404"],
     "несуществующая страница отвечает 200"),
)


def тревоги(снимок: dict, вчера: dict | None) -> list[dict]:
    из = []
    for код, правило, текст in ПРАВИЛА:
        if правило(снимок):
            из.append({"rule": код, "domain": снимок["domain"], "detail": текст})
    if вчера:
        if снимок["renderer_build_id"] != вчера.get("renderer_build_id"):
            из.append({"rule": "RENDERER_CHANGED", "domain": снимок["domain"],
                       "detail": f'сборка рендерера сменилась: '
                                 f'{вчера.get("renderer_build_id")} → {снимок["renderer_build_id"]}'
                                 + ("; тег при этом на месте" if снимок["metrika_tag_present"]
                                    else "; И ТЕГ ПРОПАЛ")})
        if вчера.get("topvisor_project_id") != снимок["topvisor_project_id"]:
            из.append({"rule": "TOPVISOR_PROJECT_CHANGED", "domain": снимок["domain"],
                       "detail": "проект Topvisor сменился или исчез"})
    return из


def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", default="artifacts/seo-daily",
                   help="каталог отчётов")
    р.add_argument("--date", default=None, help="дата отчёта, по умолчанию сегодня")
    а = р.parse_args(argv)

    каталог = pathlib.Path(а.out)
    каталог.mkdir(parents=True, exist_ok=True)
    день = а.date or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    файл = каталог / f"seo-health-{день}.json"

    прежние = {}
    предыдущие = sorted(p for p in каталог.glob("seo-health-*.json") if p != файл)
    if предыдущие:
        было = json.loads(предыдущие[-1].read_text(encoding="utf-8"))
        прежние = {с["domain"]: с for с in было.get("sites", [])}

    сайты, все_тревоги = [], []
    for домен, данные in ВИТРИНЫ.items():
        с = осмотреть(домен, данные)
        сайты.append(с)
        все_тревоги += тревоги(с, прежние.get(домен))

    отчёт = {
        "schema": "seo.daily_health/1.0.0",
        "date": день,
        "paid_operations": 0,
        "position_check_started": False,
        "sites": сайты,
        "alerts": все_тревоги,
        "alert_delivery_status": "NOT_CONFIGURED",
        "alert_delivery_note":
            "Внешний канал доставки не настроен. Файл на диске уведомлением не "
            "является: никто его не получит, пока за ним не придут.",
        "compared_with": предыдущие[-1].name if предыдущие else None,
    }
    файл.write_text(json.dumps(отчёт, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"report": str(файл), "sites": len(сайты),
                      "alerts": len(все_тревоги),
                      "alert_rules": [a["rule"] for a in все_тревоги]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
