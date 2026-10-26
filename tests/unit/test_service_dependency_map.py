"""Измеритель зависимостей служб: честность разбора, а не красота вывода.

MOD-198 требует перед переносом установить фактические зависимости каждой
службы. Опасность здесь одна и конкретная: разбор, который чего-то не умеет,
печатает «файлов кода: 1» вместо отказа — и перенос по такому набору даёт
службу, которая запускается и молча делает не то. Поэтому проверяются ровно
те четыре вида точек входа, которые встретились в системе, и каждая была
сначала разобрана неверно.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "service_dependency_map", КОРЕНЬ / "automation" / "local" / "service-dependency-map.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)


def test_многострочный_execstart_склеивается():
    """systemd разрешает перенос обратным слешем, и реальные юниты им пользуются.

    Первая редакция читала только первую строку и теряла `-m пакет.модуль`,
    то есть саму точку входа.
    """
    текст = ("[Service]\n"
             "ExecStart=/path/.venv/bin/python \\\n"
             "  -m seo_engine.content_operator.report_server \\\n"
             "  --port 8231\n")
    значение = инс._поле(текст, "ExecStart")
    assert "-m seo_engine.content_operator.report_server" in значение
    assert "--port 8231" in значение


def test_интерпретатор_не_считается_точкой_входа(tmp_path):
    """Иначе точкой входа оказывается .venv/bin/python, и это бесполезно."""
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    (tmp_path / "automation").mkdir()
    сценарий = tmp_path / "automation" / "дело.sh"
    сценарий.write_text("#!/bin/bash\n", encoding="utf-8")
    юнит = {"ExecStart": f"{tmp_path}/.venv/bin/python {tmp_path}/automation/дело.sh"}
    вход, как = инс.точка_входа(юнит, tmp_path)
    assert вход is not None and вход.name == "дело.sh", как


def test_инлайн_c_разбирается(tmp_path):
    """community-ratings-monitor запускается через python -c с импортом."""
    (tmp_path / "factory" / "community").mkdir(parents=True)
    цель = tmp_path / "factory" / "community" / "monitor_once.py"
    цель.write_text("def main():\n    return 0\n", encoding="utf-8")
    юнит = {"ExecStart": "/usr/bin/python3 -c 'from factory.community.monitor_once import main; "
                         "raise SystemExit(main())'"}
    вход, как = инс.точка_входа(юнит, tmp_path)
    assert вход == цель and "-c" in как


def test_обёртка_вне_дерева_с_pythonpath_раскрывается(tmp_path):
    """Худший вид привязки: юнит дерева не называет, оно спрятано в PYTHONPATH."""
    дерево = tmp_path / "wt-дерево"
    (дерево / "factory" / "community").mkdir(parents=True)
    цель = дерево / "factory" / "community" / "http_gateway.py"
    цель.write_text("def main():\n    return 0\n", encoding="utf-8")
    обёртка = tmp_path / "обёртка"
    обёртка.write_text(
        f"#!/bin/bash\nexport PYTHONPATH={дерево}\n"
        "exec /usr/bin/python3 -c 'from factory.community.http_gateway import main; "
        "raise SystemExit(main())'\n", encoding="utf-8")
    вход, как = инс.точка_входа({"ExecStart": str(обёртка)}, дерево)
    assert вход == цель, как
    assert "PYTHONPATH" in как


def test_сценарий_оболочки_тянет_то_что_зовёт(tmp_path):
    """«Файлов кода: 1» у обёртки — это недоразбор, а не факт."""
    (tmp_path / "automation" / "host").mkdir(parents=True)
    (tmp_path / "seo_operator").mkdir()
    модуль = tmp_path / "seo_operator" / "cli.py"
    модуль.write_text("import json\n", encoding="utf-8")
    сценарий = tmp_path / "automation" / "host" / "дело.sh"
    сценарий.write_text("#!/bin/bash\npython3 -m seo_operator.cli regular\n", encoding="utf-8")
    файлы = инс.зависимости_оболочки(сценарий, tmp_path)
    assert модуль in файлы and сценарий in файлы


def test_нулевые_байты_не_ломают_разбор(tmp_path):
    """В грязном дереве бывает частично записанный файл; это ValueError."""
    (tmp_path / "pkg").mkdir()
    плохой = tmp_path / "pkg" / "битый.py"
    плохой.write_bytes(b"import json\x00\n")
    assert инс.импорты(плохой, tmp_path) == {плохой}


def test_карта_покрывает_все_работающие_службы():
    """Замер по системе: ни одной службы без разобранной точки входа.

    Числа измеренные (26.10): 18 работающих служб из пяти рабочих копий, и
    зависимость от незакоммиченного — ровно у двух.
    """
    запись = КОРЕНЬ / "artifacts" / "evidence" / "service-dependency-map-20261026.json"
    д = json.loads(запись.read_text(encoding="utf-8"))
    assert д["служб"] == 18
    без_входа = [з["служба"] for з in д["службы"] if not з["точка_входа"]]
    assert not без_входа, f"без точки входа: {без_входа}"
    # 26.10 около 10:34Z линия аудита закоммитила три файла (ff8d678), и
    # зависимость от незакоммиченного исчезла у обеих своих служб. Проверка
    # следит за СВОЙСТВОМ, а не за прежним числом: как только какая-то служба
    # снова начнёт зависеть от незакоммиченного, она назовёт её по имени —
    # это и есть сигнал, что переносить её рано.
    грязные = {з["служба"]: з["нужны_незакоммиченные"] for з in д["службы"]
               if з["нужны_незакоммиченные"]}
    assert not грязные, (
        "служба снова зависит от незакоммиченного — перенос такой службы "
        f"откатил бы её поведение на неизвестную величину: {грязные}")
    # Агентные службы: правила каталога запуска — часть выпуска, и их нельзя
    # потерять при переносе.
    агентные = {з["служба"] for з in д["службы"]
                if (з.get("неимпортные") or {}).get("агентная")}
    assert агентные == {"editor-run.service", "seo-tech-run.service"}, агентные
    for з in д["службы"]:
        ни = з.get("неимпортные") or {}
        if ни.get("агентная"):
            assert "CLAUDE.md" in (ни.get("правила_агента") or []), з["служба"]


# --- Вердикт переноса (MOD-198) ---------------------------------------------

def _сценарий(tmp_path, текст: str, имя: str = "служба.sh"):
    ф = tmp_path / имя
    ф.write_text(текст, encoding="utf-8")
    return ф


def test_самоотносительный_путь_находится_и_называет_строку(tmp_path):
    """То, что ломается ровно при переносе: корень, посчитанный от себя."""
    ф = _сценарий(tmp_path, '#!/bin/bash\nФАЙЛ="$(dirname "$0")/../var/state.json"\n')
    найдено = инс.самоотносительные(ф)
    assert [с["строка"] for с in найдено] == [2]
    assert найдено[0]["вид"] == "оболочка: dirname $0"
    assert найдено[0]["переменная"] == ""


def test_упоминание_в_комментарии_не_зависимость(tmp_path):
    """Иначе исправленная служба остаётся непереносимой по своему же пояснению.

    Найдено 26.10 на yummy-sitemap-warm.sh: путь уже стал параметром, а
    строка-комментарий объясняла, ЧТО именно заменено, — и вердикт по ней
    выходил «нельзя».
    """
    ф = _сценарий(tmp_path, '#!/bin/bash\n# dirname $0 указал бы на выпуск\necho ок\n')
    assert инс.самоотносительные(ф) == []


def test_переменная_делает_перенос_условным(tmp_path):
    """Третий вердикт: можно, но юнит обязан задать переменную."""
    ф = _сценарий(tmp_path,
                  '#!/bin/bash\nП="${WARM_PAUSE:-$(dirname "$0")/../var/pause.json}"\n')
    найдено = инс.самоотносительные(ф)
    assert найдено and найдено[0]["переменная"] == "WARM_PAUSE"
    вердикт = инс.вердикт_переноса({"самоотносительные": найдено, "точка_входа": "служба.sh"})
    assert вердикт["можно"] is True
    assert вердикт["при_условии"] == ["юнит задаёт WARM_PAUSE (строка 2)"]


def test_git_по_своему_корню_запрещает_перенос(tmp_path):
    """Каталог выпуска не репозиторий: такой вызов отказывает, а не молчит."""
    ф = _сценарий(tmp_path, 'КОРЕНЬ = Path(__file__).resolve().parents[1]\n'
                            'subprocess.run(["git", "-C", str(КОРЕНЬ), "rev-parse", "HEAD"])\n',
                  имя="служба.py")
    зовёт, запас = инс.зовёт_git_по_корню(ф)
    assert зовёт is True and запас == ""
    вердикт = инс.вердикт_переноса({"самоотносительные": инс.самоотносительные(ф),
                                    "зовёт_git_по_корню": True, "точка_входа": "служба.py"})
    assert вердикт["можно"] is False
    assert any("не репозиторий" in п for п in вердикт["почему"])


def test_состояние_из_вычисленного_корня_видно(tmp_path):
    """Прежде путь «$(…)/var/…» был невидим: ловился только «var/…» от корня."""
    ф = _сценарий(tmp_path,
                  '#!/bin/bash\nП="$(cd "$(dirname "$0")/../.." && pwd)/var/yummy/pause.json"\n')
    ни = инс.неимпортные(ф, tmp_path)
    assert "var/yummy/pause.json" in ни["состояние"]


def test_чистая_служба_переносима_без_условий():
    """Мерка не в числе файлов: site-cell-executor крупнее всех и переносим.

    Прежде здесь же утверждалось, что seo-regular-daily переносу не подлежит.
    26.10 линия SEO вынесла корни состояния и реестров в параметры (коммит
    8bf52ba), и утверждение стало неверным — оно закрепляло состояние, а не
    свойство. Свойство проверяется на построенном случае
    (test_смысловой_путь_находится_в_модуле_а_не_только_во_входе), а здесь
    остаётся то, что от состояния чужих линий не зависит.
    """
    записи = [инс.разобрать(з) for з in инс.службы_из_копий()]
    по_имени = {з["служба"]: з for з in записи}
    чистая = по_имени["community-ratings-monitor.service"]["перенос"]
    assert чистая["можно"] is True
    # Условия бывают двух родов, и для «чистой» службы допустим только первый:
    # «выпуск обязан включить …» выполняет САМ установщик, а «юнит задаёт …»
    # требует действия оператора. 26.10 у пилота появились три условия первого
    # рода (миграции, которые грузятся по пути от PATHS.root) — прежнее
    # утверждение «условий нет» закрепляло состояние до этой находки.
    чужие = [у for у in чистая["при_условии"] if not у.startswith("выпуск обязан включить")]
    assert чужие == [], чужие
    # У каждой службы вердикт обязан быть объяснён: «нельзя» без причины
    # ничем не отличается от «не измеряли».
    for з in записи:
        assert з["перенос"]["почему"], з["служба"]


# --- Состав выпуска: импорт модуля через `from … import` и относительный -----

def test_from_import_модуля_попадает_в_состав(tmp_path):
    """Найдено запуском: сверка сумм давала 0 расхождений, а служба не импортировалась.

    `from factory.community import metrics_store` разбор считал импортом
    ИМЕНИ, модуль в выпуск не попадал, и установленная копия падала с
    ImportError на первой же строке.
    """
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "store.py").write_text("ЗНАЧЕНИЕ = 1\n", encoding="utf-8")
    вход = tmp_path / "pkg" / "main.py"
    вход.write_text("from pkg import store\n", encoding="utf-8")
    состав = {str(ф.relative_to(tmp_path)) for ф in инс.импорты(вход, tmp_path)}
    assert "pkg/store.py" in состав


def test_относительный_импорт_попадает_в_состав(tmp_path):
    """Прежнее условие `level == 0` пропускало весь внутрипакетный импорт."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "models.py").write_text("КЛАСС = 1\n", encoding="utf-8")
    вход = tmp_path / "pkg" / "main.py"
    вход.write_text("from .models import КЛАСС\nfrom . import models\n", encoding="utf-8")
    состав = {str(ф.relative_to(tmp_path)) for ф in инс.импорты(вход, tmp_path)}
    assert "pkg/models.py" in состав


def test_имя_при_from_import_не_считается_обязательным_модулем(tmp_path):
    """Иначе `from pkg.models import Класс` даёт ложную находку «нет модуля»."""
    вход = tmp_path / "main.py"
    вход.write_text("from pkg.models import Класс\n", encoding="utf-8")
    import ast
    разбор = ast.parse(вход.read_text(encoding="utf-8"))
    все = инс._кандидаты_импорта(разбор, вход, tmp_path)
    обязательные = инс._кандидаты_импорта(разбор, вход, tmp_path, обязательные_только=True)
    assert "pkg/models/Класс" in все
    assert обязательные == ["pkg/models"]


# --- Весь состав, а не только точка входа (MOD-198, правка линии SEO) --------

def test_смысловой_путь_находится_в_модуле_а_не_только_во_входе(tmp_path):
    """Переопределение корней уехало на модуль глубже — вердикт обязан это видеть.

    26.10 линия SEO вынесла корни в seo_operator/paths.py, и мой вердикт по
    пяти службам остался «нельзя» только потому, что сканировалась одна точка
    входа. Это ложный отказ, и он дороже пропуска: он останавливает уже
    сделанную работу.
    """
    модуль = tmp_path / "модуль.py"
    модуль.write_text('КОРЕНЬ = Path(__file__).resolve().parents[1]\n'
                      'ОЧЕРЕДЬ = КОРЕНЬ / "config" / "queue.json"\n', encoding="utf-8")
    найдено = инс.смысловые_от_себя({модуль}, tmp_path)
    assert [(з["строка"], з["берёт"]) for з in найдено] == [(2, "config")]
    вердикт = инс.вердикт_переноса({"смысловые_от_себя": найдено,
                                    "точка_входа": "модуль.py"})
    assert вердикт["можно"] is False
    assert "модуль.py:2" in вердикт["почему"][0]


def test_переопределение_в_том_же_файле_снимает_находку(tmp_path):
    модуль = tmp_path / "модуль.py"
    модуль.write_text('import os\n'
                      'КОРЕНЬ = Path(__file__).resolve().parents[1]\n'
                      'КОРЕНЬ = Path(os.environ.get("STATE_ROOT", КОРЕНЬ))\n'
                      'ОЧЕРЕДЬ = КОРЕНЬ / "config" / "queue.json"\n', encoding="utf-8")
    assert инс.смысловые_от_себя({модуль}, tmp_path) == []


def test_фикстура_и_схема_смысловыми_не_считаются(tmp_path):
    """Схемы и фикстуры едут с кодом: в выпуске они должны быть именно его."""
    модуль = tmp_path / "модуль.py"
    модуль.write_text('КОРЕНЬ = Path(__file__).resolve().parent.parent\n'
                      'Ф = КОРЕНЬ / "config" / "portfolio.fixture.json"\n'
                      'С = КОРЕНЬ / "schemas" / "site.schema.json"\n', encoding="utf-8")
    assert инс.смысловые_от_себя({модуль}, tmp_path) == []


def test_путь_состояния_из_справки_и_комментария_не_состояние(tmp_path):
    """Прозa давала «состояние в дереве» там, где его нет.

    Измерено на seo_operator/cli.py: `var/seo-tech/runs.jsonl` стоял в тексте
    справки `--record`, а настоящее состояние берётся через paths.state(...).
    """
    вход = tmp_path / "служба.py"
    вход.write_text('p.add_argument("--record", help="дописать в var/seo-tech/runs.jsonl")\n'
                    '# код 10 — задача захвачена (var/seo-tech/next.json)\n'
                    'состояние = paths.state("artifacts", "сводка.json")\n', encoding="utf-8")
    ни = инс.неимпортные(вход, tmp_path)
    assert ни["состояние"] == []


def test_путь_внутри_параметризованного_корня_покрыт_им(tmp_path):
    """Обёртки подставляют корень по префиксу — вложенные пути лечатся вместе.

    Без учёта вложенности editor-run и seo-tech-run оставались «нельзя» из-за
    ledger.jsonl и next.json, хотя `sed s#var/editor-runs#$STATE#g` в обёртке
    переписывает и их.
    """
    запись = {"точка_входа": "служба.sh", "неимпортные": {
        "состояние": ["var/editor-runs", "var/editor-runs/ledger.jsonl",
                      "var/editor-runs/next.json", "var/other/state.json"],
        "переменные_состояния": {"var/editor-runs": "SEO_STATE_ROOT"}}}
    вердикт = инс.вердикт_переноса(запись)
    assert вердикт["можно"] is False, "непокрытый путь обязан остаться запретом"
    почему = "; ".join(вердикт["почему"])
    assert "var/other/state.json" in почему
    assert "ledger.jsonl" not in почему


def test_агентная_служба_держит_состояние_названное_заданием():
    """Для агентной службы путь из задания — настоящая зависимость.

    Сценарий у editor-run и seo-tech-run уже параметризован, но пути названы
    в документах задания (EDITOR_RUN_PROMPT.md, SEO_TECH_RUN_PROMPT.md),
    которые читает МОДЕЛЬ. Пока там стоит путь от корня копии, перенос уводит
    запись не туда, и вердикт обязан это держать.
    """
    записи = {з["служба"]: инс.разобрать(з) for з in инс.службы_из_копий()}
    for имя in ("editor-run.service", "seo-tech-run.service"):
        з = записи[имя]
        assert (з["неимпортные"] or {}).get("агентная") is True, имя
        assert з["неимпортные"]["состояние"], имя
        # Состояние названо заданием, и это зависимость — но уже
        # параметризованная: 26.10 линия SEO стала подставлять в текст
        # задания фактический корень (коммит 4574dd3, проверено чтением
        # строки PROMPT= в обёртке). Поэтому проверяется не «нельзя», а то,
        # что корень состояния назван переменной, а не зашит.
        assert з["неимпортные"]["переменные_состояния"], имя
        assert з["перенос"]["при_условии"], имя


def test_догружаемый_по_пути_файл_находится(tmp_path):
    """Импортом такого не видно, а без него перенос теряет часть работы.

    Найдено 26.10 на seo-daily-cycle: вердикт вышел «можно», а в 15 файлах
    состава не было seo_qwen_review.py, который служба грузит по пути от
    своего каталога. Теперь файл называется и попадает в выпуск.
    """
    вход = tmp_path / "служба.py"
    вход.write_text('СВОЙ = pathlib.Path(__file__).resolve().parent\n'
                    'путь = СВОЙ / "обзор.py"\n', encoding="utf-8")
    (tmp_path / "обзор.py").write_text("ЗНАЧЕНИЕ = 1\n", encoding="utf-8")
    найдено = инс.догружаемые({вход}, tmp_path)
    assert найдено == [{"файл": "служба.py", "строка": 2, "цель": "обзор.py",
                        "разрешён": "обзор.py"}]
    вердикт = инс.вердикт_переноса({"догружаемые": найдено, "точка_входа": "служба.py"})
    assert вердикт["можно"] is True
    assert any("обязан включить обзор.py" in у for у in вердикт["при_условии"])


def test_ненайденный_догружаемый_файл_запрещает_перенос(tmp_path):
    """Угадывать нельзя: не найден — значит перенос неполон, и это отказ."""
    вход = tmp_path / "служба.py"
    вход.write_text('СВОЙ = pathlib.Path(__file__).resolve().parent\n'
                    'путь = СВОЙ / "нет-такого.py"\n', encoding="utf-8")
    найдено = инс.догружаемые({вход}, tmp_path)
    assert найдено[0]["разрешён"] is None
    вердикт = инс.вердикт_переноса({"догружаемые": найдено, "точка_входа": "служба.py"})
    assert вердикт["можно"] is False


def test_обёртка_вне_дерева_прибивает_службу_к_копии(tmp_path):
    """Состав чист, а переключить службу нельзя: обёртка перекрывает юнит.

    Найдено 26.10 на community-ratings-gateway: ExecStart ведёт на
    /usr/local/bin/community-ratings-gateway, обёртка принадлежит root и
    делает export PYTHONPATH на рабочую копию. По одному составу вердикт
    выходил «можно без условий» — и это был бы неверный совет оператору.
    """
    дерево = tmp_path / "копия"
    дерево.mkdir()
    обёртка = tmp_path / "обёртка.sh"
    обёртка.write_text("#!/bin/bash\n"
                       f"export PYTHONPATH={дерево}\n"
                       "exec /usr/bin/python3 -c 'import служба'\n", encoding="utf-8")
    найдено = инс.обёртка_юнита({"ExecStart": str(обёртка)}, дерево)
    assert найдено and найдено["прибивает"][0]["строка"] == 2
    вердикт = инс.вердикт_переноса({"обёртка": найдено, "точка_входа": "служба.py"})
    assert вердикт["можно"] is False
    assert "перекрывает Environment" in вердикт["почему"][0]


def test_обёртка_не_упомянувшая_копию_помехой_не_считается(tmp_path):
    дерево = tmp_path / "копия"
    дерево.mkdir()
    обёртка = tmp_path / "обёртка.sh"
    обёртка.write_text("#!/bin/bash\nexec /usr/bin/python3 -m служба\n", encoding="utf-8")
    assert инс.обёртка_юнита({"ExecStart": str(обёртка)}, дерево) is None


def test_использование_экспортированной_переменной_считается_параметром(tmp_path):
    """После упрощения кода переменная видна только в объявлении, не в строке пути.

    Измерено 26.10: линия SEO убрала мёртвую ветку `:-$REPO`, строка стала
    `STATE="$SEO_STATE_ROOT/var/editor-runs"` — и вердикт по двум агентным
    службам откатился в «нельзя», хотя код стал ЧИЩЕ. Вердикт, который
    наказывает за упрощение, неверен.
    """
    вход = tmp_path / "служба.sh"
    вход.write_text('#!/bin/bash\n'
                    'export SEO_STATE_ROOT="${SEO_STATE_ROOT:-/дерево}"\n'
                    'STATE="$SEO_STATE_ROOT/var/editor-runs"\n', encoding="utf-8")
    ни = инс.неимпортные(вход, tmp_path)
    assert ни["состояние"] == ["var/editor-runs"]
    assert ни["переменные_состояния"] == {"var/editor-runs": "SEO_STATE_ROOT"}
    вердикт = инс.вердикт_переноса({"неимпортные": ни, "точка_входа": "служба.sh"})
    assert вердикт["можно"] is True


def test_неизвестная_переменная_параметром_не_считается(tmp_path):
    """Иначе любой $ПЕРЕМЕННАЯ/путь сходил бы за параметр юнита."""
    вход = tmp_path / "служба.sh"
    вход.write_text('#!/bin/bash\nМЕСТНАЯ=/дерево\nSTATE="$МЕСТНАЯ/var/seo-tech"\n',
                    encoding="utf-8")
    ни = инс.неимпортные(вход, tmp_path)
    assert ни["состояние"] == ["var/seo-tech"]
    assert ни["переменные_состояния"] == {}


# --- Задание, названное строкой (находка линии аудита 26.10) -----------------

def test_задание_строкой_находится_и_разрешается(tmp_path):
    """Импорта у такого модуля нет НАМЕРЕННО: планировщику нельзя тянуть прикладной слой.

    Линия wt-seo-index-audit-20260930 измерила цену в своём дереве:
    статическое замыкание 40 файлов, замыкание от трёх строк — 134,
    пропущено 96. И это худший случай для приёмки: отказ не виден ни при
    установке, ни при импорте, ни при старте — он приходит с первым заданием
    такого типа.
    """
    (tmp_path / "pkg" / "services").mkdir(parents=True)
    for имя in ("pkg/__init__.py", "pkg/services/__init__.py",
                "pkg/services/queue.py"):
        (tmp_path / имя).write_text("", encoding="utf-8")
    вход = tmp_path / "pkg" / "tasks.py"
    вход.write_text('QUEUE_TASK = "pkg.services.queue.scheduled_run"\n', encoding="utf-8")
    найдено = инс.задания_строкой({вход}, tmp_path)
    assert [(з["ссылка"], з["разрешён"]) for з in найдено] == [
        ("pkg.services.queue.scheduled_run", "pkg/services/queue.py")]
    вердикт = инс.вердикт_переноса({"задания_строкой": найдено, "точка_входа": "pkg/tasks.py"})
    assert вердикт["можно"] is True
    assert any("задание названо строкой" in у for у in вердикт["при_условии"])


def test_строка_не_разрешающаяся_в_модуль_не_считается_заданием(tmp_path):
    """Правило — по РАЗРЕШИМОСТИ, а не по виду строки: иначе это эвристика."""
    вход = tmp_path / "служба.py"
    вход.write_text('ПУТЬ = "чужой.пакет.которого.нет"\n'
                    'ТЕКСТ = "это.просто.предложение"\n', encoding="utf-8")
    assert инс.задания_строкой({вход}, tmp_path) == []


def test_короткая_точечная_строка_заданием_не_считается(tmp_path):
    """«os.path» и подобное — не ссылка на задание; нужно не меньше трёх частей."""
    (tmp_path / "os").mkdir()
    (tmp_path / "os" / "path.py").write_text("", encoding="utf-8")
    вход = tmp_path / "служба.py"
    вход.write_text('ИМЯ = "os.path"\n', encoding="utf-8")
    assert инс.задания_строкой({вход}, tmp_path) == []


def test_живая_служба_с_заданиями_строкой_несёт_их_в_составе():
    """Выпуск, уже названный проверенным, оказался неполным: 149 → 154 файла."""
    записи = {з["служба"]: инс.разобрать(з) for з in инс.службы_из_копий()}
    р = записи["seo-engine-topvisor-inventory.service"]
    ссылки = {з["разрешён"] for з in р["задания_строкой"]}
    assert len(ссылки) >= 3, р["задания_строкой"]
    assert "seo_engine/services/content_queue.py" in ссылки


def test_догрузка_по_цепочке_сегментов_находится(tmp_path):
    """`КОРЕНЬ / "automation" / "local" / "x.py"` — тот же случай, другой вид.

    Найдено 26.10 линией wt-portable-site-cell-01: её суточный отчёт грузится
    так, и односегментный образец его не видел. Следствие в выпуске было бы
    тихим: раздел отчёта выходил бы пустым с пояснением «календарный отчёт не
    подключён к этому прогону», то есть как настройка, а не как потеря файла.
    """
    (tmp_path / "automation" / "local").mkdir(parents=True)
    (tmp_path / "automation" / "local" / "отчёт.py").write_text("", encoding="utf-8")
    вход = tmp_path / "служба.py"
    вход.write_text('КОРЕНЬ = Path(__file__).resolve().parents[1]\n'
                    'СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "отчёт.py"\n',
                    encoding="utf-8")
    найдено = инс.догружаемые({вход}, tmp_path)
    assert [(з["цель"], з["разрешён"]) for з in найдено] == [
        ("отчёт.py", "automation/local/отчёт.py")]


def test_цепочка_без_py_на_конце_догрузкой_не_считается(tmp_path):
    """`КОРЕНЬ / "var" / "состояние"` — это данные, а не модуль."""
    вход = tmp_path / "служба.py"
    вход.write_text('КОРЕНЬ = Path(__file__).resolve().parent\n'
                    'СОСТОЯНИЕ = КОРЕНЬ / "var" / "seo-tech"\n', encoding="utf-8")
    assert инс.догружаемые({вход}, tmp_path) == []


def test_живая_служба_несёт_загружаемый_по_пути_отчёт():
    """Состав seo-regular-* обязан включать automation/local/editor-day-report.py."""
    записи = {з["служба"]: инс.разобрать(з) for з in инс.службы_из_копий()}
    р = записи["seo-regular-daily.service"]
    цели = {з["разрешён"] for з in р["догружаемые"]}
    assert "automation/local/editor-day-report.py" in цели, р["догружаемые"]


# --- Пары «писатель — читатель»: межслужебный класс (находка линии SEO) ------

def _служба(имя, *, состояние=None, переменные=None, юнит=None):
    return {"служба": имя,
            "неимпортные": {"состояние": list(состояние or {}),
                            "переменные_состояния": переменные or {}},
            "состояние_состава": состояние or {},
            "путевые_поля_юнита": юнит or {}}


def test_один_корень_у_всех_это_согласовано():
    пары = инс.общие_файлы([
        _служба("а.service", состояние={"var/общее/файл.json": "SEO_STATE_ROOT"}),
        _служба("б.service", состояние={"var/общее/файл.json": "SEO_STATE_ROOT"})])
    assert [п["исход"] for п in пары] == ["согласованы"]


def test_разные_названные_корни_это_находка():
    """Единственный случай, который считается находкой.

    Так ломались все четыре пары, названные линией SEO: файл остаётся на
    месте, обе службы работают, а связь между ними исчезает молча.
    """
    пары = инс.общие_файлы([
        _служба("писатель.service", состояние={"var/общее/токен": "FACTORY_ROOT"}),
        _служба("читатель.service", состояние={"var/общее/токен": "SEO_STATE_ROOT"})])
    assert [п["исход"] for п in пары] == ["расходятся"]
    assert "FACTORY_ROOT" in пары[0]["почему"] and "SEO_STATE_ROOT" in пары[0]["почему"]


def test_корень_назван_не_у_всех_это_не_измерено():
    """Третий исход обязателен: иначе карта объявляла 20 расхождений из 21."""
    пары = инс.общие_файлы([
        _служба("а.service", состояние={"var/общее/файл.json": "SEO_STATE_ROOT"}),
        _служба("б.service", состояние={"var/общее/файл.json": ""})])
    assert [п["исход"] for п in пары] == ["не измерено"]


def test_способ_обращения_расхождением_не_считается():
    """«SEO_STATE_ROOT» и «SEO_STATE_ROOT (paths.state)» — один корень."""
    пары = инс.общие_файлы([
        _служба("а.service", состояние={"var/о/ф.json": "SEO_STATE_ROOT (paths.state)"}),
        _служба("б.service", состояние={"var/о/ф.json": "SEO_STATE_ROOT"})])
    assert [п["исход"] for п in пары] == ["согласованы"]


def test_путь_из_юнита_остаётся_отдельным_корнем():
    """Путь, записанный в юните, при переносе состояния сам не переедет."""
    пары = инс.общие_файлы([
        _служба("кабинет.service", юнит={"ExecStartPre": ["/дерево/var/analytics/x"]}),
        _служба("читатель.service", состояние={"var/analytics/x": "SEO_STATE_ROOT"})])
    assert [п["исход"] for п in пары] == ["расходятся"]
    assert "юнит:ExecStartPre" in пары[0]["почему"]


def test_обрывки_текста_путями_не_считаются():
    """`var/`, `var/.` и `var/что-то.` — хвосты предложений, а не пути."""
    assert инс._путь_опрятно("var/") == ""
    assert инс._путь_опрятно("var/.") == ""
    assert инс._путь_опрятно("var/analytics/.") == "var/analytics"
    assert инс._путь_опрятно("var/seo-regular/hourly.") == "var/seo-regular/hourly"
    assert инс._путь_опрятно("var/seo-tech/next.json") == "var/seo-tech/next.json"


def test_доступ_через_функцию_корней_распознаётся(tmp_path):
    """`paths.state("var", …)` — параметризация: литерала пути в тексте нет."""
    файл = tmp_path / "модуль.py"
    файл.write_text('ПУТЬ = paths.state("var", "analytics", "cabinet-latest.json")\n',
                    encoding="utf-8")
    найдено = инс.состояние_состава({файл}, tmp_path)
    assert найдено.get("var/analytics/cabinet-latest.json", "").startswith("SEO_STATE_ROOT")


def test_корень_атрибутом_объекта_распознаётся(tmp_path):
    """`PATHS.root / "migrations" / "0002_x.py"` — корень приходит из другого модуля.

    Найдено 26.10 на пилоте переноса: factory/ratings/store.py грузит три
    миграции именно так, присваивания от __file__ в этом файле нет, и прежний
    разбор путь не видел вовсе — миграции не попадали в выпуск.
    """
    (tmp_path / "migrations").mkdir()
    (tmp_path / "migrations" / "0002_x.py").write_text("", encoding="utf-8")
    файл = tmp_path / "store.py"
    файл.write_text('from factory.paths import PATHS\n'
                    'путь = PATHS.root / "migrations" / "0002_x.py"\n', encoding="utf-8")
    найдено = инс.догружаемые({файл}, tmp_path)
    assert [(з["цель"], з["разрешён"]) for з in найдено] == [
        ("0002_x.py", "migrations/0002_x.py")]


def test_пилот_несёт_свои_миграции_в_составе():
    """Состав community-ratings-monitor обязан включать три файла миграций."""
    записи = {з["служба"]: инс.разобрать(з) for з in инс.службы_из_копий()}
    цели = {з["разрешён"] for з in записи["community-ratings-monitor.service"]["догружаемые"]}
    assert цели == {"migrations/0002_ratings_ingestion.py",
                    "migrations/0003_ratings_local_amd.py",
                    "migrations/0004_ratings_absence.py"}, цели
