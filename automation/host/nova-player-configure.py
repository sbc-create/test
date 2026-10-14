#!/usr/bin/env python3
"""PLAYER_CONFIGURE — подключение плеера витрине. Только шесть названных целей.

Операции подключения плеера в штатном брокере не было: рендерер берёт Publisher ID
из бокового файла `player-<site>.json` рядом со снимком каталога, и создавать этот
файл было нечем. Отсюда и дефект — пять витрин из шести отдавали `noaccess`.

Что делает операция:
  1) берёт назначенный номер из учёта реестра ячеек и сверяет его с объявлением
     пакета витрины — расхождение останавливает операцию (значение не печатается);
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
ОБРАЗЕЦ = ЛОГОВО / "player-lords-01.json"
ПЛЕЙЛИСТ = "https://plapi.cdnvideohub.com/api/v1/player/sv/playlist"

# Таблицы файлов направления здесь больше нет, и это намеренно.
#
# Она хранила ОДНО значение на направление: `yami` — один файл на animedia.icu,
# animedia.space, zonafilm.space и арендаторов Yummy. Пока она была запасным
# источником, повторный запуск операции возвращал витрине прежний номер и молча
# отменял назначение владельца. Номер теперь берётся только из учёта реестра
# (см. `назначение`); чтобы вернуть откат, недостаточно поправить одну строку.

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
    #: Арендатор верхнего приложения. Описывает принадлежность витрины и попадает
    #: в отчёт; номер издателя он НЕ выбирает — это делает учёт реестра.
    профиль: str


#: Закрытый список. Ничего, кроме этих шести, операция не принимает.
ЦЕЛИ = {
    ц.сайт: ц
    for ц in (
        Цель("lords-01", "lordfilm47.space", "lords-nova-01.service", "lords"),
        Цель("lords-02", "lordserial33.biz", "nova-lords-02.service", "lords"),
        Цель("lords-03", "1lordserials1.online", "nova-lords-03.service", "lords"),
        # Юнит у zona-01 свой: витрина переехала в собственную ячейку, а
        # nova-zona-01.service запускает общий загрузчик и этот домен больше не
        # обслуживает. Арендатор здесь — `yami`, но номер издателя он уже не
        # выбирает: с D214 номер приходит из учёта реестра, и прежняя история
        # про «секрет соседней витрины lords-01» закрыта вместе с таблицей
        # направлений.
        Цель("zona-01", "zonafilm.space", "nova-zonafilm-space.service", "yami"),
        Цель("animedia-01", "animedia.icu", "nova-animedia-01.service", "yami"),
        Цель("animedia-02", "animedia.space", "nova-animedia-02.service", "yami"),
    )
}


#: Реестр ячеек и основание для относительных `repo.path`.
#:
#: Берётся от МЕСТА ЭТОГО ФАЙЛА, а не от `/srv/site-factory/repo`: там лежит
#: отдельная, более старая копия пакета, в которой каталога `var/site-repos`
#: нет вовсе. Прочитав реестр оттуда, функция ничего не нашла бы и молча
#: вернулась бы к значению направления — то есть вернула бы витрине прежний
#: номер, ровно тот запасной путь, который и требовалось закрыть. Проверено
#: 2026-10-01: ветка в той копии `claude/players-only-production-009`,
#: `var/site-repos` отсутствует.
КОРЕНЬ_ПАКЕТА = Path(__file__).resolve().parents[2]
РЕЕСТР_ЯЧЕЕК = КОРЕНЬ_ПАКЕТА / "config" / "site-cells.json"
КОРЕНЬ_РЕПОЗИТОРИЕВ = КОРЕНЬ_ПАКЕТА


def запись_ячейки(site_id: str) -> dict:
    """Запись витрины в реестре ячеек. Любая неудача — отказ, не пустота.

    Прежняя редакция возвращала пустое значение на каждой неудаче, и вызывающий
    после этого брал номер направления — то есть ПРЕЖНИЙ номер витрины. Для
    `yami` файл направления один на семейство, поэтому тихий возврат отменял
    назначение владельца и выглядел снаружи как «изменение не удержалось».
    """
    try:
        реестр = json.loads(РЕЕСТР_ЯЧЕЕК.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        raise SystemExit(
            f"{site_id}: реестр ячеек {РЕЕСТР_ЯЧЕЕК} не читается ({type(ош).__name__}). "
            "Номер издателя назначает владелец и хранит учёт реестра; брать значение "
            "направления вместо него запрещено — оно вернёт витрине прежний номер"
        ) from None
    ячейки = реестр.get("cells") or реестр.get("sites") or []
    список = ячейки if isinstance(ячейки, list) else list(ячейки.values())
    for ячейка in список:
        if ячейка.get("site_id") == site_id:
            return ячейка
    raise SystemExit(
        f"{site_id}: записи витрины нет в {РЕЕСТР_ЯЧЕЕК}. Это BLOCKED_INPUT: "
        "назначенный номер неизвестен, а подставлять значение направления нельзя")


def назначение(site_id: str) -> str:
    """Назначенный владельцем Publisher ID. Значение возвращается, но не печатается.

    Источник один — учёт реестра (`publisher.publisher_id`, D177). Объявление
    пакета (`config/site.json#publisher_id_expected`) обязано совпадать с ним:
    это тот файл, который попадает в выкладку, и расхождение означает, что
    следующая штатная операция отдаст витрине другой номер. Какое из двух
    значений верно, решает владелец, поэтому расхождение — отказ, а не правка.

    Значение публичное: оно стоит в разметке атрибутом `data-publisher-id`
    (D89/D138), поэтому его место в конфигурации витрины, а не в хранилище
    секретов. Секретом остаётся `api_token`, и он сюда не попадает.
    """
    ячейка = запись_ячейки(site_id)
    учёт = str((ячейка.get("publisher") or {}).get("publisher_id") or "").strip()
    if not учёт:
        raise SystemExit(
            f"{site_id}: в учёте реестра нет publisher_id. Это BLOCKED_INPUT, а не "
            "повод взять значение направления: номер назначает владелец")
    # Плеер вызывает Number(publisherId): нечисловое даёт NaN и 400 от провайдера.
    if not учёт.isdigit() or учёт.startswith("0"):
        raise SystemExit(f"{site_id}: publisher_id в учёте реестра непригоден")

    путь = str((ячейка.get("repo") or {}).get("path") or "").strip()
    if not путь:
        raise SystemExit(
            f"{site_id}: в реестре не записан repo.path, и объявление пакета "
            "проверить нечем; без сверки операция не выполняется")
    файл = КОРЕНЬ_РЕПОЗИТОРИЕВ / путь / "config" / "site.json"
    try:
        данные = json.loads(файл.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        raise SystemExit(
            f"{site_id}: {файл} не читается ({type(ош).__name__}). Это и есть тот "
            "случай, в котором прежняя редакция тихо возвращала номер направления"
        ) from None
    объявлено = str(данные.get("publisher_id_expected") or "").strip()
    if not объявлено:
        raise SystemExit(
            f"{site_id}: пакет витрины не объявляет publisher_id_expected, а учёт "
            "реестра номер назначает. Следующая выкладка отдала бы витрине другое "
            "значение, поэтому операция останавливается")
    if объявлено != учёт:
        raise SystemExit(
            f"{site_id}: учёт реестра и объявление пакета расходятся. Какое из двух "
            "верно — решает владелец, а не эта операция; значения не печатаются")
    return учёт


def издатель(цель: Цель) -> str:
    """Publisher ID витрины. Возвращается значение, но никогда не печатается."""
    return назначение(цель.сайт)


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
    восстанавливаться из канонической конфигурации, иначе после чистой
    пересборки витрина тихо вернётся к прежнему неполному покрытию.

    Профиль берётся от МЕСТА ЭТОГО ФАЙЛА — от того же корня, что и реестр.
    Прежняя редакция читала `/srv/site-factory/repo/config/site-profiles`, где
    лежит отдельная, более старая копия пакета (измерено 2026-10-01, там же
    описано для реестра), и при любой неудаче чтения возвращала
    `external-ids`. У всех шести целей в профиле стоит `provider-id`, поэтому
    молчаливая подмена означала бы выложенный боковой файл с другим режимом,
    упавшее покрытие просмотра и поиск причины в данных каталога.

    Отсутствие профиля для НАЗВАННОЙ цели — отказ: список целей закрыт, профиль
    есть у каждой, и «нет профиля» здесь значит «пакет не тот».
    """
    файл = КОРЕНЬ_ПАКЕТА / "config" / "site-profiles" / f"{цель.сайт}.json"
    try:
        профиль = json.loads(файл.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        raise SystemExit(
            f"{цель.сайт}: профиль витрины {файл} не читается "
            f"({type(ош).__name__}). Подставить режим по умолчанию нельзя: у всех "
            "шести целей он provider-id, и подмена уронила бы покрытие просмотра"
        ) from None
    режим = str((профиль.get("player") or {}).get("source_mode") or "").strip()
    if режим not in ("external-ids", "provider-id"):
        raise SystemExit(
            f"{цель.сайт}: в профиле {файл} нет пригодного player.source_mode")
    return режим


def боковой_файл(цель: Цель) -> Path:
    return ЛОГОВО / f"player-{цель.сайт}.json"


def записать(цель: Цель, pub: str) -> None:
    """Атомарная запись бокового файла: витрина не увидит половины файла."""
    uid, gid, режим = владение_образца()
    содержимое = {
        "publisher_id": pub,
        "source_mode": режим_источника(цель),
        "provenance": (
            "учёт реестра ячеек config/site-cells.json#publisher.publisher_id, "
            "подтверждённый объявлением пакета config/site.json#publisher_id_expected "
            "(D177/D138)"),
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
