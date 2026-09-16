"""Фактическая карта кода: что откуда импортирует.

Не оценка и не план — измерение. Граф строится разбором AST, а не поиском по
тексту: строка со словом «import» в комментарии не должна попадать в граф.
"""
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
PKG = "factory"

def module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)

def top_area(name: str) -> str:
    """Область — второй уровень: factory.lords.render -> lords."""
    parts = name.split(".")
    return parts[1] if len(parts) > 1 else "(корень)"

edges = defaultdict(set)
files = {}
for path in sorted((ROOT / PKG).rglob("*.py")):
    name = module_name(path)
    source = path.read_text(encoding="utf-8")
    files[name] = {"path": str(path.relative_to(ROOT)), "lines": source.count("\n") + 1}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PKG):
                    edges[name].add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # относительный импорт
                base = name.rsplit(".", node.level)[0] if node.level <= name.count(".") else PKG
                target = f"{base}.{node.module}" if node.module else base
                edges[name].add(target)
            elif node.module and node.module.startswith(PKG):
                edges[name].add(node.module)

# Свести к областям.
area_edges = defaultdict(set)
for src, targets in edges.items():
    a = top_area(src)
    for t in targets:
        b = top_area(t)
        if a != b:
            area_edges[a].add(b)

# Циклы между областями.
cycles = []
for a, outs in area_edges.items():
    for b in outs:
        if a in area_edges.get(b, set()) and (b, a) not in cycles:
            cycles.append((a, b))

print("=== области и их размер ===")
sizes = defaultdict(lambda: [0, 0])
for name, info in files.items():
    area = top_area(name)
    sizes[area][0] += 1
    sizes[area][1] += info["lines"]
for area, (count, lines) in sorted(sizes.items(), key=lambda kv: -kv[1][1]):
    print(f"  {area:<16} файлов {count:>3}  строк {lines:>6}")

print("\n=== зависимости между областями ===")
for a in sorted(area_edges):
    print(f"  {a:<16} -> {', '.join(sorted(area_edges[a]))}")

print("\n=== взаимные зависимости (циклы уровня областей) ===")
print("  нет" if not cycles else "\n".join(f"  {a} <-> {b}" for a, b in cycles))

out = {
    "areas": {a: {"files": c, "lines": ln} for a, (c, ln) in sizes.items()},
    "area_edges": {a: sorted(v) for a, v in area_edges.items()},
    "area_cycles": [list(c) for c in cycles],
    "module_edges": {k: sorted(v) for k, v in edges.items()},
}
# Граф ложится рядом с прочими артефактами, а не во временный каталог: на него
# ссылается DEPENDENCY-MAP.md, и он должен пережить перезагрузку.
target = ROOT / "artifacts" / "site-engine" / "dependency-graph.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(f"\nграф сохранён: {target}")
