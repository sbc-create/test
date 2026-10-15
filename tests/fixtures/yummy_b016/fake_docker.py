#!/usr/bin/env python3
"""Поддельный docker для тестов yummy-b016-release.py. Состояние — JSON в $FAKE_DOCKER_STATE.

Поддержано ровно то, что вызывает сценарий: inspect, image inspect, tag, compose config/build/up.
Отказы задаются ключом "fail" состояния: build, tag, label, up, up_rollback, health_new, config.
Каждый вызов дописывается в "calls".
"""
import hashlib
import json
import os
import sys

P = os.environ["FAKE_DOCKER_STATE"]


def load():
    return json.load(open(P))


def save(s):
    json.dump(s, open(P, "w"), indent=1)


def pins(env_file):
    out = {}
    for line in open(env_file):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            out[k] = v
    return out


def resolve(s, ref):
    if ref in s["images"]:
        return ref, s["images"][ref]
    for k, v in s["images"].items():
        if v["id"] == ref:
            return k, v
    return None, None


def main(a):
    s = load()
    s["calls"].append(a)
    save(s)
    fail = s.get("fail", {})
    if a[0] == "inspect":
        c = s["containers"].get(a[1])
        if not c:
            print(f"no such container {a[1]}", file=sys.stderr)
            return 1
        img = resolve(s, c["image_ref"])[1]
        print(json.dumps([{"Image": img["id"], "Config": {"Image": c["image_ref"], "Env": c["env"],
                                                          "Labels": {"org.opencontainers.image.revision": img["revision"]}},
                           "State": {"Health": {"Status": c["health"]}}, "Mounts": [{"Destination": m} for m in c["mounts"]]}]))
        return 0
    if a[:2] == ["image", "inspect"]:
        if a[2] == "-f":
            fmt, ref = a[3], a[4]
            _, img = resolve(s, ref)
            if not img:
                print(f"no such image {ref}", file=sys.stderr)
                return 1
            print(img["id"] if fmt == "{{.Id}}" else img["revision"])
            return 0
        _, img = resolve(s, a[2])
        print(json.dumps([{"Id": img["id"], "Config": {"Env": img.get("env", [])}}]))
        return 0
    if a[0] == "tag":
        if fail.get("tag"):
            print("tag failed", file=sys.stderr)
            return 1
        _, img = resolve(s, a[1])
        if not img:
            return 1
        s = load()
        s["images"][a[2]] = dict(img)
        save(s)
        return 0
    if a[0] == "compose":
        env_file = a[a.index("--env-file") + 1]
        if "config" in a:
            if fail.get("config"):
                return 1
            cfg = json.loads(json.dumps(s["config"]))
            p = pins(env_file)
            for svc, var in (("web-site", "WEB_SITE_IMAGE"), ("web-org", "WEB_ORG_IMAGE"), ("web-biz", "WEB_BIZ_IMAGE")):
                cfg["services"][svc]["image"] = p.get(var, "yummyani/web:staging")
            print(json.dumps(cfg))
            return 0
        if "build" in a:
            print("Step 1/9 : FROM node  (шум сборки в stdout)")
            if fail.get("build"):
                return 1
            rev = os.environ.get("GIT_REVISION", "unknown")
            s = load()
            s["images"]["yummyani/web:staging"] = {"id": "sha256:" + hashlib.sha256(rev.encode()).hexdigest(),
                                                   "revision": "wrong" if fail.get("label") else rev, "env": []}
            save(s)
            return 0
        if "up" in a:
            svc = a[-1]
            s = load()
            rollback = s.get("deployed_once", {}).get(svc)
            if fail.get("up") and not rollback:
                return 1
            if fail.get("up_rollback") and rollback:
                return 1
            var = {"web-site": "WEB_SITE_IMAGE", "web-org": "WEB_ORG_IMAGE", "web-biz": "WEB_BIZ_IMAGE"}[svc]
            ref = pins(env_file)[var]
            c = s["containers"][f"yummyani-staging-{svc}-1"]
            c["image_ref"] = ref
            new = not rollback
            c["health"] = "unhealthy" if (new and fail.get("health_new") == svc) else "healthy"
            s.setdefault("deployed_once", {})[svc] = True
            save(s)
            return 0
    print("unsupported: " + " ".join(a), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
