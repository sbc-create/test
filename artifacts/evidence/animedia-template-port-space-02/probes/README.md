# Проверочный экземпляр стадии ANIMEDIA-TEMPLATE-PORT-SPACE-02

Изолированный экземпляр шаблона: свой каталог данных, свой порт, своё
хранилище сообщества. Живые витрины не читаются на запись и не трогаются.

## Как поднять

```bash
V=<любой пустой каталог>/verify
mkdir -p $V/data/site-data $V/releases

# 1. Данные: КОПИЯ снимка, а не сам снимок. Эталон нужен сценариям обновления:
#    они всегда начинаются с него, иначе второй прогон не воспроизводит первый.
cp /srv/lords/.frontend/animedia-02-catalog.json     $V/data/animedia-verify-catalog.json
cp /srv/lords/.frontend/animedia-02-details.json     $V/data/animedia-verify-details.json
cp /srv/lords/.frontend/animedia-02-ratings-top.json $V/data/animedia-verify-ratings-top.json
cp $V/data/animedia-verify-catalog.json $V/data/animedia-verify-catalog.orig.json
cp $V/data/animedia-verify-details.json $V/data/animedia-verify-details.orig.json
echo '{"events":[]}' > $V/data/animedia-verify-episode-events.json

# 2. Релиз из дерева ветки
python3 automation/host/animedia_release_build.py --out-dir $V/releases \
        --stage ANIMEDIA-TEMPLATE-PORT-SPACE-02-VERIFY

# 3. Манифест витрины и запуск (порт свободный, 9310 в этом прогоне)
#    ANIMEDIA_RUNTIME_ROOT      → $V/data
#    ANIMEDIA_TEMPLATE_MANIFEST → манифест с design_version из TEMPLATE_VERSION.json
#    ANIMEDIA_CATALOG/DETAILS   → снимки выше
#    ANIMEDIA_SITE_DATA_DIR     → $V/data/site-data   (голоса и комментарии)
```

Имя снимка задаёт идентификатор витрины (`animedia-verify`), поэтому реестр
событий, топ и хранилище сообщества этого экземпляра не пересекаются ни с одной
боевой витриной.

`config/player.json` здесь не создаётся: publisher_id — секрет, и подставлять
любой другой нельзя. Витрина поднимается с «плеер без доступа», точка
монтирования плеера и переход между сериями при этом проверяемы.

## Порядок прогона

Порядок значим: сценарии обновления наполняют реестр событий, и лента главной
без него показывает другой блок.

| шаг | что проверяет |
| --- | --- |
| `pytest tests/unit -k animedia` | правила в коде шаблона |
| `update_scenarios.py $V` | доставка, повтор, просадка, возврат, рубеж, подрезка |
| `probe.py` | собранная разметка всех ключевых страниц |
| `community.py` | голос и комментарий через формы витрины |
| `redeploy.py $V` | обновление каталога и обновление кода |
| `after_update.py $V <slug>` | что уцелело после обоих обновлений |
| `browser.mjs` | 1440x900 и 390x844, темы dark и light, настоящие клики |

`browser.mjs` требует `playwright` рядом (`ln -s /home/claude/node_modules`).
