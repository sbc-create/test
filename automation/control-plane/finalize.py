#!/usr/bin/env python3
"""Changelog, migration guide, политика совместимости и пересборка сумм."""
import datetime as dt, hashlib, json, pathlib
КОРЕНЬ = pathlib.Path("/srv/site-factory/control-plane-contracts/1.0.0")
СЕЙЧАС = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

(КОРЕНЬ / "CHANGELOG.md").write_text(f"""# fleet-control-plane-contracts

## 1.0.0 — {СЕЙЧАС}

Первая версия. Ломать нечего: предыдущих версий bundle не существовало.

Включено:

* 13 базовых схем: SiteRef, ActorRef, ObservedValue, CorrelationContext,
  VersionRef, EvidenceRef, DesiredObservedState, CommandEnvelope.v1,
  CommandReceipt.v1, EventEnvelope.v1, Problem.v1, Page.v1, Capability.v1;
* OpenAPI на 22 пути, из них 8 — зарезервированные пространства имён со
  статусом PLANNED и без адресов;
* AsyncAPI на 28 каналов: 4 существующих события реестра со статусом
  AVAILABLE и 24 объявленных со статусом PLANNED;
* матрица владения на 9 ресурсов, ни у одного нет двух писателей;
* каталог возможностей: 7 AVAILABLE после живой проверки, 12 PLANNED;
* каталог ошибок и правил надёжности.

Совместимость с существующим Registry сохранена: `GET /api/v1/sites`
продолжает отдавать прежние четыре ключа, новые поля добавлены аддитивно.

### Известный разрыв

`SITES_QUERY_FILTER_NOT_APPLIED` — параметры `environment` и
`lifecycle_state` у `/api/v1/sites` объявлены, но провайдером не
применяются. Помечены в OpenAPI как PLANNED. Каноническим источником
ACTIVE production служит `/api/v1/registry/snapshot`, и референсные клиенты
берут девять сайтов именно оттуда. Исправление требует аддитивной правки
Control API и ждёт разрешения владельца.
""", encoding="utf-8")

(КОРЕНЬ / "COMPATIBILITY.md").write_text("""# Политика совместимости

Мажор в URL (`/api/v1`), SemVer у bundle, суффикс `.v1` у типов событий.

Внутри мажора допустимо:

* добавить необязательное поле;
* добавить новый тип события;
* добавить endpoint;
* расширить перечисление новым значением, если потребитель обязан
  игнорировать незнакомое.

Требует нового мажора:

* удалить или переименовать поле;
* сделать необязательное поле обязательным;
* изменить смысл существующего поля;
* сузить перечисление.

Обязанности сторон:

* потребитель обязан терпеть неизвестные необязательные поля. Иначе любое
  аддитивное расширение производителя ломает всех разом;
* производитель не вправе молча перестать возвращать обязательное поле.
  Тихое исчезновение хуже ошибки: потребитель продолжит работать на
  неполных данных;
* оба мажора поддерживаются до завершения объявленной миграции.

Ломающее изменение блокируется проверкой совместимости, а не соглашением.
""", encoding="utf-8")

(КОРЕНЬ / "MIGRATION.md").write_text("""# Миграция потребителей

Ни один потребитель в этом шаге на production-мутации не переводится.
Доказана только читающая совместимость на тестовых адаптерах.

| контур | как находит сайты сейчас | целевой способ | что меняется у клиента | владелец | предпосылки | откат | будущий prompt |
|---|---|---|---|---|---|---|---|
| Templates | манифесты в `/srv/lords/.frontend` | `GET /api/v1/registry/snapshot` | заменить чтение файлов на клиент; ключ — `site_id` | templates | FLEET-CORE-003 (IAM) для записи | продолжать читать манифесты | FLEET-TPL-001 |
| SEO | `config/site-profiles` и собственные списки | тот же snapshot | отказаться от своего portfolio | seo | подтвердить владельца `inventory/portfolios.yaml` | вернуть чтение профилей | FLEET-SEO-003.R2 |
| Content | кэш каталога и таблица маршрутов витрины | snapshot + `site_id` | связывать сущности по `site_id` | content | — | текущий путь | FLEET-CNT-001 |
| Monitoring | нет | snapshot + события `site.*` | подписка на ленту с durable-курсором | monitoring | владелец не реализован | — | FLEET-MON-001 |
| Backup | нет | snapshot + `backup_policy_ref` | политика на `site_id` | backup | владелец не реализован | — | FLEET-BCK-001 |
| Qwen | нет | snapshot только на чтение | предложения, без применения | architect | IAM и ChangeSet | — | FLEET-CORE-003 |

Общее правило перехода: `site_id` — единственный ключ связи. Домен
использовать ключом нельзя: он меняется, а идентификатор нет.
""", encoding="utf-8")

суммы = {}
for p in sorted(КОРЕНЬ.rglob("*")):
    if p.is_file() and p.name not in ("checksums.json", "_partial-checksums.json"):
        суммы[str(p.relative_to(КОРЕНЬ))] = hashlib.sha256(p.read_bytes()).hexdigest()
(КОРЕНЬ / "checksums.json").write_text(json.dumps(
    {"algorithm": "sha256", "generated_at": СЕЙЧАС, "count": len(суммы),
     "files": суммы}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
м = json.loads((КОРЕНЬ / "manifest.json").read_text(encoding="utf-8"))
м["artifacts"] = sorted(суммы)
м["generated_at"] = СЕЙЧАС
(КОРЕНЬ / "manifest.json").write_text(
    json.dumps(м, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("артефактов:", len(суммы))
print("манифест обновлён, сумма checksums.json:",
      hashlib.sha256((КОРЕНЬ / "checksums.json").read_bytes()).hexdigest()[:16])
