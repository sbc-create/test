#!/usr/bin/env python3
"""Состояние ПОСЛЕ обновления каталога и обновления кода.

Каталог доставлен новым снимком (ревизия сменилась с e2c18b52546c на
e7cd4829fadb, витрина перечитала его сама), релиз пересобран и витрина
перезапущена на новом каталоге релиза. Здесь проверяется, что уцелело.
"""
import json
import os, re, sys, urllib.request
from pathlib import Path
САЙТ = os.environ.get("ANIMEDIA_PROBE_SITE", "animedia-verify")
V = Path(sys.argv[1]); БАЗА = os.environ.get("ANIMEDIA_PROBE_BASE", "http://127.0.0.1:9310")
# Произведение берётся из того, что выбрал шаг с голосом, а не из аргумента:
# аргумент расходится с данными молча.
выбор = Path(__file__).with_name("chosen.json")
if выбор.is_file():
    SLUG = json.loads(выбор.read_text(encoding="utf-8"))["slug"]
elif len(sys.argv) > 2:
    SLUG = sys.argv[2]
else:
    # Шаг с голосом выбирает произведение по данным и записывает выбор рядом.
    # Без него проверять «голос уцелел» не на чем, и молчать об этом нельзя:
    # пустая проверка выглядит как пройденная.
    raise SystemExit("нет chosen.json — сначала выполните community.py "
                     "(или передайте slug вторым аргументом)")
ок, плохо = [], []
def п(имя, усл, подр=""):
    (ок if усл else плохо).append(f"{имя}{(' — ' + подр) if подр else ''}")
def дай(п_):
    with urllib.request.urlopen(БАЗА + п_, timeout=60) as о:
        return о.read().decode("utf-8", "replace")

хранилище = V / "data" / "site-data" / "animedia-community.json"
d = json.loads(хранилище.read_text(encoding="utf-8"))
т = d.get("titles") or {}
п("хранилище сообщества цело", bool(т), str(list(т)[:1]))
запись = list(т.values())[0]
def сколько(поле):
    з = запись.get(поле)
    if isinstance(з, (list, dict)):
        return len(з)
    try:
        return int(з or 0)
    except (TypeError, ValueError):
        return 0
сводка = json.dumps({k: сколько(k) for k in ("votes", "comments", "reactions")},
                    ensure_ascii=False)
п("голос на месте после обновления каталога и кода", сколько("votes") >= 1, сводка)
п("комментарии на месте", сколько("comments") >= 1, сводка)
п("закреплённая база оценки на месте", запись.get("base") is not None,
  str(запись.get("base")))

стр = дай(f"/title/{SLUG}/")
п("витрина отвечает на новом коде", "<h1" in стр)
# `data-voted` привязан к КУКЕ посетителя, и у безымянного запроса его быть не
# должно. Проверяется то, что видно всем: голос учтён в главной оценке, и
# витрина говорит, из чего эта оценка собрана.
наши = re.search(r'data-our-votes="(\d+)"', стр)
состояние_оценки = re.search(r'data-rating-state="[^"]*"', стр)
п("голос учтён в главной оценке и это объявлено",
  bool(наши) and int(наши.group(1)) == сколько("votes")
  and 'data-rating-state="base+votes"' in стр,
  f'витрина объявляет {наши.group(1) if наши else "нет"} голосов, '
  f'хранилище знает {сколько("votes")}; состояние '
  + (состояние_оценки.group(0) if состояние_оценки else "нет"))
п("оценка считается общим модулем, а не своей формулой шаблона",
  'data-rating-formula="main-score/1.0"' in стр)
версия = re.search(r'name="site-factory-design-version" content="([^"]*)"', стр)
п("оформление объявлено 1.2.11",
  bool(версия) and версия.group(1) == "1.2.11", версия.group(1) if версия else "нет")
рев = re.search(r'name="site-factory-artifact-sha256" content="([^"]*)"', стр)
п("артефакт объявлен в разметке", bool(рев), рев.group(1)[:16] if рев else "")

серия = re.search(r'href="(/title/[^"]+/season-\d+/episode-\d+/)"', стр)
п("ссылка на серию есть", bool(серия))
if серия:
    с = дай(серия.group(1))
    п("плеер смонтирован после обновления", 'data-b08="player"' in с)
    п("переход между сериями работает", "zepnav" in с)
    п("карточка произведения на серии на месте", 'data-episode-context="1"' in с)
    п("оценка произведения подписана", "Рейтинг произведения" in с)

# ТОП, подборки и лента после обновления
топ = дай("/top/")
ранги = [int(n) for n in re.findall(r'data-rank="(\d+)"', топ)]
п("ТОП-100 после обновления цел", ранги == list(range(1, 101)), f"мест {len(ранги)}")
главная = дай("/")
п("подборки на главной с обложками после обновления",
  главная.count('<img class="zhub__img"') >= 8,
  str(главная.count('<img class="zhub__img"')))
лента = re.search(r'data-b03="populated".*?</section>', главная, re.S)
п("лента новых серий жива после обновления", bool(лента))
if лента:
    адреса = re.findall(r'<a class="aeps__row"[^>]*href="([^"]+)"', лента.group(0))
    тайтлы = {а.split("/season-")[0] for а in адреса}
    п("история ленты не стёрта обновлением", len(адреса) >= 10, f"карточек {len(адреса)}")
    п("одно произведение — одна карточка", len(тайтлы) == len(адреса))
реестр = json.loads(
    (V / "data" / f"{САЙТ}-episode-events.json").read_text(encoding="utf-8"))
п("реестр событий уцелел", len(реестр.get("events") or []) >= 60,
  str(len(реестр.get("events") or [])))

print(f"\nОК: {len(ок)}   ПЛОХО: {len(плохо)}")
for с in ок: print("  ·", с)
for с in плохо: print("  ✗", с)
sys.exit(1 if плохо else 0)
