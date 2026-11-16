#!/usr/bin/env python3
"""mcmodels.net 무료 모델 → BetterModel 모델 폴더.
   ModelEngine용 모델에는 'hitbox' 뼈가 있는데, BetterModel은 이걸 그냥 흰 상자로 그리므로 뺀다.
   쓰는 법: python3 models-src/import_mcmodels.py"""
import json, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "imported", "mcmodels", "x")
OUT = os.path.join(HERE, "..", "plugins", "BetterModel", "models")

# 원본 파일 이름 → 서버 모델 ID
PICK = {
    "goofy_goblin.bbmodel": "mc_goblin",
    "shroomling.bbmodel": "mc_shroomling",
    "q_cursed_one_forest.bbmodel": "mc_cursed_forest",
    "q_cursed_one_ice.bbmodel": "mc_cursed_ice",
    "q_cursed_one_crystal.bbmodel": "mc_cursed_crystal",
    "1bit_nautilus.bbmodel": "mc_nautilus",
    "evilwolf.bbmodel": "mc_evilwolf",
    "boar.bbmodel": "mc_boar",
    "deer.bbmodel": "mc_deer",
    "spectralwolf.bbmodel": "mc_spiritwolf",
}
DROP = ("hitbox",)          # 이 이름의 뼈와 그 안의 큐브는 뺀다


def find(name):
    hits = [p for p in glob.glob(os.path.join(SRC, "**", name), recursive=True)]
    return hits[0] if hits else None


def strip(m):
    removed = set()

    def walk(node):
        if isinstance(node, str):
            return node
        if node.get("name", "").lower() in DROP:
            collect(node)
            return None
        node["children"] = [c for c in (walk(c) for c in node.get("children", [])) if c is not None]
        return node

    def collect(node):
        if isinstance(node, str):
            removed.add(node); return
        removed.add(node.get("uuid"))
        for c in node.get("children", []):
            collect(c)

    m["outliner"] = [n for n in (walk(n) for n in m.get("outliner", [])) if n is not None]
    m["elements"] = [e for e in m.get("elements", []) if e.get("uuid") not in removed]
    if "groups" in m:
        m["groups"] = [g for g in m["groups"] if g.get("uuid") not in removed]
    return len(removed)


def main():
    os.makedirs(OUT, exist_ok=True)
    for src, mid in PICK.items():
        p = find(src)
        if not p:
            print("없음:", src); continue
        m = json.load(open(p, encoding="utf-8"))
        n = strip(m)
        m["name"] = mid
        json.dump(m, open(os.path.join(OUT, mid + ".bbmodel"), "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  {mid:20s} ← {src} (큐브 {len(m['elements'])}, 뺀 것 {n})")


if __name__ == "__main__":
    main()
