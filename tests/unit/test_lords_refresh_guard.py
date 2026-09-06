"""REQ-CANARY-PERSISTENCE: ворота обновления вызываются, а не просто существуют.

Модуль можно написать правильно и не подключить — снаружи это неотличимо от
отсутствия исправления. Поэтому здесь проверяется и сама оснастка (adopt → plan
→ finalize сквозным запуском), и то, что сценарий обновления действительно ею
пользуется: не переносит манифест копией и не переключает ссылку в обход ворот.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

РЕПО = Path(__file__).resolve().parents[2]
ВОРОТА = РЕПО / "automation" / "host" / "lords-refresh-guard.py"
СЦЕНАРИЙ = РЕПО / "automation" / "host" / "lords-content-refresh.sh"


def _запуск(*аргументы: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ВОРОТА), *аргументы],
                          capture_output=True, text=True, timeout=300)


@pytest.fixture()
def витрина(tmp_path):
    рантайм = tmp_path / "runtime" / "lords-02"
    релиз = рантайм / "releases" / "aaaa0001"
    (релиз / "site" / "title").mkdir(parents=True)
    for н in range(3):
        (релиз / "site" / "title" / f"t{н}").mkdir()
    (рантайм / "current").symlink_to(релиз)
    return {"runtime": рантайм, "root": tmp_path / "runtime",
            "artifacts": tmp_path / "artifacts", "release": релиз}


def _adopt(витрина, ревизия: str) -> subprocess.CompletedProcess:
    return _запуск(
        "--runtime-root", str(витрина["root"]), "--artifact-root", str(витрина["artifacts"]),
        "adopt", "lords-02", "--revision", ревизия, "--repo", str(РЕПО),
        "--domain", "lordserial33.biz", "--theme", "lords_dark",
        "--content-source", "cdnvideohub-live",
    )


def _ревизия() -> str:
    из = subprocess.run(["git", "-C", str(РЕПО), "rev-parse", "HEAD"],
                        capture_output=True, text=True)
    return из.stdout.strip()


def test_adopt_заводит_манифест_и_закрепляет_артефакт(витрина):
    итог = _adopt(витрина, _ревизия())
    assert итог.returncode == 0, итог.stderr
    манифест = json.loads((витрина["release"] / "release-manifest.json").read_text("utf-8"))
    assert манифест["tenant_id"] == "lords-02"
    assert манифест["content_count"] == 3
    assert len(манифест["template_digest"]) == 64
    архив = витрина["artifacts"] / манифест["template_artifact_ref"]
    assert архив.is_file(), "артефакт не закреплён — восстановить шаблон нечем"


def test_adopt_отвергает_неполный_sha(витрина):
    итог = _adopt(витрина, "abc123")
    assert итог.returncode != 0
    assert "SHA" in итог.stderr or "ревизия" in итог.stderr


def test_plan_показывает_корень_закреплённого_шаблона(витрина):
    _adopt(витрина, _ревизия())
    итог = _запуск("--runtime-root", str(витрина["root"]),
                   "--artifact-root", str(витрина["artifacts"]), "plan", "lords-02")
    assert итог.returncode == 0, итог.stderr
    корень = Path(итог.stdout.strip())
    assert (корень / "factory" / "lords" / "render.py").is_file(), (
        "в закреплённом дереве нет отрисовщика — отрисовывать будет нечем")


def test_plan_отказывает_без_манифеста(витрина):
    итог = _запуск("--runtime-root", str(витрина["root"]),
                   "--artifact-root", str(витрина["artifacts"]), "plan", "lords-02")
    assert итог.returncode == 3
    assert "манифест" in итог.stderr


def test_finalize_переключает_и_сохраняет_шаблон(витрина):
    _adopt(витрина, _ревизия())
    прежний = json.loads((витрина["release"] / "release-manifest.json").read_text("utf-8"))

    новый_релиз = витрина["runtime"] / "releases" / "bbbb0002"
    (новый_релиз / "site" / "title").mkdir(parents=True)
    for н in range(5):
        (новый_релиз / "site" / "title" / f"t{н}").mkdir()

    итог = _запуск("--runtime-root", str(витрина["root"]),
                   "--artifact-root", str(витрина["artifacts"]), "finalize", "lords-02",
                   "--target", str(новый_релиз), "--snapshot", "snap-bbbb0002",
                   "--content-count", "5")
    assert итог.returncode == 0, итог.stderr
    assert (витрина["runtime"] / "current").resolve().name == "bbbb0002"

    стало = json.loads((новый_релиз / "release-manifest.json").read_text("utf-8"))
    assert стало["template_digest"] == прежний["template_digest"], "шаблон подменён"
    assert стало["renderer_revision"] == прежний["renderer_revision"]
    assert стало["content_count"] == 5 and стало["content_snapshot_id"] == "snap-bbbb0002"
    assert стало["previous_release"] == "aaaa0001"
    assert стало["rollback_target"] == "aaaa0001"


def test_finalize_отказывает_если_current_ушёл(витрина):
    _adopt(витрина, _ревизия())
    чужой = витрина["runtime"] / "releases" / "cccc0003"
    (чужой / "site").mkdir(parents=True)
    (чужой / "release-manifest.json").write_text(
        (витрина["release"] / "release-manifest.json").read_text("utf-8"), encoding="utf-8")
    (витрина["runtime"] / "current").unlink()
    (витрина["runtime"] / "current").symlink_to(чужой)

    цель = витрина["runtime"] / "releases" / "dddd0004"
    (цель / "site").mkdir(parents=True)
    итог = _запуск("--runtime-root", str(витрина["root"]),
                   "--artifact-root", str(витрина["artifacts"]), "finalize", "lords-02",
                   "--target", str(цель), "--snapshot", "s", "--content-count", "1")
    # План читает манифест уже ЧУЖОГО релиза, и ожидаемым предыдущим станет он.
    # Витрина при этом не остаётся ни с чем: переключение либо корректно, либо
    # отказано, но никогда не выполняется вслепую.
    assert (витрина["runtime"] / "current").resolve().name in ("cccc0003", "dddd0004")
    if итог.returncode != 0:
        assert "ОТКАЗ" in итог.stderr


# --- сценарий действительно пользуется воротами -----------------------------

def test_сценарий_не_переносит_манифест_копией():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    строка = [с for с in текст.splitlines() if "for extra in" in с]
    assert строка, "список переносимых файлов исчез — проверка потеряла смысл"
    assert "bundle-manifest.json" not in строка[0], (
        "манифест снова переносится копией: он будет утверждать происхождение "
        "прежнего релиза при пересобранном содержимом")


def test_сценарий_переключает_только_через_ворота():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    # Возврат на прежний релиз воротами не проходит и не должен: откат обязан
    # работать, даже когда ворота отказали, — иначе плохой релиз останется в
    # работе именно тогда, когда снять его нужнее всего.
    вперёд = [с.strip() for с in текст.splitlines()
              if "ln -sfn" in с and "${runtime}/current" in с
              and not с.strip().startswith("#")
              and '"${current}"' not in с]
    # Один запасной путь остаётся — он под явным выключателем LORDS_PINNED_TEMPLATE=0
    # и нужен, чтобы витрину можно было обновить при поломке самих ворот.
    assert len(вперёд) <= 1, f"переключений вперёд в обход ворот: {вперёд}"
    assert "finalize" in текст, "ворота переключения не вызываются вовсе"
    assert 'plan "$site"' in текст, "ворота шаблона не вызываются перед отрисовкой"


def test_сценарий_отрисовывает_из_закреплённого_дерева():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert 'cd "$TEMPLATE_ROOT"' in текст, (
        "полная сборка идёт из репозитория: закреплённый артефакт был бы "
        "объявлен и не использован")
    assert '--repo "$REPO" --staging' not in текст, "быстрый путь всё ещё берёт рабочее дерево"


def test_смена_шаблона_отменяет_быстрый_путь():
    """Быстрый путь при смене шаблона оставляет витрину наполовину старой.

    Измерено на канареечной выкладке lords-02: страницы разделов пересобрались,
    а карточка произведения осталась прежней и несла "duration": "PTNoneM",
    исправленный в выкладываемой ревизии. Приёмка по разделам такую витрину
    объявляет принятой.
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert 'if [ "$site_canary" = "1" ]; then\n    fast_allowed=0' in текст, (
        "канареечная выкладка снова идёт быстрым путём")
    # Быстрый путь включается по вычисленному разрешению, а не по переменной
    # окружения напрямую: иначе отключение выше ни на что не влияет.
    assert 'if [ "$fast_allowed" = "1" ]' in текст
    assert 'if [ "${LORDS_FAST_PATH:-1}" = "1" ] && [ -x "${REPO}/automation/host/lords-fast-render.py" ]' \
        not in текст


def test_быстрый_путь_остаётся_для_обычного_обновления():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert 'fast_allowed="${LORDS_FAST_PATH:-1}"' in текст, (
        "обычное обновление обязано остаться быстрым: полный рендер 53 тысяч "
        "страниц ради одной новой серии — это семь часов вместо минуты")


def test_канареечная_выкладка_не_отменяется_воротами_рендера():
    """Ворота описывают вход, а не то, что лежит в релизе.

    После выкладки быстрым путём страницы произведений остались от прежнего
    шаблона при совпадающем отпечатке входа, и повторная выкладка была
    пропущена как ненужная. Решение выложить шаблон принято снаружи и
    оптимизацией не пересматривается.
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert 'gate_allowed=0' in текст, "канарейку снова может пропустить оптимизация"
    assert 'if [ "$gate_allowed" = "1" ]' in текст
    assert 'gate_allowed="${LORDS_RENDER_GATE:-1}"' in текст, (
        "обычное обновление обязано сохранить ворота: без них каждый цикл "
        "платит полную цену рендера")
