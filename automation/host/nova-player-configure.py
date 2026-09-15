#!/usr/bin/env python3
"""PLAYER_CONFIGURE — подключение плеера витрине. Только шесть названных целей.

Операции подключения плеера в штатном брокере не было: рендерер берёт Publisher ID
из бокового файла `player-<site>.json` рядом со снимком каталога, и создавать этот
файл было нечем. Отсюда и дефект — пять витрин из шести отдавали `noaccess`.

Что делает операция:
  1) читает Publisher ID из уже существующего секрета профиля (значение не печатается);
  2) пишет боковой файл атомарно, сохраняя прежний во временной копии;
  3) перезапускает юнит витрины;
  4) проверяет живьём: элемент провайдера в разметке и реальная дорожка у провайдера;
  5) при неудаче возвращает прежнее состояние и завершается ненулевым кодом.

Границы жёсткие. Список целей закрыт, посторонняя витрина отклоняется до любых
действий. Операция трогает только player-контур: боковой файл и перезапуск юнита.
"""

from __future__ import annotations

import argparse
import contextlib
import grp
import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ЛОГОВО = Path("/srv/lords/.frontend")
ПРОФИЛИ_ВИТРИН = Path("/srv/site-factory/repo/config/site-profiles")
ОБРАЗЕЦ = ЛОГОВО / "player-lords-01.json"
ПЛЕЙЛИСТ = "https://plapi.cdnvideohub.com/api/v1/player/sv/playlist"

#: Профили учётных данных. Значения живут только в этих файлах и наружу не выходят.
ПРОФИЛИ = {
    "lords": "/etc/site-factory/secrets/lords/{site}/cdnvideohub-publisher-id",
    "yami": "/srv/sites/yummyani-staging/runtime/cdnvideohub/publisher-id",
}

ЗАПРЕЩЁННЫЕ = (
    "витрина без доступа",
    "Просмотр на витрине не подключён",
    "не выдан идентификатор издателя",
)


@dataclass(frozen=True)
class Цель:
    сайт: str
    домен: str
    юнит: str
    профиль: str
    #: Откуда берётся Publisher ID. Для витрин без собственного каталога секретов
    #: указывается витрина-владелец пары: пара одна на семейство.
    секрет_витрины: str


#: Закрытый список. Ничего, кроме этих шести, операция не принимает.
ЦЕЛИ = {
    ц.сайт: ц
    for ц in (
        Цель("lords-01", "lordfilm47.space", "lords-nova-01.service", "lords", "lords-01"),
        Цель("lords-02", "lordserial33.biz", "nova-lords-02.service", "lords", "lords-02"),
        Цель("lords-03", "1lordserials1.online", "nova-lords-03.service", "lords", "lords-03"),
        Цель("zona-01", "zonafilm.space", "nova-zona-01.service", "lords", "lords-01"),
        Цель("animedia-01", "animedia.icu", "nova-animedia-01.service", "yami", ""),
        Цель("animedia-02", "animedia.space", "nova-animedia-02.service", "yami", ""),
    )
}


def издатель(цель: Цель) -> str:
    """Publisher ID профиля. Возвращается значение, но никогда не печатается."""
    шаблон = ПРОФИЛИ[цель.профиль]
    путь = Path(шаблон.format(site=цель.секрет_витрины))
    значение = путь.read_text(encoding="utf-8").strip()
    # Плеер вызывает Number(publisherId): нечисловое даёт NaN и 400 от провайдера.
    if not значение.isdigit() or значение.startswith("0"):
        raise SystemExit(f"{цель.сайт}: Publisher ID профиля {цель.профиль} непригоден")
    return значение


def владение_образца() -> tuple[int, int, int]:
    """Владелец и режим уже работающего бокового файла.

    Свой режим не выдумывается: витрину обслуживает отдельная учётная запись,
    и файл обязан читаться ею так же, как читается существующий.
    """
    if ОБРАЗЕЦ.exists():
        с = ОБРАЗЕЦ.stat()
        return с.st_uid, с.st_gid, с.st_mode & 0o777
    return pwd.getpwnam("claude").pw_uid, grp.getgrnam("claude").gr_gid, 0o644


def режим_источника(цель: Цель) -> str:
    """Режим выбора источника из профиля витрины.

    Значение живёт в git, а не в аргументах запуска: боковой файл обязан
    восстанавливаться из канонической конфигурации, иначе после чистой пересборки
    витрина тихо вернётся к прежнему неполному покрытию.
    """
    файл = ПРОФИЛИ_ВИТРИН / f"{цель.сайт}.json"
    try:
        профиль = json.loads(файл.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "external-ids"
    режим = str((профиль.get("player") or {}).get("source_mode") or "").strip()
    return режим if режим in ("external-ids", "provider-id") else "external-ids"


def боковой_файл(цель: Цель) -> Path:
    return ЛОГОВО / f"player-{цель.сайт}.json"


def записать(цель: Цель, pub: str) -> None:
    """Атомарная запись бокового файла: витрина не увидит половины файла."""
    uid, gid, режим = владение_образца()
    содержимое = {
        "publisher_id": pub,
        "source_mode": режим_источника(цель),
        "provenance": f"Secret Hub, профиль {цель.профиль}"
        + (f" (пара витрины {цель.секрет_витрины})" if цель.секрет_витрины else ""),
        "note": "значение вне git; файл читает рендерер витрины по соглашению имени",
    }
    цель_путь = боковой_файл(цель)
    с_врем = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(ЛОГОВО), prefix=".player-", suffix=".tmp", delete=False
    )
    try:
        json.dump(содержимое, с_врем, ensure_ascii=False, indent=1)
        с_врем.write("\n")
        с_врем.flush()
        os.fsync(с_врем.fileno())
        с_врем.close()
        os.chown(с_врем.name, uid, gid)
        os.chmod(с_врем.name, режим)
        os.replace(с_врем.name, цель_путь)
    except Exception:
        Path(с_врем.name).unlink(missing_ok=True)
        raise


def перезапуск(цель: Цель) -> None:
    subprocess.run(["systemctl", "restart", цель.юнит], check=True, timeout=120)
    # Витрина поднимает каталог с диска: до готовности она не отвечает.
    for _ in range(60):
        time.sleep(1)
        готово = subprocess.run(["systemctl", "is-active", "--quiet", цель.юнит], timeout=20)
        if готово.returncode == 0:
            return
    raise SystemExit(f"{цель.сайт}: юнит {цель.юнит} не поднялся после перезапуска")


def дождаться_витрины(цель: Цель, секунд: int = 300) -> None:
    """Ждёт, пока витрина начнёт отвечать.

    `systemctl is-active` says «active» сразу: юнит Type=simple. Но рендерер в это
    время ещё загружает снимок каталога на десятки мегабайт и не слушает порт.
    Проверка в этом окне даёт ложный отказ — именно он и случился на zona-01.
    """
    предел = time.monotonic() + секунд
    последняя = ""
    while time.monotonic() < предел:
        try:
            код, _ = страница(f"https://{цель.домен}/", timeout=20)
            if код == 200:
                return
            последняя = f"http={код}"
        except Exception as e:
            последняя = str(e)
        time.sleep(3)
    raise SystemExit(f"{цель.сайт}: витрина не отвечает после перезапуска ({последняя})")


def страница(url: str, timeout: int = 30) -> tuple[int, str]:
    зп = urllib.request.Request(url, headers={"User-Agent": "nova-player-configure"})
    with urllib.request.urlopen(зп, timeout=timeout) as о:
        return о.status, о.read().decode("utf-8", "replace")


def дорожка_есть(pub: str, kp: str, домен: str) -> tuple[bool, str]:
    """Спрашивает у провайдера настоящую дорожку. Пустой плеер за успех не считается."""
    url = f"{ПЛЕЙЛИСТ}?pub={pub}&id={kp}&aggr=kp"
    зп = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Origin": f"https://{домен}",
            "x-origin": f"https://{домен}",
            "Referer": f"https://{домен}/",
        },
    )
    try:
        with urllib.request.urlopen(зп, timeout=30) as о:
            тело = json.loads(о.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return False, f"provider http={e.code}"
    except Exception as e:  # сеть, разбор — всё это отказ доказательства
        return False, f"provider error={e}"
    вещи = тело.get("items") or []
    если_поток = bool(вещи and (вещи[0].get("cvhId") or вещи[0].get("vkId")))
    return если_поток, f"items={len(вещи)}"


def пригодные_слаги(цель: Цель, сколько: int) -> list[tuple[str, str]]:
    """Слаги с kp-идентификатором: только на них плеер вообще обязан появиться.

    Словарь `details` ключуется слагом витрины — он же и есть адрес страницы.
    """
    файл = ЛОГОВО / f"{цель.сайт}-details.json"
    данные = json.loads(файл.read_text(encoding="utf-8"))
    подробности = данные.get("details") or {}
    найдено: list[tuple[str, str]] = []
    for слаг, деталь in подробности.items():
        if len(найдено) >= сколько:
            break
        if not isinstance(деталь, dict):
            continue
        kp = str((деталь.get("external_ids") or {}).get("kp") or "").strip()
        if kp and слаг:
            найдено.append((слаг, kp))
    return найдено


def проверить(цель: Цель, pub: str, сколько: int) -> tuple[int, int, list[dict]]:
    ок = 0
    плохо = 0
    строки = []
    for слаг, kp in пригодные_слаги(цель, сколько):
        url = f"https://{цель.домен}/title/{слаг}/"
        строка = {"url": url, "kp": kp}
        try:
            код, html_ = страница(url)
        except Exception as e:
            строка["result"] = f"FETCH_ERROR:{e}"
            плохо += 1
            строки.append(строка)
            continue
        строка["http"] = код
        строка["element"] = "<video-player" in html_
        строка["sdk"] = "player.cdnvideohub.com" in html_
        строка["blocked_msgs"] = [м for м in ЗАПРЕЩЁННЫЕ if м in html_]
        поток, деталь = дорожка_есть(pub, kp, цель.домен)
        строка["provider"] = деталь
        строка["stream"] = поток
        if строка["element"] and строка["sdk"] and not строка["blocked_msgs"] and поток:
            строка["result"] = "PLAYER_WORKING"
            ок += 1
        elif строка["blocked_msgs"]:
            строка["result"] = "SITE_PROVIDER_CONFIGURATION_MISSING"
            плохо += 1
        elif not поток:
            # Источник в каталоге есть, но провайдер дорожки не отдал: это состояние
            # записи, а не витрины. Отказом подключения не считается.
            строка["result"] = "RECORD_SOURCE_MISSING"
        else:
            строка["result"] = "UNPROVEN"
            плохо += 1
        строки.append(строка)
    return ок, плохо, строки


def применить(цель: Цель, сколько: int) -> dict:
    pub = издатель(цель)
    путь = боковой_файл(цель)
    резерв = None
    if путь.exists():
        резерв = путь.with_suffix(".json.bak-player-configure")
        shutil.copy2(путь, резерв)

    записать(цель, pub)
    try:
        перезапуск(цель)
        дождаться_витрины(цель)
        ок, плохо, строки = проверить(цель, pub, сколько)
        if ок < 1 or плохо > 0:
            raise RuntimeError(f"проверка не пройдена: ok={ок} bad={плохо}")
    except Exception as e:
        строки_отказа = locals().get("строки") or []
        # Откат только player-изменения: боковой файл и перезапуск. Больше ничего.
        if резерв is not None:
            os.replace(резерв, путь)
        else:
            путь.unlink(missing_ok=True)
        # Откат уже сделан: боковой файл возвращён. Если и перезапуск не удался,
        # витрина поднимется прежней конфигурацией сама — ронять отчёт об откате
        # из-за этого нельзя.
        with contextlib.suppress(Exception):
            перезапуск(цель)
        return {
            "site": цель.сайт,
            "domain": цель.домен,
            "status": "ROLLED_BACK",
            "reason": str(e),
            "rows": строки_отказа,
        }
    if резерв is not None:
        резерв.unlink(missing_ok=True)
    return {
        "site": цель.сайт,
        "domain": цель.домен,
        "status": "CONFIGURED",
        "source_mode": режим_источника(цель),
        "checked": len(строки),
        "player_working": ок,
        "rows": строки,
    }


def откатить(цель: Цель) -> dict:
    путь = боковой_файл(цель)
    было = путь.exists()
    путь.unlink(missing_ok=True)
    перезапуск(цель)
    return {"site": цель.сайт, "status": "REVERTED" if было else "NOTHING_TO_REVERT"}


def главная() -> int:
    р = argparse.ArgumentParser(description="PLAYER_CONFIGURE для шести витрин")
    р.add_argument("--sites", required=True, help="через запятую: " + ", ".join(sorted(ЦЕЛИ)))
    р.add_argument("--apply", action="store_true", help="без него — только план")
    р.add_argument("--rollback", action="store_true", help="снять привязку плеера")
    р.add_argument("--checks", type=int, default=5, help="сколько карточек проверить")
    а = р.parse_args()

    просьба = [s.strip() for s in а.sites.split(",") if s.strip()]
    чужие = [s for s in просьба if s not in ЦЕЛИ]
    if чужие:
        print(json.dumps({"error": "target not allowed", "sites": чужие}, ensure_ascii=False))
        return 2
    if os.geteuid() != 0:
        print(
            json.dumps(
                {"error": "нужен root: Publisher ID читается из защищённого файла"},
                ensure_ascii=False,
            )
        )
        return 2

    итог = []
    for имя in просьба:
        ц = ЦЕЛИ[имя]
        if а.rollback:
            итог.append(откатить(ц))
        elif а.apply:
            итог.append(применить(ц, а.checks))
        else:
            итог.append(
                {
                    "site": ц.сайт,
                    "domain": ц.домен,
                    "unit": ц.юнит,
                    "profile": ц.профиль,
                    "sidecar": str(боковой_файл(ц)),
                    "source_mode": режим_источника(ц),
                    "status": "PLANNED",
                }
            )
    print(json.dumps(итог, ensure_ascii=False, indent=1))
    плохо = [с for с in итог if с.get("status") == "ROLLED_BACK"]
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(главная())
