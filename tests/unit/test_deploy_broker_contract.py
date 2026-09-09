"""Контракт приёмщика выкладки: схема заявки, статусы и сериализация.

Два дефекта этого цикла закрепляются здесь.

`LORDS-NIGHT-RUNNER-NOEXEC-WORKER-35`. Прошлая выкладка объявила `ROLLED_BACK`,
не тронув production: страж `noexec` стоял в рабочем сценарии, который законно
запускается через `/bin/bash` из `/run`, и остановил всё в предполёте. «Откат»
и «ничего не произошло» — разные события, и путать их значит терять доверие к
отчёту: после `ROLLED_BACK` полагается искать, что откатилось, а откатываться
было нечему.

`LORDS-SUMMARY-JSON-ESCAPE-36`. Свод выкладки содержал буквальные `\\n` вместо
переводов строки: `printf '%s' "${x}"` не разворачивает экранирование в
аргументе, только в формате. Файл переставал быть JSON, и прочитать итог
машинно было нельзя. Здесь запись идёт через `json.dumps`, а проверка требует,
чтобы результат разбирался обратно.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _загрузить(имя: str, путь: Path):
    спец = importlib.util.spec_from_loader(
        имя, importlib.machinery.SourceFileLoader(имя, str(путь)))
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


@pytest.fixture(scope="module")
def брокер():
    return _загрузить("lords_deploy_broker", ROOT / "automation" / "deploy" / "lords-deploy-broker")


@pytest.fixture(scope="module")
def помощник():
    return _загрузить("lords_deployctl", ROOT / "automation" / "deploy" / "lords-deployctl")


ГОДНАЯ = {
    "deployment_id": "lords-fleet-001",
    "sites": ["lords-02", "lords-01", "lords-03"],
    "revision": "a" * 40,
    "artifact_sha256": "b" * 64,
    "artifact_source": "/home/claude/wt-integration-28/var/artifacts/aaaaaaaaaaaa.tar.gz",
    "soak_seconds": 180,
}


class TestСхемаЗаявки:
    def test_годная_заявка_принимается(self, брокер):
        принято = брокер.проверить_заявку(dict(ГОДНАЯ))
        assert принято["sites"] == ["lords-02", "lords-01", "lords-03"]
        assert принято["soak_seconds"] == 180

    def test_неизвестное_поле_отвергается(self, брокер):
        """Молчаливое игнорирование скрывает опечатку в имени поля, и заявка
        делает не то, что в ней написано."""
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку({**ГОДНАЯ, "service": "lords-02.service"})

    def test_витрина_вне_списка_отвергается(self, брокер):
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку({**ГОДНАЯ, "sites": ["lords-02", "yummy"]})

    def test_повтор_витрины_отвергается(self, брокер):
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку({**ГОДНАЯ, "sites": ["lords-02", "lords-02"]})

    def test_короткая_ревизия_отвергается(self, брокер):
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку({**ГОДНАЯ, "revision": "a" * 12})

    def test_отпечаток_не_sha256_отвергается(self, брокер):
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку({**ГОДНАЯ, "artifact_sha256": "b" * 40})

    def test_путь_с_выходом_вверх_отвергается(self, брокер):
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку(
                {**ГОДНАЯ, "artifact_source": "/home/claude/../../etc/shadow"})

    def test_относительный_путь_отвергается(self, брокер):
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку({**ГОДНАЯ, "artifact_source": "artifact.tar.gz"})

    def test_выдержка_вне_границ_отвергается(self, брокер):
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку({**ГОДНАЯ, "soak_seconds": 99999})

    def test_идентификатор_с_косой_чертой_отвергается(self, брокер):
        """Иначе имя файла состояния увело бы запись за пределы каталога."""
        with pytest.raises(брокер.Отвергнуто):
            брокер.проверить_заявку({**ГОДНАЯ, "deployment_id": "../../etc/passwd"})

    def test_заявка_не_может_назвать_команду_или_службу(self, брокер):
        принято = брокер.проверить_заявку(dict(ГОДНАЯ))
        for запретное in ("command", "service", "repo", "path", "script"):
            assert запретное not in принято


class TestСтатусыРазличаются:
    def test_все_пять_статусов_объявлены(self, брокер):
        текст = (ROOT / "automation" / "deploy" / "lords-deploy-broker").read_text(
            encoding="utf-8")
        for статус in ("PRECHECK_FAILED_NO_CHANGE", "BUILD_FAILED_NO_CHANGE",
                       "SWITCH_FAILED_NO_CHANGE", "ROLLED_BACK_VERIFIED",
                       "DEPLOYED_AND_VERIFIED"):
            assert статус in текст, f"статус {статус} не используется"

    def test_откат_не_объявляется_без_смены_ссылки(self, брокер):
        """Отказ в предполёте обязан давать PRECHECK_FAILED_NO_CHANGE.

        Прошлая выкладка объявила ROLLED_BACK, не тронув production: страж
        noexec остановил её до единого действия. Слово «откат» в отчёте
        отправляет искать несуществующее событие.
        """
        текст = (ROOT / "automation" / "deploy" / "lords-deploy-broker").read_text(
            encoding="utf-8")
        # Возврат ROLLED_BACK_VERIFIED существует ровно в одном месте — там, где
        # откат действительно выполнен и подтверждён.
        assert текст.count('return "ROLLED_BACK_VERIFIED"') == 1
        начало = текст.index("def _откатить")
        assert текст.index('return "ROLLED_BACK_VERIFIED"') > начало, (
            "ROLLED_BACK_VERIFIED возвращается вне процедуры отката")

    def test_неподтверждённый_откат_называется_иначе(self, брокер):
        текст = (ROOT / "automation" / "deploy" / "lords-deploy-broker").read_text(
            encoding="utf-8")
        assert 'return "ROLLBACK_FAILED"' in текст, (
            "неподтверждённый откат обязан отличаться от подтверждённого")


class TestСериализация:
    def test_запись_даёт_разбираемый_json(self, брокер, tmp_path):
        путь = tmp_path / "свод.json"
        данные = {"sites": {"lords-02": {"verdict": "DEPLOYED_AND_VERIFIED"}},
                  "note": "строка\nс переводом"}
        брокер.записать_json(путь, данные)
        назад = json.loads(путь.read_text(encoding="utf-8"))
        assert назад == данные

    def test_в_файле_нет_буквального_экранирования_вне_строк(self, брокер, tmp_path):
        r"""Свод прошлой выкладки содержал `{\n    "lords-02"` — не JSON.

        Причина: `printf '%s' "${x}"` не разворачивает `\n` в аргументе, только
        в формате. Здесь запись идёт через json.dumps, и проверка требует, чтобы
        результат разбирался обратно, а не выглядел похоже.
        """
        путь = tmp_path / "свод.json"
        брокер.записать_json(путь, {"sites": {"lords-02": {"verdict": "OK"}}})
        текст = путь.read_text(encoding="utf-8")
        assert "{\\n" not in текст
        json.loads(текст)

    def test_запись_атомарна(self, брокер, tmp_path):
        путь = tmp_path / "свод.json"
        брокер.записать_json(путь, {"a": 1})
        брокер.записать_json(путь, {"a": 2})
        assert json.loads(путь.read_text(encoding="utf-8")) == {"a": 2}
        assert not list(tmp_path.glob("*.tmp")), "временный файл остался"


class TestГраницыПомощника:
    def test_витрина_вне_списка_отвергается(self, помощник):
        with pytest.raises(помощник.Отказ):
            помощник._сайт("yummy")

    def test_ревизия_обязана_быть_полной(self, помощник):
        with pytest.raises(помощник.Отказ):
            помощник._ревизия("119605bbaca2")
        assert помощник._ревизия("1" * 40) == "1" * 40

    def test_оболочка_не_используется(self, помощник):
        """Разбор дерева, а не поиск подстроки.

        Первая редакция искала `shell=True` в тексте и падала на собственной
        документации, где эта строка названа запрещённой. Проверка, срабатывающая
        на упоминании запрета, не отличает запрет от нарушения.
        """
        import ast
        дерево = ast.parse(Path(помощник.__file__).read_text(encoding="utf-8"))
        нарушения = [
            узел.lineno for узел in ast.walk(дерево)
            if isinstance(узел, ast.Call)
            for ключ in узел.keywords
            if ключ.arg == "shell" and getattr(ключ.value, "value", False) is True
        ]
        assert нарушения == [], f"оболочка вызвана в строках {нарушения}"

    def test_источник_артефакта_ограничен_префиксами(self, помощник):
        assert помощник.ИСТОЧНИКИ
        assert all(п.startswith("/") for п in помощник.ИСТОЧНИКИ)

    def test_пути_заданы_в_помощнике_а_не_в_запросе(self, помощник):
        assert str(помощник.RUNTIME_ROOT) == "/srv/lords"
        assert помощник.САЙТЫ == ("lords-01", "lords-02", "lords-03")


class TestДефектыВыкладки38и39:
    """Две проверки, которых не хватило и которые стоили двух прогонов.

    38: предполёт требовал увидеть новый шаблон ДО выкладки. Условие
    невыполнимо по построению, и выкладка отказывала, ни разу не дойдя до
    отрисовки. Проверка, которую нельзя пройти, не защищает.

    39: сценарий обновления зовёт `python -m factory`, а модуль находится
    относительно текущего каталога. Приёмщик работает из корня файловой
    системы, и первый же вызов дал «No module named factory» за ноль секунд.
    Штатный юнит объявляет WorkingDirectory=/srv/site-factory/repo.
    """

    def test_маркер_шаблона_не_проверяется_до_переключения(self, брокер):
        текст = (ROOT / "automation" / "deploy" / "lords-deploy-broker").read_text(
            encoding="utf-8")
        assert 'метка != "before"' in текст, (
            "маркер нового шаблона снова требуется до выкладки")

    def test_рабочий_каталог_обеспечен_штатным_юнитом(self, помощник):
        """Дефект 39 вытеснен дефектом 40, и это правильный исход.

        Сначала рабочий каталог задавался вызову напрямую. Затем выяснилось,
        что подпроцессом запускать вообще нельзя — credentials приходят только
        через LoadCredential, — и канарейка ушла в штатный юнит. Юнит объявляет
        WorkingDirectory сам, поэтому отдельная правка стала лишней: причина
        устранена целиком, а не заклеена.

        Проверка сторожит именно это: константа обязана совпадать с
        WorkingDirectory юнита, чтобы расхождение было заметно, если юнит
        когда-нибудь переедет.
        """
        assert str(помощник.СОСТОЯНИЕ_КОРЕНЬ) == "/srv/site-factory/repo"
        объявлено = subprocess.run(
            ["systemctl", "show", "-p", "WorkingDirectory", "--value",
             помощник.ОБНОВЛЕНИЕ_СЛУЖБА],
            capture_output=True, text=True).stdout.strip()
        if объявлено:
            assert объявлено.rstrip("/").endswith("/srv/site-factory/repo"), объявлено

    def test_рабочий_каталог_содержит_пакет_factory(self, помощник):
        """Иначе `python -m factory` не найдёт модуль, как и случилось."""
        assert (помощник.СОСТОЯНИЕ_КОРЕНЬ / "factory").is_dir()


class TestКанарейкаИдётШтатнымЮнитом:
    """Дефект LORDS-DEPLOYCTL-CREDENTIALS-40.

    Сценарий обновления запускался подпроцессом и отказывал:
    «CREDENTIALS_DIRECTORY не задан: Lords читает credentials только через
    systemd LoadCredential». Это защита, а не препятствие — секрет не должен
    приходить процессу иначе, и обойти её значило бы сломать то, ради чего она
    поставлена. Канарейка идёт штатным юнитом, получающим credentials законно.
    """

    def test_запускается_служба_а_не_сценарий(self, помощник):
        текст = Path(помощник.__file__).read_text(encoding="utf-8")
        assert '"systemctl", "start", ОБНОВЛЕНИЕ_СЛУЖБА' in текст
        assert помощник.ОБНОВЛЕНИЕ_СЛУЖБА == "lords-content-refresh.service"
        assert '_выполнить(["/bin/bash", str(ОБНОВЛЕНИЕ)]' not in текст, (
            "сценарий снова запускается напрямую — credentials не придут")

    def test_дропин_удаляется_на_любом_пути(self, помощник):
        import ast
        дерево = ast.parse(Path(помощник.__file__).read_text(encoding="utf-8"))
        нашли = False
        for узел in ast.walk(дерево):
            if isinstance(узел, ast.Try) and узел.finalbody:
                текст = ast.unparse(ast.Module(body=узел.finalbody, type_ignores=[]))
                if "ДРОПИН.unlink" in текст:
                    нашли = True
        assert нашли, "drop-in канарейки не удаляется в finally — чужая настройка не вернётся"

    def test_имя_дропина_сортируется_после_чужого(self, помощник):
        """Иначе наши переменные не перекрыли бы соседнюю полосу."""
        assert помощник.ДРОПИН.name > "zz-canary-29.conf"
        assert помощник.ДРОПИН.name.endswith(".conf")


class TestКанарейкаНеПрисоединяетсяКЧужомуПрогону:
    """Дефект LORDS-DEPLOYCTL-JOIN-RUNNING-41.

    `systemctl start` для уже работающего юнита не запускает второй прогон — он
    присоединяется к идущему. Тот загрузил окружение при своём старте, до
    появления нашего drop-in, и канареечных переменных не видел: прогон
    отработал два с половиной часа и выпустил обычное обновление каталога, а
    выкладка считала его своим.

    Тот же класс, что и дефект 32: факт возврата команды принят за факт
    запуска. Здесь запуск обязан доказать себя новым InvocationID.
    """

    def test_ждём_простоя_перед_запуском(self, помощник):
        текст = Path(помощник.__file__).read_text(encoding="utf-8")
        assert "while _занят(ОБНОВЛЕНИЕ_СЛУЖБА):" in текст, (
            "канарейка запускается, не убедившись, что юнит свободен")

    def test_занятость_шире_чем_active(self, помощник):
        """Дефект LORDS-DEPLOYCTL-BUSY-IS-NOT-ONLY-ACTIVE.

        Проверка на один лишь `active` пропускает юнит, который в этот миг
        поднимается или останавливается: `is-active` вернёт `activating` или
        `deactivating`, канарейка сочтёт его свободным и присоединится ровно к
        тому прогону, от которого её отделяет дефект 41. Поэтому занятость
        обязана покрывать и переходные состояния.
        """
        assert set(помощник.ЗАНЯТЫЕ_СОСТОЯНИЯ) >= {
            "active", "activating", "deactivating", "reloading"}, (
            "занятость сведена к active: переходные состояния прошли бы как простой")

    def test_новый_invocationid_обязателен(self, помощник):
        текст = Path(помощник.__file__).read_text(encoding="utf-8")
        assert "InvocationID не изменился" in текст, (
            "запуск принимается без доказательства нового прогона")

    def test_ожидание_простоя_ограничено(self, помощник):
        текст = Path(помощник.__file__).read_text(encoding="utf-8")
        assert "--wait-idle" in текст, "ожидание простоя не ограничено по времени"
