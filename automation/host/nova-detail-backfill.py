#!/usr/bin/env python3
"""Добор подробностей каталога из detail API CDNVideoHub.

Зачем отдельный инструмент
--------------------------

Обогащение живёт внутри сборки сайта и ограничено бюджетом в 300–400 запросов
за прогон: полный каталог за раз — это десятки тысяч запросов подряд, и для
пятнадцатиминутного цикла это отказ источника, а не обогащение.

Но у бюджета есть следствие, которое видно только на длинной дистанции: при
400 записях в сутки каталог из 53 390 записей набирает покрытие сто тридцать
дней. Описание, жанры, страны и состав сезонов до страниц всё это время не
доходят — не потому, что источник их не отдаёт, а потому, что их не успели
спросить.

Этот инструмент закрывает разрыв один раз: он проходит весь каталог с
ограничением частоты, складывает ответы в тот же кэш и после этого суточному
циклу остаётся только приращение.

Чего он не делает
-----------------

Не трогает каталог витрин, шаблоны, плеер и оценки. Пишет только в кэш
подробностей; публикация — отдельный шаг, и запускается она явно.

Оценок тут ждать не следует. Detail отдаёт те же `kinopoisk_rating` и
`imdb_rating`, что и список: на выборке в 3 000 записей detail добавил одну
оценку Кинопоиска и одну IMDb. Инструмент добирает описания и метаданные, а
не рейтинги, и обещать обратное значило бы объяснять невыполнимый порог
незавершённой работой.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from factory.lords import content_live, detail_enrichment  # noqa: E402

СНИМОК = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json")
КЭШ = Path("/srv/site-factory/repo/var/lords/detail-cache")
ОТЧЁТ = Path("/srv/site-factory/repo/var/lords/detail-backfill-report.json")
ЗАМОК = Path("/srv/site-factory/repo/var/lords/nova-detail-backfill.lock")
ПОЗИЦИЯ = Path("/srv/site-factory/repo/var/lords/detail-ring-position.json")
ПОЗИЦИЯ_СВЕЖИХ = Path("/srv/site-factory/repo/var/lords/detail-hot-position.json")


def токен() -> str:
    """Токен из systemd credential. В окружении и журнале его нет.

    Значение не печатается и не возвращается наружу ни при каких условиях:
    единственный его потребитель — Fetcher.
    """
    каталог = os.environ.get("CREDENTIALS_DIRECTORY")
    имя = os.environ.get("CDNVIDEOHUB_API_TOKEN_CREDENTIAL", "cdnvideohub_api_token")
    if not каталог:
        raise SystemExit("нет CREDENTIALS_DIRECTORY: запускать через systemd с LoadCredential")
    путь = Path(каталог) / имя
    if not путь.is_file():
        raise SystemExit(f"credential {имя} не передан")
    return путь.read_text(encoding="utf-8").strip()


def _продолжающиеся(идентификаторы: list[str], кэш: Path) -> list[str]:
    """Тайтлы, у которых доступно меньше заявленного, — по кэшу.

    Определяется по уже известным данным, а не запросом к источнику:
    спрашивать источник о том, кого спрашивать, значило бы потратить тот
    самый бюджет, который здесь экономится.
    """
    идущие = []
    for ид in идентификаторы:
        путь = кэш / f"{ид}.json"
        if not путь.is_file():
            continue
        try:
            деталь = (json.loads(путь.read_text(encoding="utf-8")).get("detail")
                      or {})
        except (OSError, ValueError):
            continue
        for сезон in (деталь.get("seasons") or []):
            try:
                доступно = int(сезон.get("available_episodes_count"))
                всего = int(сезон.get("episodes_count"))
            except (TypeError, ValueError):
                continue
            if доступно < всего:
                идущие.append(ид)
                break
    return идущие


def _состав_сезонов(ид: str, кэш: Path) -> dict[int, tuple[int, int]]:
    """Сезоны тайтла из кэша: номер -> (доступно, заявлено)."""
    путь = кэш / f"{ид}.json"
    if not путь.is_file():
        return {}
    try:
        деталь = (json.loads(путь.read_text(encoding="utf-8")).get("detail") or {})
    except (OSError, ValueError):
        return {}
    итог = {}
    for сезон in (деталь.get("seasons") or []):
        try:
            итог[int(сезон.get("season_number") or сезон.get("number") or 0)] = (
                int(сезон.get("available_episodes_count")),
                int(сезон.get("episodes_count")))
        except (TypeError, ValueError):
            continue
    return итог


def _сериалы(идентификаторы: list[str], кэш: Path) -> list[str]:
    """Только те, у кого вообще бывают серии.

    Полнометражное кино в круг брать незачем: у него нечему вырасти, а бюджет
    оно тратит наравне с сериалом.
    """
    return [ид for ид in идентификаторы if _состав_сезонов(ид, кэш)]


def _прочитать_позицию(файл: Path | None = None) -> str:
    файл = файл if файл is not None else ПОЗИЦИЯ
    try:
        return str(json.loads(файл.read_text(encoding="utf-8")).get("after") or "")
    except (OSError, ValueError):
        return ""


def _записать_позицию(после: str, пройдено: int, файл: Path | None = None) -> None:
    файл = файл if файл is not None else ПОЗИЦИЯ
    файл.parent.mkdir(parents=True, exist_ok=True)
    файл.write_text(json.dumps(
        {"after": после, "walked_last_run": пройдено,
         "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _свежие_сериалы(записи: list[dict], с_года: int) -> list[str]:
    """Сериалы, у которых серии ещё могут выходить.

    Год — единственный дешёвый признак, который здесь работает. Признаки из
    самих данных не годятся: поставщик поднимает доступное и заявленное вместе,
    и выросший сезон выглядит завершённым, а `updated_at` при выходе серии не
    меняется. Год берётся из СПИСКА, то есть не стоит ни одного запроса.

    Сериал 2015 года новых серий не получит, и держать его в одном круге с
    текущим сезоном значит тратить на него ту же долю бюджета.
    """
    return [str(з["external_id"]) for з in записи
            if з.get("is_series") and з.get("external_id")
            and (з.get("year") or 0) >= с_года]


def _круг(идентификаторы: list[str], кэш: Path | None = None, *,
          кроме: set[str], сколько: int,
          позиция: Path | None = None) -> list[str]:
    """Следующий отрезок кругового обхода, начиная с сохранённой позиции.

    Порядок обязан быть устойчивым, иначе «позиция» ничего не гарантирует:
    при нестабильном порядке круг не проворачивается, а перетасовывается.
    Поэтому `sorted`, а позиция хранится ИДЕНТИФИКАТОРОМ, а не номером —
    каталог между прогонами растёт и уменьшается, и номер указывал бы каждый
    раз на другого.

    Срочные исключены: они уже спрошены отдельным проходом, и второй запрос в
    том же прогоне им не нужен.
    """
    основа = _сериалы(идентификаторы, кэш) if кэш is not None else идентификаторы
    кольцо = [ид for ид in sorted(основа) if ид not in кроме]
    if not кольцо or сколько == 0:
        return []
    if сколько < 0:                       # весь круг за один прогон
        сколько = len(кольцо)
    после = _прочитать_позицию(позиция)
    начало = 0
    if после:
        # bisect не годится: позиция могла исчезнуть из каталога.
        начало = next((i for i, ид in enumerate(кольцо) if ид > после), 0)
    отрезок = кольцо[начало:начало + сколько]
    if len(отрезок) < сколько:                       # круг замкнулся
        отрезок += кольцо[:сколько - len(отрезок)]
    return отрезок


def _не_понижать(прежние: dict[str, dict[int, tuple[int, int]]], кэш: Path) -> dict:
    """Вернуть прежнее число серий там, где ответ его УМЕНЬШИЛ.

    Понижение `available_episodes_count` — это отзыв прав или сбой выдачи, а
    не «серий стало меньше». Снять по одному такому ответу ссылку, которая уже
    работала, значит отдать посетителю 404 на месте рабочей серии.
    """
    восстановлено = []
    for ид, было_сезонов in прежние.items():
        стало = _состав_сезонов(ид, кэш)
        починить = {н: было_сезонов[н][0] for н, (дост, _) in стало.items()
                    if н in было_сезонов and дост < было_сезонов[н][0]}
        if not починить:
            continue
        путь = кэш / f"{ид}.json"
        try:
            данные = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for сезон in ((данные.get("detail") or {}).get("seasons") or []):
            н = int(сезон.get("season_number") or сезон.get("number") or 0)
            if н in починить:
                сезон["available_episodes_count"] = починить[н]
        путь.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
        восстановлено.append(ид)
    return {"count": len(восстановлено), "titles": восстановлено[:20]}


def покрытие_кэша(идентификаторы: list[str], кэш: Path) -> dict:
    есть = сописанием = 0
    for ид in идентификаторы:
        п = кэш / f"{ид}.json"
        if not п.is_file():
            continue
        есть += 1
        try:
            д = json.loads(п.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        текст = ((д.get("detail") or {}).get("description") or "").strip()
        if len(текст) >= 40:
            сописанием += 1
    всего = len(идентификаторы) or 1
    return {"titles": len(идентификаторы), "cached": есть,
            "cached_pct": round(есть * 100 / всего, 2),
            "with_description": сописанием,
            "description_pct": round(сописанием * 100 / всего, 2)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="добор подробностей каталога")
    ap.add_argument("--snapshot", type=Path, default=СНИМОК)
    ap.add_argument("--cache", type=Path, default=КЭШ)
    ap.add_argument("--budget", type=int, default=2000,
                    help="предел сетевых запросов за прогон")
    ap.add_argument("--report", type=Path, default=ОТЧЁТ)
    ap.add_argument("--ongoing-ttl", type=int, default=6 * 3600,
                    help="срок годности записи продолжающегося тайтла, с; "
                         "0 выключает отдельный проход")
    ap.add_argument("--ongoing-budget", type=int, default=1000,
                    help="предел запросов на проход по продолжающимся")
    # Бюджеты подобраны так, чтобы СУТОЧНЫЙ прогон остался ниже уже
    # подтверждённой нагрузки (6000 запросов), а не выше неё. Частый опрос
    # передаёт свои значения явно: см. automation/host/nova-episode-poll.service.
    #
    # Дробить круг по прогонам приходится потому, что узкое место — бюджет
    # источника, а не наша скорость. Арифметика простая и от неё не уйти:
    # сериалов 20 473, из них с годом от прошлого — 3 036. Полный круг при
    # 6000 запросов в сутки — три с половиной суток; круг по свежим — около
    # пятнадцати часов. Хотите быстрее — нужен больший бюджет, и это решение
    # владельца, а не умолчание инструмента.
    ap.add_argument("--ring-budget", type=int, default=600,
                    help="запросов на круг по ВСЕМ сериалам; 0 выключает")
    ap.add_argument("--hot-budget", type=int, default=600,
                    help="запросов на круг по сериалам последних лет; 0 выключает")
    ap.add_argument("--hot-since-year", type=int, default=0,
                    help="год, с которого сериал считается свежим; "
                         "0 — прошлый календарный год")
    ap.add_argument("--ring-ttl", type=int, default=6 * 3600,
                    help="срок годности записи в круговом обходе, с")
    ap.add_argument("--order", choices=("uncached-first", "catalog"),
                    default="uncached-first",
                    help="кого спрашивать первым")
    a = ap.parse_args(argv)

    # Один добор за раз. Два процесса, идущих по одному кэшу, тратят бюджет
    # источника на одни и те же записи и мешают друг другу считать покрытие.
    ЗАМОК.parent.mkdir(parents=True, exist_ok=True)
    замок = open(ЗАМОК, "w")
    try:
        fcntl.flock(замок, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(json.dumps({"status": "SKIPPED_LOCKED",
                          "detail": f"другой добор уже идёт ({ЗАМОК})"},
                         ensure_ascii=False))
        return 0

    начало = time.time()
    записи = json.loads(a.snapshot.read_text(encoding="utf-8")).get("items") or []
    идентификаторы = [str(з["external_id"]) for з in записи if з.get("external_id")]
    до = покрытие_кэша(идентификаторы, a.cache)

    contract = content_live.load_live_contract()
    fetcher = content_live.Fetcher(contract=contract, token=токен())
    cache = detail_enrichment.DetailCache(a.cache)

    # Порядок решает, что вырастет за прогон. По умолчанию модуль идёт по
    # каталогу, и устаревшая запись съедает запрос наравне с той, которой в
    # кэше нет вовсе. На каталоге, где кэш покрывает треть, это значит, что
    # бюджет уходит на обновление уже известного, а покрытие стоит на месте:
    # замер показал 2 069 обновлённых записей и ноль новых за полчаса.
    #
    # Поэтому сначала спрашиваются те, кого в кэше нет. Обновление устаревшего
    # никуда не девается — оно идёт следом, когда добирать уже нечего.
    # ПРОДОЛЖАЮЩИЕСЯ СПРАШИВАЮТСЯ ОТДЕЛЬНО И ЧАЩЕ.
    #
    # `available_episodes_count` — единственное поле, которое меняется не раз
    # в месяц, а каждую неделю выхода серии. Оно приезжает тем же кэшем, у
    # которого TTL семь суток, и при бюджете 6000 записей на 53688 запись
    # перечитывается примерно раз в девять суток. Для описания и постера это
    # нормально; для числа вышедших серий — нет: витрина показывала на серию
    # меньше, чем поставщик, и ошибки при этом не возникало нигде — ни у
    # производителя, ни у витрины. Так «Новые серии» на animedia.space
    # простояли на тринадцати событиях при зелёном таймере.
    #
    # Измерено: продолжающихся (доступно меньше заявленного) во всём каталоге
    # 403 из 53688 — 0.8 %. При трёх секундах на запись это около двадцати
    # минут, то есть теряется в существующем шестичасовом пределе юнита.
    # Обход всего каталога чаще не нужен и источнику не полезен.
    продолжающиеся = _продолжающиеся(идентификаторы, a.cache)
    if продолжающиеся and a.ongoing_ttl > 0:
        print(f"[продолжающиеся] {len(продолжающиеся)} из {len(идентификаторы)},"
              f" TTL {a.ongoing_ttl} с", file=sys.stderr)
        быстрый = detail_enrichment.DetailCache(a.cache, ttl=a.ongoing_ttl)
        идущие_записи = [з for з in записи
                         if str(з.get("external_id")) in set(продолжающиеся)]
        _, отчёт_идущих = detail_enrichment.enrich_items(
            идущие_записи, fetcher=fetcher, contract=contract, cache=быстрый,
            budget=min(len(продолжающиеся), a.ongoing_budget),
            order=продолжающиеся)
    else:
        отчёт_идущих = {"skipped": ("продолжающихся нет" if not продолжающиеся
                                    else "выключено ongoing-ttl=0")}

    # Круговой обход. Отбор «доступно меньше заявленного» его не заменяет:
    # поставщик поднимает `available_episodes_count` и `episodes_count`
    # ВМЕСТЕ, поэтому выросший сезон в устаревшем снимке выглядит завершённым
    # (9 из 9) и в набор срочных не попадает вообще. Так тайтл может стоять на
    # девяти сериях при двадцати трёх у источника, и ни один отбор по
    # признакам его не увидит — увидит только тот, кто спросит.
    #
    # `updated_since` тут тоже непригоден: `updated_at` при выходе серии не
    # меняется, и инкрементальный отбор пропустил бы ровно эти случаи.
    #
    # Отсюда круг: спрашиваем ВСЕХ сериалов по очереди, сохраняя позицию между
    # прогонами. Полнота не зависит ни от одного признака в устаревших данных.
    прежние = {ид: _состав_сезонов(ид, a.cache) for ид in продолжающиеся}
    с_года = a.hot_since_year or (time.gmtime().tm_year - 1)

    def пройти(имя, отрезок, позиция_файла):
        """Один круг: спросить отрезок и сдвинуть позицию на пройденное."""
        if not отрезок:
            return {"walked": 0, "skipped": "пусто"}
        print(f"[{имя}] {len(отрезок)} начиная после "
              f"{_прочитать_позицию(позиция_файла) or 'начала'}", file=sys.stderr)
        прежние.update({ид: _состав_сезонов(ид, a.cache) for ид in отрезок})
        кольцевой = detail_enrichment.DetailCache(a.cache, ttl=a.ring_ttl)
        свои = [з for з in записи if str(з.get("external_id")) in set(отрезок)]
        _, отчёт_ = detail_enrichment.enrich_items(
            свои, fetcher=fetcher, contract=contract, cache=кольцевой,
            budget=len(отрезок), order=отрезок)
        # Позиция двигается на число ПРОЙДЕННЫХ по этому кругу, а не на размер
        # очереди: иначе срочные незаметно замедляли бы продвижение.
        _записать_позицию(отрезок[-1], len(отрезок), позиция_файла)
        return {"walked": len(отрезок),
                "report": {k: v for k, v in vars(отчёт_).items()
                           if isinstance(v, (int, float, str))}}

    # Круг по свежим идёт ПЕРВЫМ: серии выходят у них, а не у каталога целиком.
    свежие = _свежие_сериалы(записи, с_года)
    спрошено = set(продолжающиеся)
    отрезок_свежих = _круг(свежие, кроме=спрошено, сколько=a.hot_budget,
                           позиция=ПОЗИЦИЯ_СВЕЖИХ)
    отчёт_свежих = пройти("свежие", отрезок_свежих, ПОЗИЦИЯ_СВЕЖИХ)
    # Пройденное свежим кругом исключается из полного: второй запрос за тот же
    # прогон ничего не добавит, а бюджет потратит.
    спрошено |= set(отрезок_свежих)

    # Полный круг — страховка от самого признака «свежести»: год берётся из
    # списка, и переизданный старый сериал в него не попадёт.
    отчёт_круга = пройти("круг", _круг(идентификаторы, a.cache, кроме=спрошено,
                                       сколько=a.ring_budget), ПОЗИЦИЯ)

    восстановлено = _не_понижать(прежние, a.cache)

    порядок = None
    if a.order == "uncached-first":
        нет_в_кэше, есть_в_кэше = [], []
        for ид in идентификаторы:
            (есть_в_кэше if (a.cache / f"{ид}.json").is_file() else нет_в_кэше).append(ид)
        порядок = нет_в_кэше + есть_в_кэше
        print(f"[порядок] нет в кэше: {len(нет_в_кэше)}, обновление: {len(есть_в_кэше)}",
              file=sys.stderr)

    _, отчёт = detail_enrichment.enrich_items(
        записи, fetcher=fetcher, contract=contract, cache=cache,
        budget=a.budget, order=порядок)

    после = покрытие_кэша(идентификаторы, a.cache)
    итог = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(начало)),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_sec": round(time.time() - начало, 1),
        "budget": a.budget,
        "ongoing": {"count": len(продолжающиеся), "ttl": a.ongoing_ttl,
                    "report": отчёт_идущих},
        "hot": {"since_year": с_года, "count": len(свежие),
                "budget": a.hot_budget, "position_after":
                _прочитать_позицию(ПОЗИЦИЯ_СВЕЖИХ), **отчёт_свежих},
        "ring": {"budget": a.ring_budget, "ttl": a.ring_ttl,
                 "position_after": _прочитать_позицию(ПОЗИЦИЯ), **отчёт_круга},
        "downgrades_restored": восстановлено,
        "requests_made": getattr(fetcher, "requests_made", None),
        "retries_made": getattr(fetcher, "retries_made", None),
        "enrichment": {k: v for k, v in vars(отчёт).items()
                       if isinstance(v, (int, float, str))},
        "before": до,
        "after": после,
        "gained_cached": после["cached"] - до["cached"],
        "gained_description": после["with_description"] - до["with_description"],
    }
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(итог, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(итог, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
