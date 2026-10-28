#!/usr/bin/env python3
"""Поставить витрине zonafilm.cc слой целей пути до просмотра (T342).

    python3 automation/host/apply-player-goals-patch.py \
        --repo var/site-repos/zonafilm-cc [--check] [--dry-run]

Разбор, замеры и обоснование смысла каждой цели — в заголовке
устанавливаемого модуля `src/player_goals.py`. Коротко о том, что делает
инструмент:

1. кладёт `src/player_goals.py` (если файл уже есть и совпадает — ничего);
2. добавляет `player_goals` в список импортируемых слоёв `src/serve.py`;
3. регистрирует его СРАЗУ ПОСЛЕ `player_watchdog`: сторож уже разобрал те же
   сообщения поставщика, и порядок делает связь очевидной при чтении.

Якоря обязаны найтись ровно один раз. Иначе инструмент отказывает и не меняет
ни одного файла: молча поставить слой целей мимо рантайма нельзя — цели
пойдут в никуда, а отчёт скажет, что измерение включено.

Что инструмент НЕ делает: не создаёт целей в счётчике (это запись в Метрику и
решение владельца), не меняет ни одной постоянной записи витрины, не трогает
снимок каталога и не отправляет ни одного имени цели мимо
`config/site.json: goals.enabled`.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

МОДУЛЬ = "player_goals.py"

ИСХОДНИК = '"""Цели пути до просмотра на zonafilm.cc (T342).\n\nЗамер 28.10 (`docs/seo-operator/ZONAFILM_CC_MEASUREMENT_20261028.md` §4,\nдоказательства — `artifacts/evidence/zonafilm-cc-behavior-20261028/player/`):\nна 1881 проверенном адресе витрины нет ни одного `reachGoal`, и все девять\nцелей счётчика показывают 0 при живом трафике. Путь «карточка → намерение →\nготовность → основное видео» не измеряется вовсе, то есть исторически он\n«не измерен», а не равен нулю.\n\nЧто следует из записанных последовательностей сообщений поставщика\n------------------------------------------------------------------\n\nЧетыре записи (`pm-onetap.json`: компьютер и телефон, по два произведения):\n\n* **`statechange: \'ready\'` приходит на 1.5–3.1 с, то есть РАНЬШЕ нажатия**\n  (`requestPlay` на 5.4 с) во всех четырёх случаях. Готовность плеера —\n  предшествующее условие, а не шаг после намерения: читать\n  «player_start → player_ready» как воронку нельзя.\n* **Реклама не присылает `timeupdate` ни разу** (0 из 4 записей), зато\n  `timeupdate` с позицией 0.09–0.13 приходит ДО нажатия. Поэтому правило\n  «первый `timeupdate` с позицией ≥ 3 с вне рекламы» отсекает и рекламу, и\n  холостые позиции загрузки.\n* **Прероллов два подряд** (22.3 с и 24.6 с), а `adStart` и\n  `rollState: start` дублируются по два раза каждый. Цель по первому\n  `adComplete` засчитала бы начало ошибочно, поэтому признак рекламы —\n  состояние, а не событие, и каждая цель уходит ровно один раз за загрузку.\n* На телефоне рекламы в записях не было (`adFailed`), `started` через\n  3–5 с после нажатия.\n\nПочему цели zona-03 не копируются\n---------------------------------\n\nПроверено по `zonafilm12-site/src/lords-frontend.py`: там `player_ready`\nсрабатывает и на `statechange:\'playing\'`, и на `play`/`started` при позиции\nменьше 3 с, то есть смешивает готовность с ранним воспроизведением, а начало\nосновного видео (`confirmPlaying`) цели не имеет вовсе. Унаследованные\nпараметры образца подтверждаются наравне с данными\n(`docs/ANALYSIS_ORDER.md`), и эти не подтвердились.\n\nКак сделано\n-----------\n\n1. **Отдельный слушатель `message`**, а не врезка в `onProviderMsg`. Так\n   якорь не сталкивается с правкой `player_watchdog`, а главное — ошибка в\n   слое целей не может сломать воспроизведение: управляющий поток плеера не\n   затрагивается.\n2. **Вся логика целей — в скрипте страницы**, в рантайме только добавление\n   слушателя. Скрипт читается и проверяется как текст.\n3. **Ни одного имени мимо разрешённых.** Список берётся из\n   `config/site.json: goals.enabled`; по умолчанию — только три цели,\n   которые у счётчика можно создать без новых решений. Новая цель в счётчике\n   — запись в Метрику и решение владельца; до неё имя не отправляется, чтобы\n   не писать под чужим.\n4. **Каждая цель — ровно один раз за загрузку страницы.**\n\nПроверка — `checks/player_goals.py`.\n"""\n\nfrom __future__ import annotations\n\nimport html\nimport json\nimport os\n\nИМЯ_ПРАВКИ = "цели пути до просмотра: title_view, player_start, player_ready"\n\n#: Цели, которые отправляются без новых решений владельца.\nПО_УМОЛЧАНИЮ = ("title_view", "player_start", "player_ready")\n\n#: Все известные слою имена. Отправляется только пересечение с разрешёнными.\nВСЕ_ЦЕЛИ = ПО_УМОЛЧАНИЮ + (\n    "player_cta",            # клик «К плееру» — отдельно от нажатия по плееру\n    "player_ad_start",       # реклама началась\n    "player_ad_end",         # реклама кончилась любым исходом\n    "player_main_observed",  # первый timeupdate с позицией ≥ 3 с вне рекламы\n)\n\n#: Порог позиции, ниже которого timeupdate — холостая позиция загрузки.\nПОРОГ_ПОЗИЦИИ = 3\n\nЯКОРЬ_СЛУШАТЕЛЯ = " window.addEventListener(\'message\', onProviderMsg);"\n\nДОБАВКА_СЛУШАТЕЛЯ = """ window.addEventListener(\'message\', onProviderMsg);\n // Слой целей слушает сообщения ОТДЕЛЬНО (src/player_goals.py витрины):\n // управляющий поток плеера не затрагивается, поэтому ошибка в целях не\n // может сломать воспроизведение.\n window.addEventListener(\'message\', function(ev){\n  if(!ev || ev.origin!==ORIGIN) return;\n  if(!window.__sfGoalMsg) return;\n  var p=ev.data, t=\'\', d=null;\n  try{\n   if(typeof p===\'string\') p=JSON.parse(p);\n   t=p && p.eventType || \'\';\n   d=p && p.data;\n  }catch(e){ return; }\n  if(!t) return;\n  try{ window.__sfGoalMsg(t, d); }catch(e){}\n });"""\n\n\ndef _скрипт(ид: str, счётчик: str, разрешено: tuple[str, ...]) -> str:\n    """Скрипт страницы: вся логика целей здесь, в рантайме — только слушатель."""\n    данные = json.dumps(\n        {"id": ид, "counter": счётчик, "allow": list(разрешено),\n         "minPos": ПОРОГ_ПОЗИЦИИ},\n        ensure_ascii=False, separators=(",", ":"))\n    return (\n        \'<script data-sf-goals>(function(){\\n\'\n        f\' var К={данные};\\n\'\n        \' var ушло={}, вРекламе=false, началось=false;\\n\'\n        \' function цель(имя){\\n\'\n        \'  if(К.allow.indexOf(имя)<0) return;   /* чужого имени не отправляем */\\n\'\n        \'  if(ушло[имя]) return;                /* ровно один раз за загрузку */\\n\'\n        \'  ушло[имя]=1;\\n\'\n        \'  try{\\n\'\n        \'   if(!window.ym || !К.counter) return;\\n\'\n        \'   window.ym(К.counter,"reachGoal",имя,{title_id:К.id});\\n\'\n        \'  }catch(e){}\\n\'\n        \' }\\n\'\n        \' window.__sfGoal=цель;\\n\'\n        \' window.__sfGoalMsg=function(тип,дан){\\n\'\n        \'  if(тип==="requestPlay"){ цель("player_start"); return; }\\n\'\n        \'  if(тип==="statechange" && дан==="ready"){ цель("player_ready"); return; }\\n\'\n        \'  if(тип==="adStart" || (тип==="rollState" && дан && дан.state==="start")){\\n\'\n        \'   вРекламе=true; цель("player_ad_start"); return;\\n\'\n        \'  }\\n\'\n        \'  if(тип==="adComplete" || тип==="adClosed" || тип==="adSkipped"\\n\'\n        \'     || тип==="adError" || тип==="adFailed"\\n\'\n        \'     || (тип==="rollState" && дан && дан.state && дан.state!=="start")){\\n\'\n        \'   вРекламе=false; цель("player_ad_end"); return;\\n\'\n        \'  }\\n\'\n        \'  if(тип==="timeupdate" && дан && typeof дан.position==="number"){\\n\'\n        \'   /* Реклама timeupdate не присылает (замер 28.10), а позиции 0.09-1.07\\n\'\n        \'      приходят до нажатия: порог отсекает и то, и другое. */\\n\'\n        \'   if(!вРекламе && !началось && дан.position>=К.minPos){\\n\'\n        \'    началось=true; цель("player_main_observed");\\n\'\n        \'   }\\n\'\n        \'  }\\n\'\n        \' };\\n\'\n        \' цель("title_view");\\n\'\n        \' document.addEventListener("click",function(ev){\\n\'\n        \'  var у=ev && ev.target;\\n\'\n        \'  var а=у && у.closest ? у.closest(\\\'a[data-cta="to-player"]\\\') : null;\\n\'\n        \'  if(а) цель("player_cta");\\n\'\n        \' },true);\\n\'\n        \'})();</script>\')\n\n\ndef разрешённые(настройка: dict | None) -> tuple[str, ...]:\n    """Имена целей из настройки витрины; неизвестные имена отбрасываются."""\n    раздел = ((настройка or {}).get("goals") or {})\n    список = раздел.get("enabled")\n    if not isinstance(список, list):\n        return ПО_УМОЛЧАНИЮ\n    выбрано = tuple(и for и in ВСЕ_ЦЕЛИ if и in список)\n    return выбрано\n\n\ndef вставить(страница: str, ид: str, счётчик: str,\n             разрешено: tuple[str, ...]) -> str:\n    """Добавляет скрипт целей перед </body>. Без идентификатора — не трогает."""\n    ид = str(ид or "").strip()\n    if not ид or "data-sf-goals" in страница:\n        return страница\n    скрипт = _скрипт(html.escape(ид, quote=True), str(счётчик or ""), разрешено)\n    низ = страница.rfind("</body>")\n    if низ < 0:\n        return страница + скрипт\n    return страница[:низ] + скрипт + страница[низ:]\n\n\ndef установить(рантайм, настройка: dict | None = None) -> str:\n    if getattr(рантайм, "_цели_плеера_поставлены", False):\n        return ИМЯ_ПРАВКИ + " — уже стоит"\n\n    n = рантайм.СКРИПТ_ПЛЕЕРА_КЛИЕНТ.count(ЯКОРЬ_СЛУШАТЕЛЯ)\n    if n != 1:\n        raise RuntimeError(\n            f"цели плеера: якорь слушателя найден {n} раз(а), ожидался 1")\n    рантайм.СКРИПТ_ПЛЕЕРА_КЛИЕНТ = рантайм.СКРИПТ_ПЛЕЕРА_КЛИЕНТ.replace(\n        ЯКОРЬ_СЛУШАТЕЛЯ, ДОБАВКА_СЛУШАТЕЛЯ, 1)\n\n    разрешено = разрешённые(настройка)\n    вид = getattr(рантайм, "ВидЗона", None)\n    if вид is None:\n        raise RuntimeError("цели плеера: класс ВидЗона не найден")\n\n    for имя in ("тайтл", "сезон", "серия"):\n        исходный = getattr(вид, имя, None)\n        if исходный is None:\n            raise RuntimeError(f"цели плеера: у ВидЗона нет метода {имя}")\n\n        def обёртка(self, запись, деталь, *а, _и=исходный, **к):\n            страница = _и(self, запись, деталь, *а, **к)\n            счётчик = os.environ.get("LORDS_METRIKA_COUNTER", "").strip()\n            if not счётчик.isdigit():\n                return страница\n            ид = (деталь or {}).get("id") if isinstance(деталь, dict) else ""\n            return вставить(страница, ид, счётчик, разрешено)\n\n        setattr(вид, имя, обёртка)\n\n    рантайм._цели_плеера_поставлены = True\n    return ИМЯ_ПРАВКИ + f" (разрешено: {\', \'.join(разрешено) or \'ничего\'})"\n'

ЯКОРЬ_ИМПОРТА = "perf_memo, player_watchdog, public_wording,"
ЗАМЕНА_ИМПОРТА = "perf_memo, player_goals, player_watchdog, public_wording,"

ЯКОРЬ_РЕГИСТРАЦИИ = "    внесено.append(player_watchdog.установить(рантайм))"
ЗАМЕНА_РЕГИСТРАЦИИ = """    внесено.append(player_watchdog.установить(рантайм))

    # 8а) Цели пути до просмотра: карточка, намерение запустить, готовность
    #     плеера, реклама и наблюдаемое начало основного видео. До этой
    #     правки витрина не отправляла ни одной цели, и все девять целей
    #     счётчика показывали 0 при живом трафике — то есть путь был НЕ
    #     ИЗМЕРЕН, а не равен нулю. Слой слушает сообщения поставщика
    #     отдельным слушателем, поэтому ошибка в целях не может сломать
    #     воспроизведение. Имена отправляются только из
    #     `config/site.json: goals.enabled`. Разбор — src/player_goals.py.
    внесено.append(player_goals.установить(
        рантайм,
        json.loads((КОРЕНЬ / "config" / "site.json").read_text(encoding="utf-8"))))"""


def применить(репо: pathlib.Path, писать: bool) -> tuple[str, str]:
    """Возвращает (исход, пояснение). Исход: ok | skip | refuse."""
    если = репо / "src" / МОДУЛЬ
    служба = репо / "src" / "serve.py"
    if not служба.is_file():
        return "refuse", f"нет {служба}"
    текст = служба.read_text(encoding="utf-8")

    уже_модуль = если.is_file() and если.read_text(encoding="utf-8") == ИСХОДНИК
    уже_импорт = ЗАМЕНА_ИМПОРТА in текст
    уже_рег = "player_goals.установить" in текст
    if уже_модуль and уже_импорт and уже_рег:
        return "skip", "слой целей уже стоит и совпадает"

    if not уже_импорт:
        n = текст.count(ЯКОРЬ_ИМПОРТА)
        if n != 1:
            return "refuse", (f"якорь импорта найден {n} раз(а), ожидался 1: "
                              f"{ЯКОРЬ_ИМПОРТА!r}")
    if not уже_рег:
        n = текст.count(ЯКОРЬ_РЕГИСТРАЦИИ)
        if n != 1:
            return "refuse", (f"якорь регистрации найден {n} раз(а), ожидался 1: "
                              f"{ЯКОРЬ_РЕГИСТРАЦИИ!r}")

    if not писать:
        сделаем = []
        if not уже_модуль:
            сделаем.append(f"src/{МОДУЛЬ}")
        if not уже_импорт:
            сделаем.append("импорт в src/serve.py")
        if not уже_рег:
            сделаем.append("регистрация после player_watchdog")
        return "ok", "будет сделано: " + ", ".join(сделаем)

    новый = текст
    if not уже_импорт:
        новый = новый.replace(ЯКОРЬ_ИМПОРТА, ЗАМЕНА_ИМПОРТА, 1)
    if not уже_рег:
        новый = новый.replace(ЯКОРЬ_РЕГИСТРАЦИИ, ЗАМЕНА_РЕГИСТРАЦИИ, 1)
    если.write_text(ИСХОДНИК, encoding="utf-8")
    служба.write_text(новый, encoding="utf-8")
    return "ok", f"поставлено: src/{МОДУЛЬ}, импорт и регистрация в src/serve.py"


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--repo", required=True)
    р.add_argument("--check", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args()
    репо = pathlib.Path(а.repo).resolve()
    исход, пояснение = применить(репо, писать=not (а.check or а.dry_run))
    print(f"[{исход}] {репо.name}: {пояснение}")
    if исход == "refuse":
        return 2
    if а.check:
        return 1 if исход == "ok" else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
