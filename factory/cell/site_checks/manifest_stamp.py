"""Манифест шаблона говорит о выпуске правду.

Ловится один класс отказа, случившийся здесь трижды: поле манифеста пишется
один раз и переживает свой выпуск. Витрина отвечает 200, build_id верен, а
рядом стоит цифра или путь чужого релиза — и по ним судят, какой код работает.

Что проверяется:

1. В репозитории сведения о выпуске ПУСТЫ. Заполненное значение здесь и есть
   тот самый пережиток: сборка его перезапишет, но если сборку обойдут, оно
   уедет на сайт как настоящее.
2. Штамп сборки согласован с `config/site.json`: каталог выпуска лежит под
   объявленным корнем размещения, ссылка совпадает с объявленной.
3. `artifact_sha256` — сумма файла рантайма, а не архива и не перенос.
4. Происхождение шаблона не подменено версией сайта: `source_commit` равен
   закреплённому в `pins.lock.json`, и он НЕ равен коммиту этого репозитория.
5. Все поля, которых рантайм требует от манифеста, на месте.

Проверка вызывает ту же функцию `штамп`, которой пользуется сборка: своя копия
правил разошлась бы с артефактом, а это ровно тот случай, ради которого
проверка и написана.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_release  # noqa: E402

#: Поля, без которых рантайм не поднимается (_манифест в lords-frontend.py).
ТРЕБУЕТ_РАНТАЙМ = ("schema_version", "template_family", "design_version",
                   "source_commit", "build_id", "artifact_sha256", "profile",
                   "built_at")

#: Происхождение шаблона: неподвижно, сборкой не меняется.
ПОЛЕ_ПРОИСХОЖДЕНИЯ = "template_origin"

#: Сведения о выпуске: в репозитории они обязаны быть пусты.
ПУСТЫЕ_В_РЕПО = ("artifact_sha256", "runtime_commit", "site_repo_commit",
                 "built_at", "release_dir", "bound_release_link")

cfg = json.loads((ROOT / "config" / "site.json").read_text(encoding="utf-8"))
pins = json.loads((ROOT / "pins.lock.json").read_text(encoding="utf-8"))
сырой = json.loads((ROOT / "config" / "template-manifest.json").read_text(encoding="utf-8"))

плохо = []

for поле in ТРЕБУЕТ_РАНТАЙМ:
    if поле not in сырой:
        плохо.append(f"манифест без поля {поле}: рантайм не поднимется")

for поле in ПУСТЫЕ_В_РЕПО:
    if сырой.get(поле):
        плохо.append(f"{поле} заполнено в репозитории ({сырой[поле]!r}): "
                     "значение переживёт свой выпуск")
происхождение = сырой.get(ПОЛЕ_ПРОИСХОЖДЕНИЯ)
if not isinstance(происхождение, dict) or not происхождение.get("source_commit"):
    плохо.append(f"нет {ПОЛЕ_ПРОИСХОЖДЕНИЯ}.source_commit: происхождение шаблона "
                 "не отделено от версии сайта")
elif происхождение["source_commit"] != pins["pins"]["source_commit"]:
    плохо.append(f"{ПОЛЕ_ПРОИСХОЖДЕНИЯ}.source_commit разошёлся с замком")

if сырой.get("build_id") != "worktree-unbuilt":
    плохо.append(f"build_id в репозитории {сырой.get('build_id')!r}, "
                 "ожидалось 'worktree-unbuilt'")

commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                        capture_output=True, text=True, check=True).stdout.strip()
готовый = build_release.штамп(сырой, cfg, pins, commit, dirty=False)

dep = cfg.get("deployment") or {}
корень = (dep.get("root") or "").rstrip("/")
if not корень:
    плохо.append("config/site.json без deployment.root: "
                 "сборке неоткуда взять каталог выпуска")
else:
    if not готовый["release_dir"].startswith(корень + "/"):
        плохо.append(f"release_dir {готовый['release_dir']} вне корня размещения {корень}")
    if not готовый["release_dir"].endswith("/" + commit[:12]):
        плохо.append(f"release_dir {готовый['release_dir']} не назван коммитом {commit[:12]}")
    if готовый["bound_release_link"] != dep.get("current_link"):
        плохо.append("bound_release_link разошёлся с deployment.current_link")

рантайм = ROOT / "src" / cfg["entrypoint"]
сумма = hashlib.sha256(рантайм.read_bytes()).hexdigest()
if готовый["artifact_sha256"] != сумма:
    плохо.append(f"artifact_sha256 {готовый['artifact_sha256'][:12]} "
                 f"не сумма {cfg['entrypoint']} ({сумма[:12]})")

закреплён = pins["pins"]["source_commit"]
if готовый["source_commit"] != закреплён:
    плохо.append(f"source_commit {готовый['source_commit'][:12]} "
                 f"разошёлся с замком {закреплён[:12]}")
if готовый["source_commit"] == commit:
    плохо.append("source_commit равен коммиту этого репозитория: "
                 "происхождение шаблона подменено версией сайта")
for поле in ("runtime_commit", "site_repo_commit"):
    if готовый[поле] != commit:
        плохо.append(f"{поле} не равен HEAD {commit[:12]}")
if готовый["built_at"] != build_release.commit_time(commit):
    плохо.append("built_at не равен времени коммита выпуска")

# Ни одно поле выпуска не смеет указывать в дерево ОБЩЕЙ фабрики: именно так
# каждая выделенная ячейка объявляла своей раскладкой чужую.
ОБЩАЯ_ФАБРИКА = "/srv/lords/.frontend"
for поле, значение in готовый.items():
    if поле == ПОЛЕ_ПРОИСХОЖДЕНИЯ:
        continue
    if isinstance(значение, str) and значение.startswith(ОБЩАЯ_ФАБРИКА):
        плохо.append(f"{поле} указывает в общую фабрику: {значение}")

if плохо:
    print("манифест выпуска недостоверен:", *плохо, sep="\n  ", file=sys.stderr)
    sys.exit(1)
