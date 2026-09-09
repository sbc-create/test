"""Мост 1.2.0 против потребителя, объявляющего 1.0.0, — без правок в SEO."""
import json, pathlib, sys
sys.path.insert(0, "/home/claude/wt-core-ident-35")
from factory.site_engine import seo_bridge as b

ПОТРЕБИТЕЛЬ = "core-seo-bridge/1.0.0"   # то, что SEO объявляет на ca2b6ca9…

рукопожатие = b.handshake(ПОТРЕБИТЕЛЬ)
print("схема производителя:", рукопожатие["producerSchema"])
print("схема потребителя:  ", рукопожатие["consumerSchema"])
print("совместимо:         ", рукопожатие["compatible"])
assert рукопожатие["compatible"], рукопожатие["reason"]

каталог = json.loads(pathlib.Path("/srv/site-factory/repo/var/lords/lords/"
                                  "catalog-cache/lords-01.json").read_text())["items"]
запись = b.export_record(каталог[0], site_id="lords-01")
поле_год = next(п for п in запись["descriptive"] if п["key"] == "year")
поле_нет = next(п for п in запись["descriptive"] if п["key"] == "director")
print("\nполе year: ", json.dumps(поле_год, ensure_ascii=False))
print("поле director:", json.dumps(поле_нет, ensure_ascii=False))

# Читатель прежних четырёх ключей обязан продолжать работать: новые ключи он
# просто не запрашивает. Это и есть смысл младшего повышения.
ПРЕЖНИЕ = {"key", "state", "value", "reason"}
for п in запись["descriptive"]:
    assert ПРЕЖНИЕ <= set(п), f"пропал прежний ключ: {sorted(ПРЕЖНИЕ - set(п))}"
    старый_взгляд = {к: п[к] for к in ПРЕЖНИЕ}
    assert старый_взгляд["key"] and старый_взгляд["state"]
print("\nпрежние четыре ключа на месте у всех",
      len(запись["descriptive"]), "полей")

# Правовой признак по-прежнему не покидает ядро. Проверяется отсутствие
# ЗНАЧЕНИЯ, а не имени: имя обязано остаться в droppedFieldNames, иначе
# потребитель не отличит снятое поле от отсутствующего у источника.
кроме_имён = {к: v for к, v in запись.items() if к != "droppedFieldNames"}
assert "licensed" not in json.dumps(кроме_имён, ensure_ascii=False)
assert "licensed" in запись["droppedFieldNames"]
assert каталог[0].get("licensed") is False   # значение, которое не ушло
print("licensed снят и назван снятым:", запись["droppedFieldNames"])

# Происхождение объявлено только там, где объявлено значение.
с_значением = [п for п in запись["descriptive"] if п["state"] == "PRESENT"]
без_значения = [п for п in запись["descriptive"] if п["state"] != "PRESENT"]
assert all(п["provenance"] and п["reference"] for п in с_значением)
assert all(not п["provenance"] and not п["reference"] for п in без_значения)
print(f"происхождение проставлено у {len(с_значением)} полей со значением "
      f"и ни у одного из {len(без_значения)} без значения")
print("\nВЫВОД: 1.1.0 происхождение утверждений НЕ несёт; добавление требует "
      "изменения схемы.\nМладшее повышение до 1.2.0 достаточно и потребителя "
      "не ломает.")
