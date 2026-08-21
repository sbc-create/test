---
name: site-intake
description: Принять новый site package, провалидировать его и превратить в job очереди. Использовать при поступлении нового сайта или изменении существующего пакета.
allowed-tools: Read, Grep, Glob, Bash(python3 -m factory validate *), Bash(python3 -m factory queue *)
---

# site-intake

1. Пакет кладётся в `sites/<site_id>/package.yaml` вместе с контентом и rights manifest.
2. `python3 -m factory validate --site <site_id>` — схема + семантика.
   Вывод содержит точный список ошибок по полям; пустое обязательное поле — ошибка,
   а не повод подставить умолчание.
3. Разбери блокеры по типам:
   - `BLOCKED_INPUT` — не хватает переданных данных;
   - `BLOCKED_RIGHTS` — нет подтверждения прав/происхождения контента;
   - `BLOCKED_LICENSE` — нет лицензии DLE на домен второго уровня;
   - `BLOCKED_ACCESS` — цель/зона/хост отсутствуют в `inventory/`;
   - `BLOCKED_SECRET` — `secret_ref` не резолвится;
   - `BLOCKED_SEO` — конфликт с матрицей индексируемости.
4. Не «чини» пакет догадками. Добавь недостающее в `docs/INPUT_REQUEST.md`
   (`python3 -m factory input-request`) и верни блокер заказчику.
5. Валидный пакет → `python3 -m factory queue enqueue --site <site_id> --action <action>`.
