# SCOPE — границы ночной работы

```text
TERMINAL_OWNER=ZONA
TENANT=ZONA
PRODUCT=ZONA_TEMPLATES_AND_SLIDER
WORKTREE=/home/claude/wt-zona-real-slider-01
BRANCH=claude/zona-real-slider-01
EXPECTED_DOMAIN=zonafilm.space
EXPECTED_SERVICE=nova-zona-01.service
```

## Что входило в область

Витрина Zona: слайдер героя, карточки каталога, оценки из собственных данных
витрины, сортировка и заполненность блоков, поиск и фильтры, страницы
произведений, сезонов и эпизодов, заголовки и семантика, маршруты и 404,
адаптивность, доступность, шаблоны витрины, тесты и evidence.

## Что в область не входило и не тронуто

| Область | Состояние |
| --- | --- |
| Animedia | не тронута; отдача сверена побайтово — 14/14 маршрутов на двух версиях |
| Lords | не тронут; отдача сверена побайтово — 14/14 маршрутов |
| Yummy | не тронут; отдельный рантайм `yummy-frontend.py` не открывался на запись |
| общий модуль оценок | не изменён; недостающий контракт описан в `RATINGS_CONTRACT_GAP.md` |
| модуль комментариев | не вызывался и не изменялся |
| SEO / Topvisor | не тронуты |
| DNS, TLS | не тронуты |
| robots, meta robots, canonical, sitemap, индексируемость | не тронуты; `noindex, nofollow` проверен на 18 маршрутах |
| чужие worktree и ветки | не открывались на запись |
| файл юнита `nova-zona-01.service` | не правился; найденный в нём риск описан, но не исправлен — это вне области |

## Production-операции: ни одной

```text
PRODUCTION_MUTATIONS=0
RESTART_PERFORMED=0
DNS_MUTATIONS=0
TLS_MUTATIONS=0
INDEXABILITY_MUTATIONS=0
ANIMEDIA_MUTATIONS=0
LORDS_MUTATIONS=0
YUMMY_MUTATIONS=0
RATINGS_BACKEND_MUTATIONS=0
COMMENTS_MODULE_MUTATIONS=0
PUSH_PERFORMED=0
```

`sudo`, `systemctl`, merge, rebase чужих веток, force-push и работа в
`main`/`master` не выполнялись. Манифест, назначение релиза и символические
ссылки production не менялись. `owner_visual_accepted` и
`production_authorized` не выставлялись.

## Чтение production — было, и только чтение

Читались (без записи):

* `zona-01-catalog.json`, `zona-01-details.json`, `zona-01-popular-weekly.json`,
  `player-zona-01.json` — данные Zona, из них сделана локальная выборка;
* `template-manifest-zona-01.json` и остальные манифесты витрин — чтобы
  сверить объявленные версии оформления;
* `zona-01-frontend.py` — чтобы доказать причину деградации на установленных
  байтах;
* `community_ratings_overlay.py` и его флаги — чтобы описать недостающий
  контракт;
* HTTP боевой витрины на `127.0.0.1:9120` — чтобы измерить её состояние.

## Соседние сессии

Во время работы активны чужие Zona-ветки: `claude/zona-slider-crop-date-01`
(`/home/claude/wt-zona-slider-01`) и `claude/zona-template-finalization-01`
(`/home/claude/wt-zona-finalization-01`, держит витрину на порту 19120). Их
рабочие каталоги не открывались. Локальные стенды этой ночи поднимались на
портах 194xx, боевые 9110–9143 и чужой 19120 не занимались.

## Чего не удалось сделать в этой области

* **Пакеты T001–T050 для Zona не существуют** — ни в этой ветке, ни в других
  ветках Zona. Найдены только в лентах Lords
  (`claude/lords-50-template-factory-01`, `claude/lords-50-factory-t006-t050`),
  а это запрещённая область: копировать оттуда код или оформление нельзя.
  Вместо пересборки чужой фабрики сделан собственный слой шаблонов Zona с
  шестью структурно разными шаблонами (`templates/index.html`). Число
  шаблонов в отчёте названо честное — шесть, а не пятьдесят.
* **Оценки сообщества на Zona не включены** — требуют правки чужого общего
  модуля.
* **Живая проверка после перезапуска не проводилась** — перезапуск запрещён и
  не выполнялся.
