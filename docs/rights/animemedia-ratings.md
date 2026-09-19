# AnimeMedia ratings source — UNVERIFIED_DISABLED

**State:** `ANIMEMEDIA_SOURCE=UNVERIFIED_DISABLED`

## Что это НЕ есть

Домены `animedia.icu` и `animedia.space` — наши витрины Site Factory.
Импортировать рейтинги с них обратно **запрещено**: циклическая provenance и
ложная внешняя оценка.

## Что нужно до включения

Если имеется в виду `amd.online` или иной внешний ресурс:

1. Точный canonical origin
2. Владелец данных
3. Документированный API/feed либо принадлежащий нам upstream
4. Право получать и хранить оценки
5. Правила атрибуции
6. Rate limits
7. Стабильные external IDs
8. Vote-count contract

Порядок допустимых вариантов: owned/allowed upstream → documented API →
HTML parsing только при явном разрешении владельца и отсутствии API.

## Запрещено

* Угадывать домен/поставщика
* Обходить Cloudflare/CAPTCHA/bot protection
* Подменять AnimeMedia на MAL/AniList по догадке
* Использовать наши сайты как внешний источник
* Включать HTML scraper без разрешения
* Копировать визуальный референс (например 9.29)

Отсутствие контракта AnimeMedia **не блокирует** Shikimori.
