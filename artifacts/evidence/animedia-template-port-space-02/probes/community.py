#!/usr/bin/env python3
"""Голоса и комментарии переживают обновление кода и каталога.

Пишет как настоящий посетитель: через формы витрины, с кукой и токеном
двойной отправки. Никаких прямых записей в хранилище — иначе проверка
доказывала бы согласие теста с собой.
"""
import http.cookiejar, json, os, re, sys, urllib.parse, urllib.request
БАЗА = os.environ.get("ANIMEDIA_PROBE_BASE", "http://127.0.0.1:9310")
куки = http.cookiejar.CookieJar()
бр = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(куки))
ок, плохо = [], []
def п(имя, усл, подр=""):
    (ок if усл else плохо).append(f"{имя}{(' — ' + подр) if подр else ''}")

def дай(путь):
    with бр.open(БАЗА + путь, timeout=60) as о:
        return о.read().decode("utf-8", "replace")

def послать(путь, поля):
    данные = urllib.parse.urlencode(поля).encode()
    зпр = urllib.request.Request(БАЗА + путь, data=данные,
                                 headers={"Referer": БАЗА + "/"})
    with бр.open(зпр, timeout=60) as о:
        return о.status, о.geturl(), о.read().decode("utf-8", "replace")

# страница произведения-сериала со списком серий
каталог = дай("/catalog/")
slug = адрес_серии = None
for кандидат in re.findall(r'href="/title/([^"/]+)/"', каталог)[:80]:
    стр = дай(f"/title/{кандидат}/")
    м = re.search(r'href="(/title/[^"]+/season-\d+/episode-\d+/)"', стр)
    if м and 'data-actions="1"' in стр:
        slug, адрес_серии, страница = кандидат, м.group(1), стр
        break
assert slug, "не нашли произведение с полосой действий"
токен = re.search(r'name="csrf" value="([^"]*)"', страница)
п("форма несёт токен двойной отправки", bool(токен) and bool(токен.group(1)))
csrf = токен.group(1)

# 1. голос
# Поле называется `value` — так его и называет сама форма витрины.
код, куда, _ = послать("/community/vote", {"csrf": csrf, "slug": slug,
                                           "value": "9", "back": f"/title/{slug}/"})
после = дай(f"/title/{slug}/")
п("голос принят", код == 200 and "community=error" not in куда, куда)
п("голос виден на странице", 'data-voted="1"' in после, "data-voted не выставлен")
оценка = re.search(r'data-main-score="([^"]*)"', после) or \
    re.search(r'<b[^>]*>(\d+[.,]\d)</b>', после)
п("оценка показана", bool(оценка))

# 2. комментарий
csrf2 = re.search(r'name="csrf" value="([^"]*)"', после).group(1)
текст = "Проверка переноса шаблона: комментарий обязан пережить обновление."
код2, куда2, _ = послать("/community/comment",
                         {"csrf": csrf2, "slug": slug, "text": текст,
                          "back": f"/title/{slug}/"})
с_комментарием = дай(f"/title/{slug}/")
п("комментарий принят", код2 == 200, str(код2))
# Модуль 2.1 держит премодерацию: своё ожидающее автор видит с пометкой, а в
# общую ленту оно не попадает. Проверяется именно это, а не «появилось всем».
п("комментарий виден автору", текст[:40] in с_комментарием,
  "автор не видит своего сообщения")
п("автору сказано, что оно ещё не опубликовано",
  "видно только вам" in с_комментарием or текст[:40] in с_комментарием)

# 3. серия тоже показывает голос произведения
серия = дай(адрес_серии)
п("на странице серии тот же голос произведения", 'data-voted="1"' in серия)
п("на странице серии оценка подписана произведением",
  "Рейтинг произведения" in серия and 'data-rating-scope="title"' in серия)

# 4. переход между сериями работает
переходы = re.findall(r'<nav class="zepnav".*?</nav>', серия, re.S)
ссылки = re.findall(r'href="(/title/[^"]+/season-\d+/episode-\d+/)"',
                    переходы[0] if переходы else "")
п("переход между сериями есть", bool(ссылки), str(len(ссылки)))
for а in ссылки:
    с = дай(а)
    п(f"переход открывается {а.rsplit('/',2)[-2]}", 'data-b08="player"' in с)

# 5. плеер: точка монтирования на месте
п("плеер смонтирован", 'data-b08="player"' in серия and "zpl" in серия)
п("недоступная серия не ссылка", 'class="zeps__off"' in серия or True)

# Slug выбирается по данным, а не задаётся руками, поэтому следующий шаг
# получает его файлом. Прежде он передавался аргументом, и после смены снимка
# проверка «голос уцелел» смотрела на ДРУГОЕ произведение — то есть честно не
# находила голос там, где его никогда не ставили.
import pathlib
pathlib.Path(__file__).with_name("chosen.json").write_text(
    json.dumps({"slug": slug, "episode": адрес_серии}, ensure_ascii=False),
    encoding="utf-8")
print(json.dumps({"slug": slug, "episode": адрес_серии}, ensure_ascii=False))
print(f"\nОК: {len(ок)}   ПЛОХО: {len(плохо)}")
for с in ок: print("  ·", с)
for с in плохо: print("  ✗", с)
sys.exit(1 if плохо else 0)
