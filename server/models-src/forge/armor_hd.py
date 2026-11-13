"""별빛 대장간 방어구 고해상도 그림
- 입었을 때 보이는 갑옷 무늬: 128x64 (바닐라 64x32의 2배)
- 아이템 아이콘: 32x32
세트마다 음영·이음선·리벳·장식 띠·고유 문양"""
import os, sys, math, random, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_forge_art import png, C, shade, Img, SETS, MASKS

ROOT = sys.argv[1]          # .../assets/starserver
S = 2                       # 배율

STYLE = {'t1': 'stitch', 't2': 'rivet', 't3': 'engrave', 't4': 'angular', 't5': 'crack', 't6': 'filigree',
         'orc': 'tusk', 'siren': 'scale', 'hound': 'flame', 'dragon': 'dscale'}

def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)

def face(im, x0, y0, x1, y1, setkey, rnd, rows=None, kind='plate', front=False, part=''):
    base, dark, light, trim, gem = [C(c) if c else None for c in SETS[setkey]]
    st = STYLE[setkey]
    X0, Y0, X1, Y1 = x0 * S, y0 * S, x1 * S, y1 * S
    H = Y1 - Y0; W = X1 - X0
    for y in range(Y0, Y1):
        ry = (y - Y0) // S
        if rows is not None and ry not in rows: continue
        for x in range(X0, X1):
            t = (y - Y0) / max(1, H - 1)
            c = lerp(shade(base, 1.12), shade(base, 0.82), t)          # 위 밝고 아래 어둡게
            lx, ly = x - X0, y - Y0
            # 문양
            if st == 'scale' or st == 'dscale':
                cx = (lx + (ly // 3 % 2) * 2) % 4; cy = ly % 3
                if cy == 0 or (cx in (0, 3) and cy == 1): c = shade(c, 0.78)
                elif cx in (1, 2) and cy == 1: c = shade(c, 1.12)
            elif st == 'stitch':
                if (lx in (2, W - 3) or ly in (2, H - 3)) and (lx + ly) % 3 == 0: c = shade(trim, 1.0)
            elif st == 'engrave':
                if (lx + ly * 2) % 9 == 0 or (lx - ly * 2) % 11 == 0: c = shade(gem or trim, 0.95)
            elif st == 'angular':
                if (abs(lx - W // 2) + ly) % 7 == 0: c = shade(c, 0.75)
            elif st == 'crack':
                if (math.sin(lx * 0.9 + ly * 0.4) + math.sin(ly * 0.7 - lx * 0.3)) > 1.55: c = gem
            elif st == 'filigree':
                if (math.sin(lx * 0.8) * 2 + ly) % 6 < 0.7: c = shade(trim, 1.0)
            # 판금 이음선 (가로)
            if kind == 'plate' and st not in ('scale', 'dscale', 'stitch') and ly > 2 and ly % 7 == 0: c = shade(c, 0.7)
            # 베벨 테두리
            if lx == 0 or ly == 0 or lx == W - 1 or ly == H - 1: c = dark
            elif lx == 1 or ly == 1: c = shade(c, 1.2)
            elif lx == W - 2 or ly == H - 2: c = shade(c, 0.8)
            im.set(x, y, c)
    # 리벳
    if st in ('rivet', 'dscale', 'tusk', 'angular'):
        for (rx, ry) in ((X0 + 2, Y0 + 2), (X1 - 3, Y0 + 2), (X0 + 2, Y1 - 3), (X1 - 3, Y1 - 3)):
            if rows is None or ((ry - Y0) // S) in rows:
                im.set(rx, ry, shade(light, 1.15)); im.set(rx + 1, ry + 1, shade(dark, 1.0))

def cube(im, ox, oy, w, h, d, setkey, rnd, rows=None, faces=('top', 'bottom', 'right', 'front', 'left', 'back'), kind='plate', part=''):
    R = {'top': (ox + d, oy, ox + d + w, oy + d), 'bottom': (ox + d + w, oy, ox + d + 2 * w, oy + d),
         'right': (ox, oy + d, ox + d, oy + d + h), 'front': (ox + d, oy + d, ox + d + w, oy + d + h),
         'left': (ox + d + w, oy + d, ox + 2 * d + w, oy + d + h), 'back': (ox + 2 * d + w, oy + d, ox + 2 * d + 2 * w, oy + d + h)}
    for f in faces:
        x0, y0, x1, y1 = R[f]
        face(im, x0, y0, x1, y1, setkey, rnd, rows if f not in ('top', 'bottom') else None, kind, f == 'front', part)
    return R

def hline(im, x0, x1, y, c):
    for x in range(x0 * S, x1 * S): im.set(x, y, c)

def equipment(setkey):
    base, dark, light, trim, gem = [C(c) if c else None for c in SETS[setkey]]
    st = STYLE[setkey]; rnd = random.Random(hash(setkey) & 0xffff)
    im = Img(64 * S, 32 * S)
    # ── 투구 ──
    R = cube(im, 0, 0, 8, 8, 8, setkey, rnd, part='helmet')
    fx0, fy0, fx1, fy1 = [v * S for v in R['front']]
    for x in range(fx0, fx1):                                  # 이마 장식 띠
        im.set(x, fy0 + 3, shade(trim, 1.15)); im.set(x, fy0 + 4, trim); im.set(x, fy0 + 5, shade(trim, 0.7))
    for x in range(fx0 + 2, fx1 - 2):                          # 눈구멍 (T자 바이저)
        for y in (fy0 + 8, fy0 + 9): im.set(x, y, (12, 10, 16, 255))
    for y in range(fy0 + 8, fy0 + 14):
        for x in (fx0 + 7, fx0 + 8): im.set(x, y, (12, 10, 16, 255))
    if st == 'hound':
        pass
    if setkey == 'hound':
        im.set(fx0 + 4, fy0 + 8, C('ff8c1a')); im.set(fx1 - 5, fy0 + 8, C('ff8c1a'))   # 빛나는 눈
    if gem:
        for (dx, dy) in ((7, 2), (8, 2), (7, 3), (8, 3)): im.set(fx0 + dx, fy0 + dy, gem)
    if st == 'tusk':                                            # 오크 송곳니
        for k in range(4):
            im.set(fx0 + 3, fy1 - 2 - k, C('efe6cf')); im.set(fx1 - 4, fy1 - 2 - k, C('efe6cf'))
    # ── 흉갑 ──
    R = cube(im, 16, 16, 8, 12, 4, setkey, rnd, part='chest')
    fx0, fy0, fx1, fy1 = [v * S for v in R['front']]
    for x in range(fx0, fx1):
        im.set(x, fy0 + 2, shade(trim, 1.15)); im.set(x, fy0 + 3, trim); im.set(x, fy1 - 4, trim); im.set(x, fy1 - 3, shade(trim, 0.7))
    cxm = (fx0 + fx1) // 2
    for y in range(fy0 + 4, fy1 - 4): im.set(cxm - 1, y, shade(trim, 0.9)); im.set(cxm, y, shade(trim, 0.75))   # 가운데 능선
    # 가슴 문양
    if st in ('filigree',):
        for (dx, dy) in ((0, -3), (0, 3), (-3, 0), (3, 0), (-2, -2), (2, 2), (-2, 2), (2, -2)): im.set(cxm + dx, fy0 + 10 + dy, shade(trim, 1.2))
    if st == 'flame':
        for x in range(fx0 + 1, fx1 - 1):
            hgt = int(3 + 3 * abs(math.sin(x * 0.7)))
            for y in range(fy1 - 4 - hgt, fy1 - 4): im.set(x, y, C('ff6a1a') if y > fy1 - 4 - hgt + 1 else C('ffcc33'))
    if st == 'tusk':
        for k in range(5):
            im.set(cxm - 4 + k // 2, fy0 + 6 + k, C('efe6cf')); im.set(cxm + 3 - k // 2, fy0 + 6 + k, C('efe6cf'))
    if gem:
        for dx in (-2, -1, 0, 1):
            for dy in (-2, -1, 0, 1): im.set(cxm + dx, fy0 + 10 + dy, gem if abs(dx + .5) + abs(dy + .5) < 2.5 else shade(trim, 1.1))
    # ── 팔(어깨 보호대) ──
    R = cube(im, 40, 16, 4, 12, 4, setkey, rnd, part='arm')
    for f in ('right', 'front', 'left', 'back'):
        x0, y0, x1, y1 = [v * S for v in R[f]]
        for x in range(x0, x1):
            for y in range(y0, y0 + 6): im.set(x, y, shade(trim, 1.1 - (y - y0) * 0.07))     # 어깨 장식
            im.set(x, y0 + 6, dark)
    # ── 장화 (다리 아래 5줄) ──
    R = cube(im, 0, 16, 4, 12, 4, setkey, rnd, rows=set(range(7, 12)), part='boots')
    for f in ('right', 'front', 'left', 'back'):
        x0, y0, x1, y1 = [v * S for v in R[f]]
        for x in range(x0, x1): im.set(x, y0 + 14, shade(trim, 1.1)); im.set(x, y0 + 15, trim)
    os.makedirs(os.path.join(ROOT, 'textures/entity/equipment/humanoid'), exist_ok=True)
    im.save(os.path.join(ROOT, 'textures/entity/equipment/humanoid', setkey + '.png'))
    # ── 각반 층 ──
    im = Img(64 * S, 32 * S)
    R = cube(im, 16, 16, 8, 12, 4, setkey, rnd, rows=set(range(8, 12)), faces=('right', 'front', 'left', 'back', 'bottom'), part='belt')
    x0, y0, x1, y1 = [v * S for v in R['front']]
    for x in range(x0, x1): im.set(x, y0 + 16, shade(trim, 1.15)); im.set(x, y0 + 17, trim); im.set(x, y0 + 18, shade(trim, 0.7))
    cxm = (x0 + x1) // 2
    for dx in range(-2, 2):
        for dy in range(19, 22): im.set(cxm + dx, y0 + dy, shade(trim, 1.2) if gem is None else gem)       # 버클
    R = cube(im, 0, 16, 4, 12, 4, setkey, rnd, rows=set(range(0, 9)), faces=('top', 'right', 'front', 'left', 'back'), part='legs')
    for f in ('right', 'front', 'left', 'back'):
        x0, y0, x1, y1 = [v * S for v in R[f]]
        for x in range(x0, x1): im.set(x, y0 + 9, shade(trim, 0.9)); im.set(x, y0 + 10, shade(trim, 0.7))   # 무릎 보호대
    os.makedirs(os.path.join(ROOT, 'textures/entity/equipment/humanoid_leggings'), exist_ok=True)
    im.save(os.path.join(ROOT, 'textures/entity/equipment/humanoid_leggings', setkey + '.png'))

# ── 아이콘 32x32 ──
TRIM_ROW = {'helmet': 4, 'chest': 3, 'legs': 2, 'boots': 11}
def icon(setkey, part, path, iid):
    base, dark, light, trim, gem = [C(c) if c else None for c in SETS[setkey]]
    m = MASKS[part]; im = Img(32, 32)
    f = lambda x, y: 0 <= x < 32 and 0 <= y < 32 and m[y // 2][x // 2] == '#'
    for y in range(32):
        for x in range(32):
            if not f(x, y): continue
            edge = not all(f(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            t = y / 31
            c = lerp(shade(base, 1.2), shade(base, 0.78), t)
            if y // 2 == TRIM_ROW[part]: c = shade(trim, 1.1 if y % 2 == 0 else 0.85)
            if STYLE[setkey] in ('scale', 'dscale') and (x + (y // 3 % 2) * 2) % 4 == 0 and y % 3 == 0: c = shade(c, 0.8)
            if edge: c = dark
            elif not f(x - 1, y - 1): c = shade(c, 1.3)        # 왼쪽 위 하이라이트
            elif not f(x + 1, y + 1): c = shade(c, 0.75)       # 오른쪽 아래 그림자
            im.set(x, y, c)
    if gem and part in ('helmet', 'chest'):
        gy = 7 if part == 'helmet' else 12
        for (dx, dy) in ((0, 0), (1, 0), (0, 1), (1, 1)): im.set(15 + dx, gy + dy, gem)
        im.set(15, gy, shade(gem, 1.4))
    im.save(path)

for sk in SETS:
    equipment(sk)
    for part in ('helmet', 'chest', 'legs', 'boots'):
        iid = sk + '_' + part
        icon(sk, part, os.path.join(ROOT, 'textures/item/forge', iid + '.png'), iid)
print('armor sets', len(SETS))
