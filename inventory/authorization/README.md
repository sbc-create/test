# Authorization manifests

Один файл на site: `<site_id>.authorization.yaml`. Несекретные. Определяют **business scope**.

Разрешение инструмента Claude Code (settings/hooks) и manifest — **два независимых слоя**.
Операция выполняется без участия владельца, только если проходят оба.
Фраза в чате не является авторизацией. Manifest не разрешает обойти hooks.

Обязательные поля: `site_id`, `domain`, `hosts`, `environment`, `allowed_actions`,
`authorization_expires_at`. Для production дополнительно: `production_authorized: true`,
`authorized_build_id`, `authorized_branch`, `backup_verified`.

Истёкший `authorization_expires_at` => `BLOCKED_AUTHORIZATION` без исключений.
