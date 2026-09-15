"""Витрина Yummy закрывает индексацию по домену, а не по всему семейству.

Дефект `YUMMY-SITE-GLOBALLY-NOINDEX`.

yummyani.site — основной продвигаемый домен владельца, но витрина закрывала его
безусловно: `X-Robots-Tag: noindex, nofollow` на каждом ответе и собственный
`robots.txt` с `Disallow: /`. Заголовок ставился в `_отдать`, через который
проходят и проксируемые страницы приложения, поэтому верное попутевое решение
приложения наружу не доходило. Снаружи дефект незаметен: сайт отвечает 200,
выглядит рабочим и просто не индексируется.

Здесь закрепляется три свойства:

* домен из списка открытых не получает глобального запрета;
* домен вне списка закрыт ровно как прежде — yummyani.org и yummyani.biz
  политику не меняют;
* открытый домен не отдаёт свой `robots.txt`, а пропускает запрос приложению,
  у которого уже есть и точечные запреты, и адрес карты сайта.

Проверка поведенческая: модуль импортируется с разным `YUMMY_VARIANT_DOMAIN`.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ФРОНТ = КОРЕНЬ / "automation" / "host" / "yummy-frontend.py"


def _загрузить(monkeypatch, **окружение):
    """Импортирует витрину с заданным окружением.

    Модуль читает политику на уровне модуля, поэтому каждый домен требует
    отдельного импорта — переиспользовать один объект нельзя.
    """
    for имя in ("YUMMY_VARIANT_DOMAIN", "YUMMY_INDEXABLE_DOMAINS"):
        monkeypatch.delenv(имя, raising=False)
    for имя, значение in окружение.items():
        monkeypatch.setenv(имя, значение)
    загрузчик = importlib.machinery.SourceFileLoader("yummy_frontend_под_тестом",
                                                     str(ФРОНТ))
    спец = importlib.util.spec_from_loader(загрузчик.name, загрузчик)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules[загрузчик.name] = модуль
    try:
        загрузчик.exec_module(модуль)
    finally:
        sys.modules.pop(загрузчик.name, None)
    return модуль


def _исходник() -> str:
    return ФРОНТ.read_text(encoding="utf-8")


class TestПолитикаПоДомену:
    def test_site_открыт(self, monkeypatch):
        м = _загрузить(monkeypatch, YUMMY_VARIANT_DOMAIN="yummyani.site")
        assert м.ИНДЕКСИРУЕТСЯ is True, (
            "yummyani.site — основной продвигаемый домен, он не может быть закрыт")

    @pytest.mark.parametrize("домен", ["yummyani.org", "yummyani.biz"])
    def test_остальные_домены_закрыты(self, monkeypatch, домен):
        """Политику .org и .biz эта правка не пересматривает."""
        м = _загрузить(monkeypatch, YUMMY_VARIANT_DOMAIN=домен)
        assert м.ИНДЕКСИРУЕТСЯ is False, f"{домен} открылся вместе с .site"

    def test_по_умолчанию_открыт_ровно_один_домен(self, monkeypatch):
        м = _загрузить(monkeypatch, YUMMY_VARIANT_DOMAIN="yummyani.site")
        assert sorted(м.ОТКРЫТЫЕ_ДОМЕНЫ) == ["yummyani.site"], (
            "список открытых доменов по умолчанию должен содержать один адрес")

    def test_список_задаётся_окружением(self, monkeypatch):
        """Политика меняется юнитом, а не правкой кода."""
        м = _загрузить(monkeypatch, YUMMY_VARIANT_DOMAIN="yummyani.org",
                       YUMMY_INDEXABLE_DOMAINS="yummyani.org, yummyani.site")
        assert м.ИНДЕКСИРУЕТСЯ is True

    def test_пустой_список_закрывает_всё(self, monkeypatch):
        """Аварийное закрытие не требует правки кода."""
        м = _загрузить(monkeypatch, YUMMY_VARIANT_DOMAIN="yummyani.site",
                       YUMMY_INDEXABLE_DOMAINS="")
        assert м.ИНДЕКСИРУЕТСЯ is False


class TestГлобальныйЗапретСнят:
    def test_заголовок_под_условием(self):
        """`X-Robots-Tag` больше не безусловен в отправке ответа."""
        т = _исходник()
        assert 'if not ИНДЕКСИРУЕТСЯ:\n            self.send_header("X-Robots-Tag"' in т, (
            "глобальный X-Robots-Tag вернулся: он снова закроет открытый домен")

    def test_нет_ветки_глобального_index(self):
        """Глобальный `index` перекрыл бы точечные запреты приложения.

        Проверяется вызов, а не текст: слова «index, follow» встречаются в
        пояснении рядом, и сравнение по всему исходнику ловило бы комментарий.
        """
        вызовы = re.findall(r'send_header\(\s*"X-Robots-Tag"\s*,\s*"([^"]*)"',
                            _исходник())
        assert вызовы == ["noindex, nofollow"], (
            "витрина не должна объявлять глобальный index: при конфликте "
            f"директив побеждает строгая. Найдено: {вызовы}")

    def test_robots_txt_перехватывается_только_на_закрытом(self):
        т = _исходник()
        assert 'if путь == "/robots.txt" and not ИНДЕКСИРУЕТСЯ:' in т, (
            "на открытом домене robots.txt обязан уходить приложению: у него "
            "точечные запреты и адрес карты сайта")

    def test_закрытый_домен_отдаёт_прежний_запрет(self):
        """Поведение стенда не меняется."""
        assert 'b"User-agent: *\\nDisallow: /\\n"' in _исходник()


СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "yummy-indexing-apply.sh"


def _сценарий() -> str:
    return СЦЕНАРИЙ.read_text(encoding="utf-8")


class TestСценарийПрименения:
    """Выкладка обязана быть обратимой и узкой.

    Точки отката для yummy на хосте не было: в `.rollback` лежат только
    lords-01 и zona-01. Сценарий обязан создать её сам, до первой мутации.
    """

    def test_сценарий_существует(self):
        assert СЦЕНАРИЙ.is_file(), (
            "правку нужно чем-то применять: адаптер цели — operator_applied, "
            "фабрика обязана отдать оператору идемпотентный сценарий")

    def test_перезапускается_только_витрина_site(self):
        т = _сценарий()
        assert "nova-yummy-site.service" in т
        for чужой in ("nova-yummy-org", "nova-yummy-biz", "lords-nova",
                      "nova-zona", "nova-animedia", "nginx"):
            assert f"systemctl restart {чужой}" not in т, (
                f"сценарий перезапускает {чужой} — за пределами scope")

    def test_снапшот_снимается_до_мутации(self):
        """Порядок важен: `install` после `cp` исходного файла, не наоборот."""
        т = _сценарий()
        снимок = т.index('cp -a "${TARGET}" "${SNAPSHOT}"')
        выкладка = т.index('install -m 0755 -o root -g root "${SOURCE}"')
        assert снимок < выкладка, (
            "файл выкладывается раньше снимка — откатываться будет не на что")

    def test_есть_автооткат_по_ошибке(self):
        т = _сценарий()
        assert 'trap \'restore "${SNAPSHOT}"\' ERR' in т
        assert "set -Eeuo pipefail" in т, (
            "без -E ловушка ERR не сработает внутри функции")

    def test_приёмка_проверяет_соседние_площадки(self):
        """Правка не должна открыть .org и .biz."""
        т = _сценарий()
        assert "yummyani.org" in т and "yummyani.biz" in т
        assert "ПЕРЕСТАЛ быть закрытым" in т

    def test_идемпотентность(self):
        т = _сценарий()
        assert 'if [ "${SOURCE_SUM}" = "${TARGET_SUM}" ]; then' in т, (
            "повторный запуск обязан обойтись без выкладки и перезапуска")
