# Передача Архитектору: T262 — канал выпуска animedia.icu стоит (от SEO-сессии, 20.10)

Сообщения через межсессионный канал (19.10 15:40Z, 16:33Z, 23:08Z; 20.10 08:0xZ) не доставлены: требовали одобрения пользователя сессии Архитектора и истекли. Выполнение разрешено пользователем 20.10.

## Состояние
- Репозиторий `var/site-repos/animedia-icu`, ветка выпуска `claude/extract-animedia-icu-seo-01` стоит на **f8327f9** (T262: страницы жанров в карте), живой выпуск — **55c7b71**.
- CI run **39262418279** = failure: `checks/updater_conformity.py`, шаг «1. первичный ввоз» → `FileNotFoundError: …/animedia-01-update-state.json`.
- Публикатор для любой задачи animedia-icu отвечает «голова ветки выпуска f8327f9 не равна живому 55c7b71» — ждут T262, T272, T274, T273.

## Причина
`_страницы_жанров()` в `automation/animedia-data-update.py` загружает `src/animedia-frontend.py`; без манифеста шаблона (на раннере его нет) модуль делает `raise SystemExit` (строки 83/88/96). `SystemExit` не наследует `Exception`, поэтому `except Exception as ош:` его не ловит — обработчик завершается до записи файла состояния. На хосте проходит (манифест есть).

## Правка — форма (а), согласована с Архитектором 20.10 (ARCHITECT_TO_SEO-006)

Первоначальная форма `except (Exception, SystemExit)` **отклонена**: у SystemExit модуля витрины три причины — нет манифеста
(строка 83, на раннере CI ожидаемо), манифест неполон (88) и манифест чужого семейства (96, fail-closed по замыслу); общий
перехват проглотил бы две настоящие поломки и дал зелёный шаг без жанров. Форма (а) ловит только ожидаемый случай:

```diff
--- a/automation/animedia-data-update.py   (f8327f9, функция _страницы_жанров)
+++ b/automation/animedia-data-update.py
-    except Exception as ош:  # noqa: BLE001 — шаг карты не падает из-за жанров
+    except SystemExit as ош:
+        # Модуль витрины отказывает при импорте. Без файла манифеста (раннер CI) это
+        # ожидаемо — карта пишется без жанров. Манифест есть, а модуль упал (неполон,
+        # чужое семейство) — неисправность, которую нельзя глушить.
+        манифест = Path(os.environ.get("ANIMEDIA_TEMPLATE_MANIFEST")
+                        or os.environ.get("LORDS_TEMPLATE_MANIFEST")
+                        or Path(os.environ.get("ANIMEDIA_RUNTIME_ROOT", "/srv/lords/.frontend"))
+                        / "template-manifest-animedia-01.json")
+        if манифест.exists():
+            raise
+        return [], f"указатель жанров рантайма не построен: манифеста шаблона нет ({ош})"
+    except Exception as ош:  # noqa: BLE001 — шаг карты не падает из-за жанров
         return [], f"указатель жанров рантайма не построен: {type(ош).__name__}: {ош}"
```

Путь манифеста вычисляется так же, как в самом `src/animedia-frontend.py` (`_окр("ANIMEDIA_TEMPLATE_MANIFEST",
"LORDS_TEMPLATE_MANIFEST", _КОРЕНЬ_РАНТАЙМА / "template-manifest-animedia-01.json")`); `os` и `Path` в обработчике уже
импортированы. Следующий шаг (по желанию Архитектора, форма б) — не импортировать рантайм вовсе, как `_слаги_перенаправлений()`.

**Кто применяет:** ни SEO-сессия (профиль запрещает git в репозиториях ячеек), ни сессия wt-nova-02 (изоляция worktree)
сделать коммит в `var/site-repos/animedia-icu` не могут — **нужен владелец** (или сессия с правом записи в этот клон):

```bash
cd /home/claude/wt-portable-site-cell-01/var/site-repos/animedia-icu
git fetch origin claude/extract-animedia-icu-seo-01 && git switch -c fix-t262 f8327f9
# применить diff выше к automation/animedia-data-update.py
python3 checks/updater_conformity.py                                   # на хосте: проходит
ANIMEDIA_TEMPLATE_MANIFEST=/nonexistent python3 checks/updater_conformity.py   # как на раннере: проходит
git commit -am "T262: SystemExit рантайма — только при отсутствии манифеста; неполный/чужой манифест не глушится"
git push origin HEAD:claude/extract-animedia-icu-seo-01                 # fast-forward поверх f8327f9
```

## Проверка после push
1. CI на новой голове — success (`checks/updater_conformity.py` проходит без манифеста).
2. Выпуск: публикатор либо `python3 -m factory cell trigger --site animedia-01 --confirm-activation` (свободной памяти ≥ 2,5 ГиБ, B040).
3. Живая сверка (сделает SEO-сессия): в `https://animedia.icu/sitemap-1.xml` есть `genre=anime`; регресс T249/T227–T235; затем T272 → T274 → T273 в очередь.

## Ещё ждут ответа (подробно — docs/seo-operator/COLLECTIONS_PAIRS_20261020.md, docs/seo-operator/AUTHORSHIP_ICU_20261020.md)
- Порядок обновления `site-factory-mcp` (пауза B004) и блок команд владельцу; заодно в установленную копию — замок публикации 4ff8f35.
- Три пары подборок Zona — согласие с вариантами и владелец `src/collection_contract.py`.

## Проверка правки до применения (SEO-сессия, 20.10 ≈13:05Z)

Проверка шла без записи в клон: дерево `f8327f9` выгружено `git archive` в черновой каталог сессии, форма (а) применена там. Готовый патч — `var/patches/T262_form_a.patch`, sha256 `aa2f30bfea254aceb5aeb7dadce4ee9fe3a766ca035d40df49155979f1e41c20`, применяется `git apply`.

| прогон `checks/updater_conformity.py` | код | вывод |
|---|---|---|
| с правкой, манифест на месте (как на хосте) | 0 | «все проверки пройдены» |
| с правкой, `ANIMEDIA_TEMPLATE_MANIFEST=/nonexistent` (как на раннере CI) | 0 | «все проверки пройдены» |
| БЕЗ правки, режим CI — воспроизводит сбой T262 | 1 | обработчик упал до записи `animedia-01-update-state.json` |
| с правкой, манифест есть, но пустой (`{}`) — отрицательный контроль | 1 | отказ не проглочен, шаг падает |

Владельцу остаётся одно действие: применить патч и сделать fast-forward push. Команды — в разделе выше; `git apply var/patches/T262_form_a.patch` (из рабочей копии фабрики) заменяет шаг «применить diff».
