"""Какие витрины инструмент доставки целей покрывает, а какие нет.

Считается по ЯКОРЯМ в рабочих копиях витрин: полное покрытие, частичное
(только цели посещения) или никакое (свой рантайм). Ничего не правится —
только чтение.
"""
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ЯКОРЬ_ТЕГА = ("'style=\"position:absolute;left:-9999px\" alt=\"\"></div></noscript>'\n"
              "    )")
ЯКОРЬ_ВОРОНКИ = " function state(k,t,p){\n  if(отказ&&k==='ok') return;"
ЯКОРЬ_ЭЛЕМЕНТА = "  host.appendChild(n);\n  bind(n, ++token);"

строки = []
корни = [(п.name, п) for п in sorted((КОРЕНЬ / "var/site-repos").iterdir())
         if п.is_dir()]
корни += [(f"K2 {п.name}", п) for п in sorted((КОРЕНЬ / "var/new-sites").iterdir())
          if п.is_dir()]

for имя, проект in корни:
    кандидаты = list((проект / "src").glob("*frontend*.py")) if (проект / "src").is_dir() else []
    общий = проект / "src" / "lords-frontend.py"
    if not кандидаты:
        строки.append((имя, "нет src/*frontend*.py", "", ""))
        continue
    if not общий.is_file():
        строки.append((имя, f"свой рантайм: {', '.join(p.name for p in кандидаты)}",
                       "", ""))
        continue
    t = общий.read_text(encoding="utf-8", errors="replace")
    если_есть = "__sfGoal" in t
    тег = t.count(ЯКОРЬ_ТЕГА)
    воронка = t.count(ЯКОРЬ_ВОРОНКИ)
    элемент = t.count(ЯКОРЬ_ЭЛЕМЕНТА)
    если_есть_текст = "ДОСТАВЛЕНО" if если_есть else ""
    строки.append((имя, f"тег {тег}", f"воронка {воронка}, элемент {элемент}",
                   если_есть_текст))

for имя, a, b, c in строки:
    print(f"{имя:28s} {a:34s} {b:28s} {c}")
