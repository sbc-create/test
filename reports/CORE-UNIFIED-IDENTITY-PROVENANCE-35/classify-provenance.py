"""Происхождение каждого утверждения: восстановить или честно назвать.

Восстановление стало возможно только после того, как у страницы появился
устойчивый идентификатор. Пока тождество не разрешено, «сверить утверждение с
каталогом» означает угадать, с какой записью сверять, — и любой ответ был бы
случайным. Поэтому этот разбор идёт после снимка маршрутов, а не рядом с ним.

Единственный допущенный источник — авторитетный кэш каталога ядра. Наши
собственные страницы источником не считаются: страница, ссылающаяся на себя,
подтверждает только то, что она существует. Внешние запросы не делаются,
приблизительное сопоставление не применяется, старый редакционный ключ не
используется.

Разрешение на переиспользование объявляется отдельной осью и по умолчанию
закрыто: `licensed=false` или отсутствие поля — это PERMISSION_UNKNOWN, а не
разрешено. Неизвестное не называется разрешённым.
"""
import collections, datetime as dt, json, pathlib

SEO = pathlib.Path("/home/claude/wt-seo-kind-34")
CORE = pathlib.Path("/home/claude/wt-core-ident-35")
ОТЧЁТ = CORE / "reports/CORE-UNIFIED-IDENTITY-PROVENANCE-35"

#: Поля каталога, которыми утверждение можно заземлить. Перечень закрыт:
#: поля, которого здесь нет, каталог не знает, и «проверить» его нечем.
ПОЛЯ = {"title": "name", "year": "year"}

#: Разделители составного заголовка страницы. Объявлены списком, потому что
#: «похоже на составной заголовок» — это догадка, а перечень — правило.
РАЗДЕЛИТЕЛИ = (" — ", " - ", ": ")

САМОЦИТАТА = "page:schema.org"
КАТАЛОЖНЫЕ = frozenset({"catalog:fact_table", "catalog:listing"})


def как_строка(значение) -> str:
    if isinstance(значение, float) and значение.is_integer():
        значение = int(значение)
    return str(значение).strip()


def классифицировать(факт, запись_каталога, создано, обновлено_каталогом):
    """Одно состояние происхождения и причина. Состояние всегда одно."""
    ключ, значение = факт["key"], как_строка(факт["value"])
    поле = ПОЛЯ.get(ключ)

    if запись_каталога is None:
        return ("SOURCE_UNKNOWN", "CATALOG_ENTRY_ABSENT",
                "записи каталога для этого произведения нет: сверить не с чем")
    if поле is None:
        # Каталог такого поля не хранит. Для утверждения, объявившего
        # каталожное происхождение, это потерянная ссылка: источник назван,
        # а записи, на которую он указывает, не существует.
        if факт["provenance"] in КАТАЛОЖНЫЕ:
            return ("SOURCE_REFERENCE_LOST", f"FIELD_NOT_IN_CATALOG:{ключ}",
                    "происхождение объявлено каталожным, но каталог такого "
                    "поля не хранит; подтвердить нечем")
        return ("SELF_CITED", f"FIELD_NOT_IN_CATALOG:{ключ}",
                "источник — наша собственная разметка, а каталог такого поля "
                "не хранит: восстановить происхождение нечем")

    эталон = запись_каталога.get(поле)
    if эталон is None or как_строка(эталон) == "":
        return ("SOURCE_UNKNOWN", f"CATALOG_FIELD_EMPTY:{поле}",
                "поле в записи каталога пусто: отсутствие значения не "
                "подтверждает и не опровергает")
    эталон = как_строка(эталон)

    if значение == эталон:
        return ("UPSTREAM_SOURCE_VERIFIED", "EXACT_MATCH",
                "значение совпадает с авторитетным каталогом дословно")

    for разделитель in РАЗДЕЛИТЕЛИ:
        начало = эталон + разделитель
        if значение.startswith(начало) and значение[len(начало):].strip():
            return ("TRANSFORMED_WITH_VERIFIED_SOURCE",
                    f"COMPOSED_TITLE:{разделитель.strip() or 'sep'}",
                    f"значение — каталожное с добавкой "
                    f"{значение[len(начало):].strip()!r}")

    # Расхождение. Устаревание и противоречие различаются временем, а не
    # впечатлением: если каталог изменился уже после того, как страница была
    # создана, расхождение объясняется устареванием.
    if обновлено_каталогом and создано and обновлено_каталогом > создано:
        return ("STALE_SOURCE", "CATALOG_CHANGED_AFTER_PAGE",
                f"каталог изменён {обновлено_каталогом:%Y-%m-%d} после "
                f"создания страницы {создано:%Y-%m-%d}: {значение!r} против "
                f"{эталон!r}")
    return ("CONFLICT", "VALUE_DISAGREES",
            f"утверждение {значение!r} против каталога {эталон!r}")


def разобрать_время(строка):
    if not строка:
        return None
    try:
        return dt.datetime.fromisoformat(str(строка).replace("Z", "+00:00"))
    except ValueError:
        return None


очередь = json.loads((SEO / "reports/SEO-CLAIM-PROVENANCE-DRAFT-PROMOTION-26/"
                      "fixtures/seo-queue-268.json").read_text())
соответствие = json.loads((ОТЧЁТ / "CONFORMANCE-268.json").read_text())
исход = {с["id"]: с for с in соответствие["rows"]}
каталог = {str(з["external_id"]): з for з in json.loads(
    pathlib.Path("/srv/site-factory/repo/var/lords/lords/catalog-cache/"
                 "lords-01.json").read_text())["items"]}

состояния = collections.Counter()
разрешение = collections.Counter()
по_ключу = collections.Counter()
причины = collections.Counter()
состояния_654 = collections.Counter()
утверждения = []
всего = самоцитат_matched = 0

for з in очередь:
    сф = з.get("source_facts")
    if not isinstance(сф, dict):
        continue
    р = исход.get(з["id"], {})
    matched = р.get("outcome") == "MATCHED"
    идентификатор = р.get("stableWorkId") or ""
    запись = каталог.get(идентификатор) if matched and идентификатор else None
    создано = разобрать_время(з.get("created_at"))
    обновлено = разобрать_время((запись or {}).get("updated_at"))

    for факт in (сф.get("facts") or []):
        всего += 1
        свой = факт["provenance"] == САМОЦИТАТА
        if свой and matched:
            самоцитат_matched += 1

        if not matched:
            состояние, код, причина = (
                "SOURCE_UNKNOWN", "IDENTITY_UNRESOLVED",
                "тождество страницы не разрешено: сверять не с чем, и выбор "
                "записи наугад приписал бы утверждение чужому произведению")
        else:
            состояние, код, причина = классифицировать(
                факт, запись, создано, обновлено)

        # Разрешение — отдельная ось, по умолчанию закрытая.
        лицензия = (запись or {}).get("licensed")
        доступ = "PERMITTED" if лицензия is True else "PERMISSION_UNKNOWN"

        состояния[состояние] += 1
        разрешение[доступ] += 1
        причины[код] += 1
        по_ключу[(факт["key"], состояние)] += 1
        if свой and matched:
            состояния_654[состояние] += 1

        утверждения.append({
            "queueId": з["id"], "domain": з["domain"],
            "stableWorkId": идентификатор, "key": факт["key"],
            "declaredProvenance": факт["provenance"],
            "declaredReference": факт["reference"],
            "provenanceState": состояние, "reasonCode": код,
            "reason": причина, "permission": доступ,
            "restoredReference": (
                f"catalog:fact_table:{идентификатор}"
                if состояние in ("UPSTREAM_SOURCE_VERIFIED",
                                 "TRANSFORMED_WITH_VERIFIED_SOURCE") else "")})

print(f"утверждений разобрано: {всего}")
print(f"самоцитируемых на разрешённых страницах: {самоцитат_matched}")
print("\n=== СОСТОЯНИЕ ПРОИСХОЖДЕНИЯ (все утверждения) ===")
for с, n in состояния.most_common():
    print(f"  {с:<34} {n:>5}")
print("\n=== ТЕ САМЫЕ 654 САМОЦИТАТЫ ===")
for с, n in состояния_654.most_common():
    print(f"  {с:<34} {n:>5}")
print("\n=== РАЗРЕШЕНИЕ НА ПЕРЕИСПОЛЬЗОВАНИЕ ===")
for с, n in разрешение.most_common():
    print(f"  {с:<34} {n:>5}")
print("\n=== ПРИЧИНЫ ===")
for с, n in причины.most_common():
    print(f"  {с:<40} {n:>5}")
print("\n=== ПО КЛЮЧУ ===")
for (k, с), n in sorted(по_ключу.items()):
    print(f"  {k:<18} {с:<34} {n:>5}")

итог = {"claimsTotal": всего, "selfCitedOnMatched": самоцитат_matched,
        "groundingSource": "core catalog cache (authoritative)",
        "externalRequests": 0, "ownPagesUsedAsSource": False,
        "editorialKeyUsed": False,
        "byProvenanceState": dict(состояния),
        "selfCited654ByState": dict(состояния_654),
        "byPermission": dict(разрешение), "byReasonCode": dict(причины),
        "byKeyAndState": {f"{k}|{с}": n for (k, с), n in sorted(по_ключу.items())},
        "claims": утверждения}
(ОТЧЁТ / "PROVENANCE-CLAIMS.json").write_text(
    json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nзаписано:", ОТЧЁТ / "PROVENANCE-CLAIMS.json")
