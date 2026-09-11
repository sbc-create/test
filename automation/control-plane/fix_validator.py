import pathlib
p = pathlib.Path("/srv/site-factory/control-plane-contracts/validate_bundle.py")
s = p.read_text(encoding="utf-8")
старое = '''списки = []
for p in КОРЕНЬ.rglob("*"):
    if p.is_file():
        т = p.read_text(encoding="utf-8", errors="replace")
        доменов = set(re.findall(r"[a-z0-9-]+\\.(?:space|biz|online|site|org|icu)", т))
        if len(доменов) >= 3:
            списки.append(f"{p.name}: {len(доменов)}")'''
новое = '''# Ищутся ФАКТИЧЕСКИЕ боевые домены, а не всё, похожее на домен.
# Прежняя регулярка принимала за домен питоновский путь модуля
# (`factory.site_engine`, `api.site_filter`) и объявляла OpenAPI статическим
# списком сайтов. Проверка, дающая ложную тревогу, обесценивает себя: её
# начинают отключать вместо того, чтобы читать.
БОЕВЫЕ = {"lordfilm47.space", "lordserial33.biz", "1lordserials1.online",
          "yummyani.biz", "yummyani.org", "yummyani.site",
          "zonafilm.space", "animedia.icu", "animedia.space"}
списки = []
for p in КОРЕНЬ.rglob("*"):
    if p.is_file():
        т = p.read_text(encoding="utf-8", errors="replace")
        найденные = {д for д in БОЕВЫЕ if д in т}
        if len(найденные) >= 3:
            списки.append(f"{p.name}: {sorted(найденные)[:3]}")'''
assert s.count(старое) == 1, "блок проверки списков не найден"
p.write_text(s.replace(старое, новое), encoding="utf-8")
print("проверка уточнена до фактических боевых доменов")
