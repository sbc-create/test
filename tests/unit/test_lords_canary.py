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
import subprocess
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


class TestPreSwitchGates:
    """Ворота, отличающие «сайт отвечает» от «сайт тот же».

    Витрина с пустым каталогом отвечает двумястами на каждой странице и
    проходит любую проверку доступности. Именно так выглядела бы подмена
    живого каталога фикстурой: маршруты верные, ошибок нет, записей на три
    порядка меньше.
    """

    def build_site(self, tmp_path: Path, slugs, *, players=True) -> Path:
        root = tmp_path / "staging"
        for slug in slugs:
            page = root / "title" / slug / "index.html"
            page.parent.mkdir(parents=True, exist_ok=True)
            body = "<html><body>" + ("<video-player id='p'></video-player>" if players else "") + "</body></html>"
            page.write_text(body, encoding="utf-8")
        return root

    def test_полный_каталог_проходит(self, tmp_path):
        slugs = [f"t{i:04d}" for i in range(1000)]
        site = self.build_site(tmp_path, slugs)
        report = canary.pre_switch_gates(site, expected_titles=1000,
                                         previous_site=None)
        assert report.passed, report.failures
        assert report.catalog_titles == 1000

    def test_обвал_каталога_останавливает(self, tmp_path):
        site = self.build_site(tmp_path, [f"t{i:03d}" for i in range(30)])
        report = canary.pre_switch_gates(site, expected_titles=53216,
                                         previous_site=None)
        assert not report.passed
        assert any("обвал каталога" in f for f in report.failures), report.failures

    def test_свод_одинаковых_адресов_не_считается_потерей(self, tmp_path):
        # Настоящий случай, из-за которого ворота пришлось перекалибровать:
        # 52 521 страница при 53 229 записях — недобор 1.33%. Причина не в
        # потере, а в том, что рендерер сводит записи с одинаковым адресом в
        # одну страницу. Прежний порог в 1% от записей отклонил бы исправную
        # сборку; проверено, что те же адреса отсутствуют и на боевом релизе.
        slugs = [f"t{i:05d}" for i in range(5252)]
        site = self.build_site(tmp_path, slugs, players=False)
        report = canary.pre_switch_gates(site, expected_titles=5323, previous_site=None)
        assert report.passed, report.failures

    def test_расхождение_с_прежним_релизом_останавливает(self, tmp_path):
        prev = self.build_site(tmp_path / "prev", [f"t{i:04d}" for i in range(1000)])
        new = self.build_site(tmp_path / "new", [f"t{i:04d}" for i in range(950)])
        report = canary.pre_switch_gates(new, expected_titles=1000, previous_site=prev)
        assert not report.passed
        assert any("прежнего релиза" in f or "у прежнего релиза" in f for f in report.failures), \
            report.failures

    def test_исчезнувшая_работающая_страница_останавливает(self, tmp_path):
        # Число страниц совпало, но состав другой: одна работающая страница
        # исчезла, вместо неё появилась новая. Счётчик такого не видит.
        prev = self.build_site(tmp_path / "prev", [f"t{i:04d}" for i in range(1000)])
        # Пропадает ровно одна страница из тысячи — 0.1%, ниже допуска на
        # убыль. Проверяется, что ворота считают исчезновение долей, а не
        # ловят его случайно: убираем сразу двадцать, это 2%.
        new_slugs = [f"t{i:04d}" for i in range(980)] + [f"новая-{i}" for i in range(20)]
        new = self.build_site(tmp_path / "new", new_slugs)
        report = canary.pre_switch_gates(new, expected_titles=1000, previous_site=prev)
        assert not report.passed
        assert any("исчезло то, что работает" in f for f in report.failures), report.failures

    def test_исчезнувший_плеер_останавливает(self, tmp_path):
        slugs = [f"t{i:04d}" for i in range(100)]
        prev = self.build_site(tmp_path / "prev", slugs, players=True)
        new = self.build_site(tmp_path / "new", slugs, players=False)
        report = canary.pre_switch_gates(new, expected_titles=100,
                                         previous_site=prev)
        assert not report.passed
        assert any("плеер исчез" in f for f in report.failures), report.failures
        assert report.players_previous == 100 and report.players_new == 0

    def test_частичная_убыль_плееров_в_пределах_допуска_проходит(self, tmp_path):
        # Источник вправе убрать видео у части тайтлов; обвал в разы — нет.
        slugs = [f"t{i:04d}" for i in range(100)]
        prev = self.build_site(tmp_path / "prev", slugs, players=True)
        new = self.build_site(tmp_path / "new", slugs[:95], players=True)
        for slug in slugs[95:]:
            page = new / "title" / slug / "index.html"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text("<html><body>без плеера</body></html>", encoding="utf-8")
        report = canary.pre_switch_gates(new, expected_titles=100,
                                         previous_site=prev)
        assert report.passed, report.failures
        assert report.players_new == 95


class TestPrivilegedPathHasNoGit:
    """Привилегированный сценарий не имеет права звать git.

    Первый настоящий запуск упал здесь: операция идёт от root, дерево
    принадлежит другой учётной записи, и git отвечает `detected dubious
    ownership`. Отказ наступал до единой проверки, то есть сценарий не делал
    ничего из того, ради чего написан.

    Объявить каталог доверенным было бы лечением симптома: git давал только
    идентификатор коммита и признак «дерево не правили», а оба получаются из
    манифеста происхождения по содержимому файлов.
    """

    SCRIPT = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-canary-apply.sh"

    def test_сценарий_не_вызывает_git(self):
        import re
        lines = self.SCRIPT.read_text(encoding="utf-8").splitlines()
        calls = [
            f"{n}: {line.strip()}"
            for n, line in enumerate(lines, 1)
            if not line.lstrip().startswith("#") and re.search(r"(^|[|;&(\s])git\s", line)
        ]
        assert calls == [], "git вернулся в привилегированный путь:\n" + "\n".join(calls)

    def test_манифест_происхождения_существует_и_полон(self):
        import json
        manifest = self.SCRIPT.parent / "lords-canary-provenance.json"
        assert manifest.is_file(), "манифест происхождения не собран"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for key in ("head_sha", "template_digest", "tooling", "tree_clean_at_write"):
            assert key in data, f"в манифесте нет поля {key}"
        assert self.SCRIPT.name in " ".join(data["tooling"]), (
            "сам привилегированный сценарий не входит в манифест — его подмену не заметят")


class TestProvenanceVerify:
    """Сверка манифеста ловит подмену того, что исполняет root."""

    TOOL = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-canary-provenance.py"

    def run(self):
        import subprocess
        import sys
        return subprocess.run([sys.executable, str(self.TOOL), "--verify"],
                              capture_output=True, text=True)

    def test_нетронутая_оснастка_проходит(self):
        result = self.run()
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip(), "commit не напечатан"

    def test_изменённый_файл_оснастки_ломает_сверку(self, tmp_path):
        target = self.TOOL.parent / "lords-canary-build.py"
        original = target.read_bytes()
        try:
            target.write_bytes(original + "\n# подмена\n".encode())
            result = self.run()
            assert result.returncode != 0
            assert "изменён файл оснастки" in result.stderr
        finally:
            target.write_bytes(original)
        assert self.run().returncode == 0, "восстановление не вернуло сверку в норму"


class TestDubiousOwnershipReproduced:
    """Отказ systemd-запуска воспроизводится детерминированно.

    Служба идёт от root, рабочее дерево принадлежит другой учётной записи, и git
    отвечает `fatal: detected dubious ownership`. Под своей учётной записью это
    не воспроизводится — владелец совпадает, и любой прогон проходит, создавая
    ложную уверенность. Ровно так дефект и дожил до боевого запуска.

    `GIT_TEST_ASSUME_DIFFERENT_OWNER=1` — штатный переключатель самого git: он
    заставляет проверку владельца считать каталог чужим. Это и есть точная
    имитация условий службы, а не приблизительная.
    """

    ROOT = Path(__file__).resolve().parents[2]
    FOREIGN = {"GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"}

    def env(self) -> dict:
        import os
        import tempfile
        # Журнал операции уводится в отдельный каталог. Прогон тестов писал в
        # боевой /var/log/site-factory, и записи вида «ОТКАЗ: в снимке 1
        # записей» — намеренно крошечный снимок теста — оседали там вперемешку
        # с записями настоящих выкладок. Журнал операции служит релизным
        # свидетельством, и шум теста в нём делает свидетельство хуже.
        audit = getattr(self, "_audit_dir", None)
        if audit is None:
            audit = tempfile.mkdtemp(prefix="canary-audit-")
            self._audit_dir = audit
        return {**os.environ, **self.FOREIGN, "LORDS_CANARY_AUDIT": audit}

    def test_контроль_условие_действительно_воспроизводится(self):
        # Без этой проверки все остальные ничего не стоят: они могли бы
        # проходить просто потому, что условие не наступило.
        import subprocess
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.ROOT,
                                capture_output=True, text=True, env=self.env())
        assert "dubious ownership" in result.stderr, (
            "имитация чужого владельца не сработала — остальные проверки бессмысленны")

    def test_сверка_происхождения_переживает_чужого_владельца(self):
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, str(self.ROOT / "automation/host/lords-canary-provenance.py"),
             "--verify"], capture_output=True, text=True, env=self.env())
        assert result.returncode == 0, f"сверка упала при чужом владельце: {result.stderr}"
        assert result.stdout.strip(), "commit не напечатан"

    def test_сценарий_проходит_предполётные_проверки_при_чужом_владельце(self, tmp_path):
        # Снимок подставляется заведомо маленький: сценарий обязан дойти до
        # проверки его размера и остановиться там. Настоящий снимок запустил бы
        # полный рендер пятидесяти трёх тысяч страниц — тест, идущий часами,
        # никто не станет запускать, и он перестанет что-либо охранять.
        import json
        import subprocess
        cache = tmp_path / "catalog-cache"
        cache.mkdir()
        (cache / "lords-02.json").write_text(json.dumps({"items": [{"external_id": "x"}]}),
                                             encoding="utf-8")
        result = subprocess.run(
            ["bash", str(self.ROOT / "automation/host/lords-canary-apply.sh"), "render", "lords-02"],
            capture_output=True, text=True, cwd=self.ROOT, timeout=120,
            env={**self.env(), "LORDS_SNAPSHOT_DIR": str(cache),
                 "LORDS_CANARY_STAGING": str(tmp_path / "staging")})
        out = result.stdout + result.stderr
        assert "dubious ownership" not in out, "git вернулся в путь запуска"
        assert "происхождение подтверждено" in out, f"предполётные проверки не пройдены:\n{out[-600:]}"
        assert "не живой каталог" in out, f"проверка размера снимка не сработала:\n{out[-400:]}"


class TestNoBlanketGitTrust:
    """Доверие не раздаётся ни каталогам вообще, ни через общий конфиг."""

    ROOT = Path(__file__).resolve().parents[2]

    def test_нигде_нет_safe_directory(self):
        bad = []
        for name in ("automation/host/lords-canary-apply.sh",
                     "automation/host/lords-canary-install-and-run.sh",
                     "automation/host/systemd/lords-canary-render@.service",
                     "automation/host/systemd/lords-canary-switch@.service",
                     "automation/host/lords-canary-provenance.py"):
            text = (self.ROOT / name).read_text(encoding="utf-8")
            for n, line in enumerate(text.splitlines(), 1):
                if "safe.directory" in line and not line.lstrip().startswith(("#", "*")):
                    bad.append(f"{name}:{n}")
        assert bad == [], "safe.directory просочился в оснастку: " + ", ".join(bad)

    def test_произвольный_каталог_не_становится_доверенным(self, tmp_path):
        # Отдельный репозиторий рядом обязан остаться недоверенным: сверка
        # происхождения не должна ничего разрешать за пределами своего дерева.
        import subprocess
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
        result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=tmp_path,
                                capture_output=True, text=True,
                                env={**os.environ, "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"})
        assert result.returncode != 0 or "dubious" in result.stderr, (
            "посторонний каталог оказался доверенным")


class TestUnitNamespace:
    """Юнит обязан строить пространство имён, а не падать на нём.

    Первый боевой запуск завершился ничем: ни релиза, ни журнала, ни файлов от
    root. Причина — `ProtectHome=read-only` вместе с путями под `/home` в
    `ReadWritePaths`: первое перемонтирует `/home` только для чтения, второе
    требует запись под ним, и служба завершается до `ExecStart`.

    Отказ такого рода не оставляет следов на диске и виден только в системном
    журнале, доступном не всякой учётной записи. Поэтому он проверяется здесь.
    """

    UNITS = ("lords-canary-render@.service", "lords-canary-switch@.service")
    BASE = Path(__file__).resolve().parents[2] / "automation" / "host" / "systemd"

    def directives(self, unit: str) -> dict:
        out: dict = {}
        for line in (self.BASE / unit).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            out.setdefault(key, []).append(value)
        return out

    def test_нет_путей_под_home_при_включённом_protecthome(self):
        for unit in self.UNITS:
            d = self.directives(unit)
            rw = " ".join(d.get("ReadWritePaths", [])).split()
            home = [p for p in rw if p.startswith("/home")]
            if d.get("ProtectHome"):
                assert home == [], (
                    f"{unit}: ProtectHome вместе с путями под /home в ReadWritePaths — "
                    f"служба не построит пространство имён: {home}")

    def test_иерархия_всё_равно_только_для_чтения(self):
        # Убрав ProtectHome, нельзя потерять защиту: её обязан давать
        # ProtectSystem=strict, иначе снятие директивы было бы послаблением.
        for unit in self.UNITS:
            assert self.directives(unit).get("ProtectSystem") == ["strict"], (
                f"{unit}: без ProtectHome защита держится только на ProtectSystem=strict")

    def test_операция_одноразовая(self):
        for unit in self.UNITS:
            d = self.directives(unit)
            assert d.get("Type") == ["oneshot"], f"{unit}: разрешение обязано истекать"
            assert d.get("RemainAfterExit") == ["no"], f"{unit}: служба не должна оставаться активной"


class TestPrivilegeSeparation:
    """Секрет и полные права не встречаются в одном процессе.

    Прежде обе вещи делала одна служба от root: и рендер тридцати пяти
    мегабайт данных поставщика, и системное переключение. Долгая фаза с чужими
    данными не имеет ни одной причины идти с полными правами.
    """

    BASE = Path(__file__).resolve().parents[2] / "automation" / "host" / "systemd"

    def directives(self, unit: str) -> dict:
        out: dict = {}
        for line in (self.BASE / unit).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            out.setdefault(key, []).append(value)
        return out

    def test_сборка_идёт_не_от_root(self):
        d = self.directives("lords-canary-render@.service")
        assert d.get("User"), "у фазы сборки не задана учётная запись — она пойдёт от root"
        assert d["User"] != ["root"], "фаза сборки не должна идти от root"

    def test_сборка_не_имеет_записи_в_боевой_рантайм(self):
        rw = " ".join(self.directives("lords-canary-render@.service").get("ReadWritePaths", [])).split()
        assert not any(p.startswith("/srv/lords") for p in rw), (
            "фаза сборки получила запись в боевой рантайм — она может тронуть витрину при любой ошибке")

    def test_переключение_не_получает_учётных_данных(self):
        d = self.directives("lords-canary-switch@.service")
        assert not d.get("LoadCredential"), (
            "фазе переключения переданы учётные данные: секрет встретился с полными правами")

    def test_учётные_данные_только_у_сборки(self):
        d = self.directives("lords-canary-render@.service")
        assert d.get("LoadCredential"), "фаза сборки без учётных данных соберёт витрину без плеера"

    def test_сценарий_отказывается_переключать_с_учётными_данными(self):
        script = (self.BASE.parent / "lords-canary-apply.sh").read_text(encoding="utf-8")
        assert "CREDENTIALS_DIRECTORY" in script and "не должны встречаться" in script, (
            "сценарий не проверяет, что фазе переключения не подсунули секрет")

    def test_фаза_сборки_отказывается_идти_от_root(self):
        script = (self.BASE.parent / "lords-canary-apply.sh").read_text(encoding="utf-8")
        assert "рендер не должен идти от root" in script


class TestSnapshotPathIsExplicitInput:
    """Снимок берётся из указанного каталога, а не «рядом с кодом».

    Отказ, ради которого написан класс, выглядел в журнале так:

        BlockedInput: нет кэша живого каталога
        /home/claude/wt-canary/var/lords/lords/catalog-cache/lords-02.json

    при том, что снимок в 53 229 записей уже лежал в боевом контуре и был
    прочитан оболочкой строкой выше. Причина: переменную `LORDS_SNAPSHOT_DIR`
    читала только оболочка — ради числа записей в отчёте, — а сборка звала
    `load_live_items` без неё и уходила искать кэш относительно собственного
    дерева. Операция из отдельного worktree с закреплённым артефактом ищет
    снимок по своему адресу и не находит его никогда.
    """

    BUILD = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-canary-build.py"
    LIVE_CACHE = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-02.json")

    def make_cache(self, tmp_path: Path, count: int = 3) -> Path:
        """Маленький кэш настоящей формы: записи берутся из боевого снимка."""
        import json
        if not self.LIVE_CACHE.is_file():
            pytest.skip("боевого снимка нет — форму записи взять неоткуда")
        raw = json.loads(self.LIVE_CACHE.read_text(encoding="utf-8"))
        items = (raw.get("items") if isinstance(raw, dict) else raw) or []
        directory = tmp_path / "catalog-cache"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "lords-02.json").write_text(
            json.dumps({"items": items[:count]}, ensure_ascii=False), encoding="utf-8")
        return directory

    def run_build(self, out: Path, env_extra: dict) -> subprocess.CompletedProcess:
        import os as _os
        import sys
        return subprocess.run(
            [sys.executable, str(self.BUILD), "lords-02", str(out)],
            capture_output=True, text=True,
            env={**_os.environ, **env_extra},
            cwd=str(self.BUILD.resolve().parents[2]))

    def test_сборка_читает_снимок_из_указанного_каталога(self, tmp_path):
        cache = self.make_cache(tmp_path, count=3)
        result = self.run_build(tmp_path / "out", {"LORDS_SNAPSHOT_DIR": str(cache)})
        assert result.returncode == 0, f"сборка не прошла: {result.stderr[-500:]}"
        assert result.stdout.strip() == "3", (
            f"собрано не из указанного снимка: напечатано {result.stdout.strip()!r}")

    def test_без_переменной_воспроизводится_прежний_отказ(self, tmp_path):
        # Контроль: без явного входа сборка ищет кэш относительно своего дерева
        # и падает — ровно то, что видел журнал службы.
        result = self.run_build(tmp_path / "out", {"LORDS_SNAPSHOT_DIR": ""})
        assert result.returncode != 0, "без указанного снимка сборка обязана отказать"
        assert "кэш" in result.stderr or "BlockedInput" in result.stderr, result.stderr[-300:]

    def test_неверный_каталог_останавливает_до_сборки(self, tmp_path):
        result = self.run_build(tmp_path / "out",
                                {"LORDS_SNAPSHOT_DIR": str(tmp_path / "нет-такого")})
        assert result.returncode != 0
        assert "не на каталог" in result.stderr, result.stderr[-300:]

    def test_сценарий_передаёт_переменную_в_сборку(self):
        # Оболочка обязана передать тот же адрес, что читает сама: иначе отчёт
        # о числе записей и фактическая сборка расходятся молча.
        script = (self.BUILD.parent / "lords-canary-apply.sh").read_text(encoding="utf-8")
        assert "LORDS_SNAPSHOT_DIR" in script, "оболочка не знает про адрес снимка"
        build = self.BUILD.read_text(encoding="utf-8")
        assert "LORDS_SNAPSHOT_DIR" in build, "сборка не читает адрес снимка"
        assert "root=snapshot_dir()" in build, "адрес снимка не доходит до load_live_items"


class TestRefreshTimerIsAlwaysRestored:
    """Таймер обновления обязан вернуться, чем бы ни кончилось переключение.

    Отказ, ради которого написан класс, не виден ни в одном отчёте: сценарий
    останавливал `lords-content-refresh.timer` перед подменой ссылки и запускал
    его обратно **только на пути отказа**. На успешном пути он лишь печатал
    совет «вернуть обновление: systemctl start …» — и таймер оставался
    остановленным.

    Цена — не у одной витрины. Таймер общий: он обновляет каталог всем трём
    сайтам сразу, и сценарий сам об этом предупреждает строкой «цена:
    обновление содержимого приостановлено у ВСЕХ ТРЁХ витрин». Удачный canary
    одного домена замораживал свежесть каталога у трёх, и заметить это можно
    было только по отсутствию новых релизов — то есть через часы.

    Проверяется не текст сообщения, а способ восстановления: оно обязано быть
    в обработчике выхода, потому что путей выхода больше двух — есть ещё
    `set -e`, прерывание сигналом и падение любой команды между остановкой
    таймера и концом сценария.
    """

    SCRIPT = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-canary-apply.sh"

    def текст(self) -> str:
        return self.SCRIPT.read_text(encoding="utf-8")

    def test_восстановление_идёт_через_обработчик_выхода(self):
        script = self.текст()
        assert "trap" in script, "в сценарии нет ни одного обработчика выхода"
        # Обработчик обязан упоминать запуск таймера: без этого он ловит выход,
        # но таймер не возвращает.
        trap_block = script[script.index("trap"):script.index("trap") + 600]
        assert "REFRESH_TIMER" in trap_block or "refresh" in trap_block.lower(), (
            "обработчик выхода не возвращает таймер обновления")

    @staticmethod
    def _команды_запуска(script: str) -> list[int]:
        """Позиции ФАКТИЧЕСКИХ запусков таймера, а не упоминаний в тексте.

        Первая редакция этой проверки считала любое вхождение подстроки
        «systemctl start» и потому проходила на сломанном сценарии: строка
        встречалась внутри сообщения `log "вернуть обновление: systemctl
        start …"`. Проверка не отличала действие от совета — ровно та ошибка,
        которую она должна ловить в сценарии.
        """
        import re
        return [m.start() for m in re.finditer(
            r"^[ \t]*(?:\[[^\]]*\][ \t]*&&[ \t]*)?systemctl start\b",
            script, re.MULTILINE)]

    def test_запуск_таймера_не_заперт_в_ветке_отказа(self):
        script = self.текст()
        starts = self._команды_запуска(script)
        assert starts, "сценарий нигде не запускает таймер обратно командой"
        # Ветка отказа кончается вызовом die. Если ЕДИНСТВЕННЫЙ запуск таймера
        # стоит внутри неё, успешный путь оставит таймер остановленным.
        внутри_отказа = script.index("приёмка не пройдена")
        конец_отказа = script.index("витрина не ответила после подмены")
        только_в_отказе = all(внутри_отказа < i < конец_отказа for i in starts)
        assert not только_в_отказе, (
            "таймер возвращается только на пути отказа: удачное переключение "
            "оставит обновление каталога остановленным у всех трёх витрин")

    def test_совет_не_заменяет_действие(self):
        """Строка «вернуть обновление: …» — подсказка человеку, а не работа.

        Она полезна и остаётся, но не может быть единственным способом вернуть
        таймер: сценарий выполняется без человека.
        """
        script = self.текст()
        # Ищется само сообщение журнала, а не любое вхождение слов: они
        # встречаются и в комментариях, объясняющих, почему совета было мало.
        import re
        hint = re.search(r'log\s+"вернуть обновление', script)
        assert hint, "подсказка о возврате исчезла из журнала"
        hint_at = hint.start()
        assert any(i < hint_at for i in self._команды_запуска(script)), (
            "до подсказки нет ни одного фактического запуска таймера")


class TestSwitchUnitDoesNotPullRender:
    """Фаза переключения не должна тянуть за собой фазу сборки.

    Отказ, ради которого написан класс, стоил ста четырнадцати минут работы и
    выглядел как успешно выполненная команда.

    Юнит переключения объявлял:

        Requires=lords-canary-render@%i.service
        After=lords-canary-render@%i.service

    systemd заводит обе задачи в одну транзакцию, поэтому запуск переключения
    сначала поднимал сборку. А сборка первым делом делает `rm -rf` каталога
    staging — то есть уничтожала готовую витрину, ради переключения которой её
    и запускали, и начинала собирать заново.

    Владелец, выполнивший ровно одну подготовленную команду, получил вместо
    минутного переключения повторный двухчасовой рендер.

    Настоящее предусловие переключения — не служба, а расписка о сборке, и
    сценарий её уже проверяет. Зависимость от службы лишняя и вредная.
    """

    UNIT = (Path(__file__).resolve().parents[2] / "automation" / "host" / "systemd"
            / "lords-canary-switch@.service")

    def директивы(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for line in self.UNIT.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            out.setdefault(key.strip(), []).append(value.strip())
        return out

    def test_переключение_не_требует_службы_сборки(self):
        d = self.директивы()
        pulled = [v for key in ("Requires", "Wants", "BindsTo", "Requisite")
                  for v in d.get(key, []) if "render" in v]
        assert not pulled, (
            f"юнит переключения тянет за собой сборку: {pulled}. Запуск "
            "переключения запустит рендер, а тот сотрёт готовую витрину")

    def test_порядок_после_сборки_допустим(self):
        """`After=` без `Requires=` безвреден и полезен.

        Он лишь упорядочивает, если обе задачи оказались в одной транзакции, но
        сам сборку не запускает. Запрещать его незачем — запрещается именно
        зависимость.
        """
        d = self.директивы()
        after_render = [v for v in d.get("After", []) if "render" in v]
        requires_render = [v for v in d.get("Requires", []) if "render" in v]
        assert not requires_render, "упорядочение подменено зависимостью"
        # Само по себе наличие After на сборку — не дефект, а полезная
        # предосторожность. Проверяется только отсутствие Requires выше;
        #  ничего не проверял и был снят.
        del after_render

    def test_конфликт_с_обновлением_содержимого_сохранён(self):
        # Одновременная работа с обновлением означала бы двух писателей в один
        # каталог релизов. Эта защита обязана остаться.
        d = self.директивы()
        assert any("lords-content-refresh" in v for v in d.get("Conflicts", [])), (
            "снят конфликт с обновлением содержимого")


class TestSwitchIsNotKilledByRefresh:
    """Переключение не должно погибать от таймера обновления содержимого.

    Наблюдалось на боевой машине. Фаза switch стартовала в 08:52:36, ушла в
    ворота содержимого — те читают 61 609 страниц сборки и столько же у
    прежнего релиза, — а в 08:52:59 сработал таймер обновления и запустил
    `lords-content-refresh.service`. Юнит переключения объявляет
    `Conflicts=lords-content-refresh.service`, и systemd остановил
    переключение.

    В журнале не осталось ни строки отказа, ни каталога нового релиза: процесс
    не отказал, его прекратили. Владелец выполнил команду и не получил ничего,
    кроме тишины.

    Причина в порядке шагов: таймер останавливался ПОСЛЕ ворот, а ворота
    длятся дольше, чем зазор между запусками таймера (десять минут). Окно, в
    котором переключение беззащитно, было гарантированно шире зазора.

    Проверяется порядок, а не текст: остановка обязана предшествовать воротам.
    """

    SCRIPT = (Path(__file__).resolve().parents[2] / "automation" / "host"
              / "lords-canary-apply.sh")

    def текст(self) -> str:
        return self.SCRIPT.read_text(encoding="utf-8")

    def test_таймер_останавливается_до_ворот(self):
        script = self.текст()
        stop_at = script.find('systemctl stop "${REFRESH_TIMER}"')
        gates_at = script.find("lords-canary-gates.py")
        assert stop_at != -1, "сценарий нигде не останавливает таймер"
        assert gates_at != -1, "сценарий нигде не вызывает ворота содержимого"
        assert stop_at < gates_at, (
            "ворота идут раньше остановки таймера: переключение останется "
            "беззащитным на всё время их работы, а они длятся дольше зазора "
            "между запусками таймера")

    def test_обработчик_возврата_ставится_до_остановки(self):
        script = self.текст()
        trap_at = script.find("trap restore_refresh_timer EXIT")
        stop_at = script.find('systemctl stop "${REFRESH_TIMER}"')
        assert trap_at != -1, "обработчик возврата таймера исчез"
        assert trap_at < stop_at, (
            "обработчик ставится после остановки: отказ между этими строками "
            "оставит таймер выключенным")

    def test_сценарий_ждёт_завершения_идущего_обновления(self):
        """Остановки таймера мало: служба могла уже работать.

        `Conflicts` действует и на запущенную службу — она остановит
        переключение так же надёжно, как только что запущенная.
        """
        script = self.текст()
        assert "lords-content-refresh.service" in script, (
            "сценарий не проверяет, не идёт ли обновление прямо сейчас")
        assert "is-active" in script
