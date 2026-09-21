"""Guard арендатора Lords обязан ОТКАЗЫВАТЬ, а не только разрешать.

Проверка, которая никогда не срабатывала, ничего не защищает. Поэтому здесь
почти все тесты отрицательные: каждому запрету соответствует случай, в котором
guard обязан закрыться и назвать причину.

Guard работает по принципу «разрешено только перечисленное». Значит достаточно
подсунуть ему неизвестную ветку, путь, идентификатор или каталог вывода — и он
должен отказать, не рассуждая, опасно это или нет.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ТЕНАНТ = КОРЕНЬ / "factory" / "templates" / "lords" / "tenant"


def _загрузить():
    spec = importlib.util.spec_from_file_location("lords_guard", ТЕНАНТ / "guard.py")
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


guard = _загрузить()


@pytest.fixture(scope="module")
def контракт() -> dict:
    return json.loads((ТЕНАНТ / "lords-tenant.json").read_text(encoding="utf-8"))


@pytest.fixture
def маркер() -> pathlib.Path:
    return КОРЕНЬ / ".lords-tenant"


def проверить(контракт, маркер, изменения):
    return guard.проверить(КОРЕНЬ, контракт, маркер, изменения)


# --- положительный случай ----------------------------------------------------

def test_own_paths_are_allowed(контракт, маркер):
    проверки = проверить(контракт, маркер, [
        "factory/templates/lords/T001-forest-cinema-stage/tokens.css",
        "artifacts/evidence/lords-50-template-factory-01/FINAL_REPORT.json",
        "tests/lords_factory/test_tenant_guard.py",
    ])
    assert проверки["branch"].startswith("claude/lords-")
    assert проверки["production_commands"] == "нет"


# --- отрицательные случаи ----------------------------------------------------

@pytest.mark.parametrize("путь,чего_касается", [
    ("config/site-profiles/lords-01.json", "чужой source path"),
    ("automation/host/lords-frontend.py", "живой рантайм"),
    ("factory/lords/nova_publish.py", "чужой модуль"),
    ("artifacts/evidence/lords-cursor-reconciliation-01/HANDOFF.json", "чужой artifact path"),
    ("docs/OPERATIONS.md", "путь вне контракта"),
    ("seo_operator/hookguard.py", "чужой контур"),
])
def test_foreign_paths_are_denied(контракт, маркер, путь, чего_касается):
    with pytest.raises(guard.Отказ) as отказ:
        проверить(контракт, маркер, [путь])
    assert "вне контракта" in str(отказ.value), f"{чего_касается}: причина не названа"


def test_foreign_branch_is_denied(контракт, маркер):
    подделка = json.loads(json.dumps(контракт))
    подделка["allowed"]["branch_prefix"] = "cursor/"
    with pytest.raises(guard.Отказ) as отказ:
        guard.проверить(КОРЕНЬ, подделка, маркер, [])
    assert "вне префикса" in str(отказ.value)


def test_branch_not_listed_is_denied(контракт, маркер):
    подделка = json.loads(json.dumps(контракт))
    подделка["allowed"]["branches"] = ["claude/lords-something-else"]
    with pytest.raises(guard.Отказ) as отказ:
        guard.проверить(КОРЕНЬ, подделка, маркер, [])
    assert "не перечислена" in str(отказ.value)


def test_foreign_worktree_is_denied(контракт, маркер):
    подделка = json.loads(json.dumps(контракт))
    подделка["allowed"]["worktrees"] = ["/home/claude/wt-somewhere-else"]
    with pytest.raises(guard.Отказ) as отказ:
        guard.проверить(КОРЕНЬ, подделка, маркер, [])
    assert "не входит в разрешённые" in str(отказ.value)


def test_missing_marker_is_denied(контракт, tmp_path):
    with pytest.raises(guard.Отказ) as отказ:
        guard.проверить(КОРЕНЬ, контракт, tmp_path / "нет-такого", [])
    assert "маркера арендатора нет" in str(отказ.value)


def test_marker_declaring_another_tenant_is_denied(контракт, tmp_path):
    чужой = tmp_path / ".lords-tenant"
    чужой.write_text(json.dumps({"tenant": "другой", "branch": "claude/lords-50-template-factory-01",
                                 "worktree": str(КОРЕНЬ)}), encoding="utf-8")
    with pytest.raises(guard.Отказ) as отказ:
        guard.проверить(КОРЕНЬ, контракт, чужой, [])
    assert "объявляет арендатора" in str(отказ.value)


def test_marker_declaring_another_branch_is_denied(контракт, tmp_path):
    чужой = tmp_path / ".lords-tenant"
    чужой.write_text(json.dumps({"tenant": "lords", "branch": "claude/lords-другая",
                                 "worktree": str(КОРЕНЬ)}), encoding="utf-8")
    with pytest.raises(guard.Отказ) as отказ:
        guard.проверить(КОРЕНЬ, контракт, чужой, [])
    assert "объявляет ветку" in str(отказ.value)


@pytest.mark.parametrize("плохой_id", ["T051", "T000", "T999", "T100"])
def test_template_id_outside_range_is_denied(контракт, маркер, плохой_id):
    with pytest.raises(guard.Отказ) as отказ:
        проверить(контракт, маркер, [f"factory/templates/lords/{плохой_id}-новый/tokens.css"])
    assert "вне диапазона" in str(отказ.value)


def test_cross_tenant_import_is_denied(контракт, маркер, tmp_path):
    """Файл внутри Lords, но обращающийся к чужому контуру, guard не пропустит."""
    относительный = "factory/templates/lords/T001-forest-cinema-stage/_проверка_импорта.py"
    файл = КОРЕНЬ / относительный
    файл.write_text("import json\n# обращение к каталогу animedia\n", encoding="utf-8")
    try:
        with pytest.raises(guard.Отказ) as отказ:
            проверить(контракт, маркер, [относительный])
        assert "чужому контуру" in str(отказ.value)
    finally:
        файл.unlink()


@pytest.mark.parametrize("строка,ожидание", [
    ("systemctl restart что-нибудь\n", "команда systemctl"),
    ("sudo -n что-нибудь\n", "команда sudo"),
    ("путь /srv/lords/.frontend/файл\n", "путь production"),
    ("certbot renew\n", "команда certbot"),
])
def test_production_commands_and_paths_are_denied(контракт, маркер, строка, ожидание):
    относительный = "factory/templates/lords/T002-forest-cinema-columns/_проверка_команд.sh"
    файл = КОРЕНЬ / относительный
    файл.write_text(строка, encoding="utf-8")
    try:
        with pytest.raises(guard.Отказ) as отказ:
            проверить(контракт, маркер, [относительный])
        assert ожидание in str(отказ.value)
    finally:
        файл.unlink()


@pytest.mark.parametrize("вывод", [
    "artifacts/evidence/другой-этап/отчёт.json",
    "var/чужой-вывод/файл.json",
])
def test_output_outside_declared_dirs_is_denied(контракт, маркер, вывод):
    with pytest.raises(guard.Отказ) as отказ:
        проверить(контракт, маркер, [вывод])
    # Путь отсекается либо как вне контракта, либо как вывод вне каталогов.
    assert "вне контракта" in str(отказ.value) or "вне разрешённых каталогов" in str(отказ.value)


def test_index_lock_is_treated_as_foreign(контракт, маркер):
    # Замок ищется в настоящем git-dir этого worktree, а не в `корень/.git`:
    # в связанном worktree это файл-ссылка, и класть туда index.lock некуда.
    git_dir = pathlib.Path(subprocess.check_output(
        ["git", "rev-parse", "--absolute-git-dir"], cwd=str(КОРЕНЬ), text=True).strip())
    замок = git_dir / "index.lock"
    замок.write_text("", encoding="utf-8")
    try:
        with pytest.raises(guard.Отказ) as отказ:
            проверить(контракт, маркер, [])
        assert "блокировка индекса" in str(отказ.value)
    finally:
        замок.unlink()


def test_status_parsing_keeps_leading_space(контракт, маркер):
    """Путь из `git status` не должен терять первый символ.

    Ошибка была настоящей: `_git` обрезал пробелы всей выдачи и съедал ведущий
    пробел ПЕРВОЙ строки статуса. Путь сдвигался на символ, «factory/…»
    становилось «actory/…», и guard объявлял собственный путь чужим.
    """
    сырое = guard._git("status", "--porcelain=v1", cwd=КОРЕНЬ, сырой=True)
    строки = [с for с in сырое.splitlines() if с.strip()]
    if not строки:
        pytest.skip("дерево чисто — разбирать нечего")
    пути = [с[3:].strip() for с in строки]
    assert all(not п.startswith(("actory/", "ests/", "rtifacts/", "in/")) for п in пути), \
        f"путь потерял первый символ: {пути[:3]}"
    assert any(п.startswith(("factory/", "tests/", "artifacts/", "bin/", ".lords-tenant"))
               for п in пути), f"ни один путь не выглядит корректным: {пути[:3]}"


# --- политика статусов --------------------------------------------------------

def test_agent_may_not_promote_status(контракт):
    политика = контракт["template_status_policy"]
    assert политика["may_agent_set_assignable"] is False
    assert политика["may_agent_set_production_ready"] is False
    assert политика["current"] == "TECHNICAL_CANDIDATE"


def test_pool_has_no_promoted_statuses():
    пул = json.loads((КОРЕНЬ / "factory" / "templates" / "lords" / "registry"
                      / "template-pool.json").read_text(encoding="utf-8"))
    статусы = {т["status"] for т in пул["templates"]}
    assert статусы == {"TECHNICAL_CANDIDATE"}, f"в пуле есть повышенные статусы: {статусы}"


def test_guard_cli_allows_current_state():
    р = subprocess.run(
        ["python3", str(ТЕНАНТ / "guard.py"), "--stage", "тест", "--worktree", str(КОРЕНЬ)],
        capture_output=True, text=True, cwd=str(КОРЕНЬ))
    assert р.returncode == 0, р.stdout + р.stderr
    assert '"GUARD": "ALLOW"' in р.stdout
