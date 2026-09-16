"""Сверка отрисованного стенда с контрактом."""
import json, re, sys, collections
from pathlib import Path
sys.path.insert(0, "/home/claude/wt-core-identity-22")
from factory.site_engine.adapters import lords_seo_binding as ad
from factory.site_engine.seo_binding import BindingState, PlaybackState, digest

стенд = Path(sys.argv[1])
env = ad.export("/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json",
                site_id="lords-01")
по_пути = {b["canonicalPath"]: b for b in env["bindings"] if b["canonicalPath"]}

ОБЕЩАНИЯ = ("смотреть онлайн", "доступен к просмотру", "все серии доступны",
            "смотрите новую серию", "видео уже появилось")

итог = collections.Counter()
расхождения = []
for файл in sorted(стенд.rglob("index.html")):
    путь = "/" + str(файл.parent.relative_to(стенд)) + "/"
    b = по_пути.get(путь)
    итог["страниц"] += 1
    if not b:
        итог["нет связи"] += 1
        расхождения.append({"path": путь, "issue": "NO_BINDING"})
        continue
    итог["связано"] += 1
    html = файл.read_text("utf-8", errors="ignore")

    m = re.search(r'<link[^>]*rel="canonical"[^>]*href="([^"]+)"', html)
    canon = m.group(1) if m else ""
    ожидаемый = "https://lordfilm47.space" + b["canonicalPath"]
    if canon.rstrip("/") == ожидаемый.rstrip("/"):
        итог["canonical совпал"] += 1
    else:
        итог["canonical разошёлся"] += 1
        расхождения.append({"path": путь, "issue": "CANONICAL",
                            "page": canon, "contract": ожидаемый})

    типы = set(re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', html))
    ожид_тип = b["schemaType"]
    if not ожид_тип:
        if типы & {"Movie", "TVSeries", "TVSpecial"}:
            итог["разметка у неустановленного вида"] += 1
            расхождения.append({"path": путь, "issue": "SCHEMA_ON_UNKNOWN",
                                "page": sorted(типы)})
        else:
            итог["разметки нет, как и ждали"] += 1
    elif ожид_тип in типы:
        итог["тип разметки совпал"] += 1
    else:
        итог["тип разметки разошёлся"] += 1
        расхождения.append({"path": путь, "issue": "SCHEMA_TYPE",
                            "page": sorted(типы), "contract": ожид_тип})

    низ = html.lower()
    обещает = [p for p in ОБЕЩАНИЯ if p in низ]
    if b["mayPromisePlayback"]:
        итог["с видео"] += 1
    else:
        итог["без видео"] += 1
        if обещает:
            итог["обещание без видео"] += 1
            расхождения.append({"path": путь, "issue": "PLAYBACK_PROMISE",
                                "found": обещает})

    if "noindex" in низ:
        итог["страниц с noindex"] += 1

повтор = digest(ad.build(
    json.load(open("/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json",
                   encoding="utf-8"))["items"],
    site_id="lords-01", snapshot_at=env["snapshotAt"],
    provenance=env["provenance"]))
итог_словарь = dict(итог)
итог_словарь["digestFirst"] = env["digest"]
итог_словарь["digestRepeat"] = повтор
итог_словарь["digestStable"] = env["digest"] == повтор
итог_словарь["mismatches"] = расхождения[:20]
итог_словарь["mismatchCount"] = len(расхождения)
print(json.dumps(итог_словарь, ensure_ascii=False, indent=1))
