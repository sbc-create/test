"""Сборщик патча D3: свежесть работы по СОСТАВУ наблюдений.

Дефект: свежесть решалась условием `record.f < at` — временем выборки против
времени наблюдения. Выборка, случившаяся позже наблюдения и вернувшая неполный
ответ, закрывала работу от повторной попытки на семь суток; так 7 серий
`yummyani.org` не доехали до карты, хотя в `.biz` стоят с 17.10.

Патч правит ДВА файла, и у каждого свои якоря. Проверяется, что отказ наступает
при любом расхождении: якорь не один, якорь отсутствует, правка уже есть.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "prepare_yummy_freshness_patch",
    КОРЕНЬ / "automation/local/prepare-yummy-freshness-patch.py")
ИНС = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНС)

ПОРЯДОК = '''import type { CatalogTitle } from "@/modules/catalog/metadata-source";
import { listedEpisodes } from "@/modules/catalog/watch-position";

export const RECHECK_MS = 7 * 24 * 3600 * 1000;
export const RECHECK_EMPTY_MS = 24 * 3600 * 1000;

export function planDetailFetch(
  titles: readonly CatalogTitle[],
  stored: ReadonlyMap<string, StoredDetail>,
  observed: Observations,
  now: number,
): string[] {
  const fresh: { slug: string; at: number }[] = [];
  const never: string[] = [];
  const due: { slug: string; at: number }[] = [];
  const seen = new Set<string>();
  for (const title of titles) {
    const slug = title.slug;
    if (!slug || seen.has(slug)) {
      continue;
    }
    seen.add(slug);
    const record = stored.get(slug);
    const at = observed.titles.get(slug);
    if (at !== undefined && (!record || record.f < at)) {
      fresh.push({ slug, at });
    } else if (!record) {
      never.push(slug);
    } else if (now - record.f >= (record.e.length > 0 ? RECHECK_MS : RECHECK_EMPTY_MS)) {
      due.push({ slug, at: record.f });
    }
  }
  return [...fresh.map((x) => x.slug), ...never, ...due.map((x) => x.slug)];
}
'''

СБОРЩИК = '''import { getRedis } from "@/lib/redis";
import {
  detailRecord,
  freshObservations,
  planDetailFetch,
  type StoredDetail,
} from "./sitemap-detail-order";

const DETAIL_KEY = "seo:sitemap-detail:v1";
const DETAIL_TTL_SEC = 30 * 24 * 3600;
const DETAIL_MAX_PER_BUILD = 800;

async function readDetails(redis: RedisLike | null): Promise<Map<string, StoredDetail>> {
  return new Map();
}

async function buildInventory(redis: RedisLike | null, budgetMs: number): Promise<SitemapInventory> {
  const titles = await walkAnimeCatalogList();
  const observed = freshObservations(await readEvents());
  const details = await readDetails(redis);
  const now = Date.now();
  const queue = planDetailFetch(titles, details, observed, now).slice(0, DETAIL_MAX_PER_BUILD);
  const listed = titles.filter((title) => details.has(title.slug)).length;
  return inventoryFromTitles(titles, details, observed.episodes);
}
'''


def _дерево(tmp_path):
    корень = tmp_path / "src"
    (корень / "lib" / "seo").mkdir(parents=True)
    (корень / "lib/seo/sitemap-detail-order.ts").write_text(ПОРЯДОК, encoding="utf-8")
    (корень / "lib/seo/sitemap-catalog.ts").write_text(СБОРЩИК, encoding="utf-8")
    return корень


def test_правка_вписывается_в_оба_файла(tmp_path):
    корень = _дерево(tmp_path)
    выход = tmp_path / "ctx"
    assert ИНС.главное(["--source", str(корень), "--out", str(выход)]) == 0
    порядок = (выход / "src/lib/seo/sitemap-detail-order.ts").read_text(encoding="utf-8")
    сборщик = (выход / "src/lib/seo/sitemap-catalog.ts").read_text(encoding="utf-8")
    assert "export function missingObserved(" in порядок
    assert "pending: ReadonlySet<string> = new Set()" in порядок
    assert "uncovered" in порядок
    assert "PENDING_KEY" in сборщик
    assert "readPending" in сборщик and "writePending" in сборщик
    assert "planDetailFetch(titles, details, observed, now, pending)" in сборщик
    assert (выход / "freshness.patch").is_file()


def test_незавершённые_задачи_пересчитываются_после_выборки(tmp_path):
    """Множество должно обновляться ПОСЛЕ выборки, иначе оно вечное."""
    корень = _дерево(tmp_path)
    выход = tmp_path / "ctx"
    ИНС.главное(["--source", str(корень), "--out", str(выход)])
    сборщик = (выход / "src/lib/seo/sitemap-catalog.ts").read_text(encoding="utf-8")
    выборка = сборщик.index("await Promise.all") if "await Promise.all" in сборщик \
        else сборщик.index("const queue =")
    пересчёт = сборщик.index("const stillPending")
    запись = сборщик.index("await writePending(")
    assert выборка < пересчёт < запись


def test_условие_свежести_сохраняет_прежние_очереди(tmp_path):
    """`never` и `due` остаются: правка добавляет состояние, а не заменяет их."""
    корень = _дерево(tmp_path)
    выход = tmp_path / "ctx"
    ИНС.главное(["--source", str(корень), "--out", str(выход)])
    порядок = (выход / "src/lib/seo/sitemap-detail-order.ts").read_text(encoding="utf-8")
    assert "never.push(slug)" in порядок
    assert "due.push({ slug, at: record.f })" in порядок
    assert "RECHECK_MS" in порядок


def test_уже_исправленный_источник_это_отказ(capsys, tmp_path):
    корень = _дерево(tmp_path)
    выход = tmp_path / "ctx"
    ИНС.главное(["--source", str(корень), "--out", str(выход)])
    # Подсовываем уже исправленный файл обратно в источник.
    (корень / "lib/seo/sitemap-detail-order.ts").write_text(
        (выход / "src/lib/seo/sitemap-detail-order.ts").read_text(encoding="utf-8"),
        encoding="utf-8")
    assert ИНС.главное(["--source", str(корень), "--out", str(tmp_path / "ctx2")]) == 2
    assert "УЖЕ есть" in capsys.readouterr().out


def test_неоднозначный_якорь_это_отказ(tmp_path):
    корень = _дерево(tmp_path)
    (корень / "lib/seo/sitemap-detail-order.ts").write_text(
        ПОРЯДОК + "\n" + ПОРЯДОК, encoding="utf-8")
    with pytest.raises(SystemExit) as ош:
        ИНС.главное(["--source", str(корень), "--out", str(tmp_path / "ctx")])
    assert "вместо одного" in str(ош.value)


def test_нет_файла_это_код_два(capsys, tmp_path):
    пустой = tmp_path / "src"
    (пустой / "lib" / "seo").mkdir(parents=True)
    assert ИНС.главное(["--source", str(пустой), "--out", str(tmp_path / "ctx")]) == 2
    assert "НЕ СОБРАНО" in capsys.readouterr().out
