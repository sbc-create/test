"""Журнал обхода дописывается в блок server, а не внутрь location.

`access_log off;` внутри `location` — не объявление журнала блока, и принять
его за таковое значило бы дописать строку в неверное место: nginx отказал бы
при проверке, а отказ одного файла не даёт перезагрузиться ВСЕМ сайтам.
"""
import importlib.util
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "stage_crawl_log", КОРЕНЬ / "automation" / "local" / "stage-crawl-log.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)

СО_СВОИМ = """server {
    listen 443 ssl;
    server_name x.test;

    access_log /var/log/nginx/x.access.log;
    error_log  /var/log/nginx/x.error.log;

    location / {
        proxy_pass http://cell_x;
    }

    location = /healthz {
        access_log off;
    }
}
"""

БЕЗ_СВОЕГО = """server {
    listen 80;
    server_name y.test;

    location = /healthz {
        access_log off;
    }
}
"""


def test_свой_журнал_находится_на_уровне_блока():
    найдено = инс.свой_журнал(СО_СВОИМ)
    assert len(найдено) == 1
    начало, конец, отступ = найдено[0]
    assert СО_СВОИМ[начало:конец].endswith("x.access.log;")
    assert отступ == "    ", repr(отступ)


def test_access_log_off_в_location_журналом_блока_не_считается():
    assert инс.свой_журнал(БЕЗ_СВОЕГО) == []


def test_строка_дописывается_после_своего_журнала(tmp_path):
    ф = tmp_path / "x.conf"
    ф.write_text(СО_СВОИМ, encoding="utf-8")
    новый, сделано = инс.дописать(ф)
    assert сделано == ["x.test"]
    assert инс.СТРОКА in новый
    # Строка стоит в блоке server и ПОСЛЕ собственного журнала, который цел.
    assert новый.index("x.access.log;") < новый.index(инс.СТРОКА)
    assert "access_log /var/log/nginx/x.access.log;" in новый
    # И не внутри location: до неё не должно открыться ни одного location.
    до = новый[:новый.index(инс.СТРОКА)]
    assert до.count("location") == 0


def test_блок_без_своего_журнала_не_правится(tmp_path):
    ф = tmp_path / "y.conf"
    ф.write_text(БЕЗ_СВОЕГО, encoding="utf-8")
    новый, сделано = инс.дописать(ф)
    assert сделано == []
    assert новый == БЕЗ_СВОЕГО


def test_повтор_не_удваивает_строку(tmp_path):
    ф = tmp_path / "x.conf"
    ф.write_text(СО_СВОИМ, encoding="utf-8")
    первый, _ = инс.дописать(ф)
    ф.write_text(первый, encoding="utf-8")
    второй, сделано = инс.дописать(ф)
    assert сделано == []
    assert второй.count(инс.СТРОКА) == 1


def test_отступ_не_захватывает_перевод_строки(tmp_path):
    """Поймано своим diff: в отступ попадал перевод строки.

    Регулярное выражение с `\\s*` после `^` в многострочном режиме съедало
    предшествующий перевод строки, и между строками пояснения появлялись
    пустые. Конфигурация оставалась рабочей, но правка выглядела неряшливо и
    читалась как две разные вставки.
    """
    ф = tmp_path / "x.conf"
    ф.write_text(СО_СВОИМ, encoding="utf-8")
    новый, _ = инс.дописать(ф)
    строки = новый.split("\n")
    первая = next(i for i, с in enumerate(строки) if "Журнал обхода" in с)
    последняя = next(i for i, с in enumerate(строки) if "crawl.log" in с)
    вставка = строки[первая:последняя + 1]
    assert вставка, строки
    assert all(с.strip() for с in вставка), вставка
    assert all(с.startswith("    ") for с in вставка), вставка


def test_объявление_формата_есть_в_репозитории():
    """Строка ссылается на формат `crawl`: без объявления nginx не поднимется."""
    объявление = (КОРЕНЬ / "automation" / "host" / "nginx"
                  / "00-crawl-log.conf").read_text(encoding="utf-8")
    assert "log_format crawl" in объявление
    assert "map $http_user_agent $is_crawler" in объявление
    assert "$host" in объявление and "$server_name" in объявление
