# Откат 02B

## Что изменено в production

| Что | Было | Стало |
| --- | --- | --- |
| `/srv/site-factory/repo` | `64bb55c` (ветка `main`) | `ad6be19` (ветка `deploy/02b`) |
| файлов изменено | — | 4 (сценарий обновления, установщик юнитов, гигиенический тест, документ блокеров) |
| файлов добавлено | — | 34 (модули движка и тесты) |
| релизы витрин | не трогались | не трогались |
| systemd-юниты | не трогались | не трогались |

`render.py`, вёрстка, стили, плеер, SEO — не изменялись.

## Как откатиться

```bash
SHA=$(cat /var/lib/lords-content-refresh/repo-rollback-sha)
cd /srv/site-factory/repo
sudo git checkout --quiet "$SHA"
sudo git rev-parse --short HEAD    # ждём 64bb55c
```

Сценарий обновления вернётся к прежнему виду, ворота перед сборкой исчезнут
вместе с файлом, и цикл снова будет рендерить всегда.

## Быстрое отключение без отката

Если ворота повели себя неверно, но откатывать код нежелательно:

```bash
sudo systemctl edit lords-content-refresh.service
# [Service]
# Environment=LORDS_RENDER_GATE=0
sudo systemctl daemon-reload
```

Ворота выключатся, поведение станет прежним, остальной код останется.

## Откат релизов витрин

Не требуется: релизы не менялись. Если понадобится, точки прежние.

| Витрина | Текущий | Откат |
| --- | --- | --- |
| lords-01 | `55d57e36b76f` | `d4296e961e19` |
| lords-02 | `f57ba6115b78` | `b769f6406158` |
| lords-03 | `e2c5d606bab7` | `3130615ac5ed` |

Откат — переключение символической ссылки, без пересборки и простоя.

## Проверка после отката

```bash
cd /srv/site-factory/repo && git rev-parse --short HEAD
systemctl is-active lords-content-refresh.timer
for h in lordfilm47.space lordserial33.biz 1lordserials1.online; do
  curl -sS -o /dev/null -w "$h %{http_code}\n" "https://$h/"
done
python3 -m factory.lords.refresh_watchdog
```
