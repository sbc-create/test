# DLE Site Factory

Фабрика повторяемого создания, проверки, публикации, обновления и отката сайтов на
DataLife Engine 20.0.

```bash
pip3 install -r requirements.txt
python3 -m factory validate --site pilot-local     # проверить пакет
python3 -m factory deploy   --site pilot-local     # собрать, выкатить, проверить
bash tests/run-all.sh                              # полный прогон всех уровней
```

## С чего начать

| Вопрос | Документ |
|--------|----------|
| Как устроена фабрика | `docs/ARCHITECTURE.md`, `adr/` |
| Как ввести новый сайт | `docs/NEW_SITE.md` |
| Как эксплуатировать | `docs/OPERATIONS.md` |
| Как выкатывать и откатывать | `docs/DEPLOY.md`, `docs/ROLLBACK.md` |
| Правила безопасности | `docs/SECURITY.md` |
| Чего не хватает для production | `docs/INPUT_REQUEST.md` |
| Что зафиксировано как факт | `knowledge/FACTS.md`, `knowledge/SOURCE_REGISTRY.yaml` |

## Текущее состояние

- Пилот проходит полный конвейер на одноразовой локальной цели: 48 маршрутов,
  6 ворот качества, backup с подтверждённым восстановлением, откат с health-проверкой.
- **DLE не устанавливается**: лицензионный дистрибутив и профиль путей не переданы,
  а угадывать структуру каталогов запрещено. Гейт — `BLOCKED_INPUT`.
- **Production недоступен**: ни одного SSH-хоста, DNS-зоны и лицензии не передано.
- **CDN Video Hub не интегрирован**: создана только extension point.

Полный список недостающих входных данных — `docs/INPUT_REQUEST.md`.
