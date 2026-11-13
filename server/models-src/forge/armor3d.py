"""방어구 입체 아이템 모델: 입었을 때 보이는 갑옷 무늬(128x64)를 그대로 입힌 3D 투구·갑옷·각반·장화.
   인벤토리·손에 든 모습과 도감에서 쓰인다 (입었을 때 모습은 equipment 텍스처 그대로).
   쓰는 법: python3 armor3d.py <.../assets/starserver>"""
import os, sys, json, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pngread import read_png

ROOT = sys.argv[1]
SETS = ["orc", "siren", "hound", "dragon", "t1", "t2", "t3", "t4", "t5", "t6"]
BW, BH = 64, 32          # 바닐라 갑옷 무늬 기준 크기 (실제 그림은 2배)

def box_uv(u, v, w, h, d, rows=None):
    """마인크래프트 상자 UV (기준 64x32 픽셀) → 면별 [u1,v1,u2,v2]. rows=(시작, 끝)이면 옆면을 그 줄만 쓴다"""
    y0, y1 = (v + d, v + d + h) if rows is None else (v + d + rows[0], v + d + rows[1])
    return {"up": [u + d, v, u + d + w, v + d], "down": [u + d + w, v, u + d + 2 * w, v + d],
            "east": [u, y0, u + d, y1], "north": [u + d, y0, u + d + w, y1],
            "west": [u + d + w, y0, u + 2 * d + w, y1], "south": [u + 2 * d + w, y0, u + 2 * d + 2 * w, y1]}

def to16(r):
    return [round(r[0] * 16 / BW, 4), round(r[1] * 16 / BH, 4), round(r[2] * 16 / BW, 4), round(r[3] * 16 / BH, 4)]

def darkest(path):
    """그림에서 가장 어두운 불투명 픽셀 위치 (안쪽 채움용) → 모델 UV"""
    w, h, px = read_png(path)
    best, at = 999, (0, 0)
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[y * w + x]
            if a < 250: continue
            s = r + g + b
            if 40 < s < best: best, at = s, (x, y)
    x, y = at
    u, v = x * 16 / w, y * 16 / h
    return [round(u + 0.02, 4), round(v + 0.02, 4), round(u + 0.06, 4), round(v + 0.06, 4)]

def cube(frm, to, faces, inner_uv=None, inset=0.35):
    els = [{"from": frm, "to": to, "faces": {f: {"uv": to16(r), "texture": "#0"} for f, r in faces.items()}}]
    if inner_uv:   # 갑옷 무늬의 빈틈(투명)으로 속이 비어 보이지 않게 어두운 안감
        els.insert(0, {"from": [a + inset for a in frm], "to": [b - inset for b in to],
                       "faces": {f: {"uv": inner_uv, "texture": "#0"} for f in ("north", "south", "east", "west", "up", "down")}})
    return els

def fit(els, size=15.0):
    """모든 상자를 0~16 칸 가운데에 들어가게 줄이고 옮긴다"""
    mn = [min(e["from"][i] for e in els) for i in range(3)]
    mx = [max(e["to"][i] for e in els) for i in range(3)]
    k = min(1.0, size / max(mx[i] - mn[i] for i in range(3)))
    for e in els:
        for key in ("from", "to"):
            e[key] = [round(8 + (e[key][i] - (mn[i] + mx[i]) / 2) * k, 4) for i in range(3)]
        if "rotation" in e:
            o = e["rotation"]["origin"]
            e["rotation"]["origin"] = [round(8 + (o[i] - (mn[i] + mx[i]) / 2) * k, 4) for i in range(3)]
    return els

from make_forge_art import SETS as COLORS

_px_cache = {}
def col(path, hexc):
    """그림에서 그 색에 가장 가까운 불투명 픽셀 → 단색 UV"""
    if path not in _px_cache: _px_cache[path] = read_png(path)
    w, h, px = _px_cache[path]
    t = tuple(int(hexc[i:i + 2], 16) for i in (0, 2, 4))
    best, at = 1e9, (0, 0)
    for i, (r, g, b_, a) in enumerate(px):
        if a < 250: continue
        d = (r - t[0]) ** 2 + (g - t[1]) ** 2 + (b_ - t[2]) ** 2
        if d < best: best, at = d, (i % w, i // w)
    u, v = at[0] * 16 / w, at[1] * 16 / h
    return [round(u + 0.02, 4), round(v + 0.02, 4), round(u + 0.06, 4), round(v + 0.06, 4)]

def solid(frm, to, uv, rot=None):
    e = {"from": frm, "to": to, "faces": {f: {"uv": uv, "texture": "#0"} for f in ("north", "south", "east", "west", "up", "down")}}
    if rot: e["rotation"] = rot
    return e

def piece(part, inner, s, tex):
    base, dark, light, trim, gem = COLORS[s]
    gem = gem or trim
    C = lambda h: col(tex, h)
    els = []
    if part == "helmet":
        els += cube([3.5, 3.5, 3.5], [12.5, 12.0, 12.5], box_uv(0, 0, 8, 8, 8), inner)          # 투구 몸통
        els.append(solid([3.3, 3.3, 3.3], [12.7, 4.3, 12.7], C(dark)))                           # 아래 테두리
        els.append(solid([4.6, 8.0, 3.2], [11.4, 8.9, 3.6], C("101010")))                       # 눈 틈
        els.append(solid([7.4, 5.0, 3.0], [8.6, 8.0, 3.5], C(trim)))                            # 코 가리개
        for x0, x1 in ((3.2, 5.0), (11.0, 12.8)):
            els.append(solid([x0, 3.0, 3.0], [x1, 7.6, 6.5], C(base)))                          # 뺨 가리개
        els.append(solid([3.0, 3.0, 11.0], [13.0, 6.0, 13.2], C(dark)))                         # 목 가리개
        els.append(solid([7.2, 12.0, 4.0], [8.8, 13.2, 12.2], C(trim)))                         # 정수리 능선
        if s == "orc":
            for x in (5.6, 9.6): els.append(solid([x, 2.0, 2.8], [x + 0.8, 5.2, 3.6], C(light)))   # 엄니
        elif s == "siren":
            els.append(solid([7.5, 12.0, 5.0], [8.5, 15.5, 11.5], C(gem)))                       # 지느러미 볏
            els.append(solid([7.5, 15.0, 7.0], [8.5, 16.5, 11.0], C(light)))
        elif s == "hound":
            for x in (3.8, 10.4):
                els.append(solid([x, 12.0, 8.0], [x + 1.8, 15.0, 10.0], C(base)))                 # 귀
                els.append(solid([x + 0.4, 14.6, 8.4], [x + 1.4, 15.8, 9.6], C(dark)))
            for x in (5.4, 9.6): els.append(solid([x, 8.2, 3.1], [x + 1.0, 8.8, 3.4], C(gem)))   # 빛나는 눈
        elif s == "dragon":
            for x0, ang in ((3.4, -22.5), (10.8, 22.5)):
                els.append(solid([x0, 11.0, 7.0], [x0 + 1.8, 12.8, 14.5], C(light),
                                 {"angle": ang * -1, "axis": "z", "origin": [8, 12, 10]}))        # 뒤로 뻗은 뿔
                els.append(solid([x0 + 0.3, 12.0, 13.5], [x0 + 1.5, 13.4, 16.0], C(trim)))
            els.append(solid([7.0, 9.4, 2.9], [9.0, 10.6, 3.4], C(gem)))                         # 이마 보석
        elif s == "t2":
            els.append(solid([7.6, 4.0, 2.8], [8.4, 9.5, 3.2], C(dark)))
        elif s == "t3":
            els.append(solid([7.4, 12.6, 6.0], [8.6, 16.0, 12.5], C(gem)))                       # 깃털 장식
        elif s == "t4":
            for x in (4.2, 7.4, 10.6): els.append(solid([x, 12.0, 7.0], [x + 1.2, 14.4, 8.2], C(light)))
        elif s == "t5":
            els.append(solid([6.8, 12.0, 5.0], [9.2, 13.4, 11.0], C(gem)))
        elif s == "t6":
            for x in (3.8, 6.0, 8.0, 10.2):
                els.append(solid([x, 12.0, 3.6], [x + 1.6, 14.6, 4.6], C(base)))                 # 왕관 장식
            els.append(solid([7.3, 12.4, 3.2], [8.7, 13.8, 3.7], C(gem)))
        return els
    if part == "chest":
        els += cube([4, 0, 6], [12, 12, 10], box_uv(16, 16, 8, 12, 4), inner)                   # 몸통
        for x0, x1 in ((0.4, 4.0), (12.0, 15.6)):
            els += cube([x0, 4.5, 6.2], [x1, 11, 9.8], box_uv(40, 16, 4, 12, 4, rows=(0, 6)), inner)   # 윗팔
            els.append(solid([x0 - 0.6, 10.2, 5.4], [x1 + 0.6, 12.6, 10.6], C(base)))             # 어깨 갑판
            els.append(solid([x0 - 0.4, 12.4, 5.8], [x1 + 0.4, 13.2, 10.2], C(light)))
            els.append(solid([x0 - 0.7, 9.6, 5.3], [x1 + 0.7, 10.3, 10.7], C(trim)))
        els.append(solid([5.0, 11.4, 5.6], [11.0, 13.0, 10.4], C(trim)))                        # 목깃
        els.append(solid([3.8, 0.8, 5.7], [12.2, 2.0, 10.3], C(trim)))                          # 허리띠
        els.append(solid([7.2, 6.4, 5.5], [8.8, 8.0, 6.0], C(gem)))                             # 가슴 보석
        els.append(solid([6.6, 5.8, 5.7], [9.4, 8.6, 6.0], C(trim)))
        return els
    if part == "legs":
        els += cube([4, 12, 6], [12, 17, 10], box_uv(16, 16, 8, 12, 4, rows=(7, 12)), inner)    # 허리
        els += cube([4, 0, 6], [7.95, 12, 10], box_uv(0, 16, 4, 12, 4), inner)
        els += cube([8.05, 0, 6], [12, 12, 10], box_uv(0, 16, 4, 12, 4), inner)
        els.append(solid([3.7, 15.6, 5.7], [12.3, 16.8, 10.3], C(trim)))                        # 허리띠
        els.append(solid([7.2, 15.4, 5.4], [8.8, 17.0, 5.8], C(gem)))                           # 버클
        for x in (4.0, 8.4):
            els.append(solid([x, 11.0, 5.4], [x + 3.6, 15.4, 6.2], C(base)))                     # 앞 허벅지 판
            els.append(solid([x + 0.6, 5.0, 5.4], [x + 3.0, 7.4, 6.0], C(light)))                # 무릎 보호대
        return els
    if part == "boots":
        for x0, x1 in ((3.6, 7.85), (8.15, 12.4)):
            els += cube([x0, 0, 5.6], [x1, 4.6, 10.4], box_uv(0, 16, 4, 12, 4, rows=(7, 12)), inner)   # 발목
            els.append(solid([x0, 0, 3.6], [x1, 2.0, 5.8], C(base)))                              # 앞코
            els.append(solid([x0 + 0.2, 1.8, 3.8], [x1 - 0.2, 2.4, 5.6], C(light)))
            els.append(solid([x0 - 0.3, 4.2, 5.3], [x1 + 0.3, 5.2, 10.7], C(trim)))               # 윗테
            els.append(solid([x0 - 0.1, -0.2, 3.4], [x1 + 0.1, 0.4, 10.6], C(dark)))              # 밑창
        return els

DISPLAY = {
    "gui": {"rotation": [20, 205, 0], "translation": [0, 0, 0], "scale": [0.95, 0.95, 0.95]},
    "ground": {"rotation": [0, 0, 0], "translation": [0, 2, 0], "scale": [0.45, 0.45, 0.45]},
    "fixed": {"rotation": [0, 180, 0], "translation": [0, 0, 0], "scale": [0.9, 0.9, 0.9]},
    "thirdperson_righthand": {"rotation": [75, 225, 0], "translation": [0, 2.5, 0], "scale": [0.4, 0.4, 0.4]},
    "thirdperson_lefthand": {"rotation": [75, 225, 0], "translation": [0, 2.5, 0], "scale": [0.4, 0.4, 0.4]},
    "firstperson_righthand": {"rotation": [0, 225, 0], "translation": [0, 1, 0], "scale": [0.45, 0.45, 0.45]},
    "firstperson_lefthand": {"rotation": [0, 225, 0], "translation": [0, 1, 0], "scale": [0.45, 0.45, 0.45]},
    "head": {"rotation": [0, 180, 0], "translation": [0, 13, 0], "scale": [0.8, 0.8, 0.8]},
}

def main():
    tdir = os.path.join(ROOT, "textures", "item", "forge", "armor3d")
    os.makedirs(tdir, exist_ok=True)
    n = 0
    for s in SETS:
        body = os.path.join(ROOT, "textures", "entity", "equipment", "humanoid", s + ".png")
        legs = os.path.join(ROOT, "textures", "entity", "equipment", "humanoid_leggings", s + ".png")
        if not (os.path.exists(body) and os.path.exists(legs)):
            print("건너뜀:", s); continue
        shutil.copy(body, os.path.join(tdir, s + ".png"))
        shutil.copy(legs, os.path.join(tdir, s + "_legs.png"))
        for part in ("helmet", "chest", "legs", "boots"):
            tex = s + ("_legs" if part == "legs" else "")
            inner = darkest(os.path.join(tdir, tex + ".png"))
            model = {"credit": "별빛 대장간 입체 방어구", "textures": {"0": f"starserver:item/forge/armor3d/{tex}",
                     "particle": f"starserver:item/forge/armor3d/{tex}"}, "gui_light": "side",
                     "elements": fit(piece(part, inner, s, os.path.join(tdir, tex + ".png"))), "display": DISPLAY}
            with open(os.path.join(ROOT, "models", "item", "forge", f"{s}_{part}.json"), "w") as f:
                json.dump(model, f, indent=1)
            n += 1
    print(f"입체 방어구 {n}개")

if __name__ == "__main__":
    main()
