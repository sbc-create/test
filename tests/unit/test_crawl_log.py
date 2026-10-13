"""Анализатор журналов обхода (B026): форматы, тестовые строки, подлинность роботов."""
from __future__ import annotations

import gzip
import json

from seo_operator import crawl_log as cl

TSV = [
    "2026-10-14T03:00:01+03:00\tlordfilm47.space\tlordfilm47.space\t5.255.253.1\tGET\t/robots.txt\t200\t120\t0.002\t0.001\t\"Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)\"",
    "2026-10-14T03:00:05+03:00\tlordfilm47.space\tlordfilm47.space\t5.255.253.1\tGET\t/sitemap-1.xml\t200\t900\t0.010\t0.009\t\"Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)\"",
    "2026-10-14T03:01:00+03:00\tlordfilm47.space\tlordfilm47.space\t5.255.253.1\tGET\t/title/x/season-1/episode-2/\t200\t5000\t0.300\t0.290\t\"Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)\"",
    "2026-10-14T03:02:00+03:00\tan1mego.site\tan1mego.site\t66.249.66.1\tGET\t/title/y/\t200\t5000\t0.100\t0.090\t\"Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)\"",
    "2026-10-14T03:03:00+03:00\tan1mego.site\tan1mego.site\t1.2.3.4\tGET\t/\t200\t5000\t0.100\t0.090\t\"Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)\"",
    "2026-10-14T03:04:00+03:00\tan1mego.site\tan1mego.site\t10.0.0.1\tGET\t/\t200\t5000\t0.100\t0.090\t\"sf-seo-logtest/abc YandexBot\"",
    "битая строка",
]


def _dns():
    обратный = {"5.255.253.1": "5-255-253-1.spider.yandex.com", "66.249.66.1": "crawl-66-249-66-1.googlebot.com",
                "1.2.3.4": "fake.example.net"}
    прямой = {"5-255-253-1.spider.yandex.com": ["5.255.253.1"], "crawl-66-249-66-1.googlebot.com": ["66.249.66.1"]}

    def о(ip):
        if ip not in обратный:
            raise OSError("нет PTR")
        return обратный[ip]

    def п(имя):
        if имя not in прямой:
            raise OSError("нет A")
        return прямой[имя]
    return о, п


def _записать(tmp_path, строки, gz=False):
    f = tmp_path / ("bots.log.gz" if gz else "bots.log")
    текст = "\n".join(строки) + "\n"
    if gz:
        with gzip.open(f, "wt", encoding="utf-8") as fh:
            fh.write(текст)
    else:
        f.write_text(текст, encoding="utf-8")
    return f


def test_tsv_counts_bots_excludes_tests_and_verifies(tmp_path):
    записи, полнота = cl.читать([_записать(tmp_path, TSV, gz=True)], "tsv", None)
    о, п = _dns()
    отчёт = cl.анализ(записи, обратный=о, прямой=п)
    assert полнота["lines"] == 7 and полнота["unparsed"] == 1
    assert отчёт["lines_test"] == 1 and отчёт["lines_bot"] == 5
    lf = отчёт["domains"]["lordfilm47.space"]["2026-10-14"]["yandex:verified"]
    assert lf["requests"] == 3 and lf["robots_fetches"] == 1 and lf["sitemap_fetches"] == 1
    assert lf["types"] == {"robots": 1, "sitemap": 1, "серия": 1}
    ag = отчёт["domains"]["an1mego.site"]["2026-10-14"]
    assert ag["google:verified"]["requests"] == 1
    assert ag["google:failed"]["requests"] == 1  # Googlebot в UA, но PTR не Google — кандидат не подтверждён
    assert отчёт["first"].startswith("2026-10-14T03:00:01")


def test_no_dns_marks_unchecked_not_verified(tmp_path):
    записи, _ = cl.читать([_записать(tmp_path, TSV)], "tsv", None)
    отчёт = cl.анализ(записи, проверять_dns=False)
    метки = {м for дни in отчёт["domains"].values() for д in дни.values() for м in д}
    assert метки and all(м.endswith(":unchecked") for м in метки)


def test_combined_needs_domain_and_parses(tmp_path):
    строки = ['5.255.253.1 - - [13/Oct/2026:10:00:00 +0000] "GET /title/z/ HTTP/1.1" 200 512 "-" '
              '"Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"',
              '8.8.8.8 - - [13/Oct/2026:10:00:01 +0000] "GET / HTTP/1.1" 200 512 "-" "Mozilla/5.0 Chrome"']
    f = _записать(tmp_path, строки)
    записи, полнота = cl.читать([f], "combined", "lordserial33.biz")
    отчёт = cl.анализ(записи, проверять_dns=False)
    assert полнота["unparsed"] == 0 and отчёт["lines_other"] == 1
    assert отчёт["domains"]["lordserial33.biz"]["2026-10-13"]["yandex:unchecked"]["types"] == {"тайтл": 1}


def test_cli_writes_report_and_requires_domain_for_combined(tmp_path, capsys):
    f = _записать(tmp_path, TSV)
    out = tmp_path / "r.json"
    assert cl.main([str(f), "--format", "tsv", "--no-dns", "--out", str(out)]) == 0
    отчёт = json.loads(out.read_text())
    assert отчёт["completeness"]["lines"] == 7 and "generated_at" in отчёт
    try:
        cl.main([str(f), "--format", "combined"])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("combined без --domain должен отказать")


def test_page_types():
    assert cl.тип_страницы("/sitemap.xml") == "sitemap"
    assert cl.тип_страницы("/sitemap/static.xml") == "sitemap"
    assert cl.тип_страницы("/anime/x/season/7/episode/4") == "серия"
    assert cl.тип_страницы("/title/x/season-7/") == "сезон"
    assert cl.тип_страницы("/catalog/?genre=драма") == "жанр"
    assert cl.тип_страницы("/poster/abc.webp") == "ресурс"
