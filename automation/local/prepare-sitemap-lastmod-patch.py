#!/usr/bin/env python3
"""Точечный патч честного `lastmod` частей карты для УСТАНОВЛЕННОГО рантайма.

Дефект (MOD-111), измеренный 20.10 по всем 17 индексируемым домéнам: в
`/sitemap.xml` у 12 витрин `lastmod` частей ОТСУТСТВУЕТ вовсе, а у
`yummyani.site` стоит одна устаревшая константа. Обходчик читает индекс первым и
по `lastmod` решает, перезапрашивать ли часть на 45 000-67 000 адресов; решать
ему нечем.

Правка одна и лежит в `построить_sitemap`: дата каждой части = МАКСИМУМ дат
внутри неё, и если внутри нет ни одной даты, `lastmod` не ставится вовсе.

ПОЧЕМУ НЕ ФАЙЛОМ, А ПАТЧЕМ, и причина здесь другая, чем обычно: файлы
РАЗОШЛИСЬ, и ветка НЕ новее. Установленный `seo_layer.py` — 22 624 Б, в ветке —
39 884 Б, но установленный содержит `крошки_со_страницы` и `_НАВ_КРОШЕК`,
которых в ветке нет вовсе. Копия файла в любую сторону снесла бы чужую работу.

ЧЕГО ПАТЧ НЕ ДЕЛАЕТ: не меняет ни один адрес в частях, не меняет их число и
порядок, не ставит дату сборки. Части после патча обязаны быть ПОБАЙТНО теми же
— это проверяется репетицией, а не обещается.

    python3 automation/local/prepare-sitemap-lastmod-patch.py --verify
    python3 automation/local/prepare-sitemap-lastmod-patch.py --source <путь> --verify
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import importlib.util
import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
#: Канарейка названа заранее: `animedia.space` — вторая витрина семейства, на
#: ней правка проверяется до `animedia.icu`.
УСТАНОВЛЕНО = Path("/srv/animedia-space/current/src/seo_layer.py")
ПАТЧ = КОРЕНЬ / "var" / "patches" / "sitemap-lastmod-seo-layer.patch"
#: Деревья, которые витриной не обслуживаются. Ошибку с `app` поймала линия
#: zona-01 на другом патче 20.10, и повторять её незачем.
ЛОВУШКИ = ("/app/", "/app.prev/", "/candidate/")

ЧАСТИ_БЫЛО = """    файлы: list[tuple[str, bytes]] = []
    части = [адреса[i:i + ПРЕДЕЛ_URL] for i in range(0, len(адреса), ПРЕДЕЛ_URL)] or [[]]
    for н, часть in enumerate(части, start=1):
        корень = ET.Element("urlset", xmlns=SM_NS)
        for а, lm in часть:
            _урл(корень, а, lm)
        файлы.append((f"sitemap-{н}.xml",
                      ET.tostring(корень, encoding="utf-8", xml_declaration=True)))
    индекс = ET.Element("sitemapindex", xmlns=SM_NS)
    for имя, _ in файлы:
        s = ET.SubElement(индекс, "sitemap")
        ET.SubElement(s, "loc").text = f"https://{хост}/{имя}\""""

ЧАСТИ_СТАЛО = """    файлы: list[tuple[str, bytes]] = []
    части = [адреса[i:i + ПРЕДЕЛ_URL] for i in range(0, len(адреса), ПРЕДЕЛ_URL)] or [[]]
    #: Дата каждой части — максимум дат ВНУТРИ неё. Копится по ходу, чтобы не
    #: разбирать готовый XML обратно.
    даты_частей: list[str] = []
    for н, часть in enumerate(части, start=1):
        корень = ET.Element("urlset", xmlns=SM_NS)
        for а, lm in часть:
            _урл(корень, а, lm)
        даты_частей.append(max((lm for _, lm in часть if lm), default=""))
        файлы.append((f"sitemap-{н}.xml",
                      ET.tostring(корень, encoding="utf-8", xml_declaration=True)))
    индекс = ET.Element("sitemapindex", xmlns=SM_NS)
    for (имя, _), дата in zip(файлы, даты_частей):
        s = ET.SubElement(индекс, "sitemap")
        ET.SubElement(s, "loc").text = f"https://{хост}/{имя}"
        # `lastmod` части обязателен: по нему обходчик решает, перезапрашивать
        # ли файл на 45 000 адресов. Измерено 20.10 на 12 витринах сети — его
        # не было вовсе, и решать было нечем (MOD-111).
        #
        # Дата берётся из СОДЕРЖИМОГО части, а не из времени сборки. Подстановка
        # времени сборки была бы хуже отсутствия: обходчик поверил бы, что
        # часть обновилась, и перечитал бы 45 000 адресов, в которых ничего не
        # изменилось. У частей постарше дата законно старая — у Lords и Zona
        # свежайшая запись во второй части от июня 2025, и так и должно быть.
        #
        # Если внутри части нет ни одной даты, `lastmod` не ставится: пустая
        # дата или выдуманная «сегодня» обе врут, а отсутствие честно.
        if дата:
            ET.SubElement(s, "lastmod").text = дата"""


def переписать(текст: str) -> str:
    if "даты_частей" in текст:
        raise SystemExit("в установленном файле правка УЖЕ есть — патч не нужен")
    сколько = текст.count(ЧАСТИ_БЫЛО)
    if сколько != 1:
        raise SystemExit(
            f"якорь встречается {сколько} раз вместо одного: установленный файл"
            " изменился. Патч собирать заново, а не подгонять по похожим местам.")
    return текст.replace(ЧАСТИ_БЫЛО, ЧАСТИ_СТАЛО, 1)


def _загрузить(файл: Path, имя: str):
    спец = importlib.util.spec_from_file_location(имя, файл)
    м = importlib.util.module_from_spec(спец)
    sys.modules[имя] = м
    спец.loader.exec_module(м)
    return м


#: Предел адресов в части для РЕПЕТИЦИИ. Настоящий предел 50 000, и на нём
#: набор уместился бы в ОДНУ часть — а тогда «максимум внутри части» и
#: «максимум по всему набору» совпадают, и проверка не различает их. Первая
#: версия репетиции именно так и прошла, ничего не проверив.
ПРЕДЕЛ_ДЛЯ_РЕПЕТИЦИИ = 10


def _страницы() -> list[dict]:
    """Три части с РАЗНЫМИ максимумами дат, все в прошлом, плюс часть без дат.

    Устроено нарочно так, чтобы «максимум внутри части» нельзя было подменить
    «максимумом по набору»: у первой части свежайшая дата 2025-06-10, у второй
    2026-10-19, у третьей дат нет вовсе. Если правка поставит всем частям одну
    дату, это увидит проверка первой части, а не рассуждение.

    Даты в прошлом нарочно: подстановка времени сборки видна сравнением с
    сегодняшним числом.
    """
    набор: list[dict] = []
    # часть 1: десять записей, максимум 2025-06-10
    набор += [{"slug": f"a{н:02d}", "lastmod": f"2025-06-{н + 1:02d}"}
              for н in range(10)]
    # часть 2: десять записей, максимум 2026-10-19
    набор += [{"slug": f"b{н:02d}",
               "lastmod": f"2026-10-{н + 10:02d}T08:00:00Z"} for н in range(10)]
    # часть 3: десять записей БЕЗ даты вовсе
    набор += [{"slug": f"c{н:02d}"} for н in range(10)]
    return набор


def репетиция(было_файл: Path, стало_файл: Path) -> list[str]:
    было = _загрузить(было_файл, "seo_layer_до")
    стало = _загрузить(стало_файл, "seo_layer_после")
    было.ПРЕДЕЛ_URL = ПРЕДЕЛ_ДЛЯ_РЕПЕТИЦИИ
    стало.ПРЕДЕЛ_URL = ПРЕДЕЛ_ДЛЯ_РЕПЕТИЦИИ
    итог: list[str] = []
    хост = "animedia.space"
    разделы = ()

    а = было.построить_sitemap(хост, _страницы(), разделы)
    б = стало.построить_sitemap(хост, _страницы(), разделы)

    было_части = {и: т for и, т in а if и != "sitemap.xml"}
    стало_части = {и: т for и, т in б if и != "sitemap.xml"}
    итог.append(f"частей до {len(было_части)}, после {len(стало_части)}")
    итог.append("ок: части ПОБАЙТНО те же" if было_части == стало_части
                else "ПРОВАЛ: содержимое частей изменилось")

    индекс_до = dict(а)["sitemap.xml"].decode("utf-8")
    индекс_после = dict(б)["sitemap.xml"].decode("utf-8")
    итог.append("ок: до патча lastmod в индексе не было"
                if "lastmod" not in индекс_до
                else "ПРОВАЛ: lastmod в индексе был и до патча — предмет не тот")
    итог.append("ок: после патча lastmod в индексе есть"
                if "<lastmod>" in индекс_после
                else "ПРОВАЛ: lastmod так и не появился")

    # Дата части обязана быть максимумом ВНУТРИ ЭТОЙ части, а не по набору.
    import re as _re
    пары = _re.findall(
        r"<sitemap><loc>([^<]+)</loc>(?:<lastmod>([^<]+)</lastmod>)?</sitemap>",
        индекс_после.replace("\n", ""))
    даты = {имя.rsplit("/", 1)[-1]: дата for имя, дата in пары}
    итог.append(f"даты частей в индексе: {даты}")
    ожидания = {"sitemap-1.xml": "2025-06-10",
                "sitemap-2.xml": "2026-10-19T08:00:00Z",
                "sitemap-3.xml": ""}
    for имя, ждём in ожидания.items():
        дано = даты.get(имя, "ОТСУТСТВУЕТ В ИНДЕКСЕ")
        словами = ждём or "без lastmod"
        итог.append(f"   {'ок' if дано == ждём else 'ПРОВАЛ'}: {имя} ждали"
                    f" {словами}, получили {дано or 'без lastmod'}")
    глобальный = "2026-10-19T08:00:00Z"
    итог.append("ок: первой части НЕ подставлен максимум по всему набору"
                if даты.get("sitemap-1.xml") != глобальный
                else "ПРОВАЛ: всем частям поставлена одна дата")

    сегодня = dt.date.today().isoformat()
    итог.append("ок: сегодняшняя дата не подставлена"
                if сегодня not in индекс_после
                else f"ПРОВАЛ: в индексе стоит дата сборки {сегодня}")

    # Часть без единой даты не получает lastmod вовсе.
    пустая = стало.построить_sitemap(хост, [{"slug": "x"}], ())
    индекс_пустой = dict(пустая)["sitemap.xml"].decode("utf-8")
    итог.append("ок: часть без дат осталась без lastmod"
                if "lastmod" not in индекс_пустой
                else "ПРОВАЛ: части без дат подставлен lastmod")
    return итог


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--source", default=str(УСТАНОВЛЕНО))
    р.add_argument("--verify", action="store_true")
    р.add_argument("--allow-stale", action="store_true")
    а = р.parse_args(аргв)

    исходный = Path(а.source)
    if not исходный.is_file():
        print(f"НЕ СОБРАНО: нет установленного файла {исходный}")
        return 2
    if any(л in str(исходный) for л in ЛОВУШКИ) and not а.allow_stale:
        print(f"НЕ СОБРАНО: {исходный} — не обслуживаемое витриной дерево."
              f" Работающий файл берётся через `current`. Если это нарочно —"
              f" --allow-stale.")
        return 2
    настоящий = исходный.resolve()
    print(f"работающий выпуск: {настоящий.parent.parent.name}")
    было = исходный.read_text(encoding="utf-8")
    стало = переписать(было)
    патч = "".join(difflib.unified_diff(
        было.splitlines(keepends=True), стало.splitlines(keepends=True),
        fromfile="a/src/seo_layer.py", tofile="b/src/seo_layer.py"))
    ПАТЧ.parent.mkdir(parents=True, exist_ok=True)
    ПАТЧ.write_text(патч, encoding="utf-8")
    print(f"патч: {ПАТЧ} ({len(патч.splitlines())} строк)")
    print(f"установленный файл: {исходный} ({исходный.stat().st_size} Б)")

    if not а.verify:
        return 0

    провалов = 0
    with tempfile.TemporaryDirectory() as врем:
        врем = Path(врем)
        к = врем / "seo_layer.py"
        к.write_text(стало, encoding="utf-8")
        try:
            py_compile.compile(str(к), doraise=True)
        except py_compile.PyCompileError as ош:
            print(f"ПРОВЕРКА НЕ ПРОЙДЕНА: не компилируется: {ош}")
            return 1
        print("исправленный файл компилируется")

        проба = врем / "проба"
        (проба / "src").mkdir(parents=True)
        shutil.copy(исходный, проба / "src/seo_layer.py")
        г = subprocess.run(["patch", "-p1", "--dry-run", "-i", str(ПАТЧ)],
                           cwd=проба, capture_output=True, text=True)
        print((г.stdout or г.stderr).strip())
        if г.returncode != 0:
            print("ПРОВЕРКА НЕ ПРОЙДЕНА: патч не прикладывается")
            return 1
        print("патч прикладывается к установленному файлу (--dry-run)")

        print("\nрепетиция: ДО (работающий файл) против ПОСЛЕ (с патчем)")
        for строка in репетиция(исходный, к):
            print(f"   {строка}")
            провалов += 1 if "ПРОВАЛ" in строка else 0
    return 1 if провалов else 0


if __name__ == "__main__":
    sys.exit(главное())
