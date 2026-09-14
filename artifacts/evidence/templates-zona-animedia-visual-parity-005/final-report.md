# Итоговый отчёт — TEMPLATES-ZONA-ANIMEDIA-VISUAL-PARITY-005

```
FINAL_STATUS                     = BLOCKED_REFERENCE
READY_FOR_OWNER_VISUAL_REVIEW    = NO
ZONA_REFERENCE_PARITY_STATUS     = BLOCKED_REFERENCE
ANIMEDIA_REFERENCE_PARITY_STATUS = BLOCKED_REFERENCE
ZONA_OPERATIONAL_RELEASE_STATUS  = PASS   (сохранён из предыдущей задачи)
TEMPLATES_ACCEPTED               = NO
HUMAN_VISUAL_REVIEW_STATUS       = NOT_APPLICABLE_YET
ANIMEDIA_DATA_READINESS          = FAIL
DATA_OWNER_ACTION_REQUIRED       = YES
PRODUCTION_RELEASE_STATUS        = NOT_REQUESTED
PRODUCTION_MUTATIONS             = 0
LORDS_MUTATIONS                  = 0
SEO_MUTATIONS                    = 0
CONTENT_PIPELINE_MUTATIONS       = 0
VIDEO_RUNTIME_MUTATIONS          = 0
FOREIGN_PROCESS_MUTATIONS        = 0
```

`HUMAN_VISUAL_REVIEW_STATUS` не выставлен в `PENDING_OWNER`: показывать владельцу
нечего — нового кандидата нет, парных снимков нет.

## Почему блокер

Оба обязательных оригинала отклоняются guard'ом до сети: «хост не входит в
переданные контракты». Это политика, а не сбой связи:

- `inventory/network-allowlist.yaml` не содержит ни `w140.zona.plus`, ни `amd.online`;
- заголовок файла прямо запрещает агенту дополнять список;
- оба `config/reference-packs/*.json` держат `access.status = blocked_policy` с 2026-09-04;
- D35 (22.08.2026) фиксирует тот же отказ на уровне прокси;
- пакет Zona содержит 0 наблюдений, пакет amd.online — 8, все `verified: "unverified"`.

Задание требует ставить `BLOCKED_REFERENCE`, а не `PASS`, и запрещает угадывать
недоступные страницы и подменять референсы похожими сайтами. Исправлять шаблоны
«на глаз» означало бы объявить паритет с тем, чего никто не измерял.

## Что измерено вместо этого

Дефекты текущих витрин, TEMPLATE отдельно от DATA. Подробности —
`data-vs-template-defects.json`.

| TEMPLATE-дефект | витрина | воспроизведён |
| --- | --- | --- |
| главная Animedia выводит фильмы каталога Zona | оба домена | да |
| 6 из 6 hero-ссылок → hard 404 | оба домена | да |
| 42 ссылки на 12 уникальных тайтлов, три блока — одна выборка | оба домена | да |
| горизонтальное переполнение на 390 px | оба домена | да, **найдено этой задачей** |
| универсальная тёмно-синяя витрина вместо аниме-портала | оба домена | да, паритет непроверяем |
| постоянная левая колонка 246 px на desktop | Zona | да |
| белый фон, serif-типографика | Zona | да, паритет непроверяем |
| три секции главной вместо пяти | Zona | да, состав пяти — из текста задания |
| постеры прямой ссылкой на внешний CDN | все три | да, **найдено этой задачей** |

| DATA-дефект | владелец |
| --- | --- |
| каталог Animedia — не аниме, подан срез Zona | контентный конвейер |
| нет достоверного времени и номера серии | контентный конвейер |
| нет КП/IMDb, описаний, студий, source ID, player bindings | конвейер и провайдер |

## Не воспроизвелось

Постеры Zona (20/20) и Animedia (42/42) загрузились полностью. Дефект **не
объявляется исправленным**: шаблоны не менялись. Зафиксирована причина —
постеры подключены прямой ссылкой на `poster.cdnvideohub.com`, поэтому результат
зависит от сети зрителя.

## Требуемое действие владельца

Одно: внести два хоста в `inventory/network-allowlist.yaml` (только `GET`).
Точные строки и продолжение работы — `deployment-runbook.md`.
