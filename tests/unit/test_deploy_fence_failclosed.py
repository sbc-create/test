"""Барьер обязан работать в установленной копии, а не только в дереве.

Дефект, который здесь закрепляется, — `LORDS-FENCE-FAIL-OPEN-37`.

Барьер поколений построен, покрыт тестами и встроен в канарейку в двух точках.
Но в production он ни разу не сработал, и не мог: установленная копия помощника
лежит в `/usr/local/libexec/site-factory/` одна, без дерева репозитория, а
модуль барьера искался как `automation.deploy.lords_fence` от третьего родителя
файла — то есть в `/usr/local/automation/deploy/`, где его нет. Импорт падал,
`барьер_мод` становился `None`, и каждая проверка барьера молча пропускалась:

    if барьер_мод is not None and поколение:   # оба ложны в production

Отказ был открытым. Заявка без поля `generation` принималась схемой (значение
по умолчанию — ноль), проходила захват без единой проверки, не получала
`--generation` в аргументах канарейки и могла переключить витрину. Ровно тот
сценарий, ради которого барьер и заводился: старый producer переключает
витрину после нового релиза.

Три требования, каждое из которых закрывает одно звено:

1. модуль барьера находится рядом с установленной копией;
2. отсутствие модуля — отказ, а не разрешение;
3. `generation` обязателен и положителен, иначе заявка терминальна и до
   отрисовки не доходит.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ИСТОЧНИК = ROOT / "automation" / "deploy"


def _загрузить(имя: str, путь: Path):
    спец = importlib.util.spec_from_loader(
        имя, importlib.machinery.SourceFileLoader(имя, str(путь)))
    модуль = importlib.util.module_from_spec(спец)
    # `dataclasses` разрешает аннотации через `sys.modules[cls.__module__]`.
    sys.modules.setdefault(имя, модуль)
    спец.loader.exec_module(модуль)
    return модуль


@pytest.fixture(scope="module")
def брокер():
    return _загрузить("lords_deploy_broker_fc", ИСТОЧНИК / "lords-deploy-broker")


@pytest.fixture(scope="module")
def помощник():
    return _загрузить("lords_deployctl_fc", ИСТОЧНИК / "lords-deployctl")


ГОДНАЯ = {
    "deployment_id": "lords-fence-001",
    "sites": ["lords-02"],
    "revision": "a" * 40,
    "artifact_sha256": "b" * 64,
    "artifact_source": "/home/claude/wt-integration-28/var/artifacts/aaaaaaaaaaaa.tar.gz",
    "soak_seconds": 180,
    "generation": 7,
}


class TestМодульБарьераНаходитсяРядом:
    """Установленная копия лежит одна: барьер обязан искаться рядом с файлом."""

    @pytest.mark.parametrize("имя", ["lords-deployctl", "lords-deploy-broker"])
    def test_копия_без_дерева_видит_барьер(self, tmp_path, имя):
        # Раскладка ровно как у установленной: файл и барьер в одном каталоге,
        # и никакого дерева репозитория ни на одном уровне выше.
        libexec = tmp_path / "usr" / "local" / "libexec" / "site-factory"
        libexec.mkdir(parents=True)
        shutil.copy2(ИСТОЧНИК / имя, libexec / имя)
        shutil.copy2(ИСТОЧНИК / "lords_fence.py", libexec / "lords_fence.py")

        # Отдельный интерпретатор, а не этот процесс. В этом процессе дерево
        # репозитория уже лежит в `sys.path`, а `automation.deploy.lords_fence`
        # уже в `sys.modules`: проверка прошла бы за счёт загрязнения и сказала
        # бы обратное тому, что происходит на хосте. Первая версия этого теста
        # именно так и «проходила».
        зонд = (
            "import importlib.machinery, importlib.util, sys\n"
            f"путь = {str(libexec / имя)!r}\n"
            "спец = importlib.util.spec_from_loader('проба',\n"
            "    importlib.machinery.SourceFileLoader('проба', путь))\n"
            "м = importlib.util.module_from_spec(спец)\n"
            "спец.loader.exec_module(м)\n"
            "print('НЕТ' if м.барьер_мод is None else м.барьер_мод.ВЫТЕСНЕНА)\n")
        готово = subprocess.run(
            [sys.executable, "-I", "-c", зонд],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=120)
        assert готово.returncode == 0, готово.stderr
        assert готово.stdout.strip() == "STALE_FENCED_NO_CHANGE", (
            "установленная копия не видит барьер: в production он молча выключен")

    @pytest.mark.parametrize("имя", ["lords-deployctl", "lords-deploy-broker"])
    def test_барьер_входит_в_полезную_нагрузку_установки(self, имя):
        """Файл, который ищется рядом, обязан туда попадать при установке."""
        текст = (ИСТОЧНИК / "lords-deploy-bootstrap.py").read_text(encoding="utf-8")
        assert "lords_fence.py" in текст, (
            "барьер не устанавливается: рядом с копией его не окажется")


class TestОтсутствиеБарьераЭтоОтказ:
    """Нет барьера — нет выкладки. Прежде это означало «выкладывай без барьера»."""

    def test_канарейка_без_модуля_отказывает_до_отрисовки(self, помощник, monkeypatch):
        monkeypatch.setattr(помощник, "барьер_мод", None)
        with pytest.raises(помощник.Отказ) as отказ:
            помощник.требовать_барьер(поколение=7)
        assert "барьер" in str(отказ.value).lower()

    def test_с_модулем_и_поколением_проверка_проходит(self, помощник):
        assert помощник.требовать_барьер(поколение=7) is None


class TestПоколениеОбязательноИПоложительно:
    def test_годная_заявка_с_поколением_принимается(self, брокер):
        разобрана = брокер.проверить_заявку(dict(ГОДНАЯ))
        assert разобрана["generation"] == 7

    def test_заявка_без_поколения_отвергается(self, брокер):
        сырая = dict(ГОДНАЯ)
        сырая.pop("generation")
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку(сырая)

    def test_нулевое_поколение_отвергается(self, брокер):
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку(dict(ГОДНАЯ, generation=0))

    def test_отрицательное_поколение_отвергается(self, брокер):
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку(dict(ГОДНАЯ, generation=-1))

    def test_логическое_значение_не_поколение(self, брокер):
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку(dict(ГОДНАЯ, generation=True))


class TestПроверкаНеОбходитсяУсловием:
    """Проверка не должна стоять за условием, которое в production ложно."""

    def test_в_брокере_нет_пропуска_барьера_по_условию(self):
        текст = (ИСТОЧНИК / "lords-deploy-broker").read_text(encoding="utf-8")
        assert "барьер_мод is not None and поколение" not in текст, (
            "проверка барьера снова спрятана за условием, ложным в production")

    def test_канарейка_всегда_получает_поколение(self):
        текст = (ИСТОЧНИК / "lords-deploy-broker").read_text(encoding="utf-8")
        assert "if поколение:" not in текст, (
            "--generation передаётся условно: канарейка снова останется без барьера")


class TestПодательОбъявляетПоколение:
    """Заявка без поколения теперь терминальна — податель обязан его объявить.

    Иначе укрепление схемы просто остановило бы выкладку: все три заявки
    2026-09-09 поля `generation` не несли, потому что построитель его не ставил.
    """

    def test_построитель_объявляет_барьер_и_кладёт_поколение(self):
        текст = (ИСТОЧНИК / "lords-deploy-request.py").read_text(encoding="utf-8")
        assert "барьер.объявить(" in текст, "податель не объявляет барьер"
        assert 'заявка["generation"]' in текст, "поколение не попадает в заявку"

    def test_поколение_растёт_и_вытесняет_прежнюю_заявку(self, tmp_path):
        барьер = _загрузить("lords_fence_подать", ИСТОЧНИК / "lords_fence.py")
        ревизия, отпечаток = "c" * 40, "d" * 64

        первое = барьер.объявить("lords-02", ревизия, отпечаток, корень=tmp_path)
        второе = барьер.объявить("lords-02", ревизия, отпечаток, корень=tmp_path)
        assert второе.generation == первое.generation + 1

        # Заявка прежнего поколения не проходит ни на одном из четырёх этапов.
        for этап in ("submit", "capture", "pre-render", "pre-switch"):
            решение = барьер.проверить("lords-02", generation=первое.generation,
                                       revision=ревизия, artifact_sha256=отпечаток,
                                       этап=этап, корень=tmp_path)
            assert not решение["allowed"]
            assert решение["verdict"] == "STALE_FENCED_NO_CHANGE"


class TestКанарейкаГаситТаймерНаВремяПрогона:
    """`LORDS-CANARY-TIMER-RACE-38`: канарейка не может выиграть гонку с таймером.

    `lords-site-render@.service` объявляет `Conflicts=lords-content-refresh.service`.
    Запуск канареечного прогона останавливает обновление каталога — и тем самым
    делает `OnUnitActiveSec=10min` немедленно выполнимым, потому что последняя
    активация была часом раньше. Таймер срабатывает через секунду, поднимает
    обновление, а `Conflicts` гасит канарейку. Прогон 22:04:53 прожил две
    секунды и вернул «Job ... canceled» ровно так.

    Гонка детерминированная: без остановки таймера канарейка не побеждает
    никогда. Поэтому таймер гасится на время прогона и восстанавливается после.
    """

    def test_канарейка_останавливает_таймер_перед_прогоном(self):
        текст = (ИСТОЧНИК / "lords-deployctl").read_text(encoding="utf-8")
        начало = текст.index("def глагол_canary")
        конец = текст.index("\ndef ", начало + 10)
        тело = текст[начало:конец]
        assert "ТАЙМЕР" in тело, "канарейка не трогает таймер: гонка остаётся"
        assert '"stop", ТАЙМЕР' in тело, "таймер не гасится перед прогоном"

    def test_таймер_восстанавливается_в_finally(self):
        текст = (ИСТОЧНИК / "lords-deployctl").read_text(encoding="utf-8")
        начало = текст.index("def глагол_canary")
        конец = текст.index("\ndef ", начало + 10)
        тело = текст[начало:конец]
        finally_блок = тело[тело.index("finally:"):]
        assert '"start", ТАЙМЕР' in finally_блок, (
            "таймер не восстанавливается: отказ канарейки оставил бы каталог "
            "без обновления навсегда")


class TestТаймаутПрогонаБольшеОтрисовки:
    """`LORDS-RENDER-TIMEOUT-TOO-SHORT-40`: юнит гасил исправную отрисовку.

    Прогон lords-02-20260909T220917Z шёл 22:09:17 → 23:09:20 и был убит
    systemd по `start operation timed out` при `TimeoutStartSec=3600`.

    Это не зависание, и доказательства собраны до правки: 56 мин 50 с
    процессорного времени за 60 мин настенных (то есть ~95 % занятости),
    непрерывный рост `.staging` 442 → 585 МиБ, постоянный RSS, ни одного
    события памяти при `MemoryMax=3G`. Сама фабрика печатает «это часы, не
    минуты», а исторический канареечный прогон занимал около 1 ч 50 мин.

    Поэтому предел обязан превышать реальную отрисовку. Обнаружение застоя —
    отдельная задача монитора по росту байтов, RSS и событиям памяти, а не
    побочный эффект короткого таймаута: короткий предел одинаково гасит и
    зависший прогон, и исправный.
    """

    #: Исторический полный рендер каталога 52 тысяч записей.
    ОТРИСОВКА_СЕК = 110 * 60

    def test_предел_юнита_превышает_реальную_отрисовку(self):
        текст = (ИСТОЧНИК / "units" / "lords-site-render@.service").read_text(encoding="utf-8")
        строки = [с for с in текст.splitlines() if с.strip().startswith("TimeoutStartSec=")]
        assert строки, "у юнита прогона нет TimeoutStartSec"
        предел = int(строки[-1].split("=", 1)[1].strip())
        assert предел > self.ОТРИСОВКА_СЕК, (
            f"предел {предел}с не покрывает отрисовку {self.ОТРИСОВКА_СЕК}с: "
            "исправный прогон будет убит")

    def test_ограничение_памяти_сохранено(self):
        """Предел времени поднят — предел памяти обязан остаться."""
        текст = (ИСТОЧНИК / "units" / "lords-site-render@.service").read_text(encoding="utf-8")
        assert "MemoryMax=" in текст, "снят предел памяти: прогон сможет съесть хост"
