HOST_VERIFIED=BLOCKED_WRONG_HOST

| Проверка | Ожидается | Фактически | Итог |
|---|---|---|---|
| hostname | claude-control-01 | vm | MISMATCH |
| IPv4 | 45.131.182.225 | 127.0.0.0, 127.0.0.1, 192.0.2.0, 192.0.2.2 | MISMATCH |
| /srv/site-factory/repo | существует | отсутствует | MISMATCH |

Расхождения:
- hostname 'vm' не совпадает с ожидаемым 'claude-control-01'
- адрес 45.131.182.225 не найден среди интерфейсов: ['127.0.0.0', '127.0.0.1', '192.0.2.0', '192.0.2.2']
- каталог /srv/site-factory/repo отсутствует

evidence: {"hostname_source": "/proc/sys/kernel/hostname", "ipv4_source": "/proc/net/fib_trie", "addresses": ["127.0.0.0", "127.0.0.1", "192.0.2.0", "192.0.2.2"], "ephemeral_addressing": true, "container_markers": ["gVisor (runsc) в /etc/hosts"]}

======================================================================
PORTFOLIO_SITES_TOTAL=6
YAMI_SITES_DISCOVERED=3
LORDS_SITES_DISCOVERED=3

| Домен | portfolio | профиль | repository | deployment target | environment | HTTPS | Metrika counter | Webmaster host | indexing | analytics data | content | фактический URL |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1lordserials1.online | lords [direction_registry] | lords-03 [direction_registry] | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED |
| lordfilm47.space | lords [direction_registry] | lords-02 [direction_registry] | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED |
| lordserial33.biz | lords [direction_registry] | lords-01 [direction_registry] | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED |
| yummyani.biz | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | 111881039 [analytics_registry] | null [analytics_registry] | False [analytics_registry] | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED |
| yummyani.org | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | 111881038 [analytics_registry] | null [analytics_registry] | False [analytics_registry] | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED |
| yummyani.site | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED | 111881037 [analytics_registry] | null [analytics_registry] | False [analytics_registry] | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED |

INVENTORY_DRIFT:
  - BLOCKING unreachable_source[portfolio]: источник deployment_manifest не прочитан: BLOCKED_WRONG_HOST: сессия не на claude-control-01
  - BLOCKING unreachable_source[portfolio]: источник live_https не прочитан: BLOCKED_WRONG_HOST: сессия не на claude-control-01
  - BLOCKING unreachable_source[portfolio]: источник nginx не прочитан: BLOCKED_WRONG_HOST: сессия не на claude-control-01
  - BLOCKING unreachable_source[portfolio]: источник systemd не прочитан: BLOCKED_WRONG_HOST: сессия не на claude-control-01
  - orphan[1lordserials1.online]: домен присутствует только в direction_registry; отсутствует в: analytics_registry
  - orphan[lordfilm47.space]: домен присутствует только в direction_registry; отсутствует в: analytics_registry
  - orphan[lordserial33.biz]: домен присутствует только в direction_registry; отсутствует в: analytics_registry
  - orphan[yummyani.biz]: домен присутствует только в analytics_registry; отсутствует в: direction_registry
  - orphan[yummyani.org]: домен присутствует только в analytics_registry; отсутствует в: direction_registry
  - orphan[yummyani.site]: домен присутствует только в analytics_registry; отсутствует в: direction_registry

targets: {"total": 2, "refs": ["local-disposable", "payload-local"], "production_capable": [], "has_production_target": false}
secret_hub: {"provider": "cdnvideohub", "store_dir": "/var/lib/site-factory-secret-hub", "portfolios": [{"id": "yami", "enabled": true, "consumers": ["yami-staging-compose"]}, {"id": "lords", "enabled": true, "consumers": ["lords-01", "lords-02", "lords-03"]}, {"id": "amedia", "enabled": true, "consumers": []}]}
