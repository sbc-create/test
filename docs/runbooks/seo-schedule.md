# Расписание автономного цикла SEO: установка

Четыре задания заведены по входящему запросу
`HANDOFF-2026-09-05-019-SEO-TO-CORE`. Описания лежат в `deploy/systemd/` и
проверяются тестом `tests/unit/test_join_keys.py::TestРасписаниеSEO`: время,
таймаут и политика повторов сверяются с таблицей запроса, а не переписываются
на память.

| Задание | Срок (МСК) | Таймаут | Ключ идемпотентности |
| --- | --- | --- | --- |
| `seo-measurement-snapshot` | ежедневно 03:10 | 300 с | `report_date` |
| `seo-content-audit` | ежедневно 03:30 | 1800 с | `report_date + domain` |
| `seo-scorecard-weekly` | понедельник 04:00 | 900 с | `iso_week + methodVersion` |
| `seo-scorecard-monthly` | 1-е число 04:30 | 3600 с | `year_month + methodVersion` |

## Что здесь не сделано намеренно

**Юниты не установлены.** Установка требует прав суперпользователя на боевой
машине — это **действие владельца**, а не автоматики. Описания подготовлены и
проверены; команда установки приведена ниже целиком, чтобы её можно было
прочитать до запуска.

**Обёртки командной строки SEO ещё не поставлены.** Запрос 019 прямо говорит,
что `content-audit` и `scorecard` существуют как сценарии, а обёртки
добавляются отдельной задачей SEO. Поэтому каждое задание проверяет наличие
команды **до** запуска и завершается кодом 78 (`EX_CONFIG`) с внятным
сообщением, если её нет. Это лучше молчаливого падения под именем задания:
дежурный видит причину, а не «упало».

## Установка

```bash
# 1. Прочитать описания. Они короткие и объясняют каждое решение.
less deploy/systemd/seo-*.service deploy/systemd/seo-*.timer

# 2. Поставить и перечитать конфигурацию.
sudo install -m 0644 deploy/systemd/seo-*.service deploy/systemd/seo-*.timer \
    /etc/systemd/system/
sudo systemctl daemon-reload

# 3. Включить таймеры (службы включать не надо: их запускает таймер).
sudo systemctl enable --now \
    seo-measurement-snapshot.timer \
    seo-content-audit.timer \
    seo-scorecard-weekly.timer \
    seo-scorecard-monthly.timer

# 4. Проверить, что сроки посчитаны так, как ожидалось.
systemctl list-timers 'seo-*'
```

## Проверка после установки

```bash
# Разовый прогон суточного снимка вручную — до наступления срока.
sudo systemctl start seo-measurement-snapshot.service
journalctl -u seo-measurement-snapshot.service -n 50 --no-pager

# Второй запуск тех же суток обязан записать ноль строк.
sudo systemctl start seo-measurement-snapshot.service
```

Ожидается `STATUS=SUCCESS`, затем `STATUS=NO_OP` и `FACTS_WRITTEN=0`. Если
второй прогон записал строки — идемпотентность нарушена, и это отказ приёмки,
а не мелочь: расписание превратит его в ежедневное дублирование.

## Снятие

```bash
sudo systemctl disable --now seo-*.timer
sudo rm /etc/systemd/system/seo-*.service /etc/systemd/system/seo-*.timer
sudo systemctl daemon-reload
```

Снятие таймеров не трогает данные: задания только читают и пишут собственные
строки, ничего не публикуют и не меняют production.
