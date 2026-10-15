"""Расхождение копий реестра: про СОСТАВ или про ЗНАЧЕНИЯ?

Поправка линии 1lordserials1.online: для её домена все три копии совпадают до
идентификаторов целей, значит расхождение в охвате, а не в значениях. Это
проверяется по всем доменам, которые есть больше чем в одной копии: если
значения совпадают всюду, вывод MOD-40 надо сузить — и тогда доменов,
которым нельзя доверять без указания копии, останется меньше.
"""
import json
import pathlib

КОПИИ = {
    "ветка (29)": "config/analytics.json",
    "каталог службы (21)": "/home/claude/wt-portable-site-cell-01/config/analytics.json",
    "фабрика (6)": "/srv/site-factory/repo/config/analytics.json",
}
КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]

данные = {}
for имя, путь in КОПИИ.items():
    p = pathlib.Path(путь) if путь.startswith("/") else КОРЕНЬ / путь
    д = json.loads(p.read_text(encoding="utf-8"))
    данные[имя] = {з["domain"]: з for з in (д.get("properties") or [])}
    print(f"{имя}: {len(данные[имя])} записей")

все_домены = sorted(set().union(*[set(d) for d in данные.values()]))
сравнимые = [д for д in все_домены
             if sum(1 for к in данные if д in данные[к]) > 1]
print(f"\nдоменов всего {len(все_домены)}, есть больше чем в одной копии: "
      f"{len(сравнимые)}")

ПОЛЯ = ("counter_id", "analytics_enabled", "webvisor", "allowed_hosts",
        "goals", "goal_ids", "seo_indexing_enabled")
расхождений = 0
for домен in сравнимые:
    записи = {к: данные[к][домен] for к in данные if домен in данные[к]}
    разные = []
    for поле in ПОЛЯ:
        значения = {json.dumps(з.get(поле), ensure_ascii=False, sort_keys=True)
                    for з in записи.values()}
        if len(значения) > 1:
            разные.append(поле)
    if разные:
        расхождений += 1
        print(f"  [x] {домен}: расходятся {разные} (копии: {list(записи)})")

print(f"\nдоменов со расхождением ЗНАЧЕНИЙ: {расхождений} из {len(сравнимые)}")
только_в_длинной = [д for д in все_домены
                    if sum(1 for к in данные if д in данные[к]) == 1]
print(f"доменов ровно в одной копии: {len(только_в_длинной)}")
for д in только_в_длинной:
    где = [к for к in данные if д in данные[к]]
    print(f"  {д}: только {где[0]}")
