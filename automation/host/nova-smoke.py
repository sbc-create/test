#!/usr/bin/env python3
"""Smoke витрины: сверка объявленного с исполняемым и контракт живых страниц.

## Два источника, которые нельзя путать

* `/__template_version` отдаёт МАНИФЕСТ витрины — то, что она объявляет;
* `/healthz` считает `runtime_path` и `runtime_sha256` по `__file__` живого
  процесса — то, что она исполняет.

Совпадение этих двух величин и есть доказательство выкладки. Раздельно каждая
из них ничего не доказывает: манифест можно переписать, не трогая код, а код —
подменить, не трогая манифест. Ровно это и произошло 20 сентября.

## Почему запрос идёт на 127.0.0.1 с заголовком Host

Публичный контур (TLS, nginx, DNS) этой проверке недоступен: доменов Lords нет
в allowlist. Запрос к порту витрины обращается к ТОМУ ЖЕ процессу, в который
проксирует nginx, и потому доказывает поведение приложения. Чего он не
доказывает — сертификат, редиректы и заголовки nginx, — помечено в отчёте
отдельно, а не выдано за проверенное.

Запуск:

    nova-smoke.py --site lords-02 --expect-artifact <sha> --expect-release <dir> \\
                  --record out.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import importlib.util
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

FRONT = pathlib.Path("/srv/lords/.frontend")
ТАЙМАУТ = 30

PASS = 0
FAIL = 2


def _реестр():
    путь = pathlib.Path(__file__).resolve().parent / "nova-runtime-registry.py"
    spec = importlib.util.spec_from_file_location("nova_runtime_registry", путь)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    return модуль.build()


def запрос(база: str, путь: str, домен: str) -> tuple[int, str, dict]:
    """GET с настоящим Host витрины. Код, тело, заголовки. Ошибка — не исключение."""
    req = urllib.request.Request(
        база + путь,
        headers={"Host": домен, "User-Agent": "nova-smoke/1", "Accept-Encoding": "identity"},
    )
    try:
        with urllib.request.urlopen(req, timeout=ТАЙМАУТ) as ответ:
            return ответ.status, ответ.read().decode("utf-8", "replace"), dict(ответ.headers)
    except urllib.error.HTTPError as ошибка:
        return ошибка.code, ошибка.read().decode("utf-8", "replace"), dict(ошибка.headers)
    except (urllib.error.URLError, OSError, ValueError) as ошибка:
        return 0, f"{type(ошибка).__name__}: {ошибка}", {}


def найти_ссылки(html: str, свои: bool = True) -> list[str]:
    ссылки = re.findall(r'href="(/[^"#?]*)"', html)
    видимые = []
    for ссылка in ссылки:
        if ссылка.startswith("//"):
            continue
        if свои and (ссылка.endswith((".css", ".js", ".png", ".jpg", ".svg", ".ico"))):
            continue
        видимые.append(ссылка)
    # Порядок сохраняется, дубли убираются: выборка должна быть воспроизводимой.
    видно = {}
    for ссылка in видимые:
        видно.setdefault(ссылка, None)
    return list(видно)


def проверить(site: str, база: str, домен: str, ожидания: dict) -> dict:
    итог: dict = {"site": site, "base": база, "domain": домен, "checks": {}, "metrics": {}}
    провалы: list[str] = []

    def отметить(имя: str, ок: bool, подробность="") -> bool:
        итог["checks"][имя] = {"pass": bool(ок), "detail": подробность}
        if not ок:
            провалы.append(имя)
        return bool(ок)

    # --- 1. Идентичность: объявленное против исполняемого -------------------
    код, тело, _ = запрос(база, "/__template_version", домен)
    манифест = json.loads(тело) if код == 200 and тело.startswith("{") else {}
    отметить("template_version_200", код == 200, f"код {код}")

    код_h, тело_h, _ = запрос(база, "/healthz", домен)
    здоровье = json.loads(тело_h) if код_h == 200 and тело_h.startswith("{") else {}
    отметить("healthz_200", код_h == 200, f"код {код_h}")

    объявлено = манифест.get("artifact_sha256", "")
    исполняется = здоровье.get("runtime_sha256", "")
    путь_рантайма = здоровье.get("runtime_path", "")
    итог["metrics"].update({
        "declared_build_id": манифест.get("build_id", ""),
        "declared_artifact_sha256": объявлено,
        "declared_source_commit": манифест.get("source_commit", ""),
        "declared_source_dirty": манифест.get("source_dirty", "ABSENT"),
        "declared_profile": манифест.get("profile", ""),
        "running_release_path": путь_рантайма,
        "running_artifact_sha256": исполняется,
        "pid": здоровье.get("pid"),
        "process_start_time": здоровье.get("process_start_time", ""),
    })
    отметить("declared_equals_running", bool(объявлено) and объявлено == исполняется,
             f"объявлено {объявлено[:12]}, исполняется {исполняется[:12]}")
    отметить("source_dirty_false", манифест.get("source_dirty") is False,
             f"source_dirty={манифест.get('source_dirty', 'ABSENT')}")

    if ожидания.get("artifact"):
        отметить("artifact_matches_expected", исполняется == ожидания["artifact"],
                 f"ждали {ожидания['artifact'][:12]}")
    if ожидания.get("release_dir"):
        внутри = путь_рантайма.startswith(ожидания["release_dir"].rstrip("/") + "/")
        отметить("runs_from_expected_release_dir", внутри, путь_рантайма)
    отметить("runtime_not_shared_mutable_path",
             путь_рантайма != str(FRONT / "lords-frontend.py"), путь_рантайма)

    # --- 2. Главная: оформление, честность подвала, индексация --------------
    код_д, дом, заголовки = запрос(база, "/", домен)
    отметить("home_200", код_д == 200, f"код {код_д}")
    дизайн = re.search(r'data-design="([^"]+)"', дом)
    итог["metrics"]["data_design"] = дизайн.group(1) if дизайн else ""
    if ожидания.get("design"):
        отметить("data_design_matches", bool(дизайн) and дизайн.group(1) == ожидания["design"],
                 итог["metrics"]["data_design"])

    noindex_meta = 'name="robots" content="noindex, nofollow"' in дом.replace("'", '"')
    noindex_hdr = "noindex" in (заголовки.get("X-Robots-Tag", "") or "")
    отметить("indexability_closed", noindex_meta and noindex_hdr,
             f"meta={noindex_meta} header={noindex_hdr}")
    итог["metrics"]["indexability"] = "closed" if (noindex_meta and noindex_hdr) else "OPEN_OR_PARTIAL"

    # Технический подвал: версия и короткий хеш рядом — след отладочного вывода.
    тех_подвал = re.search(r"Lords\s*·\s*\d+\.\d+\.\d+\s*·\s*[0-9a-f]{7,}", дом)
    отметить("footer_without_build_markers", тех_подвал is None,
             тех_подвал.group(0) if тех_подвал else "")

    канон = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', дом)
    итог["metrics"]["canonical"] = канон.group(1) if канон else ""
    if канон:
        отметить("canonical_is_exact_domain", домен in канон.group(1), канон.group(1))
    else:
        отметить("canonical_present", False, "нет link rel=canonical")

    карточек = len(re.findall(r'class="[^"]*\bc--(?:poster|episode|editorial)\b', дом))
    итог["metrics"]["home_cards"] = карточек
    отметить("home_has_cards", карточек > 0, f"{карточек} карточек")

    # --- 3. Каталог, постраничность, 404 ------------------------------------
    код_к, каталог, _ = запрос(база, "/catalog/", домен)
    отметить("catalog_200", код_к == 200, f"код {код_к}")
    карточек_к = len(re.findall(r'class="[^"]*\bc--(?:poster|episode|editorial)\b', каталог))
    итог["metrics"]["catalog_cards"] = карточек_к
    отметить("catalog_has_cards", карточек_к > 0, f"{карточек_к} карточек")

    # Постраничность у витрины параметром запроса, а не сегментом пути:
    # `/catalog/?page=2`. Проверять сегмент значило бы проверять несуществующий
    # маршрут и объявлять провалом работающую страницу.
    код_2, _, _ = запрос(база, "/catalog/?page=2", домен)
    отметить("pagination_second_200", код_2 == 200, f"код {код_2}")
    код_н, тело_н, _ = запрос(база, "/catalog/?page=999999", домен)
    отметить("pagination_invalid_404", код_н == 404, f"код {код_н}")
    отметить("invalid_page_not_soft_404", код_н != 200, f"код {код_н}")

    код_нет, тело_нет, _ = запрос(база, "/zzz-nonexistent-route-smoke/", домен)
    отметить("unknown_route_404", код_нет == 404, f"код {код_нет}")
    итог["metrics"]["soft_404_count"] = int(код_н == 200) + int(код_нет == 200)

    # --- 4. Поиск: точный и бессмысленный -----------------------------------
    код_б, бессмыслица, _ = запрос(база, "/search/?q=zzzqqxvbnmwy", домен)
    карточек_б = len(re.findall(r'class="[^"]*\bc--(?:poster|episode|editorial)\b', бессмыслица))
    итог["metrics"]["search_nonsense_cards"] = карточек_б
    отметить("search_nonsense_is_empty", код_б == 200 and карточек_б == 0,
             f"код {код_б}, карточек {карточек_б}")

    # --- 5. Плеер: один экземпляр, без автозапуска ---------------------------
    ссылки = найти_ссылки(дом) + найти_ссылки(каталог)
    тайтлы = [s for s in ссылки if re.match(r"^/(?:film|serial|movie|title|watch)/", s)]
    итог["metrics"]["title_links_found"] = len(тайтлы)
    if тайтлы:
        код_т, тайтл, _ = запрос(база, тайтлы[0], домен)
        отметить("title_200", код_т == 200, f"{тайтлы[0]} код {код_т}")
        # Плеер монтируется не тегом iframe, а узлом `data-player-host`: провайдер
        # подставляет кадр скриптом уже в браузере. Считать iframe в серверной
        # разметке значит всегда получать ноль и выдавать это за «не больше
        # одного» — проверка, которая не может упасть, ничего не проверяет.
        # Считаются ЭЛЕМЕНТЫ с атрибутом, а не вхождения строки: та же строка
        # встречается в CSS-селекторе и в скрипте монтирования, и подсчёт по
        # тексту давал четыре «экземпляра» там, где элемент ровно один.
        хостов = len(re.findall(r"<[a-zA-Z][^>]*\bdata-player-host\b[^>]*>", тайтл))
        рам = len(re.findall(r'<[a-zA-Z][^>]*class="[^"]*\bpl__frame\b[^"]*"[^>]*>', тайтл))
        кадров = len(re.findall(r"<iframe\b", тайтл))
        плееров = max(хостов, кадров)
        итог["metrics"]["player_instance_max"] = плееров
        итог["metrics"]["player_frames_declared"] = рам
        отметить("player_present", плееров >= 1, f"хостов {хостов}, iframe {кадров}")
        отметить("player_instance_max_1", плееров <= 1, f"{плееров} экземпляров")
        отметить("player_layout_contract", 'data-player-layout-contract="full-bleed-v1"' in тайтл, "")
        автозапусков = len(
            re.findall(r"autoplay\s*[:=]\s*(?:true|1|\"1\"|'1')|\ballow=\"[^\"]*autoplay", тайтл, re.I)
        )
        итог["metrics"]["autoplay_count"] = автозапусков
        отметить("autoplay_absent", автозапусков == 0, f"{автозапусков} совпадений")
        итог["metrics"]["title_probe"] = тайтлы[0]
    else:
        итог["metrics"]["player_instance_max"] = "NOT_MEASURABLE_NO_TITLE_LINK"
        итог["metrics"]["autoplay_count"] = "NOT_MEASURABLE_NO_TITLE_LINK"

    # --- 6. Свежесть: дата видна целиком ------------------------------------
    # Обрезанная обязательная дата выглядит как «20.09…» — многоточие в дате
    # запрещено контрактом, и его видно прямо в разметке.
    обрезанных = len(re.findall(r"\d{2}\.\d{2}\.\d{0,4}\s*(?:…|\.\.\.)", дом + каталог))
    итог["metrics"]["timestamp_ellipsis_count"] = обрезанных
    отметить("no_timestamp_ellipsis", обрезанных == 0, f"{обрезанных} совпадений")

    # --- 7. Геометрия постера объявлена --------------------------------------
    пропорция = re.search(r"aspect-ratio\s*:\s*2\s*/\s*3", дом)
    отметить("poster_aspect_ratio_declared", пропорция is not None,
             "aspect-ratio: 2/3" if пропорция else "не найдено в разметке главной")
    итог["metrics"]["poster_aspect_ratio_violations"] = 0 if пропорция else "NOT_MEASURABLE"

    # --- 8. Адаптивность: мета и точки перелома ------------------------------
    отметить("viewport_meta", 'name="viewport"' in дом, "")
    точки = len(set(re.findall(r"@media[^{]*max-width:\s*(\d+)px", дом)))
    итог["metrics"]["breakpoints_declared"] = точки
    отметить("responsive_breakpoints_declared", точки >= 2, f"{точки} точек перелома")

    # --- 9. Внутренние ссылки ------------------------------------------------
    выборка = ссылки[: ожидания.get("link_sample", 25)]
    битых = []
    коды5xx = 0
    for ссылка in выборка:
        код_с, _, _ = запрос(база, ссылка, домен)
        if код_с >= 500 or код_с == 0:
            коды5xx += 1
            битых.append(f"{ссылка}:{код_с}")
        elif код_с >= 400:
            битых.append(f"{ссылка}:{код_с}")
    итог["metrics"]["internal_links_checked"] = len(выборка)
    итог["metrics"]["broken_internal_links"] = len(битых)
    итог["metrics"]["http_5xx_count"] = коды5xx
    отметить("no_broken_internal_links", not битых, "; ".join(битых[:5]))
    отметить("no_5xx", коды5xx == 0, f"{коды5xx} ответов 5xx")

    итог["failed_checks"] = провалы
    итог["verdict"] = "PASS" if not провалы else "FAIL"
    итог["checked_at_utc"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    итог["not_measurable_here"] = [
        "TLS, редиректы и заголовки nginx: публичный контур недоступен (нет хостов в allowlist)",
        "обрезание текста и наложения в пикселях: требуется браузер; контракт закрыт набором tests/lords",
    ]
    return итог


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--expect-artifact", default="")
    parser.add_argument("--expect-release", default="")
    parser.add_argument("--expect-design", default="")
    parser.add_argument("--record")
    parser.add_argument("--runs", type=int, default=1, help="сколько последовательных прогонов")
    args = parser.parse_args()

    реестр = _реестр()
    запись = (реестр.get("sites") or {}).get(args.site)
    if not запись or запись.get("scope") != "exact-domain-registry":
        print(f"витрины {args.site} нет в exact-domain реестре", file=sys.stderr)
        return FAIL
    база = f"http://127.0.0.1:{запись['port']}"
    домен = запись["exact_domain"]

    прогоны = []
    for номер in range(1, args.runs + 1):
        итог = проверить(args.site, база, домен, {
            "artifact": args.expect_artifact,
            "release_dir": args.expect_release,
            "design": args.expect_design,
        })
        итог["run"] = номер
        прогоны.append(итог)
        print(f"прогон {номер}: {итог['verdict']}"
              + (f" — провалы: {', '.join(итог['failed_checks'])}" if итог["failed_checks"] else ""))

    сводка = {
        "site": args.site,
        "domain": домен,
        "unit": запись["unit"],
        "runs": прогоны,
        "stable_runs": sum(1 for п in прогоны if п["verdict"] == "PASS"),
        "verdict": "PASS" if all(п["verdict"] == "PASS" for п in прогоны) else "FAIL",
    }
    if args.record:
        pathlib.Path(args.record).write_text(
            json.dumps(сводка, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps({k: v for k, v in сводка.items() if k != "runs"}, ensure_ascii=False))
    return PASS if сводка["verdict"] == "PASS" else FAIL


if __name__ == "__main__":
    raise SystemExit(main())
