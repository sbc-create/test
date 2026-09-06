"""Проба потребителя: запускается интерпретатором SEO, а не ядра.

Файл живёт в дереве ядра, но исполняется чужим Python. Причина измерена:
ядро работает на 3.10.12, потребитель — на 3.11.16 и пользуется `enum.StrEnum`,
которого в 3.10 нет. Ввезти потребителя в интерпретатор ядра невозможно.

Это не обходной приём, а верное устройство проверки. Контракт пересекает
границу процесса в виде JSON — ровно так, как он пересекает её в работе.
Проверка, выполненная ввозом чужого модуля, доказала бы совместимость
объектов в одной памяти, а не совместимость контракта.

Читает файл с записями контракта, прогоняет их через настоящий код SEO и
печатает машинный итог. Ненулевой код возврата означает, что потребитель
контракт не принял.
"""
from __future__ import annotations

import datetime as dt
import json
import sys


def main() -> int:
    путь = sys.argv[1]
    записи = json.loads(open(путь, encoding="utf-8").read())

    from seo_engine.content import authoritative_kind as ak
    from seo_engine.policy import eligibility as el
    from seo_engine.policy import playback as pb

    итог: dict[str, object] = {
        "consumerCompatibility": ak.COMPATIBILITY,
        "checks": [],
        "failures": [],
    }

    def проверка(имя: str, условие: bool, деталь: str = "") -> None:
        итог["checks"].append({"name": имя, "passed": bool(условие),
                               "detail": деталь})
        if not условие:
            итог["failures"].append(f"{имя}: {деталь}")

    for запись in записи:
        ожидание = запись["expect"]
        payload = запись["contentIdentity"]
        вид = ak.from_payload(payload)

        проверка(f"{запись['case']}: вид",
                 вид.kind.value == ожидание["contentKind"],
                 f"получено {вид.kind.value}, ждали {ожидание['contentKind']}")
        проверка(f"{запись['case']}: состояние вида",
                 вид.status.value == ожидание["identityStatus"],
                 f"получено {вид.status.value}")
        проверка(f"{запись['case']}: разметка",
                 вид.schema_type == ожидание["schemaType"],
                 f"получено {вид.schema_type!r}")

        момент = dt.datetime.now(dt.UTC)
        наблюдено = запись.get("playbackObservedAt") or ""
        подтверждено = (dt.datetime.fromisoformat(наблюдено)
                        if наблюдено else None)
        if подтверждено is not None:
            момент = подтверждено + dt.timedelta(hours=1)
        видео = pb.from_core(запись["playbackReasonCode"],
                             confirmed_at=подтверждено,
                             identifiers=tuple(запись.get("externalIds") or ()))
        можно, почему = видео.may_promise(момент)
        проверка(f"{запись['case']}: право обещать просмотр",
                 можно is ожидание["mayPromisePlayback"],
                 f"получено {можно} ({почему})")

        решение = el.decide(el.Inputs(
            domain=запись["domain"], path=запись["canonicalPath"], kind=вид,
            playback=видео, profile_version=запись["profileVersion"],
            profile_allows_kinds=(вид.kind,) if вид.usable else (),
            confirmed_facts=запись.get("confirmedFacts", 6),
            is_canonical_owner=True, has_unique_text=True,
            observed_at=момент, evidence_ref="contract"),
            today=момент.date(), now=момент)
        проверка(f"{запись['case']}: решение о странице",
                 решение.state.value == ожидание["eligibility"],
                 f"получено {решение.state.value}, ждали "
                 f"{ожидание['eligibility']}")

    итог["passed"] = len(итог["failures"]) == 0
    print(json.dumps(итог, ensure_ascii=False))
    return 0 if итог["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
