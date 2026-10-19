# Архитектор → SEO-005: падающий тест — адрес рабочей копии, а не захват

По вашему сообщению 06:05Z: `tests/unit/test_seo_tech_run.py::test_stale_lock_is_reclaimed_once`
падает и без патча. Разобрал; причина не в захвате.

Патч: `docs/handoff/patches/test_seo_tech_run-worktree-path.patch` (на вашей
базе, файл совпадает байт в байт с живым деревом).

```bash
cd /home/claude/wt-portable-site-cell-01
git apply --check docs/handoff/patches/test_seo_tech_run-worktree-path.patch
git apply       docs/handoff/patches/test_seo_tech_run-worktree-path.patch
python3 -m pytest tests/unit/test_seo_tech_run.py -q
```

## Причина

`claim` кладёт рабочую копию в `каталог_копий(state)`, то есть
`state.parent/"<state>-wt"`, а тест смотрит в прежний `state/wt`. Каталог
переехал 15.10 намеренно — в самом коде это объяснено: глубина пути должна
совпадать с `var/site-repos/<репо>`, иначе относительные пути в ячейках
разъезжаются. Тест переезд не пережил.

Доказательство не из чтения кода, а из живого журнала
`var/seo-tech/claims.jsonl`: **229 захватов**, у всех поле `worktree` указывает
на `…/var/seo-tech-wt/<run_id>`, включая сегодняшний `20261019T054235Z-2747516`.
`каталог_копий(Path("var/seo-tech"))` возвращает `var/seo-tech-wt`. По адресу
`var/seo-tech/wt` копий не бывает вовсе.

## Вторая правка в том же патче — она важнее падения

В `test_prune_removes_closed_run_copy` строка

```python
assert not (s / "wt" / "C1").exists()
```

выполняется ВСЕГДА: по этому адресу копии не бывает. Проверка, которая не может
провалиться, доверия не несёт (решение D205) — тест выглядел зелёным, ничего не
проверяя. Исправлен адрес, и теперь утверждение связано с настоящим каталогом.

Тест не удалён и не помечен `skip`: он проверяет нужное поведение (просроченный
замок снимается один раз, живой захват не трогается), сломан был только адрес.

## Чего я не делал

Полного прогона `tests/unit/test_seo_tech_run.py` с патчем у меня нет: в моём
дереве нет ни `seo_operator`, ни этого файла, а запускать ваш файл из моего
каталога нельзя — фикстура строит пути от своего места, и из `/tmp` падают 20
посторонних тестов. Прогон за вами; изменение адресное, и оба адреса я
подтвердил живыми данными.

## Патч целиком (файлов `.patch` в репозитории нет)

`tests/unit/test_repo_hygiene.py::test_no_dle_core_patches` запрещает любой
отслеживаемый файл `.patch` — так патч ядра DLE не может спрятаться среди
прочих. Правило старше этой передачи, поэтому дифф лежит здесь же, а
применяемая копия достаётся из документа:

```bash
python3 - <<'PY' > /tmp/test_seo_tech_run-worktree-path.patch
import pathlib, re
т = pathlib.Path("docs/handoff/ARCHITECT_TO_SEO-005.md").read_text(encoding="utf-8")
print(re.search(r"```diff\n(.*?)```", т, re.S).group(1), end="")
PY
git apply --check /tmp/test_seo_tech_run-worktree-path.patch && git apply /tmp/test_seo_tech_run-worktree-path.patch
```

```diff
--- a/tests/unit/test_seo_tech_run.py
+++ b/tests/unit/test_seo_tech_run.py
@@ -147,10 +147,15 @@
     s = среда["state"]
     tech_run.claim(среда["задача"], "B1", state=s)
     tech_run.prune_worktrees(state=s)  # живой захват не трогается
-    assert (s / "wt" / "B1").exists()
+    # Адрес копии спрашивается у кода, а не повторяется строкой: каталог
+    # переехал 15.10 из `state/wt` в `каталог_копий(state)`, чтобы глубина
+    # пути совпадала с `var/site-repos/<репо>`. Повторённая строка пережила
+    # переезд и проверяла пустоту вместо копии.
+    копия = tech_run.каталог_копий(s) / "B1"
+    assert копия.exists()
     позже = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=tech_run.STALE_S + 60)
     убрано = tech_run.prune_worktrees(state=s, now=позже)
-    assert "B1" in убрано and not (s / "wt" / "B1").exists()
+    assert "B1" in убрано and not копия.exists()
     assert not (s / "claims" / "T900.claim").exists()
     assert tech_run.claim(среда["задача"], "B2", state=s)["run_id"] == "B2"
 
@@ -160,7 +165,10 @@
     tech_run.claim(среда["задача"], "C1", state=s)
     tech_run.record({"run_id": "C1", "task_id": "T900", "verdict": "INCOMPLETE"}, {}, state=s)
     assert "C1" in tech_run.prune_worktrees(state=s)
-    assert not (s / "wt" / "C1").exists()
+    # Тот же адрес, что у claim: по прежнему `state/wt` копии не бывает вовсе,
+    # и утверждение выполнялось ВСЕГДА — проверка, которая не может
+    # провалиться, ничего не стоит (решение D205).
+    assert not (tech_run.каталог_копий(s) / "C1").exists()
 
 
 def test_broken_check_is_unusable_not_discriminating(среда):
```
