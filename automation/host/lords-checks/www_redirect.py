"""www-зеркало — 308 на основной домен, а не индексируемый дубль (T225, 21.10; B001, образец T222).

Живая сверка 18.10 13:26Z: https://www.lordserials22.info/ и страницы под www
отвечали 200, index, follow, canonical на www-адрес — полный индексируемый
дубль сайта. Норма — единый канонический хост (SEO_KNOWLEDGE_PACK §1 п.2–3):
неканонический вариант — ровно один переход на итоговый адрес. Правка nginx
(B001) за владельцем; переход уровня приложения с ней совместим.

Проверка: витрина выпуска (run.py) на КОПИИ снимка ячейки (SITE_DATA_DIR либо
/srv/<домен-через-дефис>/data; снимок только читается), свой порт.
Ожидается: Host www.<домен> на / и /catalog/?page=2, GET и HEAD — 308,
Location https://<домен><тот же путь с запросом>, тела нет; WWW.<ДОМЕН>:443 —
тоже 308; Host <домен> и Host localhost — 200; /healthz под www не трогается.

Коды выхода: 0 — норма, 1 — дефект на месте, 2 — не измерено (снимка нет,
стенд не поднялся, ошибка выполнения).
"""
import sys

try:
    import http.client
    import json
    import os
    import shutil
    import socket
    import subprocess
    import tempfile
    import time
    from pathlib import Path

    КОРЕНЬ = Path(__file__).resolve().parent.parent
    ДОМЕН = json.loads((КОРЕНЬ / "config" / "site.json").read_text(encoding="utf-8"))["domain"].lower()
    # Адрес снимка — общим резолвером (MOD-220/MOD-223), а не догадкой по
    # домену: у 1lordserials1.online домен даёт /srv/1lordserials1-online, а
    # настоящий каталог называется /srv/site-1lordserials1-online, и проверка
    # уходила в «не измерено».
    def _каталог_снимков() -> str:
        import importlib.util as _иу
        путь = Path(__file__).resolve().parent / "_snapshot_dir.py"
        if not путь.is_file():
            return ""
        спец = _иу.spec_from_file_location("_snapshot_dir", путь)
        if спец is None or спец.loader is None:
            return ""
        модуль = _иу.module_from_spec(спец)
        try:
            спец.loader.exec_module(модуль)
            return модуль.каталог()
        except Exception:  # noqa: BLE001
            return ""

    ДАННЫЕ = Path(os.environ.get("SITE_DATA_DIR") or _каталог_снимков()
                  or f"/srv/{ДОМЕН.replace('.', '-')}/data")
    снимки = sorted(ДАННЫЕ.glob("*-catalog.json"))
except BaseException as e:  # noqa: BLE001 — и SystemExit импорта: сбой не равен дефекту
    print(f"НЕ ИЗМЕРЕНО: {e!r}")
    sys.exit(2)
if not снимки:
    print(f"НЕ ИЗМЕРЕНО: снимка в {ДАННЫЕ} нет — проверка выполняется на хосте площадки")
    sys.exit(2)

ПУТИ = ("/", "/catalog/?page=2")


def взять(порт: int, путь: str, хост: str, метод: str = "GET"):
    с = http.client.HTTPConnection("127.0.0.1", порт, timeout=90)
    try:
        с.request(метод, путь, headers={"Host": хост})
        о = с.getresponse()
        return о.status, о.getheader("Location"), о.read()
    finally:
        с.close()


def осмотреть(порт: int) -> list:
    for хост in (ДОМЕН, "localhost"):
        код, _, _ = взять(порт, "/", хост)
        if код != 200:
            return [f"НЕ ИЗМЕРЕНО: / с Host {хост} ответил {код}"]
    беды = []
    www = "www." + ДОМЕН
    for метод in ("GET", "HEAD"):
        for путь in ПУТИ:
            код, куда, тело = взять(порт, путь, www, метод)
            ожидание = f"https://{ДОМЕН}{путь}"
            if код != 308 or куда != ожидание:
                беды.append(f"{метод} {путь} с Host {www}: {код}, Location {куда!r}; "
                            f"ожидалось 308 на {ожидание}")
            elif тело:
                беды.append(f"{метод} {путь} с Host {www}: у перехода есть тело ({len(тело)} байт)")
    код, куда, _ = взять(порт, "/", f"{www}:443".upper())
    if код != 308 or куда != f"https://{ДОМЕН}/":
        беды.append(f"Host {www.upper()}:443 (регистр, порт): {код}, Location {куда!r}; ожидалось 308")
    код, _, _ = взять(порт, "/healthz", www)
    if код != 200:
        беды.append(f"/healthz под www: {код} — служебный путь трогать нельзя")
    return беды


def main() -> int:
    врем = Path(tempfile.mkdtemp(prefix="www-redirect-"))
    процесс = None
    try:
        данные = врем / "data"
        данные.mkdir()
        # Закрытые файлы ПРОПУСКАЮТСЯ, а не роняют проверку. Измерено 28.10:
        # у lordserial33.biz права 600 у lords-02-block-history.json (журнал
        # правок редактора) и lords-02-community.json (оценки и комментарии
        # посетителей), у 1lordserials1.online — у lords-03-community.json.
        # Закрытость этих данных правильна: они постоянные и принадлежат
        # посетителям и редакции. Проверке они не нужны — ей нужен снимок
        # каталога, — а копирование всего подряд роняло её с PermissionError
        # на тех самых витринах, где живые данные и есть.
        пропущено = []
        for ф in ДАННЫЕ.glob("*.json"):
            try:
                shutil.copyfile(ф, данные / ф.name)
            except (PermissionError, OSError):
                пропущено.append(ф.name)
        if пропущено:
            print(f"    | не читаются и пропущены: {', '.join(пропущено[:4])}")
        с = socket.socket(); с.bind(("127.0.0.1", 0)); порт = с.getsockname()[1]; с.close()
        процесс = subprocess.Popen([sys.executable, "run.py", "--port", str(порт), "--data-dir", str(данные)],
                                   cwd=КОРЕНЬ, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(240):
            if процесс.poll() is not None:
                print("НЕ ИЗМЕРЕНО: стенд завершился при старте")
                return 2
            try:
                if взять(порт, "/healthz", "localhost")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(1)
        else:
            print("НЕ ИЗМЕРЕНО: стенд не поднялся")
            return 2
        беды = осмотреть(порт)
        if беды and беды[0].startswith("НЕ ИЗМЕРЕНО"):
            print(беды[0])
            return 2
        for б in беды:
            print("FAIL:", б)
        if not беды:
            print(f"PASS: www.{ДОМЕН} — 308 на https://{ДОМЕН} с путём и запросом, без тела; "
                  f"{ДОМЕН} и localhost — 200; /healthz не тронут")
        return 1 if беды else 0
    finally:
        if процесс is not None and процесс.poll() is None:
            процесс.terminate()
            try:
                процесс.wait(15)
            except Exception:  # noqa: BLE001
                процесс.kill()
        shutil.rmtree(врем, ignore_errors=True)


try:
    код_выхода = main()
except BaseException as e:  # noqa: BLE001 — и SystemExit изнутри: сбой не равен дефекту
    if isinstance(e, KeyboardInterrupt):
        raise
    print(f"НЕ ИЗМЕРЕНО: проверка не выполнилась: {e!r}")
    код_выхода = 2
sys.exit(код_выхода if код_выхода in (0, 1, 2) else 2)
