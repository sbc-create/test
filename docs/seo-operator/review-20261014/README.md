# Решение о выпуске — видимые правки, 14.10

Для владельца. По каждой ветке: что меняется, ссылка на изменения, скриншоты «до/после» и проверки. Решение — «выпускать» или «нет» по строке. Выпуск идёт штатно (`factory cell trigger`), затем сверка на живом сайте.

**Как сняты скриншоты.**
- «До» — выпущенный код, «после» — ветка. Обе стороны подняты на одной копии снимка ячейки; данные ячейки только читаются.
- Lords — урезанный снимок (`mini/<repo>`), поэтому вместо постеров буквы-заглушки. Это ограничение стенда, не правки.
- Внешние запросы (плеер, счётчики) обрывались.
- Для AnimeGo, где `player.json` закрыт от сессии, — штатный `checks/stand_root.py`.
- `img/*-live.jpg` — живая страница с оборванными внешними запросами.

## Сводка

| # | Сайт | Ветка | Что меняется | Проверки | Риск |
| --- | --- | --- | --- | --- | --- |
| 1 | lordserials22.info | [`claude/review-lords-t072`](https://github.com/sbc-create/site-lordserials22-info/compare/ff8a4b0...claude/review-lords-t072) f93fa23 | T072 + T076: см. §1 | run.sh 38 PASS / 0 FAIL; новые проверки: прежний код rc=1, ветка rc=0 | низкий |
| 2 | lordfilm47.space | [`claude/review-lords-t054`](https://github.com/sbc-create/site-lordfilm47-space/compare/1112880...claude/review-lords-t054) 7a4a392 | T054: в подвале «Жанры» вместо закрытого от индекса «западный контент» — следующий жанр («криминал») | home_genre_links: прежний rc=1, ветка rc=0; run.sh 38 PASS | низкий |
| 3 | animedia.space | [`claude/review-anime-t071`](https://github.com/sbc-create/site-animedia-space/compare/474c553...claude/review-anime-t071) 5ba45c5 | T071: строка «Следующая серия: N серия — дата (МСК)» на странице тайтла из снимка расписания | next_episode_title: прежний rc=1, ветка rc=0; run.sh rc=0 | низкий |
| 4 | animeg0.site | [`claude/review-anime-t071`](https://github.com/sbc-create/site-animeg0-site/compare/c8bb9ec...claude/review-anime-t071) d7e854e | T071, то же для AnimeGo (класс .ag-next) | next_episode_title на копии живого снимка: PASS «3 серия — 18 октября, вс, 11:00 (МСК)»; CI success 38554685026 | низкий |
| 5 | animedia.icu | [`claude/review-anime-t071`](https://github.com/sbc-create/site-animedia-icu/compare/f7694c4...claude/review-anime-t071) 6547bca | T071, исходный образец | прежний rc=1, ветка rc=0 (13.10) | низкий |
| 6 | Zona ×3 | `claude/review-zona-batchb`: [zonafilm12](https://github.com/sbc-create/site-zonafilm12-site/compare/7ecfdb1...claude/review-zona-batchb) b68e1fd, [zonafilm.cc](https://github.com/sbc-create/site-zonafilm-cc/compare/b5742cb...claude/review-zona-batchb) 5a001ec, [zonafilm.space](https://github.com/sbc-create/site-zonafilm-space/compare/81e717e...claude/review-zona-batchb) 5868d7b | T034, T039 (видимые), T044, T046 (невидимые), см. §6 | zonafilm12 run.sh 41 PASS / 0 FAIL; catalog_scope, catalog_genre_links (97), sitemap_genres_race — rc=0 | средний: см. §6 |
| 7 | lordserial33.biz | [`claude/review-lords-t086`](https://github.com/sbc-create/site-lordserial33-biz/compare/2f2c46f...claude/review-lords-t086) 339e700 | T086: из фактов карточки «Жанр» убрана служебная метка «западный контент» (её раздел noindex; метка стоит и у индийских фильмов) | card_service_genre: прежний rc=1, ветка rc=0; run.sh на урезанном снимке rc=0 | низкий |
| 8 | animedia.icu (animedia.space — T084, следом) | [`claude/review-anime-t083`](https://github.com/sbc-create/site-animedia-icu/compare/f7694c4...claude/review-anime-t083) 2070741 | T083: в ленте «Новые серии» главной — только серии с дорожкой (раньше сверка шла по числу `avail`, и строка вела на «Эта серия пока недоступна» с noindex) | home_fresh_episodes_track: прежний rc=1, ветка rc=0; фоновый прогон VERIFIED 9/9 | низкий |

Все ветки содержат выпущенный код целиком: выпуск не откатит канарейки T074/T075 и правки ночи. T072 перебазирован на ff8a4b0 — без этого выпуск убрал бы канарейку T075.

## 1. lordserials22.info — T072 + T076

**T072.** `/anime/` и `/dorama/` получали title «Каталог: смотреть онлайн — …», H1 «Каталог» и описание «Каталог на …», как `/catalog/`. Три индексируемых раздела с одним title.

| | title | H1 | description |
| --- | --- | --- | --- |
| до | Каталог: смотреть онлайн — Lordserials Animation | Каталог | Каталог на Lordserials Animation: 393 записи каталога — смотреть онлайн. |
| после | Аниме: смотреть онлайн — Lordserials Animation | Аниме | Аниме на Lordserials Animation: 393 записи каталога — смотреть онлайн. |

`/dorama/` — так же, «Дорамы». `/catalog/` не меняется. Число 393 — урезанный стенд; на живом сайте число раздела своё.

**T076** (найдено сегодня на живом сайте):
- было: плашка «section: anime» и кнопка «Сбросить» — внутреннее имя ключа показано как выбранное условие, хотя посетитель ничего не выбирал;
- стало: плашки нет; у остальных Lords разделы вида и так без плашек;
- выбранный год по-прежнему даёт плашку «Год» и «Сбросить» — это тоже проверяется.

| | до | после |
| --- | --- | --- |
| мобильный | ![](img/t072-anime-mobile-before.jpg) | ![](img/t072-anime-mobile-after.jpg) |
| фильтр, компьютер | ![](img/t072-anime-desktop-before-focus.jpg) | ![](img/t072-anime-desktop-after-focus.jpg) |

Полные кадры: `img/t072-{anime,dorama}-{desktop,mobile}-{before,after}.jpg`.

## 2. lordfilm47.space — T054

Подвал главной, колонка «Жанры»: первой стояла ссылка «западный контент». Её раздел закрыт от индекса как служебная метка (T044) — ссылка с каждой страницы вела в noindex. Теперь служебные метки пропускаются, восьмой слот получает «криминал».

| до | после |
| --- | --- |
| ![](img/t054-home-desktop-before-focus.jpg) | ![](img/t054-home-desktop-after-focus.jpg) |

## 3–5. «Следующая серия» — animedia.space, animeg0.site (animedia.icu — образец)

Строка под панелью действий: «Следующая серия: 3 серия — 18 октября, вс, 11:00 (МСК)».
- Берётся из того же снимка расписания, что `/schedule/`.
- Только будущий выход и только у свежего расписания (`stale=false`). Нет события — нет строки.
- В description дата не идёт: сниппет кешируется и устарел бы.
- Основание — аудит 13.10 §11: запросы «<название> дата выхода серий», позиция около 10, а даты на странице не было.

| | до | после |
| --- | --- | --- |
| animedia.space, компьютер | ![](img/t071s-title_ao_asi_2-desktop-before.jpg) | ![](img/t071s-title_ao_asi_2-desktop-after.jpg) |
| animedia.space, строка | — | ![](img/t071s-title_ao_asi_2-desktop-after-focus.jpg) |
| animeg0.site, мобильный | ![](img/t071ag-title_ao_asi_2-mobile-before.jpg) | ![](img/t071ag-title_ao_asi_2-mobile-after.jpg) |
| animeg0.site, строка | — | ![](img/t071ag-title_ao_asi_2-mobile-after-focus.jpg) |

На мобильном строка ниже первого экрана — после характеристик.

## 6. Zona — T034, T039 (видимые), T044, T046

**T039.** На голом `/catalog/` вместо «Результаты в этой выборке» и ссылки «Сбросить» — «Результаты в каталоге», без «Сбросить». Условий нет, сбрасывать нечего.

| до | после |
| --- | --- |
| ![](img/zona12-catalog-desktop-before.jpg) | ![](img/zona12-catalog-desktop-after.jpg) |

**T034.** На голом `/catalog/` — блок «Жанры»: 97 ссылок на разделы жанров (набор тот же, что в карте сайта). Сейчас с `/catalog/` на разделы жанров не ведёт ни одной ссылки.

![](img/zona12-catalog-desktop-after-focus.jpg)

Снимок блока сделан до T077: в нём ещё есть «Азиатский контент», после T077 эта ссылка уходит.

**Замечание к T034 — решить до выпуска.**
- В блоке и в живой карте есть «Азиатский контент» (`?genre=aziatskiykontent`, сейчас 200 и index).
- На Lords та же метка признана служебной и закрыта от индекса (T064). На Zona закрыт только «западный контент» (T044).
- Сделано на той же ветке (T077: zonafilm12 6d67605, zonafilm-cc e31341e, zonafilm-space 6592da4): метка уходит из блока и карты, раздел — noindex, follow. Проверка technical_genre_noindex: прежний код rc=1, правка rc=0 на всех трёх; жанров в блоке и карте на один меньше (97/98/97).
- T077 — не отдельное решение: выпускается с T034 одной веткой.

**Невидимые:**
- T044 — раздел «западный контент» noindex, follow;
- T046 — description главной пересказывает видимый блок. Было «Zona Cinema: фильмы, сериалы и анимация.», стало «… — высокие оценки недели, недавние поступления и каталог с фильтрами по виду, жанру, году и стране.»;
- правки CI;
- `launcher-refuses` (только zonafilm12, b68e1fd) — см. ниже.

### launcher-refuses — причина найдена, проверка усилена, не отключена

- **Причина.** Шаг падал, когда checks/run.sh запускали с `SITE_DATA_DIR` (его требуют проверки на живом снимке). `run.py` берёт каталог и из окружения, поэтому проба «запуск без каталога» каталог получала и не отказывала. Это провал окружения прогона, а не рабочей копии — прежнее объяснение («только в рабочих копиях») было неверным.
- **Правка (b68e1fd)** — только ужесточает шаг:
  - проба идёт без `SITE_DATA_DIR`;
  - отказ обязан называть причину: «каталог данных не задан» в первой пробе, подставленный путь во второй.
- **Мутант** (run.py молча берёт чужой каталог по умолчанию): прежний шаг rc=0 — пропустил бы; новый — rc=1.
- **Итог:** полный run.sh под `SITE_DATA_DIR` — 41 PASS, 0 FAIL.
- Та же проверка в остальных репозиториях — тем же переносом после одобрения.

## CI веток просмотра (14.10 ~11:50Z)

| Репозиторий | Коммит | CI |
| --- | --- | --- |
| site-lordserials22-info | f93fa23 | success, 38554672849 |
| site-lordfilm47-space | 7a4a392 | success, 38554676007 |
| site-animedia-space | 5ba45c5 | success, 38554680009 |
| site-animeg0-site | d7e854e | success, 38554685026 |
| site-animedia-icu | 6547bca | success, 38554733369 |
| site-zonafilm12-site | b68e1fd | success, 38554688311 |
| site-zonafilm-cc | 5a001ec | success, 38554692518 |
| site-zonafilm-space | 5868d7b | success, 38554696141 |

Zona — следующий коммит T077 (zonafilm12 6d67605, zonafilm-cc e31341e, zonafilm-space 6592da4): отправка после полного run.sh, CI допишу.

## 7. lordserial33.biz — T086

Факты карточки тайтла:
- было: «Жанр: триллер · криминал · детектив · западный контент», последняя ссылка ведёт в закрытый от индекса раздел метки;
- стало: только настоящие жанры;
- если метка была единственным «жанром», строки «Жанр» нет.

После одобрения — перенос на остальные Lords.

| до | после |
| --- | --- |
| ![](img/t086-title_cyber_vaar-desktop-before-focus.jpg) | ![](img/t086-title_cyber_vaar-desktop-after-focus.jpg) |
| ![](img/t086-title_magiya_lyubvi_2-desktop-before-focus.jpg) | ![](img/t086-title_magiya_lyubvi_2-desktop-after-focus.jpg) |

## 8. animedia.icu — T083

- **Было.** Лента «Новые серии» на главной сверяла доступность по числу `avail`. Строка могла вести на серию, у которой ещё нет дорожки: страница «Эта серия пока недоступна», noindex.
- **Замеры на живом сайте:**
  - 12:35Z — 2 строки из 100 (Сюнмао Ли, 14 серия; Русалочка Марина, 24 серия);
  - 13:30Z — 1 из 100: 14-я серия к этому времени стала доступна.
- **Стало.** Сверка по перечню доступных номеров — тем же правилом, что у страницы серии (T070) и карты серий (T074). Порядок и прочие строки не меняются.
- **Видимая разница** — только пропажа таких строк. Скриншоты (`img/t083-*`) почти совпадают, потому что недоступные серии сейчас вне первого экрана. Разница доказана проверкой на образце: база показывает строку `/title/bez/season-1/episode-14/` без дорожки, ветка — нет.
- **Фоновый прогон** подготовил правку. Первые два вердикта были INCOMPLETE из-за дефекта самого механизма (в копиях вердикта не было `config/player.json`). Дефект исправлен (d080112), повторный вердикт — VERIFIED 9/9.
