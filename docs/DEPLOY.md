# Развёртывание

## Порядок

```bash
python3 -m factory validate --site <id>
python3 -m factory plan     --site <id>                       # mutations применено: 0
python3 -m factory deploy   --site <id> --dry-run             # инфраструктура не меняется
python3 -m factory deploy   --site <id> --environment staging
python3 -m factory verify   --site <id>
```

Production дополнительно требует **всех** условий одновременно:

1. `environment: production` и `production_authorized: true` в манифесте;
2. заполненные `authorized_by` и `authorized_at`;
3. лицензия DLE, покрывающая домен второго уровня (`inventory/dle-licenses.yaml`);
4. цель с `production_capable: true`;
5. зелёный staging QA;
6. явный флаг оператора: `--allow-production`.

Отсутствие любого пункта даёт `BLOCKED_AUTHORIZATION`, `BLOCKED_LICENSE` или
`BLOCKED_ACCESS` **до** первой мутации.

## Что делает деплой

| Шаг | Мутация | Комментарий |
|-----|---------|-------------|
| `prepare_dirs` | да, при первом запуске | `releases/`, `shared/` |
| `backup` | нет для цели, да для данных | архив shared + дамп БД; затем проверка восстановимости |
| `upload_release` | да | `releases/<build_id>`; повтор того же build_id — no-op |
| `health_check` | нет | релиз-кандидат обслуживается до переключения |
| `switch_current` | да | атомарная замена симлинка `current` |
| `post_switch_health` | нет | подтверждение после переключения |
| `prune_releases` | да | хранится `keep_releases` + текущий и предыдущий |

## DNS cutover

Отдельный журналируемый шаг **после** проверки origin, конфигурации, сертификата,
health и готового плана отката. Токен ограничен зоной и типами записей
(`inventory/dns-zones.yaml: scope: zone_records_only`). Фабрика не расширяет список
зон по своей инициативе.

## Проверка перед выкатом

```bash
bash tests/run-all.sh                     # полный прогон с чистого состояния
python3 -m factory knowledge verify       # база знаний не менялась мимо /research-freeze
python3 -m factory blueprint check        # профиль путей DLE заполнен
```
