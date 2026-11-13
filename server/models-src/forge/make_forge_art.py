"""별빛 대장간 장비 그림 생성기 → 리소스팩(pack-extra)
- 아이템 그림 16x16 (검·대검·활·지팡이·투구·갑옷·각반·장화)
- 입었을 때 보이는 갑옷 무늬 64x32 (humanoid / humanoid_leggings)
- 아이템 모델·아이템 정의·장비(equipment) JSON"""
import struct, zlib, os, sys, json, random

ROOT = sys.argv[1]   # .../pack-extra/assets/starserver

def png(path, w, h, px):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    raw = b''.join(b'\x00' + bytes(px[y*w*4:(y+1)*w*4]) for y in range(h))
    def ch(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                           + ch(b'IDAT', zlib.compress(raw, 9)) + ch(b'IEND', b''))

def C(h): return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
def shade(c, f): return tuple(max(0, min(255, int(v * f))) for v in c[:3]) + (255,)

class Img:
    def __init__(s, w, h): s.w, s.h = w, h; s.px = bytearray(w * h * 4)
    def set(s, x, y, c):
        if 0 <= x < s.w and 0 <= y < s.h: i = (y * s.w + x) * 4; s.px[i:i+4] = bytes(c)
    def get(s, x, y):
        if 0 <= x < s.w and 0 <= y < s.h: i = (y * s.w + x) * 4; return tuple(s.px[i:i+4])
        return (0, 0, 0, 0)
    def save(s, p): png(p, s.w, s.h, s.px)

# 세트 색: 바탕, 어두움, 밝음, 장식, 보석
SETS = {
 't1': ('8b5a2b', '4e3015', 'b98a55', 'd8c08a', None),
 't2': ('a9aeb5', '5f646b', 'e2e6ea', '3f67a8', None),
 't3': ('9fdfe4', '4f97a2', 'eafcff', 'ffffff', '6fc8ff'),
 't4': ('2f8f8a', '174a47', '74d6cb', 'c8c8c8', '3dffcf'),
 't5': ('2b2339', '120e18', '5a4977', '8a5cff', 'c09bff'),
 't6': ('f0cf62', 'a87f22', 'fff3c0', 'ffffff', '79b6ff'),
 'orc': ('5d7d33', '2f411a', '93b65e', '7a4a22', 'c43c2c'),
 'siren': ('3db6c8', '1c6676', 'a2f2ff', 'efe39a', 'ff78d6'),
 'hound': ('7a1f1f', '360a0a', 'c33f30', '1b1b1b', 'ff8c1a'),
 'dragon': ('b4271f', '560e09', 'ff6d4c', 'e3b14a', 'ffd84a'),
}
# 무기 색: 날, 날 어두움, 날 빛, 손잡이, 가드, 보석, 모양
WEAPONS = {
 'fang_sword': ('e7dfc6', '9c927a', 'fffbea', '4a3420', '5d7d33', 'c43c2c', 'sword'),
 'siren_blade': ('5fd4e2', '1f7d8c', 'd8fbff', '2b4c63', 'efe39a', 'ff78d6', 'sword'),
 'hound_sword': ('3a1414', '170606', 'ff8c1a', '1b1b1b', '7a1f1f', 'ff8c1a', 'sword'),
 'giant_crusher': ('b8a07a', '6e5b3c', 'f0dcae', '3a2a18', '8a6a3a', 'ffcc33', 'great'),
 'dragon_greatsword': ('d8352a', '6a100b', 'ffb08a', '2a1a10', 'e3b14a', 'ffd84a', 'great'),
 'harpy_bow': ('d9b04a', '8a6820', 'fff0b0', 'ffffff', 'f2f2f2', 'fff27a', 'bow'),
 'star_staff': ('6b4a2a', '3a2614', 'a0784a', '6b4a2a', 'cfd8ff', '7fb8ff', 'staff'),
}
TIER_SWORD = {'t1': ('9a9a9a', '5c5c5c', 'd0d0d0', '6b4a2a', '8b5a2b', None),
              't2': ('d8dde3', '7b8189', 'ffffff', '3a2a1a', '3f67a8', None),
              't3': ('b9f3f7', '5aa7b1', 'ffffff', '2b3d52', 'eafcff', '6fc8ff'),
              't4': ('4fc9bd', '1d6e66', 'baffF6'[0:6].lower(), '1d2a2a', 'c8c8c8', '3dffcf'),
              't5': ('3d3352', '17121f', 'b89cff', '0e0b12', '8a5cff', 'c09bff'),
              't6': ('fff2bf', 'c9a33a', 'ffffff', '3a2a12', 'f0cf62', '79b6ff')}

def noise(c, rnd, amt=0.08): return shade(c, 1 + (rnd.random() - 0.5) * amt * 2)

# ── 아이템: 검 ──
def sword(path, blade, dark, light, handle, guard, gem, wide=False, seed=0):
    im = Img(16, 16); rnd = random.Random(seed)
    B, D, L, H, G = C(blade), C(dark), C(light), C(handle), C(guard)
    for t in range(10):
        x, y = 5 + t, 10 - t
        im.set(x, y, noise(B, rnd)); im.set(x + 1, y, L if t < 9 else B); im.set(x, y + 1, D)
        if wide:
            im.set(x - 1, y + 1, D); im.set(x, y + 1, noise(B, rnd)); im.set(x + 1, y - 1, L)
    im.set(15, 0, L); im.set(14, 0, B); im.set(15, 1, D)
    for k in range(-2, 3):
        im.set(4 + k, 11 + k, G if abs(k) < 2 else shade(G, 0.7))
    im.set(3, 12, H); im.set(2, 13, shade(H, 1.2)); im.set(1, 14, H)
    im.set(0, 15, C(gem) if gem else shade(G, 0.8))
    if gem: im.set(4, 11, C(gem))
    im.save(path)

def bow(path, wood, dark, light, string, _g, gem, seed=0):
    im = Img(16, 16); W, D, L, S = C(wood), C(dark), C(light), C(string)
    import math
    pts = []
    for a in range(0, 91, 3):
        r = math.radians(a)
        pts.append((round(1 + 12 * math.sin(r)), round(14 - 12 * math.cos(r))))
    for (x, y) in pts:
        im.set(x + 1, y, W); im.set(x + 2, y, D); im.set(x + 1, y - 1, L)
    for t in range(12): im.set(2 + t, 2 + t, S)
    im.set(8, 8, C(gem)); im.set(7, 9, C(gem))   # 깃털 장식
    im.set(14, 13, C('ffffff')); im.set(3, 2, C('ffffff'))
    im.save(path)

def staff(path, wood, dark, light, _h, ring, gem, seed=0):
    im = Img(16, 16); W, D, L, R, G = C(wood), C(dark), C(light), C(ring), C(gem)
    for t in range(10):
        x, y = 2 + t, 13 - t
        im.set(x, y, W); im.set(x + 1, y, L if t % 3 else D); im.set(x, y + 1, D)
    for (dx, dy) in [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)]:
        im.set(12 + dx, 3 + dy, R)
    for (dx, dy) in [(1, -1), (2, -2), (2, 0), (0, -2), (3, -3), (2, -3), (3, -2)]:
        im.set(12 + dx, 3 + dy, G)
    im.set(14, 1, C('ffffff')); im.set(15, 0, shade(G, 1.3))
    im.save(path)

# ── 아이템: 방어구 ──
MASKS = {
 'helmet': ["................", "................", "....########....", "...##########...", "..############..",
            "..############..", "..####....####..", "..###......###..", "..###......###..", "..##........##..",
            "................", "................", "................", "................", "................", "................"],
 'chest': ["................", "..###......###..", ".####......####.", ".##############.", ".##############.",
           "..############..", "...##########...", "...##########...", "...##########...", "...##########...",
           "...##########...", "...##########...", "....########....", "................", "................", "................"],
 'legs': ["................", "................", "...##########...", "...##########...", "...####..####...",
          "...###....###...", "...###....###...", "...###....###...", "...###....###...", "...###....###...",
          "...###....###...", "...###....###...", "...###....###...", "...###....###...", "................", "................"],
 'boots': ["................", "................", "................", "................", "................",
           "................", "................", "................", "..###......###..", "..###......###..",
           "..###......###..", "..####.....####.", ".#####....#####.", ".#####....#####.", "................", "................"],
}
TRIM_ROW = {'helmet': 4, 'chest': 3, 'legs': 2, 'boots': 11}
GEM_AT = {'helmet': [(7, 3), (8, 3)], 'chest': [(7, 6), (8, 6)], 'legs': [], 'boots': []}

def armor_icon(path, part, setkey, seed=0):
    base, dark, light, trim, gem = [C(c) if c else None for c in SETS[setkey]]
    m = MASKS[part]; im = Img(16, 16); rnd = random.Random(seed)
    filled = lambda x, y: 0 <= x < 16 and 0 <= y < 16 and m[y][x] == '#'
    for y in range(16):
        for x in range(16):
            if not filled(x, y): continue
            edge = not all(filled(x + dx, y + dy) for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)])
            c = noise(base, rnd)
            if y == TRIM_ROW[part]: c = trim
            if edge: c = dark
            elif not filled(x, y - 1) or not filled(x - 1, y - 1): c = light if y != TRIM_ROW[part] else shade(trim, 1.15)
            im.set(x, y, c)
    if gem:
        for (x, y) in GEM_AT[part]: im.set(x, y, gem)
    im.save(path)

# ── 입었을 때 보이는 갑옷 무늬 (64x32) ──
def face(im, x0, y0, x1, y1, base, dark, light, rnd, rows=None):
    for y in range(y0, y1):
        if rows and (y - y0) not in rows: continue
        for x in range(x0, x1):
            c = noise(base, rnd, 0.1)
            if x in (x0, x1 - 1) or y in (y0, y1 - 1): c = dark
            elif y == y0 + 1: c = light
            im.set(x, y, c)

def cube(im, ox, oy, w, h, d, cols, rnd, rows=None, faces=('top', 'bottom', 'right', 'front', 'left', 'back')):
    base, dark, light = cols
    R = {'top': (ox + d, oy, ox + d + w, oy + d), 'bottom': (ox + d + w, oy, ox + d + 2 * w, oy + d),
         'right': (ox, oy + d, ox + d, oy + d + h), 'front': (ox + d, oy + d, ox + d + w, oy + d + h),
         'left': (ox + d + w, oy + d, ox + 2 * d + w, oy + d + h), 'back': (ox + 2 * d + w, oy + d, ox + 2 * d + 2 * w, oy + d + h)}
    for f in faces:
        x0, y0, x1, y1 = R[f]
        face(im, x0, y0, x1, y1, base, dark, light, rnd, rows if f not in ('top', 'bottom') else None)
    return R

def equipment(root, setkey):
    base, dark, light, trim, gem = [C(c) if c else None for c in SETS[setkey]]
    cols = (base, dark, light); rnd = random.Random(hash(setkey) & 0xffff)
    # 1층: 투구 + 흉갑(몸·팔) + 장화(다리 아래)
    im = Img(64, 32)
    R = cube(im, 0, 0, 8, 8, 8, cols, rnd)
    fx0, fy0, fx1, fy1 = R['front']
    for x in range(fx0 + 1, fx1 - 1): im.set(x, fy0 + 4, dark)          # 눈구멍
    for x in range(fx0, fx1): im.set(x, fy0 + 2, trim)                  # 이마 띠
    if gem: im.set(fx0 + 3, fy0 + 1, gem); im.set(fx0 + 4, fy0 + 1, gem)
    R = cube(im, 16, 16, 8, 12, 4, cols, rnd)
    fx0, fy0, fx1, fy1 = R['front']
    for x in range(fx0, fx1): im.set(x, fy0 + 1, trim); im.set(x, fy1 - 2, trim)
    for y in range(fy0 + 2, fy1 - 2): im.set(fx0 + 3, y, shade(trim, 0.9)); im.set(fx0 + 4, y, shade(trim, 0.9))
    if gem:
        for (dx, dy) in [(3, 4), (4, 4), (3, 5), (4, 5)]: im.set(fx0 + dx, fy0 + dy, gem)
    R = cube(im, 40, 16, 4, 12, 4, cols, rnd)
    for f in ('right', 'front', 'left', 'back'):
        x0, y0, x1, y1 = R[f]
        for x in range(x0, x1): im.set(x, y0 + 1, trim); im.set(x, y0 + 2, trim)
    R = cube(im, 0, 16, 4, 12, 4, cols, rnd, rows=set(range(7, 12)))     # 장화: 아래 5줄
    for f in ('right', 'front', 'left', 'back'):
        x0, y0, x1, y1 = R[f]
        for x in range(x0, x1): im.set(x, y0 + 7, trim)
    im.save(os.path.join(root, 'textures/entity/equipment/humanoid', setkey + '.png'))
    # 2층: 각반 (허리 + 다리 위쪽)
    im = Img(64, 32)
    R = cube(im, 16, 16, 8, 12, 4, cols, rnd, rows=set(range(8, 12)), faces=('right', 'front', 'left', 'back', 'bottom'))
    x0, y0, x1, y1 = R['front']
    for x in range(x0, x1): im.set(x, y0 + 8, trim)
    if gem: im.set(x0 + 3, y0 + 9, gem); im.set(x0 + 4, y0 + 9, gem)
    R = cube(im, 0, 16, 4, 12, 4, cols, rnd, rows=set(range(0, 9)), faces=('top', 'right', 'front', 'left', 'back'))
    for f in ('right', 'front', 'left', 'back'):
        x0, y0, x1, y1 = R[f]
        for x in range(x0, x1): im.set(x, y0 + 4, shade(trim, 0.85))
    im.save(os.path.join(root, 'textures/entity/equipment/humanoid_leggings', setkey + '.png'))
    os.makedirs(os.path.join(root, 'equipment'), exist_ok=True)
    json.dump({"layers": {"humanoid": [{"texture": "starserver:" + setkey}],
                          "humanoid_leggings": [{"texture": "starserver:" + setkey}]}},
              open(os.path.join(root, 'equipment', setkey + '.json'), 'w'), indent=1)

def item_files(root, iid, parent):
    os.makedirs(os.path.join(root, 'models/item/forge'), exist_ok=True)
    os.makedirs(os.path.join(root, 'items/forge'), exist_ok=True)
    json.dump({"parent": parent, "textures": {"layer0": "starserver:item/forge/" + iid}},
              open(os.path.join(root, 'models/item/forge', iid + '.json'), 'w'), indent=1)
    json.dump({"model": {"type": "minecraft:model", "model": "starserver:item/forge/" + iid}},
              open(os.path.join(root, 'items/forge', iid + '.json'), 'w'), indent=1)

if __name__ == '__main__':
    tex = lambda iid: os.path.join(ROOT, 'textures/item/forge', iid + '.png')
    n = 0
    for i, (iid, v) in enumerate(WEAPONS.items()):
        blade, dark, light, handle, guard, gem, kind = v
        if kind in ('sword', 'great'): sword(tex(iid), blade, dark, light, handle, guard, gem, kind == 'great', i)
        elif kind == 'bow': bow(tex(iid), blade, dark, light, handle, guard, gem, i)
        else: staff(tex(iid), blade, dark, light, handle, guard, gem, i)
        item_files(ROOT, iid, "minecraft:item/handheld" if kind != 'bow' else "minecraft:item/generated"); n += 1
    for i, (t, v) in enumerate(TIER_SWORD.items()):
        iid = t + '_sword'
        sword(tex(iid), *v, wide=(t in ('t5', 't6')), seed=100 + i)
        item_files(ROOT, iid, "minecraft:item/handheld"); n += 1
    for s_i, setkey in enumerate(SETS):
        for p_i, part in enumerate(('helmet', 'chest', 'legs', 'boots')):
            iid = setkey + '_' + part
            armor_icon(tex(iid), part, setkey, seed=s_i * 10 + p_i)
            item_files(ROOT, iid, "minecraft:item/generated"); n += 1
        equipment(ROOT, setkey)
    print('items', n, 'equipment sets', len(SETS))
