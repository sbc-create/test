# plugins/cdnvideohub — extension point (пока no-op)

CDN Video Hub **не интегрирован**: по условию первого задания интеграция отложена до
второго change request вместе с актуальной документацией.

Здесь зарезервированы:

- `manifest.yaml` — версия и контракт будущего плагина;
- место для knowledge pack: `knowledge/cdnvideohub/`;
- точка расширения плеера в теме: `themes/basis-video/theme.yaml: extension_points.cdnvideohub`.

Пока документация не передана, адаптер отсутствует, а любая попытка включить
интеграцию в site package даёт `BLOCKED_INPUT`: `integrations[].documentation_ref`
обязателен, а неизвестное имя интеграции не считается разрешением.
