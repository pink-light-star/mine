#!/usr/bin/env python3
"""third_party/hanmapo 모델 → plugins/StarRPG/pack-extra (리소스팩에 합쳐질 무기 모델, 네임스페이스 starserver)"""
import json, os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "third_party", "hanmapo")
OUT = os.path.join(HERE, "..", "plugins", "StarRPG", "pack-extra")

# 이름: (모델 json, 텍스처 png)
ITEMS = {
    "fenrir_dagger": ("fenrir_dagger/assets/minecraft/models/item/stone_sword.json", "fenrir_dagger/assets/minecraft/textures/items/dagger_fenrir.png"),
    "mosin_nagant": ("mosin_nagant/Mosin_Nagant/Mosin_Nagant.json", "mosin_nagant/Mosin_Nagant/Mosin.png"),
    "psg1": ("psg1/PSG1/PSG-1.json", "psg1/PSG1/PSG-1_texture.png"),
    "hk416": ("hk416/hk416_16x.json", "hk416/hk416.png"),
    "kriss_vector": ("kriss_vector/kriss_vector_16x.json", "kriss_vector/kriss_vector.png"),
}
REF = "hk416"   # 디스플레이 설정이 빠진 모델은 HK416 설정을 크기에 맞춰 빌려 쓴다

def load(p):
    return json.load(open(os.path.join(SRC, p), encoding="utf-8-sig"))

def extent(j):
    xs = []
    for e in j.get("elements", []):
        for a, b in zip(e["from"], e["to"]):
            xs.append(abs(a - b))
    lo = [min(e["from"][i] for e in j["elements"]) for i in range(3)]
    hi = [max(e["to"][i] for e in j["elements"]) for i in range(3)]
    return max(h - l for h, l in zip(hi, lo))

shutil.rmtree(OUT, ignore_errors=True)
ref = load(ITEMS[REF][0])
ref_ext = extent(ref)
for name, (mp, tp) in ITEMS.items():
    j = load(mp)
    j.pop("credit", None)
    j["textures"] = {k: f"starserver:item/{name}" for k in j.get("textures", {})} or {"0": f"starserver:item/{name}"}
    j["textures"]["particle"] = f"starserver:item/{name}"
    # 마인크래프트는 좌표가 -16~32를 넘으면 모델을 못 읽는다 → 가운데(8,8,8) 기준으로 줄이고 표시 크기를 키운다
    lo = min(min(e["from"] + e["to"]) for e in j["elements"])
    hi = max(max(e["from"] + e["to"]) for e in j["elements"])
    shrink = min(1.0, 24 / max(8 - lo, 1e-9), 24 / max(hi - 8, 1e-9))
    if shrink < 1.0:
        sc = lambda v: [round(8 + (a - 8) * shrink, 4) for a in v]
        for e in j["elements"]:
            e["from"], e["to"] = sc(e["from"]), sc(e["to"])
            if "rotation" in e:
                e["rotation"]["origin"] = sc(e["rotation"]["origin"])
        for v in j.get("display", {}).values():
            if "scale" in v:
                v["scale"] = [min(4, round(x / shrink, 3)) for x in v["scale"]]
            if "translation" in v:
                pass
        print(f"  {name}: 좌표 범위 초과 → {shrink:.2f}배로 줄임")
    disp = j.setdefault("display", {})
    f = ref_ext / extent(j)
    for key, v in ref["display"].items():
        if key not in disp:
            v = json.loads(json.dumps(v))
            if "scale" in v:
                v["scale"] = [round(s * f, 3) for s in v["scale"]]
            disp[key] = v
    if "thirdperson_lefthand" not in disp and "thirdperson_righthand" in disp:
        disp["thirdperson_lefthand"] = disp["thirdperson_righthand"]
    mdir = os.path.join(OUT, "assets", "starserver", "models", "item")
    tdir = os.path.join(OUT, "assets", "starserver", "textures", "item")
    idir = os.path.join(OUT, "assets", "starserver", "items")
    for d in (mdir, tdir, idir):
        os.makedirs(d, exist_ok=True)
    json.dump(j, open(os.path.join(mdir, name + ".json"), "w"), separators=(",", ":"))
    shutil.copy(os.path.join(SRC, tp), os.path.join(tdir, name + ".png"))
    json.dump({"model": {"type": "minecraft:model", "model": f"starserver:item/{name}"}},
              open(os.path.join(idir, name + ".json"), "w"))
    print(f"  {name}: 큐브 {len(j.get('elements', []))}개, 디스플레이 {sorted(disp)}")
shutil.copy(os.path.join(SRC, "CREDITS.txt"), os.path.join(OUT, "CREDITS-hanmapo.txt"))
print("완료:", os.path.abspath(OUT))
