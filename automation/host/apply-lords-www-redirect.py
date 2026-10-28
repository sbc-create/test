#!/usr/bin/env python3
"""MOD-218: канонический хост держит приложение, а не только слой nginx.

    python3 automation/host/apply-lords-www-redirect.py \
        --target var/site-repos/lordserial33-biz \
        --target var/site-repos/1lordserials1-online [--check] [--dry-run]

Что измерено
------------

28.10: www-зеркала всех трёх действующих витрин Lords отвечают 308 на основной
домен. Но держат переход РАЗНЫЕ слои. У `lordserials22.info` он сделан в
приложении (`src/lords-frontend.py`, начало `do_GET`). У `lordserial33.biz` и
`1lordserials1.online` переходов по хосту в приложении НОЛЬ: поиск строк с 308
вместе с хостом или доменом даёт 0 попаданий у обеих. Единственное, что их
приложение делает с www, — снимает приставку при сравнении хоста
(`removeprefix("www.")`), то есть считает www тем же сайтом и отдаёт по нему
обычную страницу 200.

Значит единственность канонического хоста у этих двух обеспечивает только слой
nginx. Риск не умозрительный: ровно такой дефект измерен на
`lordserials22.info` 18.10 — www-адреса отвечали 200, `index, follow` и
canonical на www-адрес, то есть полный индексируемый дубль сайта (T225). Там
его и закрыли в приложении.

Почему перенос безопасен — проверено, а не предположено
-------------------------------------------------------

* `ИНДЕКС_ДОМЕН = os.environ.get("LORDS_INDEXING_SITE", "").strip()` — строка
  одинакова во всех трёх рантаймах, и `run.py` ставит эту переменную из
  `config.domain`;
* `_переход(self, цель)` есть во всех трёх;
* `urlparse` импортирован во всех трёх;
* `do_HEAD` зовёт `do_GET` во всех трёх, поэтому блок покрывает и HEAD —
  проверка требует оба метода;
* якорь `def do_GET(self):` + `д = self.данные` в целевых рантаймах
  единственный.

Ворота: сначала прогнать на копии
---------------------------------

Инструмент правит ВРЕМЕННУЮ копию витрины, доставляет туда
`checks/www_redirect.py` от `lordserials22.info` и ЗАПУСКАЕТ её. Правка идёт
по-настоящему только если прогон дал 0. Так ворота не сверяют признаки, а
смотрят на поведение, и не могут отстать от самой проверки.

Чего инструмент не делает: не трогает слой nginx и ничего о нём не утверждает;
не меняет правил индексации; не правит снимки; не перезаписывает существующий
блок и существующую проверку.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

#: Доставляется ИСПРАВЛЕННАЯ проверка из своего дерева, а не копия от 22i:
#: та берёт адрес снимка догадкой по домену (у 1on это даёт несуществующий
#: путь, MOD-220) и роняется с PermissionError на закрытых файлах постоянных
#: данных, которые есть ровно у 33 и 1on (MOD-224).
ИСТОЧНИК_ПРОВЕРКИ = (pathlib.Path(__file__).resolve().parent
                     / "lords-checks" / "www_redirect.py")
ИСТОЧНИК_РЕЗОЛВЕРА = (pathlib.Path(__file__).resolve().parent
                      / "lords-checks" / "_snapshot_dir.py")

ЯКОРЬ = "    def do_GET(self):\n        д = self.данные"

БЛОК = '''    def do_GET(self):
        # REQ-SEO-URL п.2–3 (knowledge/SEO_KNOWLEDGE_PACK.md §1; T225, B001;
        # MOD-218, перенос с lordserials22.info): www-зеркало — не дубль
        # сайта, а 308 на основной домен с тем же путём и запросом. Прочие
        # хосты (localhost, сам домен, чужие имена) и /healthz — без
        # изменений; HEAD приходит сюда же через do_HEAD.
        #
        # До этой правки приложение лишь снимало приставку www при сравнении
        # хоста, то есть считало www тем же сайтом и отдавало по нему 200;
        # единственность канонического хоста держал только слой nginx.
        заголовки = getattr(self, "headers", None)
        хост = ((заголовки.get("Host") if заголовки is not None else "") or "").split(":")[0].strip().lower()
        if (ИНДЕКС_ДОМЕН and хост == "www." + ИНДЕКС_ДОМЕН.lower()
                and urlparse(self.path).path != "/healthz"):
            return self._переход(f"https://{ИНДЕКС_ДОМЕН.lower()}"
                                 + (self.path if self.path.startswith("/") else "/"))
        д = self.данные'''

ПРИЗНАКИ = (
    'ИНДЕКС_ДОМЕН = os.environ.get("LORDS_INDEXING_SITE", "").strip()',
    "def _переход(self, цель: str):",
    "def do_HEAD(self):\n        self.do_GET()",
    "urlparse",
)

РАННЕР = "checks/run.sh"
#: Якорь вызова — СТРУКТУРНЫЙ: строка вставляется после ПОСЛЕДНЕЙ строки
#: `check `. Якорь по имени чужой проверки непереносим: `check "contrast"` я
#: взял от zona-02, а у Lords его нет вовсе — инструмент честно отказал с
#: названной причиной и ничего не записал.
СТРОКА_РАННЕРА = (
    '# www-зеркало — 308 на основной домен, не дубль сайта (MOD-218, перенос\n'
    '# T225/B001). Код 2 — «не измерено» (снимка нет, CI): пропуск, а не провал.\n'
    'check "www-redirect"            bash -c \'python3 checks/www_redirect.py; '
    'rc=$?; [ "$rc" -eq 2 ] && exit 0; exit "$rc"\'\n')


def _правка(корень: pathlib.Path) -> tuple[bool, str]:
    """Правит рантайм и кладёт проверку. Возвращает (сделано, причина)."""
    рантайм = корень / "src" / "lords-frontend.py"
    if not рантайм.is_file():
        return False, f"нет {рантайм}"
    текст = рантайм.read_text(encoding="utf-8")
    if "MOD-218" in текст:
        return False, "блок перехода уже стоит"
    нет = [п for п in ПРИЗНАКИ if п not in текст]
    if нет:
        коротко = [п.split("(")[0][:46] for п in нет]
        return False, f"в рантайме нет: {', '.join(коротко)}"
    n = текст.count(ЯКОРЬ)
    if n != 1:
        return False, f"якорь do_GET найден {n} раз(а), ожидался 1"
    рантайм.write_text(текст.replace(ЯКОРЬ, БЛОК, 1), encoding="utf-8")

    if not ИСТОЧНИК_ПРОВЕРКИ.is_file():
        return False, f"нет источника проверки {ИСТОЧНИК_ПРОВЕРКИ}"
    проверка = корень / "checks" / "www_redirect.py"
    if not проверка.is_file():
        shutil.copyfile(ИСТОЧНИК_ПРОВЕРКИ, проверка)
    резолвер = корень / "checks" / "_snapshot_dir.py"
    if not резолвер.is_file():
        if not ИСТОЧНИК_РЕЗОЛВЕРА.is_file():
            return False, f"нет источника резолвера {ИСТОЧНИК_РЕЗОЛВЕРА}"
        shutil.copyfile(ИСТОЧНИК_РЕЗОЛВЕРА, резолвер)

    раннер = корень / РАННЕР
    if раннер.is_file():
        т = раннер.read_text(encoding="utf-8")
        if "checks/www_redirect.py" not in т:
            строки = т.splitlines(keepends=True)
            места = [i for i, с in enumerate(строки) if с.startswith("check ")]
            if not места:
                return False, f"в {РАННЕР} нет ни одной строки `check `"
            строки.insert(места[-1] + 1, СТРОКА_РАННЕРА)
            раннер.write_text("".join(строки), encoding="utf-8")
    return True, "правка наложена"


def _прогнать_на_копии(цель: pathlib.Path) -> tuple[int, str]:
    врем = pathlib.Path(tempfile.mkdtemp(prefix="www-redirect-"))
    try:
        копия = врем / "repo"
        shutil.copytree(цель, копия, symlinks=True,
                        ignore=shutil.ignore_patterns(
                            "__pycache__", ".git", "var", "artifacts"))
        сделано, причина = _правка(копия)
        if not сделано:
            return -1, причина
        готово = subprocess.run(  # noqa: S603
            [sys.executable, "checks/www_redirect.py"],
            cwd=копия, capture_output=True, text=True, timeout=1200)
        хвост = (готово.stdout + готово.stderr).strip().splitlines()
        return готово.returncode, (хвост[-1][:200] if хвост else "")
    except subprocess.TimeoutExpired:
        return 124, "не уложилась в 1200 с"
    finally:
        shutil.rmtree(врем, ignore_errors=True)


def применить(цель: pathlib.Path, писать: bool) -> tuple[str, str]:
    рантайм = цель / "src" / "lords-frontend.py"
    if not рантайм.is_file():
        return "refuse", f"нет {рантайм}"
    if "MOD-218" in рантайм.read_text(encoding="utf-8"):
        return "skip", "блок перехода уже стоит"

    код, пояснение = _прогнать_на_копии(цель)
    if код == -1:
        return "refuse", f"правка на копии не наложилась: {пояснение}"
    if код != 0:
        исход = {2: "«не измерено»"}.get(код, f"код {код}")
        return "refuse", (f"прогон на копии дал {исход}: {пояснение}. Правка не "
                          "применена: переход, который не подтверждён проверкой, "
                          "защитой не является")
    if not писать:
        return "ok", ("прогон на копии зелёный; будет наложено: блок перехода в "
                      "рантайме, checks/www_redirect.py, вызов в " + РАННЕР)
    сделано, причина = _правка(цель)
    if not сделано:
        return "refuse", причина
    return "ok", ("наложено и подтверждено прогоном: блок перехода, "
                  "checks/www_redirect.py, вызов в " + РАННЕР)


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--target", action="append", required=True)
    р.add_argument("--check", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args()
    отказы = правок = 0
    for путь in а.target:
        цель = pathlib.Path(путь).resolve()
        исход, пояснение = применить(цель, писать=not (а.check or а.dry_run))
        print(f"[{исход:6s}] {цель.name}: {пояснение}")
        if исход == "refuse":
            отказы += 1
        elif исход == "ok":
            правок += 1
    if отказы:
        print(f"ОТКАЗ по {отказы} витринам: причина названа выше")
        return 2
    if а.check:
        return 1 if правок else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
