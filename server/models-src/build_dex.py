#!/usr/bin/env python3
"""서버 파일 → HTML 도감 데이터.
   몹(Dex.java) · 탈것(Species.java) · 펫(PetType.java) · 장비(대장간.sk) 정보와 3D 모델을 모아
   models-src/dex/dex-data.json 과 썸네일(models-src/dex/thumbs/*.png)을 만든다.
   쓰는 법: python3 models-src/build_dex.py"""
import json, os, re, sys, base64, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SRC = os.path.join(ROOT, "starrpg-src", "src", "kr", "starserver", "starrpg")
BBM = os.path.join(ROOT, "plugins", "BetterModel", "models")
SK = os.path.join(ROOT, "plugins", "Skript", "scripts", "대장간.sk")
PACK = os.path.join(ROOT, "plugins", "StarRPG", "pack-extra", "assets", "starserver")
OUT = os.path.join(HERE, "dex")
sys.path.insert(0, os.path.join(HERE, "tools"))
from render_bb import render

def plain(s):
    s = re.sub(r"[§&][0-9a-fklmnor]", "", s).replace("%%", "%")
    return re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", "", s).strip()

def r3(v):
    return round(v, 3)

# ------------------------------------------------------------------ 3D 모델 압축
def pack_bbmodel(path):
    m = json.load(open(path, encoding="utf-8"))
    uvs, uvi = [], {}
    def uv(u):
        k = tuple(r3(x) for x in u)
        if k not in uvi:
            uvi[k] = len(uvs); uvs.append(list(k))
        return uvi[k]
    E = {e["uuid"]: e for e in m["elements"]}
    G = {g["uuid"]: g for g in m.get("groups", [])}
    order = ["east", "west", "up", "down", "south", "north"]
    def face_ok(fd):   # 텍스처 없는 면(안 보임)과 스킬 효과 그림(2번째 이후 텍스처)은 그리지 않는다
        t = fd.get("texture")
        return t is not None and str(t) in ("0", "#0")
    def el(e):
        return [*map(r3, e["from"]), *map(r3, e["to"]), *map(r3, e["origin"]), *map(r3, e.get("rotation", [0, 0, 0])),
                [uv(e["faces"][f]["uv"]) if face_ok(e["faces"][f]) else -1 for f in order]]
    def node(n):
        g = G.get(n["uuid"], n)
        kids = []
        for c in n["children"]:
            if isinstance(c, str):
                e = E.get(c)
                if e and "from" in e and "faces" in e and e.get("visibility") is not False and all(f in e["faces"] for f in order) \
                        and any(face_ok(e["faces"][f]) for f in order):
                    kids.append(el(e))
            else:
                kids.append(node(c))
        return {"n": g["name"], "o": list(map(r3, g["origin"])), "r": list(map(r3, g.get("rotation", [0, 0, 0]))), "c": kids}
    anims = {}
    for a in m["animations"]:
        tr = {}
        for uid, an in a["animators"].items():
            for kf in an.get("keyframes", []):
                if kf["channel"] == "rotation":
                    p = kf["data_points"][0]
                    tr[an["name"]] = [str(p["x"]), str(p["y"]), str(p["z"])]
        anims[a["name"]] = {"len": a["length"], "loop": a["loop"], "tr": tr}
    return {"res": m["resolution"]["width"], "tex": m["textures"][0]["source"], "uv": uvs,
            "tree": [node(n) for n in m["outliner"]], "anims": anims, "cubes": len(m["elements"])}

def pack_item(model_json, tex_png):
    m = json.load(open(model_json))
    if "elements" not in m:
        return None
    uvs, uvi = [], {}
    def uv(u):
        k = tuple(r3(x) for x in u)
        if k not in uvi:
            uvi[k] = len(uvs); uvs.append(list(k))
        return uvi[k]
    order = ["east", "west", "up", "down", "south", "north"]
    els = []
    for e in m["elements"]:
        rot = [0, 0, 0]; org = [(a + b) / 2 for a, b in zip(e["from"], e["to"])]
        if "rotation" in e:
            ax = "xyz".index(e["rotation"]["axis"]); rot[ax] = e["rotation"]["angle"]; org = e["rotation"]["origin"]
        els.append([*map(r3, e["from"]), *map(r3, e["to"]), *map(r3, org), *rot,
                    [uv(e["faces"][f]["uv"]) if f in e["faces"] else -1 for f in order]])
    tex = "data:image/png;base64," + base64.b64encode(open(tex_png, "rb").read()).decode()
    return {"res": 16, "tex": tex, "uv": uvs, "tree": [{"n": "item", "o": [8, 0, 8], "r": [0, 0, 0], "c": els}],
            "anims": {}, "cubes": len(els), "item": True}

# ------------------------------------------------------------------ 정보 읽기
def read(p):
    return open(p, encoding="utf-8").read()

def mobs():
    out = []
    for g in re.finditer(r'new Mob\("([^"]+)",\s*"([^"]+)",\s*(\d+),\s*(\d+),\s*"([^"]+)",\s*Material\.(\w+),\s*\n?\s*"([^"]+)"\)', read(os.path.join(SRC, "Dex.java"))):
        name, model, hp, dmg, kind, _, note = g.groups()
        out.append({"id": model, "name": plain(name), "model": model, "hp": int(hp), "dmg": int(dmg), "kind": plain(kind), "note": note})
    return out

GRADES = {"COMMON": ("일반", 0.60), "RARE": ("레어", 0.40), "UNIQUE": ("유니크", 0.25), "ANCIENT": ("고대", 0.12),
          "HERO": ("영웅", 0.05), "LEGEND": ("전설", 0), "MYTH": ("신화", 0)}
SPECIAL_HOW = {"WHALE": "적룡 30% · 메두사·미노타우로스·크루가 10%", "BROOM": "/그물상점 에서 구매",
               "DRAGON": "용기사 전직 보상 · 적룡 처치 10%"}
MOUNT_NOTE = {"mount_horse": "바닐라 말 위에 루비 왕관과 깃털", "mount_wolf": "붉은 망토와 왕관을 두른 늑대왕",
              "mount_fox": "벚꽃 화관과 금방울", "sky_whale": "하늘을 헤엄치는 별빛 고래",
              "broom": "덩굴 손잡이와 랜턴이 달린 빗자루", "mount_dragon": "타고 좌클릭하면 화염 숨결"}

def mounts():
    out = []
    for g in re.finditer(r'^\s*(\w+)\("([^"]+)",\s*EntityType\.(\w+),\s*([\d.]+),\s*([\d.]+),\s*(true|false),\s*Grade\.(\w+),\s*[\d.]+(?:,\s*"(\w+)")?\)', read(os.path.join(SRC, "Species.java")), re.M):
        key, ko, etype, speed, jump, fly, grade, model = g.groups()
        gk, cap = GRADES[grade]
        how = SPECIAL_HOW.get(key) or (f"그물총 포획 {round(cap * 50)}~{round(min(0.95, cap * 1.5) * 100)}%" if cap > 0 else "야생 포획 불가")
        out.append({"id": key.lower(), "name": ko, "grade": gk, "speed": round(float(speed) * 20, 1), "jump": float(jump),
                    "fly": fly == "true", "how": how, "model": model, "note": MOUNT_NOTE.get(model or "", "")})
    order = list(GRADES)
    out.sort(key=lambda m: -[GRADES[k][0] for k in order].index(m["grade"]))
    return out

def pets():
    src = read(os.path.join(SRC, "PetType.java"))
    weapons = {w: (ko, float(dmg), int(shots), float(rng)) for w, ko, rng, stop, dmg, cd, shots in
               re.findall(r'(\w+)\("([^"]+)",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*(\d+),\s*(\d+)\)', src)}
    out = []
    for key, nn, cn, nm, cm, gun, col, wp in re.findall(r'(\w+)\("([^"]+)",\s*"([^"]+)",\s*"(\w+)",\s*"(\w+)",\s*(true|false),\s*"([^"]+)",\s*Weapon\.(\w+)\)', src):
        ko, dmg, shots, rng = weapons[wp]
        out.append({"id": key.lower(), "name": nn, "combat": (cn if cn != nn else "무장한 모습") if nm != cm else None, "model": nm, "combatModel": cm if nm != cm else None,
                    "weapon": ko, "dmg": dmg, "shots": shots, "range": rng})
    return out

STAT = {1: "힘", 2: "민첩", 3: "지능", 4: "체력", 5: "행운"}

def gear():
    sk = read(SK)
    bonus = {i: s for i, s in re.findall(r'^\s*fBonus\("(\w+)",\s*"([\d:,]+)"\)', sk, re.M)}
    hidden = dict(re.findall(r'set \{-forge::(\w+)::hidden\} to "([^"]+)"', sk))
    def bl(spec):
        if not spec: return []
        return [[STAT[int(k)], int(v)] for k, v in (kv.split(":") for kv in spec.split(","))]
    items = []
    ids = re.search(r'set \{-forge::ids::\*\} to (.+)', sk).group(1)
    order = re.findall(r'"(\w+)"', ids)
    reg = {}
    for i, n, k, lv, st, amt, price, desc in re.findall(r'^\s*fReg\("(\w+)",\s*"([^"]+)",\s*"(\w)",\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*"([^"]*)",\s*"[^"]*"\)', sk, re.M):
        reg[i] = dict(name=plain(n), lv=int(lv), st=int(st), amt=int(amt), price=int(price), desc=plain(desc))
    for i in order:
        r = reg[i]
        kind = "단검" if "dagger" in i else "활" if "bow" in i else "지팡이" if "staff" in i else "고서" if "tome" in i else "검"
        it = {"id": i, "cat": "special", "kind": kind, "lv": r["lv"], "req": [STAT.get(r["st"], ""), r["amt"]] if r["amt"] else None,
              "price": r["price"], "bonus": bl(bonus.get(i))}
        if i in hidden:
            it.update(name="???", hidden=hidden[i], desc="히든 퀘스트로만 얻을 수 있어요.")
        else:
            it.update(name=r["name"], desc=r["desc"])
        items.append(it)
    sb = {"orc": "4:3,1:1", "siren": "2:3,4:2", "hound": "4:5,1:2", "dragon": "4:7,1:3"}
    parts = [("helmet", "투구", 4), ("chest", "갑옷", 8), ("legs", "각반", 7), ("boots", "장화", 3)]
    for sid, sname, lv, st, amt, price, desc in re.findall(r'^\s*fArmorSet\("(\w+)",\s*"([^"]+)",\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*"[^"]*",\s*[\d, ]+,\s*[\w ]+,\s*"([^"]+)"\)', sk, re.M):
        for pid, pk, wt in parts:
            items.append({"id": f"{sid}_{pid}", "cat": "armor", "set": plain(sname), "kind": pk, "name": f"{plain(sname)} {pk}",
                          "lv": int(lv), "req": [STAT[int(st)], int(amt)], "price": round(int(price) * wt / 5),
                          "desc": desc, "bonus": bl(sb[sid])})
    for t, lv, pre, wreq, areq, dmg, df, price in re.findall(r'^\s*fTier\((\d),\s*(\d+),\s*"([^"]+)",\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),', sk, re.M):
        t = int(t); pre = plain(pre)
        tw = [("sword", "검", 1, f"공격력 +{dmg}%", f"1:{t*2},2:{t}"), ("dagger", "단검", 2, f"공격력 +{dmg}%, 뒤치기 +40%", f"2:{t*2},5:{t}"),
              ("bow", "활", 2, f"화살 피해 +{dmg}%", f"2:{t*2},5:{t}"), ("staff", "지팡이", 3, f"우클릭 마력탄: 피해 {3 + t*2} + 지능×0.1", f"3:{t*2},4:{t}")]
        for pid, pk, st, d, b in tw:
            items.append({"id": f"t{t}_{pid}", "cat": "tier", "tier": t, "kind": pk, "name": f"{pre} {pk}", "lv": int(lv),
                          "req": [STAT[st], int(wreq)] if int(wreq) else None, "price": int(price), "desc": "기본 장비 · " + d, "bonus": bl(b)})
        for pid, pk, wt in parts:
            items.append({"id": f"t{t}_{pid}", "cat": "tier", "tier": t, "kind": pk, "name": f"{pre} {pk}", "lv": int(lv),
                          "req": ["체력", int(areq)] if int(areq) else None, "price": round(int(price) * wt / 8),
                          "desc": f"기본 장비 · 받는 피해 -{df}% (부위당)", "bonus": bl(f"4:{t}")})
    return items

def item_thumb(mj, tx, g):
    """아이템 입체 모델을 렌더러가 읽는 bbmodel 꼴로 바꿔 썸네일을 그린다"""
    m = json.load(open(mj))
    els = []
    for k, e in enumerate(m["elements"]):
        rot = [0, 0, 0]; org = [(a + b) / 2 for a, b in zip(e["from"], e["to"])]
        if "rotation" in e:
            rot["xyz".index(e["rotation"]["axis"])] = e["rotation"]["angle"]; org = e["rotation"]["origin"]
        els.append({"uuid": f"e{k}", "from": e["from"], "to": e["to"], "origin": org, "rotation": rot,
                    "faces": {f: {"uv": v["uv"]} for f, v in e["faces"].items()}})
    bb = {"resolution": {"width": 16, "height": 16}, "elements": els, "groups": [], "outliner": [e["uuid"] for e in els],
          "textures": [{"source": "data:image/png;base64," + base64.b64encode(open(tx, "rb").read()).decode()}]}
    tmp = os.path.join(OUT, "_tmp.bbmodel")
    json.dump(bb, open(tmp, "w"))
    render(tmp, os.path.join(OUT, "thumbs", "v_" + g["id"] + ".png"), -55, 240, 240, alpha=True)
    os.remove(tmp)
    g["thumb"] = f"thumbs/v_{g['id']}.png"

# ------------------------------------------------------------------ 만들기
def main():
    shutil.rmtree(os.path.join(OUT, "thumbs"), ignore_errors=True)   # index.html 은 남긴다
    os.makedirs(os.path.join(OUT, "thumbs"))
    models = {}
    def thumb(model, yaw=-35):
        p = os.path.join(BBM, model + ".bbmodel")
        if not os.path.exists(p): return None
        if model not in models:
            models[model] = pack_bbmodel(p)
            render(p, os.path.join(OUT, "thumbs", model + ".png"), yaw, 360, 300, alpha=True)
        return f"thumbs/{model}.png"
    data = {"mobs": mobs(), "mounts": mounts(), "pets": pets(), "gear": gear()}
    for m in data["mobs"]: m["thumb"] = thumb(m["model"])
    for m in data["mounts"]:
        if m["model"]: m["thumb"] = thumb(m["model"])
    for p in data["pets"]:
        p["thumb"] = thumb(p["model"])
        if p["combatModel"]: thumb(p["combatModel"])
    for g in data["gear"]:
        if g.get("hidden"): continue
        icon = os.path.join(PACK, "textures", "item", "forge", g["id"] + ".png")
        if os.path.exists(icon):
            shutil.copy(icon, os.path.join(OUT, "thumbs", "i_" + g["id"] + ".png")); g["thumb"] = f"thumbs/i_{g['id']}.png"
        mj = os.path.join(PACK, "models", "item", "forge", g["id"] + ".json")
        tx = None
        if os.path.exists(mj):
            t0 = json.load(open(mj)).get("textures", {}).get("0")
            if t0: tx = os.path.join(PACK, "textures", t0.split(":", 1)[1] + ".png")
        if tx and os.path.exists(tx):
            pm = pack_item(mj, tx)
            if pm:
                models["item_" + g["id"]] = pm; g["model"] = "item_" + g["id"]
                item_thumb(mj, tx, g)
    data["models"] = models
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    open(os.path.join(OUT, "dex-data.json"), "w", encoding="utf-8").write(js)
    import hashlib   # 데이터가 바뀌면 페이지가 새 파일을 받도록 버전 값을 바꿔 넣는다
    ver = hashlib.sha1(js.encode()).hexdigest()[:10]
    ip = os.path.join(OUT, "index.html")
    if os.path.exists(ip):
        h = open(ip, encoding="utf-8").read()
        h = re.sub(r'const DATA_VER = "[^"]*";', f'const DATA_VER = "{ver}";', h)
        open(ip, "w", encoding="utf-8").write(h)
    print(f"몹 {len(data['mobs'])} · 탈것 {len(data['mounts'])} · 펫 {len(data['pets'])} · 장비 {len(data['gear'])} · 3D 모델 {len(models)} · 데이터 {len(js)//1024}KB")

if __name__ == "__main__":
    main()
