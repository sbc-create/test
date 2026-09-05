"""REQ-CORE-CANARY-01: выкладка одной витрины и ничего сверх неё.

Режим появился из задачи, которую существующая оснастка не решает:
`automation/host/lords-staging-apply.sh` применяет конфигурацию всем трём
витринам разом (`[[ ${#SITES[@]} -eq 3 ]] || die`) и попутно переставляет
nginx, сертификаты и юниты. Поэтапной выкладки — одна витрина, наблюдение,
затем следующая — этим сценарием выразить нельзя.

Проверяется здесь не «работает ли выкладка», а пять свойств, каждое из
которых, будучи нарушенным, превращает canary в обычный массовый выкат:

1. **Одна витрина.** Ссылки соседних сайтов обязаны остаться нетронутыми —
   не «обычно остаются», а быть проверенными после каждого прогона.
2. **Отпечаток сверяется до мутации.** Выкатывать «текущее дерево» вместо
   названного артефакта — самый тихий способ выложить не то.
3. **Здоровье до переключения.** Релиз, который не отвечает, не должен
   получать трафик; проверка обязана идти до подмены ссылки, а не после.
4. **Атомарность.** В любой момент `current` указывает на существующий
   релиз. Промежуточного состояния «ссылки нет» быть не может.
5. **Отказ до первой мутации.** Нет прав, не совпал отпечаток, нет предыдущего
   релиза для отката — всё это обязано останавливать до записи, а не на
   середине.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from factory.lords import canary


DIGEST = "a" * 64


def make_runtime(tmp_path: Path, sites=("lords-01", "lords-02", "lords-03")) -> Path:
    """Поддельный рантайм той же формы, что боевой: releases/<id> + ссылка current."""
    root = tmp_path / "lords"
    for index, site in enumerate(sites, start=1):
        base = root / site
        old = base / "releases" / f"old{index:02d}"
        (old / "site").mkdir(parents=True)
        (old / "site" / "index.html").write_text(f"<html>{site} old</html>", encoding="utf-8")
        (old / "serve.py").write_text("# runtime\n", encoding="utf-8")
        (base / "current").symlink_to(old, target_is_directory=True)
        (base / "data").mkdir(exist_ok=True)
    return root


def payload(tmp_path: Path, marker: str = "new") -> Path:
    """Собранный сайт, который выкладывается. Форма важнее содержимого."""
    src = tmp_path / "built"
    (src / "site").mkdir(parents=True, exist_ok=True)
    (src / "site" / "index.html").write_text(f"<html>{marker}</html>", encoding="utf-8")
    (src / "serve.py").write_text("# runtime\n", encoding="utf-8")
    return src


def targets(root: Path) -> dict[str, str]:
    """Куда указывает ссылка каждой витрины. Основа проверки «одна витрина»."""
    return {
        p.name: os.path.basename(os.readlink(p / "current"))
        for p in sorted(root.iterdir()) if (p / "current").is_symlink()
    }


class TestPlanRefusesBeforeMutation:
    def test_отпечаток_не_совпал(self, tmp_path):
        root = make_runtime(tmp_path)
        before = targets(root)
        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest="b" * 64, payload=payload(tmp_path))
        assert not plan.allowed
        assert any("отпечаток" in r for r in plan.refusals), plan.refusals
        assert targets(root) == before

    def test_каталог_витрины_недоступен_на_запись(self, tmp_path):
        root = make_runtime(tmp_path)
        site = root / "lords-01"
        site.chmod(0o500)
        try:
            plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                               expect_template_digest=DIGEST, payload=payload(tmp_path))
            assert not plan.allowed
            assert any("права" in r for r in plan.refusals), plan.refusals
        finally:
            site.chmod(0o755)

    def test_неизвестная_витрина(self, tmp_path):
        root = make_runtime(tmp_path)
        plan = canary.plan("lords-99", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        assert not plan.allowed
        assert any("нет каталога" in r for r in plan.refusals), plan.refusals

    def test_отказ_не_пишет_ничего(self, tmp_path):
        root = make_runtime(tmp_path)
        snapshot = {p: sorted(os.listdir(p)) for p in
                    [root / s / "releases" for s in ("lords-01", "lords-02", "lords-03")]}
        canary.plan("lords-01", root=root, template_digest=DIGEST,
                    expect_template_digest="b" * 64, payload=payload(tmp_path))
        assert {p: sorted(os.listdir(p)) for p in snapshot} == snapshot


class TestApplyTouchesOneSite:
    def test_соседние_витрины_не_тронуты(self, tmp_path):
        root = make_runtime(tmp_path)
        before = targets(root)
        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        assert plan.allowed, plan.refusals
        result = canary.apply(plan, health=lambda directory: (True, "ok"))
        assert result.switched
        after = targets(root)
        assert after["lords-01"] != before["lords-01"], "витрина не переключилась"
        assert after["lords-02"] == before["lords-02"], "тронута соседняя витрина"
        assert after["lords-03"] == before["lords-03"], "тронута соседняя витрина"

    def test_запись_только_внутри_своей_витрины(self, tmp_path):
        root = make_runtime(tmp_path)
        others = {s: sorted((root / s / "releases").iterdir()) for s in ("lords-02", "lords-03")}
        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        canary.apply(plan, health=lambda directory: (True, "ok"))
        for site, listing in others.items():
            assert sorted((root / site / "releases").iterdir()) == listing


class TestHealthBeforeSwitch:
    def test_неотвечающий_релиз_не_получает_трафик(self, tmp_path):
        root = make_runtime(tmp_path)
        before = targets(root)
        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        result = canary.apply(plan, health=lambda directory: (False, "502 на главной"))
        assert not result.switched
        assert "502" in result.detail
        assert targets(root) == before, "ссылка переключена вопреки провалу проверки"

    def test_проверка_идёт_по_разложенному_релизу_а_не_по_исходнику(self, tmp_path):
        root = make_runtime(tmp_path)
        seen: list[Path] = []

        def health(directory: Path):
            seen.append(directory)
            return True, "ok"

        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        canary.apply(plan, health=health)
        assert seen, "проверка здоровья не вызывалась"
        # Проверять исходник бессмысленно: трафик пойдёт в разложенный каталог,
        # и расхождение между ними — ровно то, что проверка обязана заметить.
        assert seen[0] == plan.release_dir


class TestAtomicSwitch:
    def test_ссылка_всегда_указывает_на_существующий_релиз(self, tmp_path):
        root = make_runtime(tmp_path)
        link = root / "lords-01" / "current"
        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        canary.apply(plan, health=lambda directory: (True, "ok"))
        assert link.is_symlink()
        assert link.resolve().is_dir()
        assert (link / "site" / "index.html").read_text(encoding="utf-8") == "<html>new</html>"

    def test_повторная_выкладка_того_же_отпечатка_идемпотентна(self, tmp_path):
        root = make_runtime(tmp_path)
        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        first = canary.apply(plan, health=lambda directory: (True, "ok"))
        plan2 = canary.plan("lords-01", root=root, template_digest=DIGEST,
                            expect_template_digest=DIGEST, payload=payload(tmp_path))
        second = canary.apply(plan2, health=lambda directory: (True, "ok"))
        assert first.new_release == second.new_release
        assert targets(root)["lords-01"] == first.new_release


class TestDryRun:
    def test_сухой_прогон_не_меняет_ничего(self, tmp_path):
        root = make_runtime(tmp_path)
        before = targets(root)
        listing = sorted((root / "lords-01" / "releases").iterdir())
        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        result = canary.apply(plan, health=lambda directory: (True, "ok"), dry_run=True)
        assert result.dry_run
        assert not result.switched
        assert targets(root) == before
        assert sorted((root / "lords-01" / "releases").iterdir()) == listing

    def test_сухой_прогон_называет_что_сделал_бы(self, tmp_path):
        root = make_runtime(tmp_path)
        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        result = canary.apply(plan, health=lambda directory: (True, "ok"), dry_run=True)
        assert result.would["switch_from"] == "old01"
        assert result.would["switch_to"] == plan.new_release
        assert result.would["site_id"] == "lords-01"


class TestRollback:
    def test_возврат_на_предыдущий_релиз(self, tmp_path):
        root = make_runtime(tmp_path)
        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        canary.apply(plan, health=lambda directory: (True, "ok"))
        assert targets(root)["lords-01"] == plan.new_release

        back = canary.rollback("lords-01", root=root, health=lambda directory: (True, "ok"))
        assert back.switched
        assert targets(root)["lords-01"] == "old01"
        assert (root / "lords-01" / "current" / "site" / "index.html").read_text(
            encoding="utf-8") == "<html>lords-01 old</html>"

    def test_откат_не_трогает_соседей(self, tmp_path):
        root = make_runtime(tmp_path)
        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        canary.apply(plan, health=lambda directory: (True, "ok"))
        before = targets(root)
        canary.rollback("lords-01", root=root, health=lambda directory: (True, "ok"))
        after = targets(root)
        assert after["lords-02"] == before["lords-02"]
        assert after["lords-03"] == before["lords-03"]

    def test_откат_без_записи_отказывается(self, tmp_path):
        root = make_runtime(tmp_path)
        # Никакой выкладки не было — возвращаться некуда, и молчаливый успех
        # здесь опаснее отказа: оператор решит, что откатился.
        with pytest.raises(canary.CanaryRefused) as exc:
            canary.rollback("lords-01", root=root, health=lambda directory: (True, "ok"))
        assert "предыдущ" in str(exc.value)

    def test_откат_проверяет_здоровье_до_переключения(self, tmp_path):
        root = make_runtime(tmp_path)
        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        canary.apply(plan, health=lambda directory: (True, "ok"))
        current = targets(root)["lords-01"]
        back = canary.rollback("lords-01", root=root,
                               health=lambda directory: (False, "прежний релиз не поднялся"))
        assert not back.switched
        assert targets(root)["lords-01"] == current, "откат переключил на нездоровый релиз"


class TestRecord:
    def test_запись_о_выкладке_читаема_и_полна(self, tmp_path):
        root = make_runtime(tmp_path)
        plan = canary.plan("lords-01", root=root, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        result = canary.apply(plan, health=lambda directory: (True, "ok"))
        record = json.loads((root / "lords-01" / "canary.json").read_text(encoding="utf-8"))
        assert record["site_id"] == "lords-01"
        assert record["template_digest"] == DIGEST
        assert record["previous_release"] == "old01"
        assert record["release"] == result.new_release
        assert record["switched_at_utc"].endswith("Z")


class TestRelativeRoot:
    """Относительный корень: ссылка обязана остаться разрешимой.

    Дефект, ради которого написан этот класс, модульные тесты пропускали: они
    получают `tmp_path`, а он абсолютен всегда. Сквозной прогон на песочном
    рантайме с корнем `var/canary-sandbox` дал `current → prev0001`, что
    разрешается относительно `lords-01/`, а релиз лежит в `lords-01/releases/`.
    Витрина «переключилась» и отвечала бы 404 на всё сразу.
    """

    def test_ссылка_разрешается_при_относительном_корне(self, tmp_path, monkeypatch):
        root = make_runtime(tmp_path)
        monkeypatch.chdir(tmp_path)
        relative = Path(root.name)
        plan = canary.plan("lords-01", root=relative, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        assert plan.allowed, plan.refusals
        canary.apply(plan, health=lambda directory: (True, "ok"))
        link = relative / "lords-01" / "current"
        assert link.is_dir(), "ссылка не ведёт в каталог: витрина отдавала бы 404 на всё"
        assert (link / "site" / "index.html").read_text(encoding="utf-8") == "<html>new</html>"

    def test_откат_при_относительном_корне_тоже_разрешим(self, tmp_path, monkeypatch):
        root = make_runtime(tmp_path)
        monkeypatch.chdir(tmp_path)
        relative = Path(root.name)
        plan = canary.plan("lords-01", root=relative, template_digest=DIGEST,
                           expect_template_digest=DIGEST, payload=payload(tmp_path))
        canary.apply(plan, health=lambda directory: (True, "ok"))
        canary.rollback("lords-01", root=relative, health=lambda directory: (True, "ok"))
        link = relative / "lords-01" / "current"
        assert link.is_dir()
        assert (link / "site" / "index.html").read_text(encoding="utf-8") == "<html>lords-01 old</html>"
