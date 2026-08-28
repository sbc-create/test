"""Иконки сайта, собранные из токенов темы.

Вкладка без иконки выглядит незаконченной, а `/favicon.ico` отдавал 404 на всех
трёх доменах. Иконка рисуется здесь процедурно из цветов темы: это собственная
геометрическая метка, а не чей-то знак, и никакой внешний файл для неё не нужен.

PNG собирается вручную, потому что тащить графическую библиотеку ради тридцати
двух пикселей в стороне — плохой размен. Формат простой: заголовок, один
IDAT со сжатыми строками, IEND.
"""
from __future__ import annotations

import struct
import zlib

SIZE = 32


def _rgb(value: str) -> tuple[int, int, int]:
    """#rrggbb → (r, g, b). Короткая запись #rgb тоже допустима."""
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ValueError(f"не цвет: {value!r}")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _mark_pixels(bg: tuple[int, int, int], fg: tuple[int, int, int]) -> list[list[tuple]]:
    """Метка: залитый квадрат со скруглением и треугольник воспроизведения.

    Треугольник — общеупотребительный символ действия, а не фирменный знак:
    он говорит посетителю, что здесь смотрят, и ничей брендинг не повторяет.
    """
    radius = 6
    rows = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            # Скругление: пиксель за дугой угла остаётся прозрачным.
            cx = radius - 1 if x < radius else (SIZE - radius if x >= SIZE - radius else x)
            cy = radius - 1 if y < radius else (SIZE - radius if y >= SIZE - radius else y)
            if (x - cx) ** 2 + (y - cy) ** 2 > radius ** 2:
                row.append((0, 0, 0, 0))
                continue
            # Треугольник, вписанный в центр: вершина справа, основание слева.
            left, top, bottom, right = 11, 9, SIZE - 9, 23
            inside = False
            if left <= x <= right and top <= y <= bottom:
                progress = (x - left) / (right - left)
                half = (bottom - top) / 2 * (1 - progress)
                inside = abs(y - (top + bottom) / 2) <= half
            row.append((*fg, 255) if inside else (*bg, 255))
        rows.append(row)
    return rows


def _png(rows) -> bytes:
    raw = b"".join(
        b"\x00" + b"".join(struct.pack("BBBB", *px) for px in row) for row in rows
    )

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def favicon_png(accent: str, glyph: str) -> bytes:
    return _png(_mark_pixels(_rgb(accent), _rgb(glyph)))


def favicon_ico(accent: str, glyph: str) -> bytes:
    """ICO с вложенным PNG — формат допускает это начиная с Vista.

    Так один и тот же растр обслуживает и `.ico`, и `.png`, и незачем держать
    две разные картинки, которые рано или поздно разойдутся.
    """
    png = favicon_png(accent, glyph)
    directory = struct.pack("<BBBBHHII", SIZE, SIZE, 0, 0, 1, 32, len(png), 22)
    return struct.pack("<HHH", 0, 1, 1) + directory + png


def favicon_svg(accent: str, glyph: str) -> str:
    """Векторная иконка для вкладок, которые её предпочитают."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
        f'<rect width="32" height="32" rx="6" fill="{accent}"/>'
        f'<path d="M11 9 L23 16 L11 23 Z" fill="{glyph}"/>'
        f"</svg>"
    )
