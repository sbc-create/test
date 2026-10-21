"""Сборщик патча D4: бюджет обхода каталога Yummy.

Дефект, ради которого всё: предел был плоским (80 запросов × 100 записей), и
просмотр каталога обрывался на 8 000 записях при каталоге 8 378 — 378 работ
недостижимы, а листалка объявляла 350 страниц.

Проверяются границы, а не только счастливый путь: якорь, встречающийся не один
раз, — отказ; уже исправленный источник — отказ; и арифметика бюджета, где
первая страница не должна стать дороже, а верхний предел обязан держать.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "prepare_yummy_walk_patch",
    КОРЕНЬ / "automation/local/prepare-yummy-walk-patch.py")
ИНС = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНС)

ОБРАЗЕЦ = '''import {
  collectSeasonEpisodes,
  listSeasonsLogged,
  seasonsForEpisodeWalk,
} from "@/modules/catalog/episode-walk";

const API_WALK_LIMIT = 100;
const MAX_SEASONS_FOR_EPISODES = 40;
const MAX_WALK_REQUESTS = 80;
const DETAIL_CONCURRENCY = 4;

export async function loadCatalogPage(filters, page, pageSize) {
    const needed = page * pageSize;
    const collected = [];
    let cursor;
    let total = null;
    let hasMore = true;
    let requests = 0;

    while (collected.length < needed && hasMore && requests < MAX_WALK_REQUESTS) {
      const chunk = await client.listTitles({ limit: API_WALK_LIMIT, cursor });
      collected.push(...chunk.items.map(catalogTitleFromListItem));
      total = chunk.total ?? total;
      hasMore = chunk.hasMore;
      cursor = chunk.nextCursor ?? undefined;
      requests += 1;
      await rememberAnimeIds(chunk.items.map((item) => item.providerTitleId));
      if (!chunk.nextCursor) {
        break;
      }
    }

    if (filters.sort === "rating") {
      collected.sort(() => 0);
    }
    return collected;
}
'''


def test_правка_вписывается():
    стало = ИНС.переписать(ОБРАЗЕЦ)
    assert 'import { API_WALK_LIMIT, walkBudget }' in стало
    assert "const budget = walkBudget(needed);" in стало
    assert "requests < budget" in стало
    assert "seenCursors" in стало
    # Плоский предел исчезает: иначе осталось бы два правила сразу.
    assert "MAX_WALK_REQUESTS" not in стало
    assert "const API_WALK_LIMIT = 100;" not in стало


def test_защита_курсора_стоит_после_проверки_последней_порции():
    """Повтор курсора проверяется ПОСЛЕ `if (!chunk.nextCursor) break`.

    Иначе на последней порции (где курсора нет) проверка читала бы `undefined`
    и ломала нормальное завершение обхода.
    """
    стало = ИНС.переписать(ОБРАЗЕЦ)
    конец_порции = стало.index("if (!chunk.nextCursor) {")
    повтор = стало.index("if (seenCursors.has(chunk.nextCursor))")
    assert конец_порции < повтор


def test_неоднозначный_якорь_это_отказ():
    with pytest.raises(SystemExit) as ош:
        ИНС.переписать(ОБРАЗЕЦ + "\n" + ОБРАЗЕЦ)
    assert "вместо одного" in str(ош.value)


def test_уже_исправленный_источник_это_отказ():
    with pytest.raises(SystemExit) as ош:
        ИНС.переписать(ИНС.переписать(ОБРАЗЕЦ))
    assert "УЖЕ есть" in str(ош.value)


def test_отсутствие_якоря_это_отказ():
    with pytest.raises(SystemExit):
        ИНС.переписать("const unrelated = 1;\n")


@pytest.mark.parametrize("нужно, ждём, зачем", [
    (24, 3, "первая страница не стала дороже"),
    (334 * 24, 83, "последняя прежняя страница"),
    (350 * 24, 86, "именно здесь плоский предел 80 не давал добрать"),
    (10_000_000, ИНС.СТРАХОВКА, "страховка держит"),
    (0, 1, "нелепый вход не превращается в бесконечный обход"),
    (-5, 1, "отрицательный вход — тоже один запрос"),
])
def test_арифметика_бюджета(нужно, ждём, зачем):
    assert ИНС.бюджет(нужно) == ждём, зачем


def test_прежний_предел_не_покрывал_объявленную_страницу():
    """Признак, который при неисправленном состоянии обязан падать."""
    assert ИНС.бюджет(350 * 24) > 80


def test_страховка_кратно_больше_измеренного_каталога():
    assert ИНС.СТРАХОВКА * ИНС.ПРЕДЕЛ_ЗАПРОСА >= 8378 * 4


def test_репетиция_без_провалов():
    строки = ИНС.репетиция()
    слитно = "\n".join(строки)
    assert "ПРОВАЛ" not in слитно, слитно


def test_нет_исходника_это_код_два(capsys, tmp_path):
    код = ИНС.главное(["--source", str(tmp_path / "нет"), "--out", str(tmp_path / "из")])
    assert код == 2
    assert "НЕ СОБРАНО" in capsys.readouterr().out


def test_патч_и_модуль_ложатся_в_контекст(tmp_path):
    источник = tmp_path / "src" / "modules" / "catalog"
    источник.mkdir(parents=True)
    (источник / "catalog-query.ts").write_text(ОБРАЗЕЦ, encoding="utf-8")
    выход = tmp_path / "ctx"
    assert ИНС.главное(["--source", str(tmp_path / "src"), "--out", str(выход)]) == 0
    assert (выход / "src/modules/catalog/catalog-query.ts").is_file()
    assert (выход / "src/modules/catalog/walk-budget.ts").is_file()
    assert (выход / "catalog-query.patch").is_file()
    модуль = (выход / "src/modules/catalog/walk-budget.ts").read_text(encoding="utf-8")
    assert "export function walkBudget(" in модуль
    assert "export const WALK_SAFETY_REQUESTS = 400;" in модуль
