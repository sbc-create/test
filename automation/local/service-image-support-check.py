#!/usr/bin/env python3
"""Умеет ли ИНТЕРПРЕТАТОР СЛУЖБЫ действительно преобразовать изображение.

Зачем именно так, а не «установлен ли пакет». 23.10 правка уменьшения обложек
(T330) была выпущена и не действовала: Pillow стоял в каталоге пользователя
`claude`, а служба идёт системным `/usr/bin/python3` и его не видела. Ни один
тест этого не показал, потому что тесты шли в окружении сессии. Поэтому здесь
проверяется НЕ импорт и НЕ наличие пакета, а РЕАЛЬНОЕ преобразование: создать
кадр, уменьшить, закодировать в WebP, прочитать обратно и сверить размеры.

ЧЕМ ПРОВЕРЯЕТСЯ, по порядку строгости:

1. системный интерпретатор без пользовательского каталога (`python3 -s`) — это
   ровно то, чем запускается служба;
2. от имени УЧЁТНОЙ ЗАПИСИ службы (`sudo -u <пользователь>`), если это
   разрешено вызывающему. Не разрешено — так и печатается, а не умалчивается;
3. живая витрина: обложка, которая обязана приходить уменьшенной.

Исходы различимы: ГОДНО / НЕ ГОДНО (с причиной) / НЕ ПРОВЕРЕНО (с причиной).
«Нет прав спросить» не выдаётся за «работает».

    python3 automation/local/service-image-support-check.py
    python3 automation/local/service-image-support-check.py --user animedia-icu \
        --url https://animedia.icu/poster/<uuid>.webp --expect-width 480

Коды: 0 — годно, 1 — не годно, 2 — не проверено.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

#: Проба делает ровно то, что делает обработчик обложек: уменьшает и кодирует.
#: Печатает одну строку JSON, чтобы вызывающий не разбирал текст.
ПРОБА = r'''
import io, json
try:
    from PIL import Image, features
except Exception as e:
    print(json.dumps({"ок": False, "почему": type(e).__name__ + ": " + str(e)}))
    raise SystemExit(0)
try:
    кадр = Image.new("RGB", (1000, 1400), (40, 80, 120))
    уменьшенный = кадр.resize((480, 672), Image.LANCZOS)
    буфер = io.BytesIO()
    уменьшенный.save(буфер, format="WEBP", quality=85, method=6)
    байты = буфер.getvalue()
    обратно = Image.open(io.BytesIO(байты))
    обратно.load()
    print(json.dumps({"ок": обратно.size == (480, 672), "байт": len(байты),
                      "размер": list(обратно.size),
                      "webp": bool(features.check("webp")),
                      "версия": getattr(__import__("PIL"), "__version__", "?")}))
except Exception as e:
    print(json.dumps({"ок": False, "почему": type(e).__name__ + ": " + str(e)}))
'''


def прогон(команда: list[str]) -> tuple[bool, dict, str]:
    try:
        г = subprocess.run(команда, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as сбой:
        return False, {}, f"{type(сбой).__name__}: {сбой}"
    строка = (г.stdout or "").strip().splitlines()
    if not строка:
        return False, {}, (г.stderr or "нет вывода").strip()[:160]
    try:
        return True, json.loads(строка[-1]), ""
    except json.JSONDecodeError:
        return False, {}, строка[-1][:160]


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--user", default="", help="учётная запись службы")
    р.add_argument("--url", default="", help="адрес обложки живой витрины")
    р.add_argument("--expect-width", type=int, default=0)
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    итог: dict = {"проверки": []}
    плохо = непроверено = 0

    # 1. системный интерпретатор, как у службы
    ладно, ответ, почему = прогон(["python3", "-s", "-c", ПРОБА])
    з = {"что": "системный python3 -s", "исход": "ГОДНО"}
    if not ладно:
        з.update({"исход": "НЕ ПРОВЕРЕНО", "почему": почему})
        непроверено += 1
    elif not ответ.get("ок"):
        з.update({"исход": "НЕ ГОДНО",
                  "почему": ответ.get("почему", "преобразование не удалось")})
        плохо += 1
    else:
        з.update({"байт": ответ.get("байт"), "размер": ответ.get("размер"),
                  "webp": ответ.get("webp"), "версия": ответ.get("версия")})
    итог["проверки"].append(з)

    # 2. от имени учётной записи службы
    if а.user:
        ладно, ответ, почему = прогон(
            ["sudo", "-n", "-u", а.user, "python3", "-s", "-c", ПРОБА])
        з = {"что": f"от имени {а.user}", "исход": "ГОДНО"}
        if not ладно:
            з.update({"исход": "НЕ ПРОВЕРЕНО",
                      "почему": f"спросить не разрешено: {почему}"})
            непроверено += 1
        elif not ответ.get("ок"):
            з.update({"исход": "НЕ ГОДНО",
                      "почему": ответ.get("почему", "преобразование не удалось")})
            плохо += 1
        else:
            з.update({"байт": ответ.get("байт"), "версия": ответ.get("версия")})
        итог["проверки"].append(з)

    # 3. живая витрина
    if а.url:
        з = {"что": f"живая обложка {а.url.rsplit('/', 1)[-1]}",
             "исход": "ГОДНО"}
        г = subprocess.run(["curl", "-s", "-m", "30", "-H",
                            "User-Agent: factory-image-support", а.url],
                           capture_output=True)
        данные = г.stdout
        if not данные:
            з.update({"исход": "НЕ ПРОВЕРЕНО", "почему": "обложка не получена"})
            непроверено += 1
        else:
            ладно2, ответ2, почему2 = прогон([
                "python3", "-c",
                "import io,json,sys;from PIL import Image;"
                "к=Image.open(io.BytesIO(sys.stdin.buffer.read()));"
                "print(json.dumps({'ок':True,'размер':list(к.size),"
                "'формат':к.format}))"])
            # читаем сами, без конвейера: stdin в прогон не передать
            try:
                from PIL import Image
                import io as _io
                кадр = Image.open(_io.BytesIO(данные))
                кадр.load()
                з.update({"байт": len(данные), "размер": list(кадр.size),
                          "формат": кадр.format})
                if а.expect_width and кадр.size[0] > а.expect_width:
                    з.update({"исход": "НЕ ГОДНО",
                              "почему": f"ширина {кадр.size[0]} больше"
                                        f" ожидаемой {а.expect_width}"})
                    плохо += 1
            except Exception as сбой:                # noqa: BLE001
                з.update({"исход": "НЕ ПРОВЕРЕНО",
                          "почему": f"{type(сбой).__name__}"})
                непроверено += 1
        итог["проверки"].append(з)

    итог["исход"] = ("НЕ ГОДНО" if плохо else
                     ("НЕ ПРОВЕРЕНО" if непроверено and len(
                         итог["проверки"]) == непроверено else "ГОДНО"))
    if а.json:
        print(json.dumps(итог, ensure_ascii=False, indent=1))
    else:
        print(f"исход: {итог['исход']}")
        for з in итог["проверки"]:
            хвост = (f" — {з['почему']}" if з.get("почему") else
                     f" {з.get('размер', '')} {з.get('байт', '')} Б"
                     f" PIL {з.get('версия', '')}")
            print(f"   {з['исход']:13} {з['что']}{хвост}")
        if итог["исход"] == "НЕ ГОДНО":
            print("   уменьшение обложек НЕ РАБОТАЕТ в окружении службы:"
                  " выпуск правки без этой зависимости ничего не изменит")
    return 0 if итог["исход"] == "ГОДНО" else (1 if плохо else 2)


if __name__ == "__main__":
    sys.exit(главное())
