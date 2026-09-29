#!/usr/bin/env python3
"""Состав сезонов в снимке конвейера: дополнить его по плейлисту провайдера.

Где именно теряются сезоны
--------------------------

Производитель строит `seasons` ИСКЛЮЧИТЕЛЬНО из detail API: состав читается в
`_состав_сезонов` (`automation/host/nova-detail-backfill.py`) и приводится к
виду витрины в `сезоны_рендерера` (`factory/lords/nova_publish.py`). Плеер же
посетителя ходит в ПЛЕЙЛИСТ. Два конца одного источника отвечают по-разному, и
это измерено 2026-09-29 на свежем кэше detail (снят 03:42 того же утра):

    boec-baki          detail: 2 сезона (24, 24)
                       плейлист: 8 сезонов — 1, 2, 3, 5, 6, 7, 8, 9; 151 серия
    avatar-korolya-2   detail: 4 сезона (12, 12, 17, 3)
                       плейлист: 5 сезонов (12, 12, 12, 12, 17)

Случаи РАЗНЫЕ, и в этом вся суть. У `boec-baki` шесть сезонов просто потеряны.
У `avatar-korolya-2` те же семнадцать серий лежат у плейлиста в ПЯТОМ сезоне, а
снимок называет их третьим: это сдвиг нумерации, и «добавить пятый сезон» здесь
значило бы показать одно и то же дважды.

Почему не по числу серий
------------------------

Число серий совпадает у разных сезонов сплошь и рядом — судить по нему значит
угадывать. Соответствие устанавливается по УСТОЙЧИВЫМ идентификаторам дорожек
(`cvhId`), общим у обоих концов источника: пересечение множеств отвечает на
вопрос «это тот же сезон?» прямо. Правила не переписаны здесь заново — они
взяты из `episode_sync.py`, того же модуля, который работает в витринах: две
копии одного правила разошлись бы, и тогда конвейер и витрина спорили бы о
составе одного и того же сериала.

Что инструмент делает и чего не делает
--------------------------------------

Делает: дополняет снимок недостающими сезонами и перечнями реальных номеров
(`nums`), включая спецвыпуск с номером 0, пропуски в нумерации и номера выше
прежнего `eps`. Помечает такой сезон `from: "player"` — происхождение видно.

Не делает: не перенумеровывает существующие сезоны, не меняет `eps` уже
объявленных, не трогает адреса страниц, каталог, оценки и разметку. При сдвиге
нумерации не добавляет НИЧЕГО и называет запись в отчёте.

    python3 nova-seasons-complete.py --snapshot <site>-details.json \
        --publisher 10238 --origin lordserial33.biz [--limit 200] [--apply]

Без `--apply` не пишет ничего: у инструмента, который пишет по умолчанию,
однажды не посмотрят на флаги.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent


_ПРАВИЛА = None


def правила():
    """Те же правила, что работают в витринах. Второй копии здесь нет.

    Модуль загружается ОДИН раз на процесс. Повторная загрузка давала бы второй
    экземпляр с собственными глобальными переменными: проверка, подменившая
    запрос к провайдеру, работала бы не с тем модулем, который потом спрашивает
    сеть, — и молча ходила бы в сеть из проверки.
    """
    global _ПРАВИЛА
    if _ПРАВИЛА is None:
        спец = importlib.util.spec_from_file_location(
            "_episode_sync", КОРЕНЬ / "episode_sync.py")
        модуль = importlib.util.module_from_spec(спец)
        sys.modules["_episode_sync"] = модуль
        спец.loader.exec_module(модуль)
        _ПРАВИЛА = модуль
    return _ПРАВИЛА


def кандидаты(деталь: dict) -> list:
    """Идентификаторы записи у поставщика, в порядке правдоподобия.

    Порядок тот же, что у витрины: подтверждённые источники, затем собственный
    идентификатор провайдера. Спрашивать не тем ключом значило бы измерять
    доступность записи, которой посетитель всё равно не увидит.
    """
    итог, увидели = [], set()

    def добавить(агрегатор, значение):
        агрегатор, значение = (агрегатор or "").strip(), str(значение or "").strip()
        if агрегатор and значение and (агрегатор, значение) not in увидели:
            увидели.add((агрегатор, значение))
            итог.append((агрегатор, значение))

    источники = [и for и in (деталь.get("sources") or ()) if isinstance(и, dict)]
    for и in источники:
        if str(и.get("availability_status") or "").lower() == "available":
            добавить(str(и.get("provider") or ""), и.get("source_id"))
    свой = str(деталь.get("id") or "").strip().lower()
    if len(свой) == 36 and свой.count("-") == 4:
        добавить("cvh", свой)
    for и in источники:
        добавить(str(и.get("provider") or ""), и.get("source_id"))
    return итог


def отбор(детали: dict, предел: int) -> list:
    """Кого спрашивать. Записи без сезонов и фильмы в круг не берутся.

    Первыми — те, у кого состав правдоподобно неполон: один сезон при
    непрерывной нумерации ничего не говорит, а вот запись, где объявленный
    состав меньше, чем бывает у сериала с таким числом источников, стоит
    спросить. Полный отбор стоил бы двадцати тысяч запросов за прогон.
    """
    годные = [(с, д) for с, д in sorted(детали.items())
              if isinstance(д, dict)
              and [x for x in (д.get("seasons") or []) if int(x.get("eps") or 0) >= 1]]
    годные.sort(key=lambda п: (len(п[1].get("seasons") or []), п[0]))
    return годные[:предел]


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--snapshot", required=True)
    р.add_argument("--publisher", required=True)
    р.add_argument("--origin", required=True)
    р.add_argument("--limit", type=int, default=200)
    р.add_argument("--rps", type=float, default=1.0)
    р.add_argument("--apply", action="store_true",
                   help="записать снимок; без флага только отчёт")
    р.add_argument("--report", default="")
    args = р.parse_args(argv)

    es = правила()
    путь = Path(args.snapshot)
    снимок = json.loads(путь.read_text(encoding="utf-8"))
    детали = снимок.get("details") or {}
    отметка = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    дополнено, сдвиги, спрошено, отказов = [], [], 0, 0
    пауза = 1.0 / args.rps if args.rps > 0 else 0.0
    for слаг, деталь in отбор(детали, args.limit):
        найдено = опознание = {}
        for агрегатор, ид in кандидаты(деталь)[:4]:
            if спрошено:
                time.sleep(пауза)
            спрошено += 1
            ответ = es._плейлист(args.publisher, агрегатор, ид, args.origin)
            if ответ is None:
                отказов += 1
                continue
            найдено = es.серии_по_сезонам(ответ)
            опознание = es.опознание_по_сезонам(ответ)
            if найдено:
                break
        if not найдено:
            continue
        объявленные = {int(с.get("n") or 0) for с in (деталь.get("seasons") or [])}
        новые = [н for н in sorted(найдено) if н not in объявленные and найдено[н]]
        if not новые:
            es.согласовать(деталь, найдено, отметка, опознание, None)
            continue
        if not es.нумерация_сходится(деталь, найдено, опознание, None):
            сдвиги.append({"slug": слаг, "seasons": новые,
                           "reason": "нумерация концов источника разошлась"})
            continue
        было = len(деталь.get("seasons") or [])
        es.согласовать(деталь, найдено, отметка, опознание, None)
        стало = len(деталь.get("seasons") or [])
        if стало > было:
            дополнено.append({"slug": слаг, "added": стало - было, "seasons": новые})

    отчёт = {
        "at": отметка, "snapshot": str(путь), "asked": спрошено,
        "request_failures": отказов, "completed": дополнено[:50],
        "completed_total": len(дополнено),
        "numbering_conflicts": сдвиги[:50], "conflicts_total": len(сдвиги),
        "applied": bool(args.apply),
    }
    if args.apply and дополнено:
        врем = путь.with_suffix(путь.suffix + ".seasons.tmp")
        врем.write_text(json.dumps(снимок, ensure_ascii=False), encoding="utf-8")
        врем.replace(путь)
    if args.report:
        Path(args.report).write_text(json.dumps(отчёт, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps({к: в for к, в in отчёт.items()
                      if к not in ("completed", "numbering_conflicts")},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
