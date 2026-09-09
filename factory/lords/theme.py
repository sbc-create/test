"""Визуальная система Lords: одна таблица стилей, четыре конфигурации.

Приложение одно. Различие сайтов задаётся токенами темы и параметрами раскладки
из профиля, а не второй копией шаблона: правка вёрстки должна доходить до всех
четырёх сайтов одним изменением, иначе они разъедутся на первом же исправлении.

Стили написаны здесь целиком и ни на что не опираются: ни внешних таблиц, ни
шрифтовых сервисов, ни библиотек. Это одновременно требование безопасности
(сайт не обращается наружу) и требование воспроизводимости (сборка не зависит от
того, что сегодня отдаёт чужой сервер).
"""

from __future__ import annotations

#: Токены выведены из измерения референсов кинотеатров, а не подобраны на глаз.
#: Замер вычисленных стилей lordfilm-hit.org и lordserials.fan на ширине 1440:
#:
#:   фон страницы      rgb(17,17,17)      — нейтральный, без синевы
#:   поверхность       rgb(34,34,34)
#:   акцент            rgb(121,193,66)    — зелёный, 60 вхождений на главной
#:   гарнитура         Open Sans, 14px
#:   H1                18px / 600
#:
#: Прежние значения давали синеватый фон #101319, синий акцент #6f9dff, базовый
#: кегль 16px и H1 в 36px — вдвое крупнее референсного. Отсюда и ощущение
#: «технической страницы»: крупные заголовки, разреженный текст и цвет ссылок
#: по умолчанию читаются как служебная вёрстка, а не как витрина кинотеатра.
DEFAULT_TOKENS = {
    "bg": "#111111",
    "surface": "#222222",
    "surface_alt": "#2b2b2b",
    "text": "#e6e6e6",
    "muted": "#9a9a9a",
    "accent": "#79c142",
    "accent_text": "#0d0d0d",
    "border": "#353535",
    "radius": "6px",
    "container": "1240px",
    # Open Sans — гарнитура обоих референсов. Список запасных оставлен: своего
    # файла шрифта у сайта нет, а тянуть чужой хостинг ради начертания незачем.
    "heading_font": "'Open Sans', 'Segoe UI', Roboto, Arial, sans-serif",
    # Кегль заголовков — часть договора профиля, а не константа темы.
    # Умолчание совпадает с прежними значениями, поэтому у витрин, которые
    # его не объявляют, не меняется ничего: 18px/600 у H1 сняты с референса
    # Lords и остаются его решением.
    #
    # Витринам с собственным договором оформления умолчание не годится:
    # заголовок, крупнее основного текста на семь процентов, иерархии не
    # создаёт — измерено, шкала выходила 1,07.
    "h1_size": "1.125rem",
    "h2_size": "1.05rem",
}

DEFAULT_LAYOUT = {
    "density": "comfortable",
    "hero": "catalog",
    "card_ratio": "2 / 3",
    "columns": {"mobile": 2, "tablet": 4, "desktop": 6},
    "facet_position": "sidebar",
}

#: Отступы плотности. Compact-профиль обязан отличаться не только цветом.
DENSITY = {
    "airy": {"gap": "28px", "pad": "34px", "card_pad": "18px"},
    "comfortable": {"gap": "18px", "pad": "22px", "card_pad": "12px"},
    "dense": {"gap": "14px", "pad": "18px", "card_pad": "10px"},
    "compact": {"gap": "10px", "pad": "13px", "card_pad": "7px"},
}



#: Нейтральные палитры под выбор зрителя.
#:
#: Профиль задаёт ЛИЦО витрины — свой фон и свой акцент. Выбор темы — другое:
#: это предпочтение зрителя поверх лица. Поэтому здесь только поверхности и
#: текст; акцент профиля не трогается, иначе витрины перестали бы различаться.
#:
#: Значения подобраны так, чтобы обычный и приглушённый текст проходили
#: WCAG AA на своём фоне; это проверяется тестом, а не глазом.
SURFACE_PALETTES = {
    "dark": {
        "bg": "#111111", "surface": "#181818", "surface_alt": "#1f1f1f",
        "text": "#e6e6e6", "muted": "#a8a8a8", "border": "#2c2c2c",
    },
    "light": {
        "bg": "#f4f6f8", "surface": "#ffffff", "surface_alt": "#e9edf1",
        "text": "#151a21", "muted": "#4d5560", "border": "#d3d9df",
    },
}


def _relative_luminance(color: str) -> float:
    value = color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    channels = []
    for i in (0, 2, 4):
        c = int(value[i:i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(foreground: str, background: str) -> float:
    a, b = _relative_luminance(foreground), _relative_luminance(background)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


def readable_on(color: str, background: str, *, target: float = 4.5) -> str:
    """Тот же цвет, доведённый до порога контраста на данном фоне.

    Нужен для ссылок. Ссылка красится акцентом профиля — это лицо витрины, — но
    акцент подобран под родную палитру. На светлой палитре зелёный `#79c142`
    даёт контраст около двух: axe справедливо считает это нарушением, и
    прочитать такую ссылку тяжело.

    Менять акцент нельзя: витрины перестали бы различаться. Поэтому цвет
    ССЫЛКИ вычисляется из акцента — затемняется или осветляется шагами, пока
    не достигнет порога. Вычисляется, а не подбирается на глаз: подбор не
    воспроизводится и разъезжается при первой смене палитры.
    """
    value = color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return color
    # Направление выбирается по фону: на светлом темнеем, на тёмном светлеем.
    darken = _relative_luminance(background) > 0.5
    for _ in range(64):
        current = f"#{r:02x}{g:02x}{b:02x}"
        if _contrast(current, background) >= target:
            return current
        if darken:
            r, g, b = (max(0, int(c * 0.94)) for c in (r, g, b))
            if r == g == b == 0:
                return "#000000"
        else:
            r, g, b = (min(255, int(c * 1.06) + 2) for c in (r, g, b))
            if r == g == b == 255:
                return "#ffffff"
    return f"#{r:02x}{g:02x}{b:02x}"


def _palette_block(selector: str, mode: str, *, accent: str = "", indent: str = "") -> str:
    """Переопределение поверхностей для одной палитры.

    Вместе с поверхностями переопределяется цвет ссылки: акцент профиля
    подобран под родную палитру и на чужой может не пройти контраст.
    """
    tokens = dict(SURFACE_PALETTES[mode])
    lines = "".join(
        f"\n{indent}  --{name.replace('_', '-')}: {value};" for name, value in tokens.items())
    if accent:
        link = readable_on(accent, tokens["bg"])
        lines += f"\n{indent}  --link: {link};"
    return f"{indent}{selector} {{{lines}\n{indent}}}"


def _поверхность(имя: str | None) -> str | None:
    """Какой поверхности соответствует объявленное имя темы.

    Вынесено из `tokens_of`: то же правило нужно и второй палитре, а два
    списка окончаний разошлись бы молча.
    """
    имя = str(имя or "")
    if имя.endswith("_light"):
        return "light"
    if имя.endswith("_dark"):
        return "dark"
    return None


def tokens_of(profile: dict, *, declared_theme: str | None = None) -> dict:
    """Токены палитры витрины. Манифест сильнее профиля.

    `declared_theme` — значение `tenant.theme` из пакета витрины. Когда оно
    расходится с темой профиля, побеждает пакет: CLAUDE.md ставит манифест
    первым источником истины, а профиль — четвёртым, и поле манифеста, которое
    рендерер не читает, выглядит настройкой, ничего не меняя.

    Расхождение не выдумано. Пакет `lords-03` объявляет `lords_light`, а его
    профиль `lords-curated` — `lords_dark` с тёмными токенами; витрина
    отрисовывалась тёмной, и семейство `lords_light` состояло из одной витрины
    вместо двух. Обнаружено измерением яркости полотна, а не чтением: на глаз
    страница выглядела исправной.

    Здесь только применяется объявленный порядок источников. Какой облик нужен
    витрине, решает владелец — и решение он выражает манифестом.
    """
    merged = dict(DEFAULT_TOKENS)
    merged.update((profile.get("theme") or {}).get("tokens") or {})
    profile_theme = str((profile.get("theme") or {}).get("name") or "")
    if declared_theme and declared_theme != profile_theme:
        surface = _поверхность(declared_theme)
        if surface:
            merged.update(SURFACE_PALETTES[surface])
    return merged


#: Схема второй палитры: какой она приходится основной. Значение проверяется,
#: а не угадывается по яркости цветов — «светлая» палитра с тёмным фоном
#: сломала бы и `prefers-color-scheme`, и переключатель.
СХЕМЫ = ("light", "dark")


def alt_tokens_of(profile: dict, *, declared_theme: str | None = None
                  ) -> tuple[str, dict] | None:
    """Вторая палитра витрины и то, какой схеме она соответствует.

    None означает, что витрина объявила одну палитру. Переключатель тем в этом
    случае не рисуется вовсе: кнопка, которая ничего не меняет, хуже её
    отсутствия — посетитель считает её сломанной, а не отсутствующей.

    Палитра не выводится из основной. Осветлить тёмные токены арифметикой можно,
    но получится не «светлая тема», а тёмная с испорченным контрастом; выбор
    цветов — решение оформления, а не вычисление.
    """
    тема = profile.get("theme") or {}
    палитра = тема.get("tokens_alt") or {}
    схема = str(тема.get("alt_scheme") or "").strip().lower()
    if not палитра:
        # Профиль второй палитры не объявил — но манифест мог назвать
        # поверхность. Тогда вторая палитра берётся противоположной из
        # SURFACE_PALETTES: это не вывод цветов арифметикой, которого модуль
        # избегает, а выбор из наборов, уже проверенных на контраст тестом —
        # ровно то же, что `tokens_of` делает для основной палитры.
        #
        # Витрина lords-02 объявляет `lords_dark` и не объявляла второй
        # палитры, поэтому переключатель не рисовался вовсе: посетитель не мог
        # сменить режим, хотя обе палитры давно есть в модуле.
        поверхность = _поверхность(declared_theme)
        if поверхность is None:
            return None
        противоположная = "light" if поверхность == "dark" else "dark"
        выведенная = dict(DEFAULT_TOKENS)
        выведенная.update(тема.get("tokens") or {})
        выведенная.update(SURFACE_PALETTES[противоположная])
        return противоположная, выведенная
    if схема not in СХЕМЫ:
        # Палитра есть, а чему она соответствует — не сказано. Догадка здесь
        # означала бы, что светлая тема включается по системной тёмной.
        return None
    слитая = dict(DEFAULT_TOKENS)
    слитая.update(тема.get("tokens") or {})
    слитая.update(палитра)
    return схема, слитая


def theme_switch_available(profile: dict, *, declared_theme: str | None = None) -> bool:
    return alt_tokens_of(profile, declared_theme=declared_theme) is not None


def _переменные(t: dict) -> str:
    поля = ("bg", "surface", "surface_alt", "text", "muted", "accent",
            "accent_text", "border")
    return "\n".join(f"  --{имя.replace('_', '-')}: {t[имя]};" for имя in поля if имя in t)


def alt_blocks(profile: dict, *, declared_theme: str | None = None) -> str:
    """Правила второй палитры: системная схема и явный выбор посетителя.

    Три блока, и каждый нужен. Медиазапрос даёт системную тему тем, кто ничего
    не выбирал; `:root:not([data-theme])` в нём — чтобы явный выбор не
    отменялся системной настройкой. Два блока по `data-theme` дают сам выбор в
    обе стороны.
    """
    пара = alt_tokens_of(profile, declared_theme=declared_theme)
    if пара is None:
        return ""
    схема, alt = пара
    основная = "dark" if схема == "light" else "light"
    свои = _переменные(alt)
    родные = _переменные(tokens_of(profile, declared_theme=declared_theme))
    return f"""

/* Вторая палитра витрины: {схема}. */
@media (prefers-color-scheme: {схема}) {{
  :root:not([data-theme="{основная}"]) {{
{свои}
  }}
}}
:root[data-theme="{схема}"] {{
{свои}
}}
:root[data-theme="{основная}"] {{
{родные}
}}
.theme-switch {{ display: inline-flex; gap: 2px; margin-left: auto; }}
.theme-switch button {{
  background: var(--surface-alt); color: var(--text); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 4px 8px; font: inherit; cursor: pointer;
}}
.theme-switch button[aria-pressed="true"] {{
  background: var(--accent); color: var(--accent-text);
}}
"""


def layout_of(profile: dict) -> dict:
    merged = dict(DEFAULT_LAYOUT)
    merged.update(profile.get("layout") or {})
    columns = dict(DEFAULT_LAYOUT["columns"])
    columns.update(merged.get("columns") or {})
    merged["columns"] = columns
    return merged


def _stylesheet_base(profile: dict, *, declared_theme: str | None = None) -> str:
    """Полная таблица стилей сайта. Один файл, без импортов и без внешних ссылок."""
    t = tokens_of(profile, declared_theme=declared_theme)
    # Блоки системной схемы выводятся только у витрин со второй палитрой.
    #
    # Они дают поведение выбору «как в системе», а сам выбор доступен лишь там,
    # где переключатель есть, — то есть где объявлена вторая палитра. У витрины
    # с одной палитрой атрибут `data-theme="system"` поставить некому, и правила
    # остаются мёртвым весом: браузер их разбирает, посетитель не видит ничего.
    #
    # Требование производственной линии здесь прямое и верное: без второй
    # палитры таблица стилей не несёт машинерии тем вовсе.
    системная_схема = ""
    if theme_switch_available(profile, declared_theme=declared_theme):
        системная_схема = (
            "@media (prefers-color-scheme: dark) {\n"
            + _palette_block(':root[data-theme="system"]', "dark",
                             accent=t["accent"], indent="  ")
            + "\n}\n@media (prefers-color-scheme: light) {\n"
            + _palette_block(':root[data-theme="system"]', "light",
                             accent=t["accent"], indent="  ")
            + "\n}"
        )
    # Правила явного выбора — по той же причине: выбирать некому там, где
    # переключателя нет.
    явный_выбор = ""
    if theme_switch_available(profile, declared_theme=declared_theme):
        явный_выбор = (
            "/* Явный выбор зрителя. Он идёт первым и побеждает системную "
            "настройку. */\n"
            + _palette_block(':root[data-theme="dark"]', "dark", accent=t["accent"])
            + "\n"
            + _palette_block(':root[data-theme="light"]', "light", accent=t["accent"])
        )
    lay = layout_of(profile)
    d = DENSITY.get(str(lay.get("density")), DENSITY["comfortable"])
    cols = lay["columns"]
    hero = str(lay.get("hero"))
    sidebar = str(lay.get("facet_position")) == "sidebar"

    return f"""/* Lords — {profile.get('profile', 'unknown')}. Сгенерировано фабрикой. */
:root {{
  --bg: {t['bg']};
  --surface: {t['surface']};
  --surface-alt: {t['surface_alt']};
  --text: {t['text']};
  --muted: {t['muted']};
  --accent: {t['accent']};
  --accent-text: {t['accent_text']};
  --border: {t['border']};
  --radius: {t['radius']};
  --container: {t['container']};
  --gap: {d['gap']};
  --pad: {d['pad']};
  --card-pad: {d['card_pad']};
  --card-ratio: {lay['card_ratio']};
  --cols: {cols['mobile']};
  --link: {readable_on(t['accent'], t['bg'])};
  --h1: {t['h1_size']};
  --h2: {t['h2_size']};
  --font: {t['heading_font']};
  /* Без color-scheme браузер рисует свои полосы прокрутки и элементы
     управления в чужой теме — страница выходит двухцветной. */
  color-scheme: light dark;
}}

{явный_выбор}

/* Системная настройка применяется только по просьбе зрителя — когда он выбрал
   «как в системе». Это исправление, а не украшение.

   Прежде оба правила стояли без условия на выбор, и системная настройка
   перебивала палитру профиля всегда. Следствие измерено: витрины семейства
   lords_dark отрисовывались со светлым полотном яркости 0,919 — ровно как
   lords_light. Два семейства, объявленные разными, выглядели одинаково у
   любого зрителя, чья система предпочитает светлую тему, и одинаково же (но
   тёмными) у того, чья предпочитает тёмную. Требование владельца о явном
   различии семейств не выполнялось ни при какой настройке.

   Теперь умолчание витрины — палитра её профиля, и это её опознавательный
   знак. «Как в системе» остаётся одним из трёх равноправных выборов, а не
   молчаливым умолчанием. Поведение обратимо: `seo.theme_follows_system: true`
   в пакете возвращает прежнее. */
{системная_схема}

*, *::before, *::after {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  /* Базовый кегль референсов — 14px: плотнее строка, больше контента
     на первом экране. */
  font-size: 14px;
  line-height: 1.55;
  overflow-x: hidden;
}}
img, svg {{ max-width: 100%; height: auto; display: block; }}
a {{ color: var(--link, var(--accent)); text-decoration: none; }}
a:hover, a:focus-visible {{ text-decoration: underline; }}
/* Ссылка внутри текста подчёркивается всегда, а не только под указателем.
   Без подчёркивания она отличается от окружающего текста одним лишь цветом, а
   это прямо запрещено критерием 1.4.1: зритель, не различающий цвета, ссылки
   не видит вовсе. Поймано на боевых данных — на фикстуре таких абзацев не
   было, и проверка молчала.
   Навигация, фасеты и карточки под правило не подпадают намеренно: они
   различимы положением и формой, а не цветом, и подчёркивание там только
   зашумило бы список. */
p a, dd a, .lede a, li > a:not([class]) {{ text-decoration: underline;
  text-underline-offset: 0.2em; }}
.site-nav a, .site-footer ul a, footer ul a {{ text-decoration: none; }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
h1, h2, h3 {{ line-height: 1.2; margin: 0 0 .5em; overflow-wrap: anywhere; }}
/* H1 референса — 18px/600. Прежние 36px/700 съедали первый экран
   и делали страницу похожей на документ, а не на витрину. */
/* Заголовки не растут вместе с окном: у референса кегль один и тот же
   на 390 и на 1920, а наш h1 доходил до 22px и делал страницу
   похожей на документ, а не на витрину. */
h1 {{ font-size: var(--h1); font-weight: 600; }}
h2 {{ font-size: var(--h2); font-weight: 600; }}
p {{ margin: 0 0 1em; overflow-wrap: anywhere; }}
.container {{ width: 100%; max-width: var(--container); margin: 0 auto; padding: 0 16px; }}
.visually-hidden {{
  position: absolute; width: 1px; height: 1px; margin: -1px;
  clip-path: inset(50%); overflow: hidden; white-space: nowrap;
}}
/* Ссылка «перейти к содержимому» обязана появляться при фокусе.
   Она первая на пути клавиатуры, и до сих пор оставалась высотой в один
   пиксель даже под фокусом: пользователь получал остановку, которой не видит,
   и не понимал, куда попал и что нажимать. Обход клавиатурой это и показал —
   цель высотой 1 px при минимуме 24 по критерию 2.5.8.
   Правило написано на `:focus-visible`, а не на `:focus`: мышью её открывать
   незачем, она нужна ровно тому, кто идёт клавишами. */
a.visually-hidden:focus-visible {{
  position: fixed; top: 8px; left: 8px; z-index: 100;
  width: auto; height: auto; margin: 0; clip-path: none; overflow: visible;
  padding: 10px 16px; min-height: 24px;
  background: var(--accent); color: var(--accent-text);
  border-radius: var(--radius); text-decoration: none;
}}

/* --- шапка ------------------------------------------------------------- */
.site-header {{
  position: sticky; top: 0; z-index: 20;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}}
.header-row {{
  display: flex; align-items: center; gap: 12px;
  min-height: 60px; flex-wrap: wrap; padding: 8px 16px;
  max-width: var(--container); margin: 0 auto;
}}
.brand {{ display: flex; align-items: baseline; gap: 8px; font-weight: 700; color: var(--text); }}
.brand__mark {{
  display: inline-grid; place-items: center;
  width: 30px; height: 30px; border-radius: 8px;
  background: var(--accent); color: var(--accent-text);
  font-size: .85rem; letter-spacing: .02em;
}}
.brand__name {{ font-size: 1.05rem; }}
.nav-toggle {{
  margin-left: auto; background: var(--surface-alt); color: var(--text);
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 8px 12px; font: inherit; cursor: pointer;
}}
.site-nav {{ width: 100%; display: none; }}
.site-nav[data-open="true"] {{ display: block; }}
.site-nav ul {{ list-style: none; margin: 0; padding: 0 0 8px; display: flex; flex-wrap: wrap; gap: 4px; }}
.site-nav a {{
  display: block; padding: 8px 12px; border-radius: var(--radius);
  color: var(--text); font-size: .95rem;
}}
.site-nav a[aria-current="page"] {{ background: var(--accent); color: var(--accent-text); }}
.site-nav a:hover {{ background: var(--surface-alt); text-decoration: none; }}
.header-search {{ width: 100%; display: flex; gap: 8px; padding-bottom: 8px; }}
.header-search input {{
  flex: 1 1 auto; min-width: 0; padding: 9px 12px;
  background: var(--bg); color: var(--text);
  border: 1px solid var(--border); border-radius: var(--radius); font: inherit;
}}
.header-search button {{
  flex: 0 0 auto; padding: 9px 16px; border: 0; border-radius: var(--radius);
  background: var(--accent); color: var(--accent-text); font: inherit; cursor: pointer;
}}

/* --- уведомление стенда ------------------------------------------------- */
.preview-banner {{
  background: var(--surface-alt); border-bottom: 1px solid var(--border);
  color: var(--muted); font-size: .82rem;
}}
.preview-banner p {{ margin: 0; padding: 7px 16px; max-width: var(--container); margin: 0 auto; }}
.preview-banner strong {{ color: var(--text); }}

/* --- общие блоки -------------------------------------------------------- */
main {{ padding: var(--pad) 0 40px; }}
.breadcrumbs {{ font-size: .82rem; color: var(--muted); margin-bottom: 14px; }}
.breadcrumbs ol {{ list-style: none; display: flex; flex-wrap: wrap; gap: 6px; margin: 0; padding: 0; }}
.breadcrumbs li::after {{ content: "/"; margin-left: 6px; color: var(--border); }}
.breadcrumbs li:last-child::after {{ content: ""; }}
.section {{ margin-bottom: 34px; }}
.section__head {{ display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }}
.section__head h2 {{ margin: 0; }}
.section__more {{ font-size: .85rem; }}
.lede {{ color: var(--muted); max-width: 70ch; }}
.count {{ color: var(--muted); font-size: .85rem; }}

/* --- герой -------------------------------------------------------------- */
.hero {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: var(--pad); margin-bottom: 26px;
}}
.hero h1 {{ margin-top: 0; }}
.hero--editorial {{ border-left: 4px solid var(--accent); }}
.hero--timeline {{ border-top: 3px solid var(--accent); }}
.hero--facets {{ background: var(--surface-alt); }}

/* --- сетка карточек ------------------------------------------------------ */
.grid {{
  display: grid; gap: var(--gap);
  grid-template-columns: repeat(var(--cols), minmax(0, 1fr));
}}
.card {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); overflow: hidden;
  display: flex; flex-direction: column;
}}
.card:hover {{ border-color: var(--accent); }}
.card__poster {{ position: relative; aspect-ratio: var(--card-ratio); background: var(--surface-alt);
  display: block; overflow: hidden; }}
/* Заглушка постера. Лежит под изображением и видна только тогда, когда
   изображения нет: постеры отдаёт внешний хост поставщика, и часть их не
   приходит. Пустой серый прямоугольник читается как поломка, буква — как
   намеренно занятое место. */
.card__poster-empty {{ position: absolute; inset: 0; display: flex;
  align-items: center; justify-content: center;
  font-size: 2.2rem; font-weight: 700; color: var(--muted);
  background: var(--surface-alt); }}
.card__poster img {{ position: relative; width: 100%; height: 100%;
  object-fit: cover; display: block; }}
.card__poster img {{ width: 100%; height: 100%; object-fit: cover; }}
/* Верхняя карусель.

   Прокручивается сама по себе — колесом, свайпом и клавиатурой, — а стрелки
   лишь удобство. Поэтому при выключенном JavaScript полка остаётся рабочей.

   Ширина карточки задана в долях видимой области, а не в пикселях: на широком
   экране помещается шесть, на телефоне — две с половиной, и обрезанная
   половинка подсказывает, что список продолжается. Кадр постера
   зафиксирован через aspect-ratio, поэтому подгрузка картинки не сдвигает
   вёрстку. */
.section--rail {{ overflow: hidden; }}
.rail {{
  display: grid; grid-auto-flow: column;
  grid-auto-columns: calc((100% - 5 * 12px) / 6);
  gap: 12px; margin: 0; padding: 0 0 6px; list-style: none;
  overflow-x: auto; overscroll-behavior-x: contain;
  scroll-snap-type: x mandatory; scrollbar-width: thin;
}}
.rail:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 3px; }}
.rail__item {{ scroll-snap-align: start; min-width: 0; }}
.rail__link {{ display: flex; flex-direction: column; gap: 6px;
  color: var(--text); text-decoration: none; }}
.rail__link:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 3px; }}
.rail__poster {{ position: relative; display: block; aspect-ratio: var(--card-ratio);
  background: var(--surface-alt); border-radius: var(--radius); overflow: hidden; }}
.rail__poster img {{ position: relative; width: 100%; height: 100%;
  object-fit: cover; display: block; }}
/* Заглушка постера карусели. Лежит под изображением и видна, когда его нет. */
.rail__poster-empty {{ position: absolute; inset: 0; display: flex;
  align-items: center; justify-content: center;
  font-size: 1.8rem; font-weight: 700; color: var(--muted);
  background: var(--surface-alt); }}
/* Названию позволено занять столько строк, сколько ему нужно.
   Прежде здесь стоял зажим в две строки. При обычном размере шрифта он ничего
   не резал, и потому выглядел безобидно, но зажим считает строки, а не текст:
   при увеличении шрифта до 200 % в те же две строки помещается вдвое меньше
   знаков, и часть названия, которую зритель только что видел, исчезает. Это
   потеря содержимого от изменения размера текста — то самое, что запрещает
   критерий 1.4.4.
   Ряд от этого не разъезжается: постеры выровнены сверху, растёт только высота
   строки заголовков, и то лишь когда шрифт увеличен. В сетке каталога
   названия и так растут свободно — теперь ряды ведут себя так же. */
.rail__title {{ font-size: .86rem; line-height: 1.3; overflow-wrap: anywhere; }}
.rail__link:hover .rail__title {{ color: var(--accent); }}
.rail__meta {{ color: var(--muted); font-size: .74rem; }}
.rail__rating {{ position: absolute; left: 6px; bottom: 6px; display: inline-flex;
  align-items: baseline; gap: 4px; padding: 2px 6px; border-radius: var(--radius);
  background: rgba(0, 0, 0, .78); }}
.rail__rating-source {{ color: #cfcfcf; font-size: .66rem; }}
.rail__rating-value {{ color: #fff; font-size: .78rem; font-weight: 600;
  font-variant-numeric: tabular-nums; }}
.rail__nav {{ display: flex; gap: 6px; }}
.rail__arrow {{ background: var(--surface-alt); color: var(--text);
  border: 1px solid var(--border); border-radius: var(--radius);
  width: 30px; height: 28px; font-size: 1rem; line-height: 1; cursor: pointer; }}
.rail__arrow:hover {{ border-color: var(--accent); color: var(--accent); }}
.rail__arrow:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}

@media (max-width: 1100px) {{
  .rail {{ grid-auto-columns: calc((100% - 3 * 12px) / 4); }}
}}
@media (max-width: 760px) {{
  /* Две с половиной карточки: половина показывает, что полка продолжается. */
  .rail {{ grid-auto-columns: calc((100% - 2 * 10px) / 2.5); gap: 10px; }}
  .rail__nav {{ display: none; }}
}}

/* Оценки. Прежде на эти классы не было ни одного правила: разметка
   выводилась, но подпись и число шли подряд без промежутка и терялись. */
.ratings {{ display: flex; flex-wrap: wrap; gap: 8px; list-style: none;
  margin: 0 0 12px; padding: 0; }}
.rating {{ display: inline-flex; align-items: baseline; gap: 6px;
  background: var(--surface-alt); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 4px 9px; }}
.rating__source {{ color: var(--muted); font-size: .78rem; }}
.rating__value {{ color: var(--text); font-weight: 600; font-variant-numeric: tabular-nums; }}

/* Оценка на обложке: тёмная подложка под числом, чтобы оно читалось на любом
   кадре, а не только на тёмном. */
/* Две оценки ведут себя как одна группа: позиционируется она, а не каждая
   оценка по отдельности. Иначе абсолютно спозиционированные подписи легли бы
   одна на другую в том же углу обложки. */
.card__ratings {{ position: absolute; left: 6px; bottom: 6px; display: flex;
  flex-wrap: wrap; gap: 4px; max-width: calc(100% - 12px); }}
.card__rating {{ position: absolute; left: 6px; bottom: 6px; display: inline-flex;
  align-items: baseline; gap: 4px; padding: 2px 6px; border-radius: var(--radius);
  background: rgba(0, 0, 0, .78); }}
.card__ratings .card__rating {{ position: static; left: auto; bottom: auto; }}
.card__rating-source {{ color: #cfcfcf; font-size: .66rem; }}
.card__rating-value {{ color: #fff; font-size: .78rem; font-weight: 600;
  font-variant-numeric: tabular-nums; }}

.card__badge {{
  position: absolute; top: 6px; left: 6px;
  background: var(--bg); color: var(--muted);
  border: 1px solid var(--border); border-radius: 6px;
  font-size: .65rem; letter-spacing: .04em; padding: 2px 6px; text-transform: uppercase;
}}
.card__seasons {{
  position: absolute; right: 6px; bottom: 6px;
  background: var(--accent); color: var(--accent-text);
  border-radius: 6px; font-size: .68rem; padding: 2px 6px;
}}
.card__body {{ padding: var(--card-pad); display: flex; flex-direction: column; gap: 4px; }}
.card__title {{ font-size: .92rem; font-weight: 600; color: var(--text); overflow-wrap: anywhere; }}
.card__meta {{ font-size: .76rem; color: var(--muted); }}

/* --- фасеты и сортировка -------------------------------------------------- */
.listing {{ display: block; }}
.facets {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: var(--card-pad); margin-bottom: 18px;
  /* Две колонки уже на телефоне: пять полей в столбик уводят первую карточку
     на второй экран, и раздел выглядит пустым при полусотне записей. */
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px;
  align-items: end;
}}
.facets h2 {{ font-size: .95rem; margin: 0; grid-column: 1 / -1; }}
.facets fieldset {{ border: 0; margin: 0; padding: 0; min-width: 0; }}
/* Значения фасета — ссылки на разделы, а не пункты списка. Оформление
   отличает их от текста: без него перечень читается как подпись, и по нему
   никто не нажимает. Цель не меньше 24 px по высоте — критерий 2.5.8. */
.facet__list {{ list-style: none; margin: 6px 0 0; padding: 0; display: flex;
  flex-wrap: wrap; gap: 6px; }}
.facet__chip, .facet__more {{ display: inline-flex; align-items: center;
  min-height: 44px; padding: 8px 12px; border-radius: var(--radius);
  background: var(--surface-alt); color: var(--text); text-decoration: none;
  font-size: .82rem; line-height: 1.2; }}
.facet__chip:hover, .facet__more:hover {{ background: var(--accent);
  color: var(--accent-text); }}
.facet__more {{ font-weight: 600; }}
/* Разрыв в пагинации — не ссылка: он не должен выглядеть нажимаемым. */
.pagination__gap {{ padding: 3px 6px; color: var(--muted); user-select: none; }}
/* Выбор темы. Цели не меньше 44 px по высоте: критерий 2.5.5 и требование
   задания. Нажатое состояние показано не только цветом — цвет один не
   различает состояние для тех, кто его не видит. */
.theme-switch {{ display: inline-flex; gap: 2px; margin-left: 8px;
  border: 1px solid var(--border); border-radius: var(--radius); padding: 2px; }}
.theme-switch button {{ min-height: 44px; min-width: 44px; padding: 4px 10px;
  border: 0; border-radius: calc(var(--radius) - 2px); background: transparent;
  color: var(--muted); font: inherit; font-size: .78rem; cursor: pointer; }}
.theme-switch button[aria-pressed="true"] {{ background: var(--accent);
  color: var(--accent-text); font-weight: 700; }}
.theme-switch button:hover {{ color: var(--text); }}
/* Кадр плеера резервирует место до подключения: иначе включение сдвинет всю
   раскладку. Размер задан пропорцией, а не высотой в пикселях. */
.player__frame {{ position: relative; aspect-ratio: 16 / 9; width: 100%;
  background: var(--surface-alt); border-radius: var(--radius);
  display: flex; align-items: center; justify-content: center; }}
.player__frame video-player {{ display: block; width: 100%; height: 100%; }}
/* Запасной текст читается тогда, когда его показали. Прежде он был скрыт
   всегда, и на его месте зритель видел пустой прямоугольник. */
.player__fallback {{ margin: 0; padding: 16px 20px; max-width: 46ch;
  text-align: center; color: var(--text); font-size: .95rem; line-height: 1.5; }}
.player__frame[data-player-state="unavailable"],
.player__frame[data-player-state="error"] {{ background: var(--surface); }}
.facets legend {{ font-size: .78rem; color: var(--muted); padding: 0 0 4px; }}
.facets select, .facets input {{
  width: 100%; padding: 7px 10px; font: inherit;
  background: var(--bg); color: var(--text);
  border: 1px solid var(--border); border-radius: var(--radius);
}}
.facets__reset {{
  width: 100%; padding: 8px 10px; font: inherit; cursor: pointer;
  background: var(--surface-alt); color: var(--text);
  border: 1px solid var(--border); border-radius: var(--radius);
}}
.chips {{ list-style: none; display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 14px; padding: 0; }}
.chips a {{
  display: inline-block; padding: 5px 11px; font-size: .82rem;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 999px; color: var(--text);
}}
.chips a:hover {{ border-color: var(--accent); text-decoration: none; }}
.chips .chips__count {{ color: var(--muted); font-size: .72rem; margin-left: 4px; }}

/* --- пагинация ------------------------------------------------------------ */
.pagination {{ margin-top: 22px; }}
.pagination ul {{ list-style: none; display: flex; flex-wrap: wrap; gap: 6px; margin: 0; padding: 0; }}
.pagination a, .pagination span {{
  display: block; min-width: 38px; text-align: center;
  padding: 7px 10px; border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--text);
}}
.pagination [aria-current="page"] {{ background: var(--accent); color: var(--accent-text); border-color: var(--accent); }}

/* --- страница произведения -------------------------------------------------- */
.title-head {{ display: grid; gap: var(--gap); margin-bottom: 26px; }}
.title-head__poster {{ max-width: 260px; }}
.title-head__poster img {{ border-radius: var(--radius); border: 1px solid var(--border); }}
.facts {{ margin: 0; display: grid; grid-template-columns: max-content 1fr; gap: 4px 14px; font-size: .9rem; }}
.facts dt {{ color: var(--muted); }}
.facts dd {{ margin: 0; overflow-wrap: anywhere; }}
.player {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: var(--pad); margin-bottom: 26px;
}}
.player__frame {{
  aspect-ratio: 16 / 9; display: grid; place-items: center; text-align: center;
  background: var(--surface-alt); border: 1px dashed var(--border);
  border-radius: var(--radius); padding: 16px; color: var(--muted);
}}
.seasons {{ margin-bottom: 26px; }}
.season {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); margin-bottom: 10px;
}}
.season > summary {{ cursor: pointer; padding: 11px 14px; font-weight: 600; }}
.season ol {{ list-style: none; margin: 0; padding: 0 14px 12px; }}
.episode {{
  display: flex; justify-content: space-between; gap: 12px;
  padding: 7px 0; border-top: 1px solid var(--border); font-size: .9rem;
}}
.episode span:last-child {{ color: var(--muted); flex: 0 0 auto; }}
.comments {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: var(--pad);
}}
.comments__note {{ color: var(--muted); font-size: .88rem; }}
.comments form {{ display: grid; gap: 8px; max-width: 46rem; }}
.comments textarea {{
  width: 100%; min-height: 90px; padding: 10px; font: inherit;
  background: var(--bg); color: var(--text);
  border: 1px solid var(--border); border-radius: var(--radius);
}}
.comments button {{
  justify-self: start; padding: 9px 16px; font: inherit;
  background: var(--surface-alt); color: var(--muted);
  border: 1px solid var(--border); border-radius: var(--radius);
}}

/* --- пусто и ошибки --------------------------------------------------------- */
.empty {{
  background: var(--surface); border: 1px dashed var(--border);
  border-radius: var(--radius); padding: var(--pad); color: var(--muted);
}}

/* --- подвал ------------------------------------------------------------------ */
.site-footer {{
  border-top: 1px solid var(--border); background: var(--surface);
  padding: 24px 0; color: var(--muted); font-size: .85rem;
}}
.site-footer ul {{ list-style: none; display: flex; flex-wrap: wrap; gap: 14px; margin: 0 0 10px; padding: 0; }}
.site-footer p {{ margin: 0 0 .5em; max-width: 80ch; }}

/* --- планшет ------------------------------------------------------------------ */
@media (min-width: 640px) {{
  :root {{ --cols: {cols['tablet']}; }}
  .header-search {{ width: auto; flex: 1 1 240px; padding-bottom: 0; order: 0; }}
  .nav-toggle {{ display: none; }}
  .site-nav {{ display: block; width: 100%; }}
  .title-head {{ grid-template-columns: 260px minmax(0, 1fr); }}
  .facets--row {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
}}

/* --- десктоп -------------------------------------------------------------------- */
@media (min-width: 1024px) {{
  :root {{ --cols: {cols['desktop']}; }}
  .site-nav {{ width: auto; flex: 1 1 auto; min-width: 0; }}
  .site-nav ul {{ padding: 0; flex-wrap: nowrap; overflow-x: auto; }}
  .site-nav a {{ white-space: nowrap; }}
  .header-search {{ flex: 0 1 300px; }}
  .facets--row {{ grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }}
  /* В сайдбаре ширины на две колонки нет: поля возвращаются в столбик. */
  {'.facets:not(.facets--row) { grid-template-columns: minmax(0, 1fr); }' if sidebar else ''}
  {'.listing { display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: var(--gap); align-items: start; }' if sidebar else ''}
  {'.facets { position: sticky; top: 78px; }' if sidebar else ''}
}}

/* Пальцевые цели на телефоне.
   Замер на 390 px показал 33 цели ниже 44 px: пункты меню и подвала высотой
   15 px, страницы пагинации 38 px, фасетные списки 34 px. По WCAG 2.2 AA
   (SC 2.5.8, порог 24 px) вёрстка проходила за счёт исключения по интервалу —
   и это проверено отдельно, — но пальцем в ссылку высотой пятнадцать пикселей
   попадают мимо независимо от того, что засчитывает критерий.

   Правило ограничено телефоном намеренно: на десктопе указатель точный, и
   строки меню высотой в палец там выглядели бы разреженной таблицей. Поэтому
   раскладка широких экранов этим блоком не затрагивается вовсе. */
@media (max-width: 767px) {{
  .site-nav a, .site-footer ul a, .pagination a, .pagination span,
  .brand, .nav-toggle, .facets__reset, .header-search button {{
    min-height: 44px; display: flex; align-items: center; justify-content: center;
  }}
  .facets select, .header-search input {{ min-height: 44px; }}
  /* Ширина не меньше высоты: подпись «Годы» укладывалась в 31 px, и цель
     оставалась узкой полосой при достаточной высоте. */
  .pagination a, .pagination span, .site-nav a, .site-footer ul a {{ min-width: 44px; }}

  /* Кегль поля не ниже 16 px. Это не критерий WCAG, а защита от поведения
     iOS Safari: при фокусе в поле с меньшим кеглем он зумит страницу и
     оставляет зрителя в увеличенной раскладке без очевидного пути назад.
     Замер показал 14 px во всех девяти полях телефона.

     Селекторы повторяют классы исходных правил не для красоты: `font: inherit`
     у `.header-search input` — правило с классом, и объявление на голом
     `input` ему проигрывает по специфичности, сколько его ни пиши. */
  .header-search input, .header-search button,
  .facets select, .facets input,
  input, select, textarea {{ font-size: 16px; }}
}}

@media (prefers-reduced-motion: reduce) {{
  * {{ animation: none !important; transition: none !important; }}
}}

/* профиль: hero={hero}, фасеты={'сбоку' if sidebar else 'в шапке раздела'} */
"""


def stylesheet(profile: dict, *, declared_theme: str | None = None) -> str:
    """Таблица стилей витрины вместе с правилами второй палитры.

    Вторая палитра приклеивается в конец, а не подмешивается в `:root`: правила
    ниже по файлу перекрывают верхние, и порядок здесь — часть смысла.

    `declared_theme` проходит насквозь: объявленная в манифесте тема сдвигает
    поверхность палитры, и разделение функции на базовую и публичную этого
    менять не должно. Слияние двух линий здесь и состояло в том, чтобы не
    выбирать между разделением и параметром — обе правки нужны.
    """
    return (_stylesheet_base(profile, declared_theme=declared_theme)
            + alt_blocks(profile, declared_theme=declared_theme))
