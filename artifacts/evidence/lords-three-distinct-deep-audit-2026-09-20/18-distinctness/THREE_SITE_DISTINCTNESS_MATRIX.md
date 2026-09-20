# THREE_SITE_DISTINCTNESS_MATRIX

Generated: 2026-09-20T22:12:59.995022+00:00

## Verdict

- STRUCTURALLY_DISTINCT (block titles/order): **True**
- VISUALLY_DISTINCT (card anatomy / product IA): **False**
- Finding: `TEMPLATE_DISTINCTNESS_INSUFFICIENT`

## Block orders
### lords-01 (lords-cinema-v2)
1. Премьеры недели
2. Фильмы по жанрам
3. Новинки
4. Популярное
5. Подборки
6. Сериалы
7. По жанрам
8. О каталоге
- cards: 58; poster class hits: 59

### lords-02 (lords-series-feed-v2)
1. Продолжающиеся сериалы
2. Новые поступления сериалов
3. Популярное за неделю
4. Подборки
5. Фильмы в каталоге
6. О каталоге
- cards: 43; poster class hits: 1

### lords-03 (lords-curated-v2)
1. Выбор редакции
2. Тематические подборки
3. Что посмотреть
4. Новые поступления
5. Страны и эпохи
6. О каталоге
- cards: 30; poster class hits: 1

## Failure reasons
- All three profiles render primary cards as identical .c.c--poster anatomy (poster grid).
- Passports explicitly defer episode-horizontal (series-feed) and mosaic editorial (curated) cards to later.
- Differentiation today is mainly block titles/order + data-design/profile tokens, not card IA.
- Shared title shell across profiles (passport: cinema title shell shared for now).
