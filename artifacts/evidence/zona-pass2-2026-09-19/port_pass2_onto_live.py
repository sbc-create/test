"""Port Zona PASS2 slices onto the live shared lords-frontend.py (Animedia tip)."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path("/home/claude/wt-zona-finalization-01")
LIVE = Path("/srv/lords/.frontend/lords-frontend.py")
OURS = ROOT / "automation" / "host" / "lords-frontend.py"
OUT = ROOT / "automation" / "host" / "lords-frontend.py"
BACKUP = ROOT / "artifacts" / "evidence" / "zona-pass2-2026-09-19" / "merge" / "ours-before-port.py"


def extract(src: str, start: str, end: str) -> str:
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


def replace_between(dst: str, start: str, end: str, new_block: str) -> str:
    i = dst.index(start)
    j = dst.index(end, i)
    return dst[:i] + new_block + dst[j:]


def replace_assignment(dst: str, name: str, new_block: str) -> str:
    """Replace `NAME = ...` through the blank line before the next top-level def/class/#."""
    pat = re.compile(
        rf"(?m)^{re.escape(name)}\s*=\s*(?:\"\"\".*?\"\"\"|'''.*?'''|.*?)(?=\n(?:def |class |#: |[A-ZА-Я_][A-ZА-Я0-9_]*\s*=))",
        re.S,
    )
    m = pat.search(dst)
    if not m:
        raise SystemExit(f"assignment not found: {name}")
    return dst[: m.start()] + new_block.rstrip() + "\n\n" + dst[m.end() :]


def main() -> None:
    shutil.copy2(OURS, BACKUP)
    live = LIVE.read_text(encoding="utf-8")
    ours = OURS.read_text(encoding="utf-8")
    out = live

    # 1) Unicode helpers through транслит start
    block = extract(
        ours,
        "def _сжать_юникод(с: str) -> str:",
        "\n#: Русская раскладка под латинскими клавишами",
    )
    out = replace_between(
        out,
        "def _сжать_юникод(с: str) -> str:" if "_сжать_юникод" in out else "def нормализовать(с: str) -> str:",
        "\n#: Русская раскладка под латинскими клавишами",
        block,
    )

    # 2) Данные.искать method — from def искать to next def at class indent
    # Find in ours
    m_ours = re.search(
        r"(?ms)^    def искать\(self, q: str, предел: int = 120\) -> list\[dict\]:.*?(?=\n    def )",
        ours,
    )
    m_live = re.search(
        r"(?ms)^    def искать\(self, q: str, предел: int = 120\) -> list\[dict\]:.*?(?=\n    def )",
        out,
    )
    if not m_ours or not m_live:
        raise SystemExit("искать not found")
    out = out[: m_live.start()] + m_ours.group(0) + out[m_live.end() :]

    # 3) Aggregators + candidates
    for start, end in [
        (
            "#: Агрегаторы, разрешённые контрактом",
            "\ndef _конфиг_плеера()",
        ),
    ]:
        if start in ours and start in out:
            out = replace_between(out, start, end, extract(ours, start, end))

    # Fix кандидаты_источника body if separate
    m_ours = re.search(
        r"(?ms)^def кандидаты_источника\(деталь: dict\).*?(?=\n\ndef )",
        ours,
    )
    m_live = re.search(
        r"(?ms)^def кандидаты_источника\(деталь: dict\).*?(?=\n\ndef )",
        out,
    )
    if m_ours and m_live:
        out = out[: m_live.start()] + m_ours.group(0) + out[m_live.end() :]

    # 4) Player markup attributes + client script
    m_ours = re.search(
        r'(?ms)^def разметка_плеера\(вид, запись: dict, деталь: dict, сезон: int,\n'
        r'                    эпизод: int \| None\) -> tuple\[str, str\]:.*?(?=\n\n\nСКРИПТ_ПЛЕЕРА_КЛИЕНТ)',
        ours,
    )
    m_live = re.search(
        r'(?ms)^def разметка_плеера\(вид, запись: dict, деталь: dict, сезон: int,\n'
        r'                    эпизод: int \| None\) -> tuple\[str, str\]:.*?(?=\n\n\nСКРИПТ_ПЛЕЕРА_КЛИЕНТ)',
        out,
    )
    if not m_ours:
        # try single-line signature variants
        m_ours = re.search(
            r"(?ms)^def разметка_плеера\(.*?(?=\n\n\nСКРИПТ_ПЛЕЕРА_КЛИЕНТ)",
            ours,
        )
        m_live = re.search(
            r"(?ms)^def разметка_плеера\(.*?(?=\n\n\nСКРИПТ_ПЛЕЕРА_КЛИЕНТ)",
            out,
        )
    if m_ours and m_live:
        out = out[: m_live.start()] + m_ours.group(0) + out[m_live.end() :]

    # Client script
    m_ours = re.search(
        r'(?ms)^СКРИПТ_ПЛЕЕРА_КЛИЕНТ = """.*?"""\n',
        ours,
    )
    m_live = re.search(
        r'(?ms)^СКРИПТ_ПЛЕЕРА_КЛИЕНТ = """.*?"""\n',
        out,
    )
    if not m_ours or not m_live:
        raise SystemExit("client script not found")
    out = out[: m_live.start()] + m_ours.group(0) + out[m_live.end() :]

    # 5) Zona CSS — replace ЗОНА_СТИЛЬ 1.2 block carefully: from marker through end of constant
    m_ours = re.search(r'(?ms)^ЗОНА_СТИЛЬ = """.*?"""\n', ours)
    m_live = re.search(r'(?ms)^ЗОНА_СТИЛЬ = """.*?"""\n', out)
    if m_ours and m_live:
        out = out[: m_live.start()] + m_ours.group(0) + out[m_live.end() :]

    # 6) Footer method
    m_ours = re.search(
        r"(?ms)^    def _подвал_зона\(self\) -> str:.*?(?=\n    # --- составные части|\n    def плитка)",
        ours,
    )
    m_live = re.search(
        r"(?ms)^    def _подвал_зона\(self\) -> str:.*?(?=\n    # --- составные части|\n    def плитка)",
        out,
    )
    if m_ours and m_live:
        out = out[: m_live.start()] + m_ours.group(0) + out[m_live.end() :]

    # 7) Title page description contract — replace тайтл method of Zona class only is hard;
    # patch the short_description block if present in live.
    old_snip = None
    for cand in (
        'полное = (деталь.get("description") or "").strip()\n        краткое_поле = (деталь.get("short_description") or "").strip()',
        'описание = (деталь.get("short_description") or деталь.get("description") or "")',
    ):
        if cand in ours and cand.split("\n")[0] in out:
            pass
    # Replace zona title description logic by unique comment marker from ours
    marker = "# Hero shows short_summary only when it is a distinct field"
    if marker in ours:
        # take from краткое_поле assignment through описание_html = ""
        chunk = extract(
            ours,
            'краткое_поле = (деталь.get("short_description") or "").strip()',
            "оценки_html = разметка_оценок(деталь, \"rbs\")",
        )
        if 'краткое_поле = (деталь.get("short_description") or "").strip()' in out:
            out = replace_between(
                out,
                'краткое_поле = (деталь.get("short_description") or "").strip()',
                "оценки_html = разметка_оценок(деталь, \"rbs\")",
                chunk,
            )
        elif 'описание = (деталь.get("short_description") or деталь.get("description") or "")' in out:
            # older title path — insert contract before ratings in zona тайтл
            pass

    # 8) Search heading
    if 'Результаты поиска: «{html.escape(q)}»' in ours:
        out2 = out
        out2 = out2.replace(
            'f\'<h1 class="zh">«{html.escape(q)}»</h1>\'',
            'f\'<h1 class="zh">Результаты поиска: «{html.escape(q)}»</h1>\'',
        )
        # value retention in input
        if 'id="q" name="q" value="' not in out2 and 'id="q" name="q" value="' in ours:
            # copy the replace block after search html_page build from ours if missing
            if 'html_page.replace(\n                \'id="q" name="q" placeholder=\'' in ours and \
               'html_page.replace(\n                \'id="q" name="q" placeholder=\'' not in out2:
                needle = 'return html_page\n\n\n    def тайтл'
                if 'if q.strip():\n            html_page = html_page.replace(' in ours and needle in out2:
                    inject = extract(
                        ours,
                        "if q.strip():\n            html_page = html_page.replace(",
                        "\n\n\n    def тайтл",
                    )
                    # find return html_page before тайтл in search method — fragile; skip if present
                    if inject.strip() and inject not in out2:
                        out2 = out2.replace(
                            "\n\n\n    def тайтл(self, запись: dict, деталь: dict) -> str:",
                            "\n        " + inject.strip() + "\n\n\n    def тайтл(self, запись: dict, деталь: dict) -> str:",
                            1,
                        )
        out = out2

    # Ensure is-show-banner false everywhere in player attrs
    out = out.replace('"is-show-banner": "true"', '"is-show-banner": "false"')

    # Sanity
    checks = {
        "postMessage": "addEventListener('message'" in out,
        "phrase_search": "phrase-first" in out or "primary.startswith" in out,
        "nfkc": "NFKC" in out,
        "banner_false": '"is-show-banner": "false"' in out,
        "animedia_kept": "АНИМЕДИА_СТИЛЬ" in out,
        "no_conflict": "<<<<<<<" not in out,
        "footer": "Каталог и информация" in out,
        "user_msg": "Видео временно недоступно" in out,
    }
    print(checks)
    if not all(checks.values()):
        raise SystemExit("sanity failed")

    OUT.write_text(out, encoding="utf-8")
    print("wrote", OUT, "lines", out.count("\n"))


if __name__ == "__main__":
    main()
