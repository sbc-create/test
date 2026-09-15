# Итоговый отчёт — TEMPLATES-ZONA-ANIMEDIA-OWNER-REVIEW-007

```
FINAL_STATUS                      = BLOCKED
причина                           = доставка пакета в сессию закрыта профилем разрешений
OWNER_REVIEW_ARTIFACT_URL         = — (Artifact и SendUserFile отклонены guard'ом)
ZONA_CONTACT_SHEET                = owner-package/zona-contact-sheet.png
ANIMEDIA_CONTACT_SHEET            = owner-package/animedia-contact-sheet.png
REFERENCE_PAGES_CAPTURED_ZONA     = 4/5 разрешённых маршрутов (пятый отдаёт 404 на самом эталоне)
REFERENCE_PAGES_CAPTURED_ANIMEDIA = 8/8 разрешённых маршрутов
CANDIDATE_PAGES_CAPTURED_ZONA     = 8 архетипов × 3 размера
CANDIDATE_PAGES_CAPTURED_ANIMEDIA = 9 архетипов × 3 размера
TEMPLATE_GAPS_REMAINING           = 2
DATA_GAPS_REMAINING               = 3
ANIMEDIA_DATA_READINESS           = FAIL
CHROMIUM_STATUS                   = PASS
FIREFOX_STATUS                    = PASS
WEBKIT_STATUS                     = PASS
ACCESSIBILITY_STATUS              = PASS (клавиатура, семантика, контраст токенов; axe-core не запускался)
LORDS_SERVED_FINGERPRINT_UNCHANGED= YES
PRODUCTION_MUTATIONS              = 0
SEO_MUTATIONS                     = 0
ANALYTICS_MUTATIONS               = 0
PLAYER_MUTATIONS                  = 0
CONTENT_PIPELINE_MUTATIONS        = 0
ZONA_OWNER_DECISION               = PENDING
ANIMEDIA_OWNER_DECISION           = PENDING
```

## Почему BLOCKED

Материал готов целиком. Закрыт **доступ**: `Artifact` и `SendUserFile` отклонены
профилем разрешений репозитория (`default-deny` на необъявленные инструменты).
Критерий задания сформулирован через возможность владельца открыть сравнения в
Claude Web, поэтому объявлять READY нельзя — это выдало бы готовность материала
за готовность доступа. Разбор и требуемое действие — `delivery-blocker.md`.

## Что сделано сверх предыдущей задачи

* Охват эталонов поднят с 1/1 до **4 маршрутов Zona и 8 Animedia**; маршруты
  внесены в реестр поимённо, без wildcard, только GET, без форм и авторизации.
* Снято **105 кадров кандидатов и прежних версий** и **36 кадров эталонов**;
  собран 51 парный композит «было \| стало» и два contact sheet.
* Прогон в **трёх браузерах** и проверка клавиатуры и семантики.
* Полный применимый набор тестов — и он вскрыл дефект, который суженный прогон
  пропускал (см. ниже).

## Главное, что нашёл полный прогон

Переработанное оформление включалось условием `ВЕРСИЯ in {1.1.0, 1.2.0}`.
Артефакт один на шесть витрин, поэтому выкладка файла ради Animedia молча
сменила бы вид боевой Zona, стоящей на 1.1.0. Мой собственный runbook
предыдущей задачи утверждал обратное. Исправлено: переработка достаётся только
витрине, объявившей 1.2.0; прежнее оформление Zona 1.1.0 восстановлено в файле.
Разбор — `version-gating-finding.md`, поправка внесена в runbook задачи 006.

## Что осталось открытым

**TEMPLATE (2).** Постеры своим адресом — механизм включён `sub_filter`-ом
только в vhost Lords, а nginx эта задача менять запрещает; в шаблоне сделан
переключатель, по умолчанию выключенный. Рецензии, комментарии и
пользовательские списки — компоненты и честные пустые состояния есть, включение
требует источника и аутентификации.

**DATA (3).** Каталог Animedia — срез Zona (3995 из 3999 адресов). Нет времени и
номера серии. Нет КП/IMDb, описаний, студий, source ID и player bindings.
Всё три — на стороне контентного конвейера; ничего не выдумывалось.
