#!/usr/bin/env python3
"""D3/MOD-122: свежесть работы решается ВРЕМЕНЕМ выборки, а не составом.

Дефект, измеренный линией ячейки 21.10: у `yummyani.org` нет 24 серий, и 7 из
них стоят в карте `yummyani.biz` с 17–19.10. Правило отбора
(`src/lib/seo/sitemap-detail-order.ts`, `planDetailFetch`) считает работу
свежей по условию `record.f < at` — время последней выборки подробностей против
времени наблюдения. Если выборка случилась ПОСЛЕ наблюдения, а провайдер серию
тогда не отдал, запись считается актуальной, и серия ждёт семисуточной
перепроверки (`RECHECK_MS`).

Второй множитель, который задание требует устранить отдельно: `readEvents`
читает только ХВОСТ журнала (`TAIL_BYTES = 512 КиБ` при 1.25 МБ), поэтому
наблюдение может выйти из окна чтения — и тогда никакое сравнение состава его
уже не увидит.

Что делает правка, двумя независимыми частями:

1. **свежесть по СОСТАВУ.** Работа считается свежей, если наблюдение называет
   серию, которой НЕТ в записи хранилища, независимо от `record.f`. Данные для
   этого уже есть: `Observations.episodes` ключуется `id:сезон:серия`, а
   `StoredDetail.e` несёт `[сезон, серия, дата]`;
2. **незавершённая задача ПЕРЕЖИВАЕТ журнал.** Такие работы складываются в
   отдельное множество (`seo:sitemap-pending:v1`, TTL 30 суток) и остаются
   свежими, пока серия не появится в записи. Ротация журнала, его рост и
   перезапуск процесса на это больше не влияют.

Ключи наблюдений и записей — провайдерские идентификаторы, а не публичные
слаги: `catalogTitleFromListItem` кладёт `slug: item.providerTitleId`, а
`attachPublicSlug` добавляет ОТДЕЛЬНОЕ поле `publicSlug`. Это проверено до
правки: иначе правка «по составу» сравнивала бы несравнимое.

    python3 automation/local/prepare-yummy-freshness-patch.py \\
        --source var/yummy-src/fixed-src --out var/yummy-build/d3-fixed
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

ПОРЯДОК = "lib/seo/sitemap-detail-order.ts"
СБОРЩИК = "lib/seo/sitemap-catalog.ts"

ЯКОРЬ_ПОДПИСИ = """export function planDetailFetch(
  titles: readonly CatalogTitle[],
  stored: ReadonlyMap<string, StoredDetail>,
  observed: Observations,
  now: number,
): string[] {"""

ПОДПИСЬ_СТАЛО = '''/**
 * Серии, которые наблюдение называет, а запись хранилища не содержит.
 *
 * Это и есть «незавершённая задача»: наблюдение было, выборка его не покрыла.
 * Сравнивается СОСТАВ, а не время, потому что выборка, случившаяся позже
 * наблюдения, но вернувшая неполный ответ, прежде закрывала работу от
 * повторной попытки на семь суток (D3/MOD-122).
 */
export function missingObserved(
  slug: string,
  record: StoredDetail | undefined,
  observed: Observations,
): string[] {
  const prefix = `${slug}:`;
  const known = new Set((record?.e ?? []).map(([season, episode]) => `${season}:${episode}`));
  const missing: string[] = [];
  for (const key of observed.episodes.keys()) {
    if (!key.startsWith(prefix)) {
      continue;
    }
    const tail = key.slice(prefix.length);
    if (!known.has(tail)) {
      missing.push(tail);
    }
  }
  return missing;
}

export function planDetailFetch(
  titles: readonly CatalogTitle[],
  stored: ReadonlyMap<string, StoredDetail>,
  observed: Observations,
  now: number,
  /**
   * Работы с незавершённой задачей, сохранённые между сборками.
   *
   * Журнал наблюдений читается хвостом (512 КиБ), поэтому наблюдение может
   * выйти из окна чтения. Без этого множества задача исчезала бы вместе с
   * событием, и серия ждала бы семисуточной перепроверки — ровно тот путь,
   * которым 7 серий `.org` не доехали до карты, хотя в `.biz` стоят с 17.10.
   */
  pending: ReadonlySet<string> = new Set(),
): string[] {'''

ЯКОРЬ_УСЛОВИЯ = """    const record = stored.get(slug);
    const at = observed.titles.get(slug);
    if (at !== undefined && (!record || record.f < at)) {
      fresh.push({ slug, at });
    } else if (!record) {"""

УСЛОВИЕ_СТАЛО = """    const record = stored.get(slug);
    const at = observed.titles.get(slug);
    // Состав важнее времени: наблюдение, называющее серию, которой нет в
    // записи, делает работу свежей независимо от того, когда была выборка.
    const uncovered = record ? missingObserved(slug, record, observed).length > 0 : false;
    if (at !== undefined && (!record || record.f < at || uncovered)) {
      fresh.push({ slug, at });
    } else if (uncovered || pending.has(slug)) {
      // Наблюдение могло выйти из прочитанного хвоста журнала — тогда `at`
      // уже нет, а задача осталась. Такая работа идёт вперёд очереди `never`:
      // у неё есть названная, но не добранная серия.
      fresh.push({ slug, at: record?.f ?? now });
    } else if (!record) {"""

ЯКОРЬ_ОЧЕРЕДИ = """  const queue = planDetailFetch(titles, details, observed, now).slice(0, DETAIL_MAX_PER_BUILD);"""

ОЧЕРЕДЬ_СТАЛО = """  const pending = await readPending(redis);
  const queue = planDetailFetch(titles, details, observed, now, pending)
    .slice(0, DETAIL_MAX_PER_BUILD);"""

ЯКОРЬ_ИТОГА = """  const listed = titles.filter((title) => details.has(title.slug)).length;"""

ИТОГ_СТАЛО = """  // Незавершённые задачи пересчитываются ПОСЛЕ выборки и сохраняются: работа,
  // у которой наблюдение назвало серию, а ответ провайдера её не принёс,
  // остаётся в очереди следующей сборки даже если событие уже вышло из хвоста
  // журнала (D3/MOD-122).
  const stillPending = new Set<string>();
  for (const title of titles) {
    const left = missingObserved(title.slug, details.get(title.slug), observed);
    if (left.length > 0) {
      stillPending.add(title.slug);
    }
  }
  for (const slug of pending) {
    if (!details.has(slug)) {
      stillPending.add(slug);
    }
  }
  await writePending(redis, stillPending);
  const listed = titles.filter((title) => details.has(title.slug)).length;"""

ЯКОРЬ_ИМПОРТА = """import {
  detailRecord,
  freshObservations,
  planDetailFetch,
  type StoredDetail,
} from "./sitemap-detail-order";"""

ИМПОРТ_СТАЛО = """import {
  detailRecord,
  freshObservations,
  missingObserved,
  planDetailFetch,
  type StoredDetail,
} from "./sitemap-detail-order";"""

ЯКОРЬ_КЛЮЧЕЙ = """const DETAIL_KEY = "seo:sitemap-detail:v1";"""

КЛЮЧИ_СТАЛО = '''const DETAIL_KEY = "seo:sitemap-detail:v1";
/**
 * Работы с незавершённой задачей по сериям.
 *
 * Отдельным ключом, а не полем записи: запись подробностей описывает то, что
 * провайдер ОТДАЛ, а это множество — то, что наблюдение назвало и чего в
 * записи нет. Срок жизни тот же, что у подробностей.
 */
const PENDING_KEY = "seo:sitemap-pending:v1";'''

ЯКОРЬ_ЧТЕНИЯ = """async function readDetails(redis: RedisLike | null): Promise<Map<string, StoredDetail>> {"""

ЧТЕНИЕ_СТАЛО = '''async function readPending(redis: RedisLike | null): Promise<Set<string>> {
  if (!redis) {
    return new Set();
  }
  try {
    const raw = await redis.get(PENDING_KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : null;
    return new Set(Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : []);
  } catch {
    // Нечитаемое множество равно пустому: сборка карты не имеет права падать
    // из-за служебного ключа, а худшее следствие — работа дождётся общей
    // перепроверки, то есть прежнее поведение.
    return new Set();
  }
}

async function writePending(redis: RedisLike | null, pending: ReadonlySet<string>): Promise<void> {
  if (!redis) {
    return;
  }
  try {
    await redis.set(PENDING_KEY, JSON.stringify([...pending]), { EX: DETAIL_TTL_SEC });
  } catch {
    // Не записалось — следующая сборка просто не увидит задачу в множестве.
  }
}

async function readDetails(redis: RedisLike | null): Promise<Map<string, StoredDetail>> {'''

ЗАМЕНЫ_ПОРЯДКА = (
    ("подпись planDetailFetch", ЯКОРЬ_ПОДПИСИ, ПОДПИСЬ_СТАЛО),
    ("условие свежести", ЯКОРЬ_УСЛОВИЯ, УСЛОВИЕ_СТАЛО),
)
ЗАМЕНЫ_СБОРЩИКА = (
    ("импорт", ЯКОРЬ_ИМПОРТА, ИМПОРТ_СТАЛО),
    ("ключ множества", ЯКОРЬ_КЛЮЧЕЙ, КЛЮЧИ_СТАЛО),
    ("чтение и запись множества", ЯКОРЬ_ЧТЕНИЯ, ЧТЕНИЕ_СТАЛО),
    ("очередь", ЯКОРЬ_ОЧЕРЕДИ, ОЧЕРЕДЬ_СТАЛО),
    ("пересчёт после выборки", ЯКОРЬ_ИТОГА, ИТОГ_СТАЛО),
)


def переписать(текст: str, замены) -> str:
    for имя, якорь, замена in замены:
        сколько = текст.count(якорь)
        if сколько != 1:
            raise SystemExit(
                f"якорь «{имя}» встречается {сколько} раз вместо одного:"
                " исходник изменился. Патч собирать заново, а не подгонять.")
        текст = текст.replace(якорь, замена, 1)
    return текст


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--source", required=True)
    р.add_argument("--out", required=True)
    а = р.parse_args(аргв)

    источник = Path(а.source)
    выход = Path(а.out)
    (выход / "src" / "lib" / "seo").mkdir(parents=True, exist_ok=True)
    патчи: list[str] = []
    for файл, замены in ((ПОРЯДОК, ЗАМЕНЫ_ПОРЯДКА), (СБОРЩИК, ЗАМЕНЫ_СБОРЩИКА)):
        путь = источник / файл
        if not путь.is_file():
            print(f"НЕ СОБРАНО: нет файла {путь}")
            return 2
        было = путь.read_text(encoding="utf-8")
        if "missingObserved" in было:
            print(f"НЕ СОБРАНО: в {файл} правка УЖЕ есть")
            return 2
        стало = переписать(было, замены)
        (выход / "src" / файл).write_text(стало, encoding="utf-8")
        патчи.append("".join(difflib.unified_diff(
            было.splitlines(keepends=True), стало.splitlines(keepends=True),
            fromfile=f"a/src/{файл}", tofile=f"b/src/{файл}")))
        print(f"{файл}: {len(было)} Б → {len(стало)} Б")
    (выход / "freshness.patch").write_text("".join(патчи), encoding="utf-8")
    print(f"diff: {выход / 'freshness.patch'}"
          f" ({len(''.join(патчи).splitlines())} строк)")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
