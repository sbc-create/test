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


def tokens_of(profile: dict) -> dict:
    merged = dict(DEFAULT_TOKENS)
    merged.update((profile.get("theme") or {}).get("tokens") or {})
    return merged


def layout_of(profile: dict) -> dict:
    merged = dict(DEFAULT_LAYOUT)
    merged.update(profile.get("layout") or {})
    columns = dict(DEFAULT_LAYOUT["columns"])
    columns.update(merged.get("columns") or {})
    merged["columns"] = columns
    return merged


def stylesheet(profile: dict) -> str:
    """Полная таблица стилей сайта. Один файл, без импортов и без внешних ссылок."""
    t = tokens_of(profile)
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
  --font: {t['heading_font']};
}}

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
a {{ color: var(--accent); text-decoration: none; }}
a:hover, a:focus-visible {{ text-decoration: underline; }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
h1, h2, h3 {{ line-height: 1.2; margin: 0 0 .5em; overflow-wrap: anywhere; }}
/* H1 референса — 18px/600. Прежние 36px/700 съедали первый экран
   и делали страницу похожей на документ, а не на витрину. */
/* Заголовки не растут вместе с окном: у референса кегль один и тот же
   на 390 и на 1920, а наш h1 доходил до 22px и делал страницу
   похожей на документ, а не на витрину. */
h1 {{ font-size: 1.125rem; font-weight: 600; }}
h2 {{ font-size: 1.05rem; font-weight: 600; }}
p {{ margin: 0 0 1em; overflow-wrap: anywhere; }}
.container {{ width: 100%; max-width: var(--container); margin: 0 auto; padding: 0 16px; }}
.visually-hidden {{
  position: absolute; width: 1px; height: 1px; margin: -1px;
  clip-path: inset(50%); overflow: hidden; white-space: nowrap;
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
.card__poster {{ position: relative; aspect-ratio: var(--card-ratio); background: var(--surface-alt); }}
.card__poster img {{ width: 100%; height: 100%; object-fit: cover; }}
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
.card__rating {{ position: absolute; left: 6px; bottom: 6px; display: inline-flex;
  align-items: baseline; gap: 4px; padding: 2px 6px; border-radius: var(--radius);
  background: rgba(0, 0, 0, .78); }}
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
.player__status {{
  display: inline-block; margin-top: 8px; padding: 4px 9px;
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .74rem;
  color: var(--text); overflow-wrap: anywhere;
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

@media (prefers-reduced-motion: reduce) {{
  * {{ animation: none !important; transition: none !important; }}
}}

/* профиль: hero={hero}, фасеты={'сбоку' if sidebar else 'в шапке раздела'} */
"""
