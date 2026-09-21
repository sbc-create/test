"""Guard контура ANIMEDIA: отказы обязаны быть, а не подразумеваться.

Тесты здесь — в основном отрицательные. Положительный случай один, потому что
цена ошибки несимметрична: пропущенный запрет меняет чужой проект и виден
только после перезапуска, а лишний отказ стоит одной строки в отчёте.

Окружение (worktree, ветка, HEAD) подаётся наблюдениями: иначе пришлось бы
создавать репозиторий другого контура ради проверки, что guard его не пустит.
Боевой путь читает git — это проверено отдельным тестом.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ / "automation" / "host"))

import animedia_tenant_guard as guard  # noqa: E402

СВОЙ = {"toplevel": "/home/claude/wt-animedia-original-parity-01",
        "branch": "claude/animedia-original-parity-01",
        "head": "b38ec506c26c048792916af9830e675536626ed6",
        "git_dir": "/home/claude/wt-animedia-original-parity-01/.git",
        "status_porcelain": []}


def н(**правки) -> dict:
    свой = dict(СВОЙ)
    свой.update(правки)
    return свой


def отказ(**kwargs) -> str:
    kwargs.setdefault("наблюдения", н())
    with pytest.raises(guard.Отказ) as e:
        guard.проверить(КОРЕНЬ, **kwargs)
    return str(e.value)


# --- положительный случай -----------------------------------------------------

def test_своя_ветка_свои_пути_и_свои_адресаты_разрешены():
    факты = guard.проверить(
        КОРЕНЬ, стадия="before-write", наблюдения=н(),
        пути=["automation/host/animedia-frontend.py",
              "factory/animedia/view.py",
              "artifacts/evidence/animedia-original-parity-01/01/X.json"],
        домен="animedia.icu", профиль="animedia-icu",
        служба="nova-animedia-01.service", template_id="animedia-original-parity",
        вывод="artifacts/evidence/animedia-original-parity-01/02")
    assert факты["allowed"] is True
    assert факты["tenant"] == "animedia"


# --- десять обязательных отказов ---------------------------------------------

def test_отказ_переход_на_ветку_другого_контура():
    assert "ветка вне контура" in отказ(
        стадия="before-write", наблюдения=н(branch="claude/neighbour-tpl-001"))


def test_отказ_запись_в_чужой_worktree():
    причина = отказ(стадия="before-write",
                    наблюдения=н(toplevel="/home/claude/wt-neighbour-01"))
    assert "worktree вне контура" in причина


def test_отказ_изменение_чужого_манифеста():
    assert "путь рантайма вне контура" in отказ(
        стадия="before-manifest",
        пути=["/srv/lords/.frontend/template-manifest-neighbour-02.json"])


def test_отказ_адресация_чужой_службы():
    assert "служба вне контура" in отказ(
        стадия="before-assignment", служба="nova-neighbour-01.service")


def test_отказ_сборка_артефакта_из_чужого_entrypoint():
    причина = отказ(стадия="before-artifact",
                    пути=["automation/host/lords-frontend.py"])
    assert "только для чтения" in причина or "вне разрешённых" in причина


def test_отказ_импорт_чужого_изменяемого_рантайма():
    assert "cross-tenant import" in отказ(
        стадия="before-build", импорты=["lords_frontend"])


def test_отказ_использование_чужих_assets():
    assert "вне разрешённых контуру" in отказ(
        стадия="before-write", пути=["themes/neighbour/assets/logo.svg"])


def test_отказ_чужие_staged_файлы_в_коммите():
    причина = отказ(стадия="before-commit",
                    наблюдения=н(status_porcelain=[
                        "M  automation/host/animedia-frontend.py",
                        "M  config/site-profiles/neighbour-site.json"]))
    assert "вне разрешённых контуру" in причина


def test_отказ_изменение_dns_tls_или_индексации():
    assert "DNS/TLS/индексации" in отказ(
        стадия="before-write", команда="certbot renew --force-renewal")
    assert "DNS/TLS/индексации" in отказ(
        стадия="before-write", команда="sed -i s/noindex/index/ robots.txt")


def test_отказ_массовый_выкат():
    причина = отказ(стадия="before-assignment",
                    цели_выката=["animedia-01", "animedia-02"])
    assert "массовый выкат запрещён" in причина
    причина2 = отказ(
        стадия="before-write",
        команда=("systemctl restart nova-animedia-01.service && "
                 "systemctl restart nova-animedia-02.service"))
    assert "массовый выкат запрещён" in причина2


# --- дополнительные запреты, названные контрактом ----------------------------

def test_отказ_самостоятельный_systemctl():
    assert "systemctl из сессии запрещён" in отказ(
        стадия="before-write", команда="systemctl restart nova-animedia-01.service")


def test_отказ_опасные_операции_с_историей():
    for команда, признак in (("git reset --hard origin/main", "git reset --hard"),
                             ("git branch -f claude/animedia-x HEAD", "git branch -f"),
                             ("git push --force origin", "push --force")):
        assert признак in отказ(стадия="before-write", команда=команда)


def test_отказ_неизвестная_стадия():
    with pytest.raises(guard.Отказ):
        guard.проверить(КОРЕНЬ, стадия="потом-как-нибудь", наблюдения=н())


def test_отказ_неизвестные_домен_профиль_и_template_id():
    assert "домен вне контура" in отказ(стадия="before-assignment",
                                        домен="animedia.example")
    assert "профиль вне контура" in отказ(стадия="before-assignment",
                                          профиль="animedia-unknown")
    assert "template ID вне контура" in отказ(стадия="before-assignment",
                                              template_id="animedia-whatever")


def test_отказ_заблокированный_worktree(tmp_path):
    (tmp_path / "locked").write_text("другой владелец", encoding="utf-8")
    assert "worktree заблокирован" in отказ(
        стадия="before-write", наблюдения=н(git_dir=str(tmp_path)))


def test_отказ_каталог_вывода_вне_контура():
    assert "каталог вывода вне контура" in отказ(
        стадия="before-report", вывод="artifacts/evidence/neighbour-stage-01")


# --- fail closed --------------------------------------------------------------

def test_guard_отказывает_без_контракта(tmp_path):
    """Нет контракта — нет разрешения. Guard, пропускающий всё, не guard."""
    with pytest.raises(guard.Отказ) as e:
        guard.проверить(tmp_path, стадия="before-write", наблюдения=н())
    assert "контракт изоляции не найден" in str(e.value)


def test_контракт_обязан_объявлять_fail_closed(tmp_path):
    (tmp_path / "config" / "animedia").mkdir(parents=True)
    (tmp_path / "config" / "animedia" / "TENANT_SCOPE.yaml").write_text(
        "schema_version: 1\ntenant: animedia\nmode: permissive\n", encoding="utf-8")
    with pytest.raises(guard.Отказ) as e:
        guard.проверить(tmp_path, стадия="before-write", наблюдения=н())
    assert "fail_closed" in str(e.value)


def test_контракт_чужого_контура_не_принимается(tmp_path):
    (tmp_path / "config" / "animedia").mkdir(parents=True)
    (tmp_path / "config" / "animedia" / "TENANT_SCOPE.yaml").write_text(
        "schema_version: 1\ntenant: neighbour\nmode: fail_closed\n", encoding="utf-8")
    with pytest.raises(guard.Отказ) as e:
        guard.проверить(tmp_path, стадия="before-write", наблюдения=н())
    assert "tenant: animedia" in str(e.value)


# --- боевой путь --------------------------------------------------------------

def test_наблюдения_по_умолчанию_читают_git():
    н_ = guard.наблюдать(КОРЕНЬ)
    assert н_["branch"].startswith("claude/animedia-")
    assert len(н_["head"]) == 40
    assert н_["toplevel"] == str(КОРЕНЬ)


def test_cli_отказывает_кодом_1_и_печатает_причину():
    p = subprocess.run(
        [sys.executable, str(КОРЕНЬ / "automation/host/animedia_tenant_guard.py"),
         "--stage", "before-assignment", "--service", "nova-neighbour-01.service"],
        cwd=str(КОРЕНЬ), capture_output=True, text=True)
    assert p.returncode == 1
    assert "GUARD=DENY" in p.stdout
    assert "служба вне контура" in p.stdout


def test_cli_разрешает_кодом_0():
    p = subprocess.run(
        [sys.executable, str(КОРЕНЬ / "automation/host/animedia_tenant_guard.py"),
         "--stage", "before-write", "--paths", "factory/animedia/view.py"],
        cwd=str(КОРЕНЬ), capture_output=True, text=True)
    assert p.returncode == 0, p.stdout
    assert "GUARD=ALLOW" in p.stdout
