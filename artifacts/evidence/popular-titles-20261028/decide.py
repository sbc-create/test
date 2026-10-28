"""Решение по каждой из 392 строк владельца: сущность каталога, направление, статус (28.10).

Вход: source-owner-20261028.json, match-candidates-20261028.json, снимки каталога (только чтение).
Выход: match-decisions-20261028.json — одна запись на строку + сводка уникальных сущностей.

Статусы (одна строка — ровно один):
  matched          — единственная подходящая запись каталога, точное название;
  matched_chosen   — из нескольких одноимённых выбрана одна по году/формату/жанрам (основание в basis);
  matched_variant  — в каталоге другое название той же работы (подтверждено original_name/сезоном);
  needs_check      — кандидат есть, но идентичность не доказана каталогом; названа недостающая проверка;
  absent           — в каталоге поставщика (28.10 03:17Z) работы нет; карточку обещать нельзя.
Направление: live (игровые фильмы/сериалы), animation (западная/не японская анимация),
anime (японское), donghua (китайская анимация), dorama (Корея/Китай/Япония и др. Азия), turkish.
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = json.loads((HERE / "source-owner-20261028.json").read_text(encoding="utf-8"))["rows"]
CAND = {r["n"]: r for r in json.loads((HERE / "match-candidates-20261028.json").read_text(encoding="utf-8"))["rows"]}
G = json.loads(pathlib.Path("/srv/zonafilm-cc/data/zona-02-details.json").read_text(encoding="utf-8"))
BUILT = G["catalog_built_at"]
G = G["details"]
A = json.loads(pathlib.Path("/srv/animedia-icu/data/animedia-01-details.json").read_text(encoding="utf-8"))["details"]

# n → (status, slug|None, direction, basis). Строки, которых здесь нет, решаются правилом ниже.
M = {
    1: ("matched_chosen", "izvne-2", "live", "2022 tv «детектив, драма»; izvne — фильм 1986, другой"),
    7: ("matched_chosen", "odisseya", "live", "2026 фильм Нолана — та же запись, что в составах 27.10 (TASK_20261027_HOME_COLLECTIONS: tt33764258)"),
    8: ("absent", None, "animation", "в каталоге только фильм 2020 «Неуязвимый» (игровой); мультсериала нет — не подменять"),
    10: ("matched_chosen", "dzhek-richer-2", "live", "сериал 2022; фильм 2012 (dzhek-richer) — отдельная работа, не сливать"),
    12: ("matched_chosen", "grimm", "live", "сериал 2011; grimm-2 (2024, «аниме») — другая работа"),
    14: ("matched_chosen", "ukrytie-5", "live", "сериал 2023 «драма, триллер»; прочие «Укрытие» — фильмы 2011–2022 и дорама"),
    20: ("matched_chosen", "kasl", "live", "сериал 2009; kasl-2 (2021) — другая работа"),
    21: ("needs_check", "dzhentlmeny-3", "live", "кандидат — сериал 2024; фильма 2019 под этим названием в каталоге нет; нужна сверка external_ids с карточкой, которую ищут"),
    24: ("matched_variant", "ochen-strashnoe-kino", "live", "Scary Movie (2026) — шестой фильм серии; в каталоге без номера, original_name «Scary Movie», 2026"),
    26: ("matched_chosen", "myslit-kak-prestupnik", "live", "сериал 2005; -2 — дорама 2017, другая"),
    28: ("needs_check", None, "live", "четыре «Колонии» (1997, 2009, 2013, 2016); какую из них отражает показатель — не установить без адреса страницы в источнике"),
    30: ("matched_chosen", "nadezhda", "live", "фильм 2026 (корейский, жанр «дорама» в снимке — метка поставщика); остальные — 2019 и 2024"),
    34: ("matched_chosen", "mys-straha", "live", "сериал 2026; фильм 1991 — отдельная работа"),
    36: ("needs_check", "holod", "live", "единственная запись — сериал 2016; совпадение с тайтлом источника не доказано"),
    41: ("matched", "moana", "live", "игровой фильм 2026"),
    46: ("matched_chosen", "mumiya", "live", "фильм 2026; 1999, 2001, 2017 — другие работы"),
    47: ("needs_check", None, "live", "пять «Приговоров» (1959–2024); без адреса страницы в источнике выбрать нельзя"),
    56: ("matched_chosen", "devil-may-cry", "animation", "сериал 2025 (original_name Devil May Cry); аниме 2007 — другая экранизация"),
    57: ("matched_chosen", "kerri-3", "live", "сериал 2026; фильмы 1976 и 2002 — другие экранизации"),
    58: ("matched_chosen", "kovcheg", "live", "сериал 2023; -2 (2011) — другой"),
    62: ("needs_check", "vershina", "live", "фильм 2026 — вероятный кандидат; также сериал-аниме 2022 и фильм 2022"),
    67: ("absent", None, "live", "в каталоге только корейский оригинал (дорама) и два фильма; американского сериала нет — не подменять"),
    68: ("matched_chosen", "sherlok", "live", "сериал 2010; -2 — дорама 2019"),
    74: ("matched_chosen", "oskolki", "live", "сериал 2026; 2012 — дорама, 2007 — фильм"),
    78: ("matched_chosen", "molodoy-sherlok-2", "live", "сериал 2026; molodoy-sherlok — дорама 2014"),
    79: ("needs_check", "novichok-3", "live", "сериал без года; фильмы 1990–2025 — другие; нужен год/IMDb записи"),
    81: ("needs_check", None, "live", "документальный сериал 2018 и фильм 1996 — ни один не подтверждён как ищемый"),
    87: ("matched", "my-vse-mertvy", "dorama", "корейский сериал 2022; в источнике категория «Лорд», направление — дорама"),
    88: ("needs_check", "milye-obmanschicy", "live", "единственная запись — турецкая версия 2015; американский сериал в каталоге не найден"),
    94: ("matched_chosen", "obitel-zla-2", "live", "фильм 2026; сериал 2022 — другая работа"),
    95: ("matched_chosen", "passazhir", "live", "фильм 2026 «ужасы»; остальные — 2014–2023"),
    97: ("absent", None, "live", "биографического фильма 2026 нет; записи 1996 и 2023 — другие"),
    98: ("matched_chosen", "skoraya-pomosch", "live", "сериал 1994; -2 — фильм 1990"),
    99: ("absent", None, "live", "в каталоге только фильм 2004; сериала нет — не подменять"),
    108: ("absent", None, "dorama", "в каталоге только западный сериал 2020; дорамы с этим названием нет"),
    115: ("absent", None, "dorama", "в каталоге только фильм 2021; корейского сериала нет"),
    118: ("matched_chosen", "pugalo", "dorama", "сериал; pugalo-2 — фильм 2023"),
    132: ("matched_chosen", "pugayuschiy-roman", "dorama", "сериал 2026; фильмы 2011 и 2023 — другие"),
    137: ("needs_check", "istinnaya-krasota", "dorama", "единственная запись 2024 с жанром «аниме» — сериал 2020 не найден; формат не подтверждён"),
    153: ("matched_chosen", "horoshiy-malchik-2", "dorama", "дорама 2025; фильмы 2010 и 2024 — другие"),
    157: ("needs_check", None, "dorama", "фильм 2026, западный сериал 2019, турецкий 2016 — дорамы нет"),
    159: ("matched_chosen", "ocharovanie-2", "dorama", "дорама 2026; 2009 и 2004 — западные"),
    165: ("matched_chosen", "skrytaya-lyubov", "dorama", "дорама 2025; фильм 2007 — другой"),
    167: ("needs_check", "psih-no-vse-v-poryadke-2", "dorama", "две записи (2020 и 2025) с одним названием; 2020 — вероятный оригинал, нужна сверка external_ids"),
    169: ("needs_check", "boltun-3", "dorama", "из трёх «Болтунов» дорама только 2022; совпадение не подтверждено"),
    170: ("matched_variant", "moy-demon-serial-2023-2024", "dorama", "в каталоге «Мой демон (сериал 2023 – 2024)»"),
    173: ("needs_check", "skazanie-o-kumiho-nezakonchennaya-istoriya", "dorama", "«Сказание о Кумихо: незаконченная история» 2020 — продолжение или иная работа; без сверки не связывать"),
    176: ("needs_check", "taksi-delyuks-3", "dorama", "есть сезоны 2 и 3 отдельными записями, первого нет; какой сезон ищут — не установлено"),
    187: ("absent", None, "dorama", "в каталоге только западный сериал 2015"),
    188: ("needs_check", "dolgaya-pesn-2", "dorama", "две записи одного названия (без года и 2024) — возможный дубль поставщика"),
    190: ("needs_check", "potomki-solnca", "dorama", "запись 2020 — не год оригинала; возможна другая версия"),
    199: ("absent", None, "dorama", "в каталоге только аниме 2003; корейского сериала нет"),
    208: ("matched_chosen", "blich-2", "anime", "аниме-сериал 2004; blich — игровой фильм 2018"),
    209: ("matched_variant", "dobro-pozhalovat-v-klass-prevoshodstva-4-vtoroy-god-pervyy-semestr", "anime", "в каталоге «…4: Второй год — Первый семестр»"),
    213: ("needs_check", "rashititel-grobnic", "donghua", "2026, жанр «аниме»; происхождение (Китай/Япония) не подтверждено каталогом"),
    217: ("matched_chosen", "neobyatnyy-okean", "anime", "сериал 2018; -4 — игровой фильм 2020"),
    225: ("matched_variant", "mir-otome-igr-eto-tyazhelyy-mir-dlya-mobov", "anime", "полное название; первый сезон 2022 (второй — отдельной записью)"),
    230: ("matched_variant", "princessa-rycar-nevesta-varvara", "anime", "«Принцесса-рыцарь — невеста варвара», Himekishi wa Barbaroi no Yome, 2026"),
    238: ("matched_chosen", "za-granyu-vremeni-2", "donghua", "дунхуа 2025; фильм 2023 — другой"),
    243: ("needs_check", "ohotnik-h-ohotnik", "anime", "в каталоге «Охотник х Охотник» 1999; экранизации 2011 нет — разные экранизации не сливать"),
    254: ("absent", None, "anime", "аниме-сериала 2006 нет; есть игровые фильмы 2006 и 2017"),
    269: ("matched_chosen", "avatar-legenda-ob-aange", "animation", "мультсериал 2005 (западная анимация, не аниме); -2 — игровой сериал 2024"),
    271: ("matched_chosen", "boevoy-master-2", "donghua", "дунхуа 2020; boevoy-master 2023 — игровой сериал (уся)"),
    286: ("needs_check", None, "donghua", "второго сезона отдельной записью нет; seasons у boevoy-master-2 — проверить"),
    294: ("needs_check", "velikiy-pravitel-2023-2", "donghua", "«Великий правитель (2023) 2», 2026; к какой версии относится строка — проверить"),
    297: ("matched_chosen", "sverhestestvennoe-3", "live", "сериал 2005; фильмы 2018 и 2019 — другие"),
    299: ("needs_check", "vozmozhno-lyubov", "turkish", "единственная запись — фильм 2021 с жанром «дорама»; 9,4 млн в «Другом» указывает на сериал"),
    301: ("needs_check", None, "turkish", "дорама 2022 и западный фильм 2013; турецкого сериала нет"),
    302: ("matched_chosen", "dnevniki-vampira", "live", "сериал 2009"),
    303: ("needs_check", "nevesta-2", "turkish", "турецкий сериал 2019 — вероятный кандидат; 2026 — западный фильм"),
    305: ("needs_check", None, "live", "фильм 2011 и сериал 2015; принадлежность к категории «Другое» не подтверждена"),
    312: ("matched_chosen", "preemnik-zov-predkov-2", "turkish", "две записи; доступна только -2 (2025), другая без воспроизведения — дубль поставщика"),
    314: ("absent", None, "live", "в каталоге только фильм 2022; сериала нет"),
    318: ("matched_chosen", "bumazhnyy-dom", "live", "сериал 2017"),
    320: ("needs_check", None, "turkish", "более десяти «Семей»; без сверки нельзя"),
    324: ("matched_chosen", "sotnya-2", "live", "сериал 2014 (The 100)"),
    329: ("needs_check", "paren-2", "turkish", "турецкий сериал без года и дорама-фильм"),
    333: ("matched_chosen", "zavist", "turkish", "турецкий сериал 2025; -2 — фильм 2009"),
    336: ("matched", "mister-robot-2", "live", "сериал 2015"),
    341: ("matched_chosen", "flesh-3", "live", "сериал 2014; 1990 и фильм 2023 — другие"),
    342: ("matched_chosen", "ofis-2", "live", "американский сериал 2005; британский 2001 — отдельная работа"),
    349: ("matched_chosen", "karatel-6", "live", "сериал 2017"),
    352: ("matched_variant", "legenda-o-vox-machina", "animation", "The Legend of Vox Machina 2022"),
    76: ("matched_variant", "legenda-o-vox-machina", "animation", "«Легенда Вокс Машины» = «Легенда о Vox Machina» (original_name The Legend of Vox Machina) — та же работа, что строка 352"),
    96: ("matched_variant", "zadornye-druzya", "animation", "Smiling Friends — в каталоге «Задорные друзья» (строка 353)"),
    353: ("matched", "zadornye-druzya", "animation", "мультсериал 2020"),
    64: ("matched", "one-piece-bolshoy-kush", "live", "игровой сериал 2023 (метка «дорама» у поставщика ошибочна: original_name One Piece, западный сериал)"),
    54: ("matched_variant", "csi-mesto-prestupleniya", "live", "CSI: Crime Scene Investigation, 2000"),
    60: ("matched_variant", "to-leto-kogda-ya-pohoroshela", "live", "The Summer I Turned Pretty — в каталоге «То лето, когда я похорошела»"),
    369: ("matched_variant", "lyubov-smert-roboty", "animation", "Love, Death & Robots — «Любовь. Смерть. Роботы»"),
    359: ("matched_chosen", "kosti-3", "live", "сериал 2005"),
    362: ("matched_chosen", "sorvigolova-2", "live", "сериал 2015; фильм 2003 — другой"),
    364: ("matched_chosen", "klinika-3", "live", "сериал 2001 (Scrubs)"),
    366: ("matched_chosen", "druzya-3", "live", "сериал 1994"),
    374: ("matched_chosen", "dostoinstvo", "turkish", "турецкий сериал 2026"),
    376: ("needs_check", None, "turkish", "два турецких сериала без года с одним названием"),
    380: ("matched_chosen", "gubka-bob-kvadratnye-shtany-2", "animation", "мультсериал 1999; -1 — фильм 2004"),
    383: ("needs_check", None, "animation", "четыре записи разных лет; какая — не установлено"),
    384: ("matched_chosen", "chernyy-spisok-2", "live", "сериал 2013; chernyy-spisok — дорама"),
    385: ("absent", None, "live", "в каталоге только фильм 2006; сериала нет"),
    386: ("absent", None, "live", "сериала 2013 нет; записи — фильмы"),
    388: ("needs_check", "bezzaschitnye", "turkish", "единственная запись — фильм 2022"),
    391: ("needs_check", None, "turkish", "фильмы и аниме; турецкого сериала нет"),
    145: ("needs_check", None, "dorama", "ни одного из вариантов («Влюбиться в твою улыбку», «Киберкраш: …», строка 149) в каталоге нет; связь вариантов не проверить"),
    149: ("needs_check", None, "dorama", "вариант строки 145; в каталоге нет"),
    147: ("needs_check", None, "dorama", "вариант строки 144? В каталоге есть только «Председатель-новичок Кан» — связь нужна по external_ids"),
    181: ("needs_check", None, "dorama", "вариант строки 130 («Чудо-дураки» есть в каталоге)? Связь нужна по external_ids"),
    212: ("absent", None, "anime", "основного сериала «Наруто» нет; есть фильмы и «Боруто»"),
    224: ("absent", None, "anime", "«Ураганных хроник» нет"),
    288: ("needs_check", None, "anime", "«Наруто 2» — возможно «Ураганные хроники» (строка 224); обоих нет в каталоге"),
    201: ("absent", None, "anime", "основных сезонов нет; есть фильм и «Дневник слизи»"),
    205: ("absent", None, "anime", "основных сезонов нет; есть фильм и «Дневник слизи»"),
    207: ("absent", None, "anime", "основных сезонов нет; «Перерыв с нуля» — спин-офф, не подменять"),
    218: ("absent", None, "anime", "основных сезонов нет; «Перерыв с нуля» — спин-офф"),
    241: ("needs_check", "puteshestvie-k-bessmertiyu-mchas-v-sinhay-prolog", "donghua", "есть только «Пролог» 2023; основной сериал не найден"),
    44: ("absent", None, "live", "основного сериала нет; есть мини-эпизоды и спин-офф"),
    86: ("absent", None, "live", "основного сериала нет; есть спин-оффы 2024–2025"),
    357: ("absent", None, "live", "основного сериала нет; есть спин-оффы"),
    340: ("absent", None, "live", "основного сериала нет; есть мини-сериалы"),
    18: ("absent", None, "live", "сериала нет; «Игра престолов: Костюмы» — документальный"),
    361: ("absent", None, "live", "сериала нет; «Благие знамения: Локдаун» — короткий фильм"),
    371: ("absent", None, "live", "сериала 2024 нет; «Фоллаут: Ядерный перекур» — фанатский 2011"),
    315: ("absent", None, "live", "сериала The Boys нет"),
    379: ("absent", None, "live", "сериала нет; «Королева Шарлотта» — спин-офф"),
    186: ("absent", None, "dorama", "третьего сезона нет; второй — без воспроизведения"),
    161: ("absent", None, "dorama", "первого сезона нет; есть только второй"),
    138: ("absent", None, "dorama", "нет; «Апартаменты 1303» — другой фильм"),
    191: ("absent", None, "dorama", "нет; «Императрица Китая» — другая работа"),
    351: ("absent", None, "turkish", "нет; «Чужая жизнь моего сердца» — другая работа"),
    335: ("absent", None, "turkish", "нет; «Твоя любовь — огонь» — другая работа"),
    363: ("absent", None, "turkish", "нет"),
}


def direction_from(v, slug, category):
    g = set(v.get("genres") or [])
    if "дунхуа" in g:
        return "donghua"
    # Метка «западный контент» стоит у поставщика и на японском аниме (Ван-Пис, Фрирен);
    # для строк категории «Аниме» решает наличие записи в аниме-каталоге (MAL/Shikimori).
    if category == "Аниме" and slug in A:
        return "anime"
    if "турецкий сериал" in g:
        return "turkish"
    if "дорама" in g or "азиатский контент" in g:
        return "dorama"
    if "аниме" in g and "западный контент" not in g:
        return "anime"
    if "мультфильм" in g:
        return "animation"
    return "live"


EXPECT = {"Лорд": "live", "Дорама": "dorama", "Аниме": "anime", "Другое": "live"}
out = []
for r in SRC:
    n = r["n"]
    cands = {c["slug"]: c for c in CAND[n]["candidates"] if c["site"] == "zonafilm.cc"}
    if n in M:
        status, slug, direction, basis = M[n]
    elif len(cands) == 1:
        slug = next(iter(cands))
        status, direction = "matched", direction_from(G[slug], slug, r["source_category"])
        basis = "единственная запись каталога с точным названием"
        # Метка поставщика «аниме» у западной работы и «дорама» у игрового фильма — частый сбой;
        # расхождение с категорией источника оставляем видимым.
        if direction != EXPECT[r["source_category"]] and not (r["source_category"] == "Другое" and direction in ("turkish", "animation", "dorama")):
            basis += f"; направление по жанрам каталога — {direction}, категория источника — {r['source_category']}"
    elif not cands:
        status, slug, direction, basis = "absent", None, EXPECT[r["source_category"]], "в каталоге поставщика нет записи с этим названием или его вариантом (поиск по name, original_name и префиксу)"
    else:
        status, slug, direction = "needs_check", None, EXPECT[r["source_category"]]
        basis = "несколько одноимённых записей: " + ", ".join(f"{s} ({c['year']}, {c['type']})" for s, c in cands.items())
    v = G.get(slug) if slug else None
    out.append({
        "n": n, "title": r["title"], "pageviews": r["pageviews"], "sites": r["sites"],
        "source_category": r["source_category"], "status": status, "direction": direction, "basis": basis,
        "entity": None if not v else {
            "slug": slug, "id": v["id"], "name": v["name"], "original_name": v.get("original_name"),
            "year": v.get("year"), "type": v.get("type"), "playable": v.get("playable"),
            "seasons": len(v.get("seasons") or []), "external_ids": v.get("external_ids") or {},
            "in_anime_catalog": slug in A,
        },
    })

by_status = {}
for o in out:
    by_status[o["status"]] = by_status.get(o["status"], 0) + 1
entities = {}
for o in out:
    if o["entity"]:
        entities.setdefault(o["entity"]["id"], []).append(o["n"])
summary = {
    "rows": len(out), "by_status": by_status,
    "unique_entities": len(entities),
    "rows_sharing_entity": {k: v for k, v in entities.items() if len(v) > 1},
    "playable_entities": sum(1 for o in out if o["entity"] and o["entity"]["playable"]) - sum(len(v) - 1 for v in entities.values() if len(v) > 1),
    "catalog_built_at": BUILT,
}
(HERE / "match-decisions-20261028.json").write_text(json.dumps({"summary": summary, "rows": out}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=1))
