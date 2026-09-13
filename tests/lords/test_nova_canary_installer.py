"""Привилегированная поверхность установщика canary.

Этот файл запускается от root. Значит каждый его аргумент — это вход в
привилегированную операцию, и проверять надо не «работает ли установка», а
что именно установщик СОГЛАСЕН сделать по чужой просьбе.

Три дыры, которые здесь закрыты и проверены:

* `--expect-sha256` был необязательным. Запуск без флага устанавливал любой
  файл: единственное, что отличало артефакт от произвольных байтов, можно было
  просто не указать.
* `--artifact` принимал любой путь. Привилегированный запуск с чужим путём
  записывал произвольное содержимое в файл, который исполняет КАЖДАЯ витрина
  парка, а не только выбранная.
* имя юнита бралось из таблицы и не сверялось с живой конфигурацией. Таблица —
  ожидание; истина в nginx и systemd, и расходиться они могут молча.

Проверки идут без единой привилегированной операции: до записи установщик
обязан отказать, и именно отказ здесь и проверяется.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-nova-canary.py"


@pytest.fixture(scope="module")
def уст():
    спец = importlib.util.spec_from_file_location("nova_canary", ИСХОДНИК)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["nova_canary"] = модуль
    спец.loader.exec_module(модуль)
    return модуль


class TestПереченьВитрин:
    def test_чужая_витрина_отвергается(self, уст):
        class Арг:
            site = "yummy-site"
            artifact = str(ИСХОДНИК)
            expect_sha256 = "0" * 64
            design_version = "1.1.0"
            commit = "0" * 40
            build_id = "X"
            record = None
        with pytest.raises(уст.Отказ) as ош:
            уст.установить(Арг())
        assert "вне перечня" in str(ош.value)

    def test_в_перечне_только_разрешённые(self, уст):
        assert set(уст.ВИТРИНЫ) == {"lords-01", "zona-01"}

    def test_у_каждой_витрины_свой_манифест_и_юнит(self, уст):
        манифесты = [в["manifest"] for в in уст.ВИТРИНЫ.values()]
        юниты = [в["unit"] for в in уст.ВИТРИНЫ.values()]
        порты = [в["port"] for в in уст.ВИТРИНЫ.values()]
        assert len(set(манифесты)) == len(манифесты), "витрины делят манифест"
        assert len(set(юниты)) == len(юниты), "витрины делят юнит"
        assert len(set(порты)) == len(порты), "витрины делят порт"


class TestИсточникАртефакта:
    def test_путь_вне_разрешённых_каталогов_отвергается(self, уст, tmp_path):
        чужой = tmp_path / "lords-frontend.py"
        чужой.write_text("print('чужое')\n", encoding="utf-8")
        with pytest.raises(уст.Отказ) as ош:
            уст.проверить_источник(чужой)
        assert "вне разрешённых каталогов" in str(ош.value)

    def test_обход_каталога_не_проходит(self, уст):
        # Префикс разрешённого каталога есть, но `resolve` уводит наружу.
        коварный = КОРЕНЬ / "automation" / "host" / ".." / ".." / ".." / "etc" / "passwd"
        with pytest.raises(уст.Отказ):
            уст.проверить_источник(коварный)

    def test_символическая_ссылка_отвергается(self, уст, tmp_path):
        цель = tmp_path / "секрет"
        цель.write_text("s", encoding="utf-8")
        ссылка = КОРЕНЬ / "automation" / "host" / ".тест-ссылка.py"
        try:
            ссылка.symlink_to(цель)
            with pytest.raises(уст.Отказ) as ош:
                уст.проверить_источник(ссылка)
            assert "символическая ссылка" in str(ош.value)
        finally:
            if ссылка.is_symlink():
                ссылка.unlink()

    def test_каталог_вместо_файла_отвергается(self, уст):
        with pytest.raises(уст.Отказ):
            уст.проверить_источник(КОРЕНЬ / "automation" / "host")

    def test_настоящий_артефакт_принимается(self, уст):
        путь = уст.проверить_источник(КОРЕНЬ / "automation" / "host" / "lords-frontend.py")
        assert путь.is_file()


class TestОтпечатокОбязателен:
    def test_флаг_объявлен_обязательным(self, уст):
        """Без отпечатка разбор аргументов обязан провалиться, а не подставить
        пустую строку и установить что угодно."""
        with pytest.raises(SystemExit):
            уст.main(["install", "--site", "lords-01",
                      "--artifact", str(ИСХОДНИК),
                      "--design-version", "1.1.0",
                      "--commit", "0" * 40, "--build-id", "X"])

    def test_несовпадающий_отпечаток_отвергается_до_записи(self, уст):
        class Арг:
            site = "lords-01"
            artifact = str(КОРЕНЬ / "automation" / "host" / "lords-frontend.py")
            expect_sha256 = "1" * 64
            design_version = "1.1.0"
            commit = "0" * 40
            build_id = "X"
            record = None
        with pytest.raises(уст.Отказ) as ош:
            уст.установить(Арг())
        assert "отпечаток артефакта не тот" in str(ош.value)


class TestНичегоЛишнегоНеТрогает:
    ЗАПРЕЩЁННОЕ = ("nsupdate", "certbot", "/etc/nginx", "systemctl daemon-reload",
                   "iptables", "resolvectl", "/etc/hosts", "letsencrypt")

    def test_в_коде_нет_обращений_к_dns_tls_и_nginx(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        # Комментарии перечисляют, чего установщик НЕ делает, — их не считаем.
        код = "\n".join(с for с in текст.splitlines()
                        if not с.lstrip().startswith("#"))
        найдено = [з for з in self.ЗАПРЕЩЁННОЕ if з in код]
        assert not найдено, f"установщик касается запрещённого: {найдено}"

    def test_подоболочка_не_используется(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        assert "shell=True" not in текст
        assert "os.system" not in текст

    def test_манифест_не_исполняется(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        for опасное in ("eval(", "exec(", "pickle", "yaml.load("):
            assert опасное not in текст, f"установщик умеет исполнять данные: {опасное}"

    def test_перезапускается_ровно_один_юнит(self):
        """systemctl вызывается ИЗ ОДНОГО места и ровно с одним именем юнита.

        Проверка стоит на числе точек вызова, а не на тексте команды: вторая
        точка — это второй способ перезапустить что-нибудь ещё, и появиться она
        может незаметно, при добавлении «заодно перезагрузим таймер».
        """
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        вызовы = [с for с in текст.splitlines() if "systemctl" in с
                  and not с.lstrip().startswith("#")]
        assert len(вызовы) == 1, f"точек вызова systemctl стало {len(вызовы)}: {вызовы}"
        assert "действие, юнит" in вызовы[0], (
            "команда systemctl собирается не из одного действия и одного юнита")
        # Единственное действие, с которым она вызывается, — перезапуск.
        действия = set(re.findall(r'_юнит\("(\w+)"', текст))
        assert действия == {"restart"}, f"установщик умеет не только restart: {действия}"


class TestЗапись:
    def test_замена_атомарна(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        assert ".replace(цель)" in текст, "замена файла не атомарна"

    def test_точка_отката_создаётся_до_записи(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        установка = текст[текст.index("def установить"):текст.index("def откатить")]
        точка = установка.index("_точка_отката")
        запись = установка.index("_атомарно(манифест")
        assert точка < запись, "точка отката создаётся после первой записи"

    def test_режимы_выставляются_явно(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        assert "манифест.chmod(0o644)" in текст
        assert "АРТЕФАКТ.chmod(0o755)" in текст

    def test_в_журнале_нет_секретов(self, уст):
        """Запись установки не содержит ни одного поля с секретом.

        Publisher ID и токены живут в файлах вне репозитория, и установщик их
        не читает вовсе — проверяется именно это, а не маскирование вывода.
        """
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        for секретное in ("publisher", "token", "api_key", "password", "htpasswd"):
            assert секретное not in текст.lower(), f"установщик знает про {секретное}"


class TestОткат:
    def test_неполная_точка_отвергается(self, уст, tmp_path):
        class Арг:
            site = "lords-01"
            point = str(tmp_path)
            record = None
        with pytest.raises(уст.Отказ) as ош:
            уст.откатить(Арг())
        assert "неполна" in str(ош.value)

    def test_откат_сверяет_и_диск_и_отданное(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        assert "disk_fingerprint_match" in текст
        assert "served_fingerprint_match" in текст
        # Вердикт обязан требовать оба совпадения.
        вердикт = текст[текст.index('запись["verdict"] = (\n        "ROLLED_BACK_VERIFIED"'):]
        голова = вердикт[:400]
        assert "disk_fingerprint_match" in голова and "served_fingerprint_match" in голова


class TestДоказательЦепочкиНаходится:
    """Путь к доказателю — часть привилегированного пути.

    Ошибка на единицу в `parents[...]` превращает обязательную сверку в отказ
    на ровном месте: установщик не находит доказатель и отказывается работать.
    Проверяется именно существование файла по тому пути, который вычисляет сам
    установщик, а не по написанному от руки.
    """

    def test_путь_вычисляется_и_файл_существует(self, уст):
        from pathlib import Path
        путь = Path(уст.__file__).resolve().parents[2] / "scripts" / "prove_serving_chain.py"
        assert путь.is_file(), f"доказателя нет по вычисленному пути: {путь}"

    def test_установщик_ссылается_именно_на_этот_путь(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        assert 'parents[2] / "scripts" / "prove_serving_chain.py"' in текст
