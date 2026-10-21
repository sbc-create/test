[//]: # (Точные команды владельцу: применение поправок года к издателю каталога. MOD-102/MOD-109.)

# Применение поправок года: точные команды

Спрашивала линия SEO 21.10: кто, где и когда применяет патч, запускалась ли
проверка сегодня и с каким кодом. Отвечаю числами, затем даю команды целиком.

## Состояние на 21.10

| что | ответ |
| --- | --- |
| патч собирается и прикладывается | да, проверено **сегодня**: `prepare-year-corrections-patch.py --verify` → **код 0** |
| репетиция на установленном издателе с реальными данными | да, **сегодня**: **код 0**, исправлено 14 годов и 2 вида, устаревших поправок 0, шесть записей отрицательного контроля не тронуты, провалов 0 |
| sha256 патча | `e3f78f12e223ed5bc276ad215ccf4397f49a2d312f044faa63aa4138f1f5d085` |
| применён ли патч к `/srv/site-factory/repo` | **НЕТ** |
| кто применяет | **не я и не линия SEO**: ни у одной из наших сессий нет права записи в это дерево. Остаётся владелец |
| видно ли это на витринах | да: снимок `animedia-01` пересобран сегодня 03:15:26Z и несёт прежние годы — `year_source` нет ни у одной из 15 записей |

Состояние «до» снято и приложено: `artifacts/evidence/year-corrections-before-20261021.txt`
(код 1 = «не применено», это ожидаемо до выпуска).

## Команды

Выполняются на **claude-control-01**. Шаг 2 — единственный, который что-то
меняет; шаги 1 и 3 только читают.

```bash
# ---------- 1. ПРОВЕРКА ДО: что установлено и что приложится ----------
cd /srv/site-factory/repo
wc -l factory/lords/nova_publish.py                      # ожидание: 587
grep -c year_corrections factory/lords/nova_publish.py   # ожидание: 0 (правки ещё нет)
ls factory/lords/year_corrections.py 2>&1                # ожидание: нет такого файла
sha256sum factory/lords/nova_publish.py                  # запишите значение: это точка откат

cd /home/claude/wt-nova-publish-memory-02
python3 automation/local/prepare-year-corrections-patch.py --verify
# ожидание: код 0 и строка «патч прикладывается к установленному файлу (--dry-run)»
# отказ здесь означает, что установленный файл изменился: патч надо собрать заново,
# а НЕ подгонять по похожим местам — сборщик сам это скажет

python3 automation/local/year-corrections-verify-live.py --site animedia-01
# ожидание ДО выпуска: код 1, «поправки НЕ применены»

# ---------- 2. ПРИМЕНЕНИЕ: три файла, не один ----------
# 2.1 патч к издателю
cd /srv/site-factory/repo
cp -p factory/lords/nova_publish.py /srv/site-factory/repo/var/backups/nova_publish.py.before-year-corrections
patch -p1 --dry-run -i /home/claude/wt-nova-publish-memory-02/var/patches/year-corrections-nova-publish.patch
patch -p1 -i /home/claude/wt-nova-publish-memory-02/var/patches/year-corrections-nova-publish.patch

# 2.2 новый файл РЯДОМ с издателем (патч ищет его по пути возле себя)
cp -p /home/claude/wt-nova-publish-memory-02/factory/lords/year_corrections.py \
      /srv/site-factory/repo/factory/lords/year_corrections.py

# 2.3 сами поправки (их читает загрузчик от корня дерева издателя)
cp -p /home/claude/wt-nova-publish-memory-02/config/anime-year-corrections.json \
      /srv/site-factory/repo/config/anime-year-corrections.json

# проверка целости до сборки каталога
cd /srv/site-factory/repo
python3 -c "import py_compile; py_compile.compile('factory/lords/nova_publish.py', doraise=True); print('компилируется')"
grep -c year_corrections factory/lords/nova_publish.py   # ожидание: больше 0

# ---------- 3. СБОРКА КАТАЛОГА И ПРОВЕРКА ПОСЛЕ ----------
# 3.1 сначала БЕЗ --apply: план, который ничего не меняет
python3 /srv/site-factory/repo/automation/host/nova-catalog-publish.py \
        --run-id "year-corrections-$(date -u +%Y%m%dT%H%M%SZ)"
# ожидание: прогон завершается без отказа; каталоги витрин ещё не тронуты

# 3.2 применение
python3 /srv/site-factory/repo/automation/host/nova-catalog-publish.py --apply \
        --run-id "year-corrections-$(date -u +%Y%m%dT%H%M%SZ)"

# 3.3 проверка результата: снимок витрины и живая страница
cd /home/claude/wt-nova-publish-memory-02
python3 automation/local/year-corrections-verify-live.py --site animedia-01 --network
python3 automation/local/year-corrections-verify-live.py --site animedia-02
# ожидание ПОСЛЕ выпуска: код 0, «все поправки применены», у 15 записей стоит
# year_source с адресом источника, и на странице ссылка /catalog/?year= ведёт на
# исправленный год, а прежней ссылки на странице НЕТ
```

## Откат

```bash
cp -p /srv/site-factory/repo/var/backups/nova_publish.py.before-year-corrections \
      /srv/site-factory/repo/factory/lords/nova_publish.py
rm -f /srv/site-factory/repo/factory/lords/year_corrections.py
# затем снова шаг 3.2: каталог пересобирается прежним кодом
```

Откат безопасен и без удаления файла поправок: без загрузчика он просто не
читается. Обратное неверно — загрузчик без файла поправок тоже работает: он
печатает `year_corrections_unavailable` в статистику, и год остаётся
поставщицким. Тишины в этом случае не будет.

## Что проверять, чтобы не принять за успех чужое

| признак | ожидание |
| --- | --- |
| `year_corrected` в статистике сборки | **14** |
| `type_corrected` | **2** |
| `year_correction_stale` | **0**. Ненулевое значение означает, что поставщик сменил значение после замера 20.10, и поправка отступила — это не поломка, но перемерить надо |
| `year_corrections_unavailable` | отсутствует. Если есть — файл поправок не доехал, и год остался прежним |
| шесть записей отрицательного контроля | без изменений: `povelitel-demonov-2099`, `shaman-king-2021`, `poschadi-menya-velikiy-gospodin-2`, `iz-odnoy-komnaty-2`, `gintama-9`, `dostuchatsya-do-tebya-4` |
| число записей каталога | не падает. Падение означает, что правка задела отбор, а не год |

## Чего эти команды НЕ делают

Не трогают постоянные данные витрин (режим индексации, редакционные накладки,
статусы публикаций, nginx), не перезапускают службы и не меняют расписания.
Пересборка каталога — штатный суточный шаг, здесь он просто запускается вне
расписания.
