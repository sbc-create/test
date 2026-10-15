"""Преобразования конфигурации nginx для правки `http → https` и `www → апекс`.

Проверяется на образцах, а не на `/etc/nginx`: инструмент готовит правку живых
доменов, и ошибка границы блока означала бы неперезагружаемый nginx — то есть
падение СОСЕДНИХ сайтов, а не только своего.
"""
import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "stage_https_www_fix",
    КОРЕНЬ / "automation" / "local" / "stage-https-www-fix.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)

ОБРАЗЕЦ = """# zonafilm.cc — витрина zona-02.
map $uri $cell_robots_zona_02 {
    include /etc/nginx/cells/zona-02.robots;
}

server {
    listen 80;
    listen [::]:80;
    server_name zonafilm.cc www.zonafilm.cc;

    server_tokens off;
    add_header X-Robots-Tag $cell_robots_zona_02 always;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type "text/plain";
    }

    location / {
        proxy_pass http://cell_zona_02;
        proxy_set_header Host $host;
    }

    location = /healthz {
        proxy_pass http://cell_zona_02/healthz;
        access_log off;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name zonafilm.cc www.zonafilm.cc;

    ssl_certificate     /etc/letsencrypt/live/zonafilm.cc/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zonafilm.cc/privkey.pem;

    location / {
        proxy_pass http://cell_zona_02;
    }
}
"""


@pytest.fixture()
def файл(tmp_path):
    п = tmp_path / "zona-02.conf"
    п.write_text(ОБРАЗЕЦ, encoding="utf-8")
    return п


def уравновешены(текст: str) -> bool:
    return текст.count("{") == текст.count("}")


def test_блоки_размечены_по_скобкам():
    найдено = инс.блоки(ОБРАЗЕЦ)
    assert len(найдено) == 2
    assert all(уравновешены(тело) for _, _, тело in найдено)
    # `map` блоком server не считается, хотя фигурные скобки у него есть.
    assert all(тело.startswith("server") for _, _, тело in найдено)


def test_порт_80_отдаёт_308_на_апекс(файл):
    новый = инс.перенаправить_порт_80(файл, "zonafilm.cc")
    блок80 = next(т for _, _, т in инс.блоки(новый) if "listen 80" in т)
    assert "return 308 https://zonafilm.cc$request_uri;" in блок80
    assert "proxy_pass http://cell_zona_02;\n" not in блок80
    assert уравновешены(новый)


def test_acme_и_healthz_остаются(файл):
    """ACME — условие продления сертификата, `/healthz` — чужой контракт."""
    новый = инс.перенаправить_порт_80(файл, "zonafilm.cc")
    блок80 = next(т for _, _, т in инс.блоки(новый) if "listen 80" in т)
    assert "/.well-known/acme-challenge/" in блок80
    assert "location = /healthz" in блок80


def test_повтор_не_применяется(файл):
    файл.write_text(инс.перенаправить_порт_80(файл, "zonafilm.cc"),
                    encoding="utf-8")
    with pytest.raises(инс.НеПрименимо):
        инс.перенаправить_порт_80(файл, "zonafilm.cc")


def test_www_уходит_только_из_блока_443(файл):
    """Имя www обязано остаться на порту 80: по нему идёт проверка ACME.

    Строка `server_name` у блоков 80 и 443 здесь буква в букву одна и та же —
    ровно на этом замена по тексту и ломала продление сертификата.
    """
    новый = инс.www_отдельным_блоком(ОБРАЗЕЦ, файл, "zonafilm.cc")
    блоки = {("80" if "listen 80" in т else "443"): т
             for _, _, т in инс.блоки(новый) if "www.zonafilm.cc" not in
             инс.имена(т) or "listen 80" in т}
    блок80 = next(т for _, _, т in инс.блоки(новый) if "listen 80" in т)
    assert "www.zonafilm.cc" in инс.имена(блок80)
    апекс443 = [т for _, _, т in инс.блоки(новый)
                if "listen 443" in т and "proxy_pass" in т]
    assert апекс443 and инс.имена(апекс443[0]) == ["zonafilm.cc"]
    assert блоки  # разметка не развалилась


def test_у_www_свой_блок_с_тем_же_сертификатом(файл):
    новый = инс.www_отдельным_блоком(ОБРАЗЕЦ, файл, "zonafilm.cc")
    www = [т for _, _, т in инс.блоки(новый)
           if инс.имена(т) == ["www.zonafilm.cc"]]
    assert len(www) == 1
    assert "return 308 https://zonafilm.cc$request_uri;" in www[0]
    assert "/etc/letsencrypt/live/zonafilm.cc/fullchain.pem" in www[0]
    # Переменная режима объявлена map-ом другого файла: ссылка на неё здесь
    # дала бы «unknown variable» и неперезагружаемый nginx. Проверяются
    # ДИРЕКТИВЫ, а не комментарии: причина названа в самом блоке текстом.
    директивы = [с for с in www[0].split("\n")
                 if с.strip() and not с.strip().startswith("#")]
    assert not [с for с in директивы if "$cell_robots" in с], директивы
    assert уравновешены(новый)


def test_без_имени_www_правка_не_придумывается(файл):
    без_www = ОБРАЗЕЦ.replace(" www.zonafilm.cc", "")
    with pytest.raises(инс.НеПрименимо):
        инс.www_отдельным_блоком(без_www, файл, "zonafilm.cc")


def test_блок_443_без_сертификата_отвергается(файл):
    битый = ОБРАЗЕЦ.replace(
        "    ssl_certificate     /etc/letsencrypt/live/zonafilm.cc/fullchain.pem;\n", "")
    with pytest.raises(инс.НеПрименимо):
        инс.www_отдельным_блоком(битый, файл, "zonafilm.cc")


def test_перечни_доменов_не_пересекаются_по_смыслу():
    """Домен не может быть одновременно жёстким и мягким случаем www."""
    assert not set(инс.ДОМЕНЫ_WWW) & set(инс.ДОМЕНЫ_WWW_МЯГКО)
    assert set(инс.ДОМЕНЫ_WWW) <= set(инс.ДОМЕНЫ_HTTP)


def test_подготовленные_файлы_уравновешены():
    """Уже выложенные в var/staged-nginx файлы — с целой разметкой."""
    каталог = КОРЕНЬ / "var" / "staged-nginx"
    if not каталог.is_dir():
        pytest.skip("правка ещё не подготовлена в этом окружении")
        return
    for ф in sorted(каталог.glob("*.conf")):
        т = ф.read_text(encoding="utf-8")
        assert уравновешены(т), ф.name
        for _, _, тело in инс.блоки(т):
            if "listen 80" in тело:
                assert "return 308 https://" in тело, ф.name
