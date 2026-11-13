"""별빛 대장간 입체(복셀) 무기 생성기 — Armourer's Workshop 스타일
무기를 '대각선 평면 그림(색) + 두께 지도'로 설계한 뒤, 0.5픽셀 블록으로 쌓아 아이템 모델(elements)로 만든다.
- 그림 해상도 44x44 → 모델 크기 22 단위 (-3 ~ 19), 바닐라 들고 있는 방식 그대로
- 같은 색·두께가 이어지는 칸은 한 덩어리로 합쳐 요소 수를 줄임
- 색은 팔레트 텍스처(64x64) 한 장에서 1칸씩 가져다 씀"""
import math, random, json, os, sys, struct, zlib

N = 64            # 그림 칸 수
SUB = 2           # 세밀 배율 (한 칸을 SUB x SUB 로 쪼갬)
VOX = 0.5 / SUB   # 세밀 칸 하나 = 0.25 단위
OFF = -3.0        # 모델 시작 좌표 (손잡이 위치를 바닐라와 같게 고정)

def C(h): return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def mix(a, b, t):
    t = max(0.0, min(1.0, t)); return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
def sh(c, f): return tuple(max(0, min(255, int(v * f))) for v in c)

NF = N * SUB
class Canvas:
    """세밀 격자. col[y][x] = 색(None=비움), dep = 두께(세밀 칸 수), glow = 빛나는지"""
    def __init__(s):
        s.col = [[None] * NF for _ in range(NF)]; s.dep = [[0] * NF for _ in range(NF)]; s.glow = [[False] * NF for _ in range(NF)]
        s.glowcols = set()
    def put(s, x, y, c, d):
        # d 는 '굵은 칸' 기준 두께 → 세밀 칸으로 환산
        if 0 <= x < NF and 0 <= y < NF: s.col[y][x] = c; s.dep[y][x] = max(1, int(round(d * SUB)))

# 대각선 좌표: u = 손잡이 끝(0) → 칼끝(1), v = 가로 거리(칸)
A = (3.0, N - 4.0)        # 손잡이 끝 (왼쪽 아래)
B = (N - 3.0, 3.0)        # 칼끝 (오른쪽 위)
L = math.dist(A, B)
def uv(x, y):
    """세밀 칸 좌표(x, y) → 대각선 좌표 (굵은 칸 단위)"""
    dx, dy = B[0] - A[0], B[1] - A[1]
    px, py = (x + 0.5) / SUB - A[0], (y + 0.5) / SUB - A[1]
    u = (px * dx + py * dy) / (L * L)
    v = (px * dy - py * dx) / L      # 오른쪽(+)/왼쪽(-)
    return u, v

def weapon(spec, seed=0):
    rnd = random.Random(seed)
    cv = Canvas()
    g0, g1 = spec['grip']          # 손잡이 u 범위
    gd0, gd1 = spec['guard_u']     # 가드 u 범위
    for y in range(N):
        for x in range(N):
            u, v = uv(x, y); av = abs(v)
            # ── 칼날 ──
            if gd1 <= u <= 1.0:
                t = (u - gd1) / (1.0 - gd1)
                hw = spec['blade_w'](t)
                hw += spec.get('edge', lambda t, v: 0)(t, v)
                if av <= hw:
                    rim = hw - av
                    base = C(spec['blade'])
                    c = mix(sh(base, 1.12), sh(base, 0.82), (v / max(hw, 0.1) + 1) / 2)   # 한쪽 밝고 한쪽 어둡게(경사면)
                    if rim < 0.9: c = C(spec['edge_c'])                                     # 날 끝선
                    if spec.get('fuller') and av < 0.6 and 0.05 < t < spec['fuller']: c = sh(base, 0.62)   # 홈
                    rune = spec.get('rune')
                    if rune and av < 0.6 and 0.12 < t < 0.75 and int(t * 40) % 4 == 0: c = C(rune)
                    c = c
                    d = 3 if rim > 2.2 else (2 if rim > 1.0 else 1)
                    if spec.get('thick'): d += spec['thick'] if rim > 1.4 else 0
                    cv.put(x, y, c, d); continue
            # ── 가드 ──
            curve = spec.get('guard_curve', 0.05) * (av / max(spec['guard_w'], 1)) ** 2
            if gd0 + curve <= u < gd1 + curve:
                gw = spec['guard_w']
                prof = spec.get('guard_prof', lambda v: 0)(v)
                if av <= gw + prof:
                    c = C(spec['guard'])
                    if av > gw - 1.2 or u < gd0 + 0.01: c = sh(c, 0.75)
                    if av < 1.6 and spec.get('gem'):
                        c = C(spec['gem']) if av < 1.0 else sh(C(spec['gem']), 0.8); cv.put(x, y, c, 7); continue
                    d = 5 if av < gw * 0.5 else 4
                    if av > gw - 1.0: c = sh(C(spec['guard']), 1.2); d = 3      # 날개 끝 장식
                    cv.put(x, y, c, d); continue
            # ── 손잡이 ──
            if g0 <= u < gd0 and av <= spec.get('grip_w', 1.3):
                c = C(spec['grip_c'])
                if int(u * 60) % 2 == 0: c = sh(c, 0.7)          # 감은 끈
                cv.put(x, y, c, 3); continue
            # ── 손잡이 끝 장식 ──
            pr = spec.get('pommel_r', 2.4)
            pc = (A[0] + (B[0] - A[0]) * (g0 - 0.012), A[1] + (B[1] - A[1]) * (g0 - 0.012))
            if math.dist((x + 0.5, y + 0.5), pc) <= pr:
                c = C(spec.get('pommel', spec['guard']))
                if math.dist((x + 0.5, y + 0.5), pc) <= pr * 0.45 and spec.get('gem'): cv.put(x, y, C(spec['gem']), 5); continue
                cv.put(x, y, c, 5)
    for fn in spec.get('extra', []): fn(cv, rnd)
    return cv

# ── 검 (실루엣이 다른 버전) ──
# s = 손잡이 끝에서 칼끝 방향 거리(칸), v = 가로(칸, +오른쪽). 구간: 손잡이 [g0,g1], 가드 [g1,b0], 칼날 [b0, b0+bl]
def sword2(sp, seed=0):
    rnd = random.Random(seed); cv = Canvas()
    if sp.get('gem'): cv.glowcols.add(C(sp['gem']))
    for key in ('rune', 'glow', 'vein'):
        if sp.get(key):
            for f in (0.97, 1.0, 1.03): cv.glowcols.add(sh(C(sp[key]), f))
    g0, g1, b0, bl = sp.get('g0', 4), sp.get('g1', 14), sp.get('b0', 17), sp['bl']
    blade, edge = C(sp['blade']), C(sp['edge_c']); guardc = C(sp['guard']); gripc = C(sp['grip_c'])
    gem = C(sp['gem']) if sp.get('gem') else None
    for y in range(NF):
        for x in range(NF):
            u, v = uv(x, y); s_ = u * L
            # 칼날
            if b0 <= s_ <= b0 + bl:
                t = (s_ - b0) / bl
                off = sp.get('curve', lambda t: 0)(t)
                vv = v - off
                lw, rw = sp['left'](t), sp['right'](t)
                if -lw <= vv <= rw:
                    w = lw + rw; pos = (vv + lw) / max(w, 0.1)      # 0=왼쪽 끝, 1=오른쪽 끝
                    c = (sh(blade, 1.14), blade, sh(blade, 0.84))[min(2, int(pos * 3))]
                    rim = min(vv + lw, rw - vv)
                    if rim < 0.85: c = edge
                    elif rim < 1.3 and not sp.get('no_band'): c = mix(c, edge, 0.4)
                    if sp.get('ridge', True) and abs(vv - (rw - lw) / 2) < 0.28 and t < 0.9 and w > 2.5: c = sh(c, 1.18)
                    if sp.get('edge_side') == 'right' and rw - vv < 1.2: c = edge
                    if sp.get('hamon') and rw - vv < 1.6 + 0.5 * math.sin(t * 30): c = C(sp['hamon'])
                    if sp.get('fuller') and abs(vv - (rw - lw) / 2) < 0.55 and 0.05 < t < sp['fuller']: c = sh(blade, 0.6)
                    if sp.get('rune') and abs(vv - (rw - lw) / 2) < 0.6 and 0.1 < t < 0.8 and int(t * 44) % 4 == 0: c = C(sp['rune'])
                    if sp.get('glow') and abs(vv - (rw - lw) / 2) < 0.5 and t < 0.85: c = C(sp['glow'])
                    vein = sp.get('vein')
                    if vein and rim > 0.9 and t < 0.9:
                        nz = math.sin(s_ * 0.42 + vv * 1.1) + 0.8 * math.sin(s_ * 0.19 - vv * 1.6) + 0.5 * math.sin(s_ * 0.8 + vv * 0.3)
                        if abs(nz) < 0.22: c = C(vein)

                    if sp.get('sweep') and t < sp['sweep'][0] and rim < sp['sweep'][1] * (1 - t / sp['sweep'][0]): c = C(sp['guard']); d_extra = 1
                    hole = sp.get('hole')
                    if hole and math.hypot(s_ - (b0 + bl * hole[0]), vv - hole[1]) < hole[2]: continue
                    d = 3 if rim > 2.0 else (2 if rim > 0.9 else 1)
                    if sp.get('sweep') and t < sp['sweep'][0] and rim < sp['sweep'][1] * (1 - t / sp['sweep'][0]): d = 4
                    d += sp.get('thick', 0) if rim > 2.0 else 0
                    cv.put(x, y, c, d); continue
                # 칼날 밖 장식(등가시 등)
                deco = sp.get('blade_deco')
                if deco:
                    r = deco(t, vv, lw, rw)
                    if r: cv.put(x, y, C(r[0]), r[1]); continue
            # 가드
            ds = s_ - g1
            gr = sp['guard_f'](ds, v)
            if gr:
                c = guardc if gr is True else C(gr[0]) if isinstance(gr, tuple) else guardc
                d = gr[1] if isinstance(gr, tuple) else 4
                if gem and abs(v) < (sp.get('eye', 1.2)) and -0.5 <= ds <= (b0 - g1) + 0.5:
                    c = gem if math.hypot(v, ds - (b0 - g1) / 2) > 0.6 or not sp.get('eye') else C('ffffff'); d = 7
                cv.put(x, y, c, d); continue
            # 손잡이
            if g0 <= s_ < g1 and abs(v) <= sp.get('grip_w', 1.2):
                c = gripc
                pat = sp.get('wrap', 'band')
                if pat == 'band' and int(s_ * 1.6) % 2 == 0: c = sh(c, 0.7)
                if pat == 'diamond' and (int(s_ * 1.2 + v) % 3 == 0 or int(s_ * 1.2 - v) % 3 == 0): c = C('e8e0d0')
                cv.put(x, y, c, 3); continue
            # 손잡이 끝
            pf = sp.get('pommel_f')
            if pf:
                r = pf(s_ - g0, v)
                if r: cv.put(x, y, C(r[0]) if isinstance(r, tuple) else guardc, r[1] if isinstance(r, tuple) else 4)
    return cv

def taper2(w, tip=0.2, end=1.0):
    return lambda t: w * (1 if t < 1 - tip else max(0, (1 - t) / tip))
ball = lambda r, col=None: (lambda ds, v: (col, 5) if (col and math.hypot(ds + r * 0.6, v) <= r) else (math.hypot(ds + r * 0.6, v) <= r))

SWORDS = {
 # 견습: 짧은 날 + 일자 막대 가드 + 둥근 끝
 't1_sword': dict(blade='a8a8a8', edge_c='dedede', guard='7a5a3a', grip_c='5a3e22', bl=24,
                  left=taper2(1.8, 0.25), right=taper2(1.8, 0.25),
                  guard_f=lambda ds, v: 0 <= ds <= 2 and abs(v) <= 4.0, pommel_f=ball(1.8)),
 # 철기병: 넓은 브로드소드 + 끝이 처진 가드 + 홈
 't2_sword': dict(sweep=(0.1, 1.4), blade='d8dde3', edge_c='ffffff', guard='3f67a8', grip_c='3a2a1a', bl=33, fuller=0.75,
                  left=taper2(2.7, 0.16), right=taper2(2.7, 0.16),
                  guard_f=lambda ds, v: (0 <= ds <= 2 and abs(v) <= 6.0) or (abs(v) > 4.6 and abs(v) <= 6.0 and -2.5 <= ds < 0),
                  pommel_f=lambda ds, v: abs(ds + 1) <= 1.4 and abs(v) <= 2.2),
 # 미스릴: 아주 가는 레이피어 + 고리 손잡이
 't3_sword': dict(blade='c9f6fa', edge_c='ffffff', guard='eafcff', grip_c='2b3d52', gem='6fc8ff', bl=40,
                  left=taper2(0.9, 0.1), right=taper2(0.9, 0.1),
                  guard_f=lambda ds, v: (0 <= ds <= 1.2 and abs(v) <= 4.0) or (3.0 <= math.hypot(ds + 4.5, v - 2.2) <= 4.0 and v > -0.5),
                  pommel_f=lambda ds, v: math.hypot(ds + 1.2, v) <= 1.6 + max(0, -ds - 1.2) * 0.2),
 # 아다만: 휜 카타나 + 둥근 날밑 + 마름모 손잡이
 't4_sword': dict(no_band=True, blade='bfe9e4', edge_c='ffffff', guard='2a2a2a', grip_c='1d2a2a', bl=36, hamon='e8fffb', edge_side='right',
                  curve=lambda t: 3.2 * t * t, left=taper2(0.8, 0.12), right=lambda t: 1.9 * (1 if t < 0.9 else max(0, (1 - t) / 0.1) ** 0.6),
                  guard_f=lambda ds, v: math.hypot(ds - 0.8, v * 0.9) <= 3.6 and 0 <= ds <= 1.6, g0=2, g1=15, b0=17, wrap='diamond',
                  pommel_f=lambda ds, v: abs(ds) <= 0.8 and abs(v) <= 1.4),
 # 흑요: 들쭉날쭉한 흑요석 조각 날 + 가시 가드
 't5_sword': dict(vein='c09bff', sweep=(0.2, 2.0), eye=1.6, blade='2a2238', edge_c='b89cff', guard='8a5cff', grip_c='0e0b12', gem='c09bff', bl=35, glow='9b6bff',
                  left=lambda t: (2.2 + 1.3 * ((int(t * 7) * 37) % 5) / 4) * (1 if t < 0.82 else (1 - t) / 0.18),
                  right=lambda t: (2.0 + 1.4 * ((int(t * 6 + 3) * 53) % 5) / 4) * (1 if t < 0.8 else (1 - t) / 0.2),
                  guard_f=lambda ds, v: (0 <= ds <= 2 and abs(v) <= 4.5) or (abs(v) > 3 and abs(v) <= 6.5 and 0 <= ds <= (6.5 - abs(v)) * 1.4),
                  pommel_f=lambda ds, v: abs(ds + 1.5) + abs(v) * 0.8 <= 2.4),
 # 별빛: 넓은 성검 + 날개 가드 + 빛나는 중심선
 't6_sword': dict(sweep=(0.22, 2.4), eye=1.8, blade='fff6d8', edge_c='ffffff', guard='f0cf62', grip_c='3a2a12', gem='79b6ff', bl=35, glow='ffe58a', thick=1,
                  left=taper2(3.0, 0.22), right=taper2(3.0, 0.22),
                  guard_f=lambda ds, v: (0 <= ds <= 2.2 and abs(v) <= 3.5) or (3.5 < abs(v) <= 9.5 and -1.5 + (abs(v) - 3.5) * 0.25 <= ds <= 2.2 + (abs(v) - 3.5) * 0.55 and int(abs(v)) % 2 == 0) and (('ffffff', 3) if abs(v) > 6.5 else True),
                  pommel_f=lambda ds, v: (('79b6ff', 5) if math.hypot(ds + 1.2, v) <= 1.0 else (math.hypot(ds + 1.2, v) <= 2.2))),
 # 송곳니: 등에 이빨이 난 외날 마체테
 'fang_sword': dict(sweep=(0.18, 1.8), blade='ece2c6', edge_c='fffaf0', guard='5d7d33', grip_c='4a3420', gem='c43c2c', bl=31, edge_side='right',
                    left=lambda t: 1.0 if t < 0.95 else 0.4, right=lambda t: (1.2 + 2.6 * t) * (1 if t < 0.88 else max(0, (1 - t) / 0.12) ** 0.5),
                    blade_deco=lambda t, vv, lw, rw: ('d8ccb0', 2) if (-lw - 1.6 <= vv < -lw and int(t * 16) % 2 == 0 and 0.1 < t < 0.85 and (-lw - vv) < 1.6 - (t * 16 % 1) * 1.6) else None,
                    guard_f=lambda ds, v: (0 <= ds <= 1.8 and abs(v) <= 3.6) or (-3.5 <= ds < 0 and 1.6 <= v <= 2.6),
                    pommel_f=ball(2.0, 'e8dcc0')),
 # 사이렌: 물결 날 + 삼지창 가드
 'siren_blade': dict(sweep=(0.2, 1.8), eye=1.8, vein='e6fdff', blade='4fc4d6', edge_c='e6fdff', guard='efe39a', grip_c='2b4c63', gem='ff78d6', bl=33, rune='bff6ff',
                     curve=lambda t: 0.9 * math.sin(t * 4 * math.pi * 2 / 2) * (t < 0.9), left=taper2(2.2, 0.2), right=taper2(2.2, 0.2),
                     guard_f=lambda ds, v: (0 <= ds <= 1.5 and abs(v) <= 5.0) or (abs(abs(v) - 4.2) <= 0.8 and 1.5 < ds <= 5.0 - abs(v) * 0.1),
                     pommel_f=lambda ds, v: ('ff78d6', 5) if math.hypot(ds + 1.0, v) <= 1.0 else math.hypot(ds + 1.0, v) <= 2.0),
 # 지옥견: 양날 불꽃 날 + 뿔 가드
 'hound_sword': dict(vein='ff6a1a', sweep=(0.22, 2.6), eye=2.0, blade='2a0e0e', edge_c='ff8c1a', guard='4a1010', grip_c='1b1b1b', gem='ff8c1a', bl=37, rune='ff5a1a', thick=1,
                     g0=3, g1=13, b0=16, grip_w=1.5,
                     left=lambda t: (3.6 + 1.3 * abs(math.sin(t * 7 * math.pi))) * (1 if t < 0.84 else (1 - t) / 0.16),
                     right=lambda t: (3.6 + 1.3 * abs(math.cos(t * 7 * math.pi))) * (1 if t < 0.84 else (1 - t) / 0.16),
                     guard_f=lambda ds, v: (0 <= ds <= 2.6 and abs(v) <= 5.5) or (abs(v) > 4.5 and abs(v) <= 9.0 and abs(ds - (abs(v) - 4.5) ** 1.4 * 0.5) <= 1.1) and (('e8d8c0', 3) if abs(v) > 7.2 else True),
                     pommel_f=lambda ds, v: abs(ds + 1.2) <= 1.6 and abs(v) <= 2.0 - abs(ds + 1.2) * 0.5),
 # 거인: 구멍 뚫린 거대한 직사각 버스터소드
 'giant_crusher': dict(sweep=(0.15, 3.0), eye=1.8, rune='ffcc33', blade='9a8a6a', edge_c='f6e6c0', guard='6e5b3c', grip_c='3a2a18', gem='ffcc33', bl=34, thick=1, g0=3, g1=13, b0=16,
                       left=lambda t: 4.6 if t < 0.9 else 4.6 - (t - 0.9) * 30, right=lambda t: 4.6 if t < 0.94 else 4.6 - (t - 0.94) * 60,
                       hole=(0.78, 0.0, 1.5), fuller=0.6, grip_w=1.5,
                       guard_f=lambda ds, v: 0 <= ds <= 3 and abs(v) <= 5.6, pommel_f=lambda ds, v: abs(ds + 1.5) <= 1.6 and abs(v) <= 2.4),
 # 용린: 등가시 대검 + 용 날개 가드
 'dragon_greatsword': dict(sweep=(0.2, 2.8), eye=2.0, vein='ff8a3a', blade='b82218', edge_c='ffd2b0', guard='e3b14a', grip_c='2a1a10', gem='ffd84a', bl=36, thick=1, rune='ffcf6a', g0=3, g1=13, b0=16,
                           curve=lambda t: -1.2 * t ** 3, left=taper2(3.6, 0.22), right=taper2(3.4, 0.25), grip_w=1.4,
                           blade_deco=lambda t, vv, lw, rw: ('8a1810', 2) if (-lw - 2.2 <= vv < -lw and 0.08 < t < 0.75 and (t * 10 % 1) < 0.45 and (-lw - vv) < 2.2 * (1 - (t * 10 % 1) / 0.45)) else None,
                           guard_f=lambda ds, v: (0 <= ds <= 2.5 and abs(v) <= 4) or (4 < abs(v) <= 9 and -0.5 - (abs(v) - 4) * 0.6 <= ds <= 2.5 - (abs(v) - 4) * 0.2 and (int(abs(v) * 1.2) % 2 == 0 or ds > 0)) and (('b88a30', 3) if abs(v) > 6 else True),
                           pommel_f=lambda ds, v: ('ffd84a', 5) if math.hypot(ds + 1.4, v) <= 1.1 else (math.hypot(ds + 1.4, v) <= 2.4)),
}

DAGGERS = {
 # 견습: 짧은 양날 단검
 't1_dagger': dict(blade='a8a8a8', edge_c='dedede', guard='7a5a3a', grip_c='5a3e22', bl=15, g0=10, g1=18, b0=20,
                   left=taper2(1.6, 0.35), right=taper2(1.6, 0.35), guard_f=lambda ds, v: 0 <= ds <= 1.5 and abs(v) <= 3.0, pommel_f=ball(1.5)),
 # 철기: 쿠나이 (고리 손잡이)
 't2_dagger': dict(blade='c8cdd3', edge_c='ffffff', guard='3a3a3a', grip_c='2a2a2a', bl=16, g0=10, g1=18, b0=19,
                   left=lambda t: 2.4 * (1 - t) ** 0.8, right=lambda t: 2.4 * (1 - t) ** 0.8, guard_f=lambda ds, v: 0 <= ds <= 1 and abs(v) <= 1.6,
                   pommel_f=lambda ds, v: 1.4 <= math.hypot(ds + 2.2, v) <= 2.4),
 # 미스릴: 가는 스틸레토
 't3_dagger': dict(blade='c9f6fa', edge_c='ffffff', guard='eafcff', grip_c='2b3d52', gem='6fc8ff', bl=19, g0=9, g1=17, b0=19,
                   left=taper2(0.8, 0.3), right=taper2(0.8, 0.3), guard_f=lambda ds, v: 0 <= ds <= 1.5 and abs(v) <= 3.5 and (abs(v) < 1.5 or ds < 0.8),
                   pommel_f=lambda ds, v: abs(ds + 1) + abs(v) * 0.9 <= 1.8),
 # 아다만: 카람빗 (갈고리처럼 휜 날)
 't4_dagger': dict(blade='bfe9e4', edge_c='ffffff', guard='1d2a2a', grip_c='2a6a66', bl=16, g0=10, g1=18, b0=19, edge_side='right',
                   curve=lambda t: -4.0 * t * t, left=lambda t: 0.9 * (1 - t * 0.6), right=lambda t: 1.8 * (1 if t < 0.8 else (1 - t) / 0.2),
                   guard_f=lambda ds, v: 0 <= ds <= 1 and abs(v) <= 2.2, pommel_f=lambda ds, v: 1.2 <= math.hypot(ds + 2, v) <= 2.2),
 # 흑요: 흑요석 조각 단검
 't5_dagger': dict(blade='3d3352', edge_c='b89cff', guard='8a5cff', grip_c='0e0b12', bl=17, g0=10, g1=18, b0=19, glow='9b6bff',
                   left=lambda t: (1.6 + 1.0 * ((int(t * 5) * 37) % 3) / 2) * (1 - t) ** 0.6, right=lambda t: (1.4 + 1.0 * ((int(t * 4 + 1) * 53) % 3) / 2) * (1 - t) ** 0.6,
                   guard_f=lambda ds, v: (0 <= ds <= 1.5 and abs(v) <= 3) or (abs(v) > 2 and abs(v) <= 4 and 0 <= ds <= (4 - abs(v)) * 1.5), pommel_f=lambda ds, v: abs(ds + 1) + abs(v) <= 1.8),
 # 별빛: 성스러운 단검 (작은 날개)
 't6_dagger': dict(blade='fff6d8', edge_c='ffffff', guard='f0cf62', grip_c='3a2a12', gem='79b6ff', bl=17, g0=10, g1=18, b0=20, glow='ffe58a',
                   left=taper2(2.0, 0.35), right=taper2(2.0, 0.35),
                   guard_f=lambda ds, v: (0 <= ds <= 1.8 and abs(v) <= 2.5) or (2.5 < abs(v) <= 6 and -1 + (abs(v) - 2.5) * 0.3 <= ds <= 1.8 + (abs(v) - 2.5) * 0.5 and int(abs(v)) % 2 == 0) and (('ffffff', 3) if abs(v) > 4 else True),
                   pommel_f=lambda ds, v: ('79b6ff', 5) if math.hypot(ds + 1, v) <= 0.9 else math.hypot(ds + 1, v) <= 1.8),
 # 그림자 단검: 검은 날 + 보라 날끝, 가드 없음 / 손잡이 끝 날
 'shadow_dagger': dict(blade='1a1626', edge_c='9b6bff', guard='2a2238', grip_c='120e18', gem='c09bff', bl=18, g0=9, g1=18, b0=19, glow='5a3a9a',
                       left=lambda t: 1.2 * (1 - t) ** 0.5, right=lambda t: 2.4 * (1 if t < 0.6 else (1 - t) / 0.4) ** 0.7,
                       guard_f=lambda ds, v: 0 <= ds <= 1 and abs(v) <= 1.8, pommel_f=lambda ds, v: ('9b6bff', 3) if (-4 <= ds <= 0 and abs(v) <= (ds + 4) * 0.3) else None),
 # 독니 단검: 초록 날 + 독 방울
 'venom_dagger': dict(vein='b6ff5a', blade='2f5a1f', edge_c='b6ff5a', guard='2a3a1a', grip_c='1a1a1a', gem='7dff3a', bl=18, g0=9, g1=17, b0=19, rune='9dff4a', edge_side='right',
                      curve=lambda t: 1.5 * t * t, left=lambda t: 1.0, right=lambda t: (1.4 + 1.2 * t) * (1 if t < 0.8 else (1 - t) / 0.2),
                      blade_deco=lambda t, vv, lw, rw: ('7dff3a', 2) if (rw < vv <= rw + 1.6 and int(t * 9) % 3 == 0 and 0.2 < t < 0.8) else None,
                      guard_f=lambda ds, v: (0 <= ds <= 1.2 and abs(v) <= 3.0) or (abs(abs(v) - 2.6) <= 0.6 and 1.2 < ds <= 3.0),
                      pommel_f=lambda ds, v: ('7dff3a', 4) if math.hypot(ds + 1, v) <= 1.5 else None),
 # 공허의 쌍단검: 위아래로 날이 달린 검보라 쌍날
 'void_dagger': dict(vein='ff4ad8', sweep=(0.3, 1.8), blade='241a38', edge_c='d080ff', guard='6a3aa0', grip_c='0e0b12', gem='ff4ad8', bl=19, g0=11, g1=18, b0=20, glow='a050ff', thick=1,
                     left=lambda t: (2.0 + 0.8 * abs(math.sin(t * 9))) * (1 - t) ** 0.7, right=lambda t: (2.0 + 0.8 * abs(math.cos(t * 9))) * (1 - t) ** 0.7,
                     guard_f=lambda ds, v: (0 <= ds <= 1.6 and abs(v) <= 3.2) or (abs(v) > 2.4 and abs(v) <= 4.6 and -2 <= ds <= 0.5),
                     pommel_f=lambda ds, v: ('8a50d0', 3) if (-7 <= ds <= -1 and abs(v) <= (ds + 7) * 0.35) else None),
}

# ── 무기별 모양 함수 ──
taper = lambda w, tip=0.15: (lambda t: w * (1 - max(0, (t - (1 - tip)) / tip)) if t < 1 else 0)
def serrate(n, amp): return lambda t, v: (amp if (v > 0 and int(t * n) % 2 == 0 and t < 0.8) else 0)
def wave(n, amp): return lambda t, v: amp * math.sin(t * n * math.pi * 2) * (1 if v > 0 else -1) * (t < 0.85)
def flame(n, amp): return lambda t, v: amp * abs(math.sin(t * n * math.pi)) * (t < 0.85)
def spikes_guard(k): return lambda v: k * (abs(v) > 3) * (int(abs(v)) % 2)

SPECS = {
 'fang_sword': dict(sweep=(0.18, 1.8), blade='ece2c6', edge_c='fffaf0', guard='5d7d33', grip_c='4a3420', gem='c43c2c', pommel='e8dcc0',
                    grip=(0.06, 0.25), guard_u=(0.25, 0.30), guard_w=5.0, blade_w=taper(2.6, 0.18), edge=serrate(14, 1.2), fuller=0.5),
 'siren_blade': dict(sweep=(0.2, 1.8), eye=1.8, vein='e6fdff', blade='4fc4d6', edge_c='e6fdff', guard='efe39a', grip_c='2b4c63', gem='ff78d6', pommel='efe39a',
                     grip=(0.06, 0.25), guard_u=(0.25, 0.30), guard_w=4.5, guard_prof=lambda v: 1.0 * math.cos(v),
                     blade_w=taper(2.4, 0.2), edge=wave(4, 0.9), rune='bff6ff'),
 'hound_sword': dict(vein='ff6a1a', sweep=(0.22, 2.6), eye=2.0, blade='2a0e0e', edge_c='ff8c1a', guard='7a1f1f', grip_c='1b1b1b', gem='ff8c1a', pommel='7a1f1f',
                     grip=(0.06, 0.25), guard_u=(0.25, 0.31), guard_w=5.5, guard_prof=spikes_guard(1.5),
                     blade_w=taper(2.8, 0.2), edge=flame(6, 1.1), rune='ff5a1a'),
 'giant_crusher': dict(sweep=(0.15, 3.0), eye=1.8, rune='ffcc33', blade='9a8a6a', edge_c='f6e6c0', guard='8a6a3a', grip_c='3a2a18', gem='ffcc33', pommel='8a6a3a',
                       grip=(0.05, 0.22), guard_u=(0.22, 0.28), guard_w=6.0, grip_w=1.6, pommel_r=2.6,
                       blade_w=lambda t: (4.6 if t < 0.88 else 4.6 * (1 - (t - 0.88) / 0.12)), fuller=0.7, thick=1),
 'dragon_greatsword': dict(sweep=(0.2, 2.8), eye=2.0, vein='ff8a3a', blade='b82218', edge_c='ffd2b0', guard='e3b14a', grip_c='2a1a10', gem='ffd84a', pommel='e3b14a',
                           grip=(0.05, 0.22), guard_u=(0.22, 0.29), guard_w=7.0, guard_prof=spikes_guard(2.0), grip_w=1.5, pommel_r=2.6,
                           blade_w=taper(3.8, 0.22), edge=serrate(8, 0.9), rune='ffcf6a', fuller=0.75, thick=1),
}
TIER = {
 't1_sword': ('9a9a9a', 'd6d6d6', '8b5a2b', '6b4a2a', None, 2.0),
 't2_sword': ('d8dde3', 'ffffff', '3f67a8', '3a2a1a', None, 2.2),
 't3_sword': ('b9f3f7', 'ffffff', 'eafcff', '2b3d52', '6fc8ff', 2.3),
 't4_sword': ('4fc9bd', 'c8fff8', 'c8c8c8', '1d2a2a', '3dffcf', 2.5),
 't5_sword': ('3d3352', 'b89cff', '8a5cff', '0e0b12', 'c09bff', 2.9),
 't6_sword': ('fff2bf', 'ffffff', 'f0cf62', '3a2a12', '79b6ff', 3.1),
}
for k, (blade, edge, guard, grip, gem, w) in TIER.items():
    SPECS[k] = dict(blade=blade, edge_c=edge, guard=guard, grip_c=grip, gem=gem, pommel=guard,
                    grip=(0.06, 0.25), guard_u=(0.25, 0.30), guard_w=4.0 + w * 0.5, blade_w=taper(w, 0.2),
                    fuller=0.6 if k != 't1_sword' else None, rune=('fff6b0' if k == 't6_sword' else ('d0b8ff' if k == 't5_sword' else None)))

def staff(seed=0, wood='6b4a2a', dark='3a2614', ring='cfd8ff', gem='7fb8ff', head='orb', size=4.3, gold='e3b14a', wings=False):
    """마법봉: 나선 장식 자루 + 발톱 받침 + 보석/수정/얼음/해골 + 빛 고리 + 떠다니는 조각"""
    cv = Canvas(); rnd = random.Random(seed)
    W, D, R, G, Au = C(wood), C(dark), C(ring), C(gem), C(gold)
    uc = 0.80
    oc = (A[0] + (B[0] - A[0]) * uc, A[1] + (B[1] - A[1]) * uc)
    ax = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)         # 자루 방향(칼끝 쪽)
    def put(x, y, c, d):
        if cv.col[y][x] is None or cv.dep[y][x] <= d: cv.put(x, y, c, d)
    for y in range(N):
        for x in range(N):
            u, v = uv(x, y); av = abs(v)
            # ── 자루 ──
            if 0.06 <= u <= uc - 0.11 and av <= 1.25:
                c = W if av < 0.6 else D
                if (u * 46 + v * 0.35) % 1 < 0.22: c = Au                     # 금 나선
                d = 3
                for m in (0.10, 0.36, uc - 0.12):                            # 금 마디
                    if abs(u - m) < 0.012: c = Au; d = 4
                put(x, y, c, d)
            if 0.0 <= u < 0.06 and av <= 1.25 * (u / 0.06):                   # 아래 뾰족한 끝
                put(x, y, R, 3)
            # ── 머리 ──
            px, py = x + .5 - oc[0], y + .5 - oc[1]; dd = math.hypot(px, py)
            along = px * ax[0] + py * ax[1]                                   # +면 칼끝 쪽
            cosang = along / dd if dd > 0 else 1
            # 발톱 받침: 보석을 감싸는 휘어진 두 갈래 (칼끝 쪽은 열려 있음)
            if size + 0.6 <= dd <= size + 2.2 and cosang < 0.55:
                put(x, y, Au if dd < size + 1.5 else sh(Au, 0.75), 4)
            if size + 2.2 < dd <= size + 3.4 and 0.35 < cosang < 0.6:         # 발톱 끝 가시
                put(x, y, sh(Au, 1.15), 3)
            # 빛 고리 (점선)
            if size + 4.0 <= dd <= size + 4.8 and (int(math.degrees(math.atan2(py, px)) + 360) // 20) % 2 == 0:
                put(x, y, sh(G, 1.25), 1)
            # 날개
            if wings and cosang < -0.1 and size + 2.2 < dd <= size + 7.5:
                side = px * ax[1] - py * ax[0]
                if abs(side) > size + 1 and (int(dd * 1.3) % 2 == 0 or dd > size + 6.5):
                    put(x, y, C('ffffff') if dd > size + 5 else C('fff3c0'), 2)
            # 핵심(보석류)
            if head == 'orb' and dd <= size:
                c = mix(C('ffffff'), G, min(1, dd / size) ** 0.8)
                put(x, y, c, 8 if dd < size * 0.6 else 6)
            elif head == 'crystal':
                q = abs(along) * 0.75 + abs(px * ax[1] - py * ax[0]) * 1.3
                if q <= size + 0.5:
                    c = mix(C('ffffff'), G, min(1, q / (size + 0.5)))
                    if (px * ax[1] - py * ax[0]) > 0: c = sh(c, 0.85)          # 결정 면 나누기
                    put(x, y, c, 8 if q < size * 0.5 else 6)
            elif head == 'frost':
                ang = math.degrees(math.atan2(py, px)) % 60
                if dd <= size * 0.75 or (dd <= size + 2.5 and (ang < 8 or ang > 52)):
                    put(x, y, mix(C('ffffff'), G, min(1, dd / (size + 2.5))), 7 if dd < size * 0.75 else 4)
            elif head == 'skull' and dd <= size:
                c = C('e8e2cf'); d = 7
                side = px * ax[1] - py * ax[0]
                if -1.6 < along < 0.4 and 0.6 < abs(side) < 2.4: c = G; d = 8   # 눈
                if along < -2.2 and abs(side) < 1.6 and int(side * 2) % 2 == 0: c = C('8a8270')  # 이빨
                put(x, y, c, d)
    # 반짝임(하이라이트)과 떠다니는 조각
    hx, hy = int(oc[0] - 1.2), int(oc[1] - 1.2)
    if 0 <= hx < N and 0 <= hy < N and cv.col[hy][hx]: cv.put(hx, hy, C('ffffff'), cv.dep[hy][hx] + 1)
    for k in range(3):
        ang = math.radians(35 + k * 120)
        sx, sy = oc[0] + math.cos(ang) * (size + 6.2), oc[1] + math.sin(ang) * (size + 6.2)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if abs(dx) + abs(dy) <= 1:
                    xx, yy = int(sx + dx), int(sy + dy)
                    if 0 <= xx < N and 0 <= yy < N: cv.put(xx, yy, C('ffffff') if (dx, dy) == (0, 0) else G, 3)
    return cv

def bow(seed=0, wood='d9b04a', light='fff0b0', string='f4f4f4', grip='6b4a2a', tip='fff27a', R=36.0, recurve=0.0, spikes=False):
    cv = Canvas(); rnd = random.Random(seed)
    Wd, Lt, St, Gp, Tp = C(wood), C(light), C(string), C(grip), C(tip)
    cx, cy = 4.0, N - 4.0
    for y in range(N):
        for x in range(N):
            d = math.dist((x + .5, y + .5), (cx, cy)); ang = math.degrees(math.atan2(cy - (y + .5), x + .5 - cx))
            rr = R + recurve * (abs(ang - 45) / 45) ** 3 * 4      # 끝이 바깥으로 휘는 리커브
            if 0 <= ang <= 90 and rr - 2.4 <= d <= rr + 0.6:
                c = Lt if d > rr - 0.4 else (Wd if int(ang) % 12 else sh(Wd, 0.7))
                th = 3 if 30 < ang < 60 else 2
                if 38 < ang < 52: c = Gp; th = 4
                cv.put(x, y, c, th)
            if spikes and 0 <= ang <= 90 and rr + 0.6 < d <= rr + 2.2 and int(ang) % 15 < 3 and not (35 < ang < 55):
                cv.put(x, y, Tp, 2)
    p0, p1 = (cx + R - 1, cy), (cx, cy - R + 1)
    for i in range(200):
        t = i / 199; x, y = int(p0[0] + (p1[0] - p0[0]) * t), int(p0[1] + (p1[1] - p0[1]) * t)
        if cv.col[y][x] is None: cv.put(x, y, St, 1)
    for (fx, fy) in [(p0[0] - 1, p0[1] - 1), (p1[0] + 1, p1[1] + 1)]:
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if abs(dx) + abs(dy) <= 2: cv.put(int(fx + dx), int(fy + dy), Tp, 2)
    return cv

STAFFS = {
 'star_staff': dict(head='orb', size=3.8, wings=True),
 'frost_staff': dict(wood='5a6b80', dark='2e3a48', ring='e0f6ff', gem='7fe0ff', head='frost', size=3.6, gold='cfefff'),
 'lich_staff': dict(wood='3a2a3a', dark='1a121a', ring='9a7ab0', gem='b04cff', head='skull', size=3.8, gold='6a4a8a'),
 't1_staff': dict(wood='7a5a3a', dark='4a3420', ring='9a9a9a', gem='c9b48a', head='orb', size=3.0),
 't2_staff': dict(wood='6b4a2a', dark='3a2614', ring='d8dde3', gem='9ab8e6', head='orb', size=3.4),
 't3_staff': dict(wood='8a9aa8', dark='4f5f6e', ring='eafcff', gem='6fc8ff', head='crystal', size=3.6),
 't4_staff': dict(wood='2a4a48', dark='173030', ring='c8c8c8', gem='3dffcf', head='crystal', size=4.0),
 't5_staff': dict(wood='2b2339', dark='120e18', ring='8a5cff', gem='c09bff', head='crystal', size=4.4),
 't6_staff': dict(wood='fff3c0', dark='c9a33a', ring='ffffff', gem='79b6ff', head='crystal', size=4.2, wings=True),
}
BOWS = {
 'harpy_bow': dict(),
 'frost_bow': dict(wood='8fd4e8', light='e8fbff', grip='2e3a48', tip='ffffff', recurve=1.0, spikes=True),
 'dragon_bow': dict(wood='b4271f', light='ff8a6a', grip='2a1a10', tip='e3b14a', recurve=1.6, spikes=True),
 't1_bow': dict(wood='8b5a2b', light='b98a55', grip='4e3015', tip='d8c08a', R=33.0),
 't2_bow': dict(wood='7a5a3a', light='a9aeb5', grip='3f67a8', tip='e2e6ea', R=34.0),
 't3_bow': dict(wood='9fdfe4', light='eafcff', grip='2b3d52', tip='6fc8ff', R=35.0, recurve=0.6),
 't4_bow': dict(wood='2f8f8a', light='74d6cb', grip='174a47', tip='3dffcf', R=35.0, recurve=0.8),
 't5_bow': dict(wood='2b2339', light='5a4977', grip='120e18', tip='c09bff', R=36.0, recurve=1.0, spikes=True),
 't6_bow': dict(wood='f0cf62', light='fff3c0', grip='a87f22', tip='79b6ff', R=37.0, recurve=1.2, spikes=True),
}


# ════════ 개성 있는 지팡이 ════════
def staff3(kind, seed=0):
    rnd = random.Random(seed); cv = Canvas()
    ax = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)
    def P(sa, sb):    # 축 거리 sa(칸), 옆 sb(칸) → 화면 좌표
        return (A[0] + ax[0] * sa + ax[1] * sb, A[1] + ax[1] * sa - ax[0] * sb)
    def put(x, y, c, d):
        if 0 <= x < N and 0 <= y < N and (cv.col[y][x] is None or cv.dep[y][x] <= d): cv.put(x, y, c, d)
    def local(x, y):
        px, py = x + .5 - A[0], y + .5 - A[1]
        return px * ax[0] + py * ax[1], px * ax[1] - py * ax[0]    # sa, sb
    J = lambda c: c
    top = 34.0 * N / 44      # 자루 끝(머리 시작) 축 거리
    K = kind
    for y in range(N):
        for x in range(N):
            sa, sb = local(x, y); ab = abs(sb)
            # ── 자루 ──
            if 2 <= sa <= top:
                if K == 't1':     # 굽은 나뭇가지
                    off = 0.9 * math.sin(sa * 0.35)
                    if abs(sb - off) <= 1.3: put(x, y, J(C('7a5a3a') if abs(sb - off) < 0.6 else C('4e3620')), 3)
                elif K == 't2':   # 철 자루 + 가죽 감기
                    if ab <= 1.1: put(x, y, J(C('8f959c') if int(sa) % 6 else C('5a3e22')), 3)
                elif K == 't3':   # 가는 은 완드
                    if ab <= 0.75 and sa > 10: put(x, y, J(C('e6f4ff')), 2)
                    elif ab <= 1.2 and 8 <= sa <= 10: put(x, y, C('6fc8ff'), 4)
                elif K == 't4':   # 청록 자루 + 마디
                    if ab <= 1.1: put(x, y, J(C('2a6a66') if int(sa / 3) % 2 else C('1a4440')), 3)
                elif K == 't5':   # 흑요석 자루, 보라 균열
                    if ab <= 1.25: put(x, y, C('b089ff') if (int(sa * 1.7 + sb * 3) % 9 == 0) else J(C('241c30')), 3)
                elif K == 't6':   # 금 자루 + 흰 리본
                    if ab <= 1.1: put(x, y, J(C('f0cf62') if (sa * 0.8 + sb * 0.6) % 3 > 0.8 else C('ffffff')), 3)
                elif K == 'star':
                    if ab <= 1.2: put(x, y, J(C('e3b14a') if (sa * 1.0 + sb * 0.4) % 1 < 0.22 else C('6b4a2a')), 3)
                elif K == 'frost':  # 서리 자루 + 고드름
                    if ab <= 1.1: put(x, y, J(C('9fc6dc')), 3)
                    if 1.1 < sb <= 2.6 and int(sa) % 7 == 0 and sa > 8: put(x, y, C('e8fbff'), 2)
                elif K == 'moon':   # 은빛 자루 + 보라 리본
                    if ab <= 1.1: put(x, y, J(C('cfd4ea') if (sa * 0.7 + sb) % 4 > 1 else C('7a6ac8')), 3)
                elif K == 'sun':    # 금 자루 + 붉은 마디
                    if ab <= 1.2: put(x, y, J(C('e3b14a') if int(sa / 2.5) % 3 else C('b4271f')), 3)
                elif K == 'lich':   # 척추뼈 자루
                    seg = sa % 3
                    if (ab <= 1.4 and seg < 2.0) or (ab <= 0.7): put(x, y, J(C('d8d0b8') if seg < 2.0 else C('8a8270')), 3)
                    if seg < 1.0 and 1.4 < ab <= 2.4: put(x, y, C('b8b098'), 2)       # 갈비 돌기
        # 끝
    # ── 머리 ──
    hc = top + 7     # 머리 중심 축 거리
    SC = 1.35        # 머리 확대 배율
    for y in range(N):
        for x in range(N):
            sa0, sb0 = local(x, y)
            sa = top + (sa0 - top) / SC; sb = sb0 / SC
            ab = abs(sb); da = sa - (top + (hc - top) / SC); r = math.hypot(da, sb)
            if K == 't1':   # 갈라진 가지 끝 + 새싹
                if top <= sa <= top + 6 and abs(sb - (sa - top) * 0.5) <= 1.0: put(x, y, C('6b4a2a'), 3)
                if top + 2 <= sa <= top + 5 and abs(sb + (sa - top - 2) * 0.7) <= 0.9: put(x, y, C('6b4a2a'), 3)
                if math.hypot(sa - top - 7, sb - 3.5) <= 1.6 or math.hypot(sa - top - 5.5, sb + 2.8) <= 1.3: put(x, y, C('6fbf4a'), 2)
            elif K == 't2':  # 날개 달린 철 셉터
                if abs(da) <= 3.2 and ab <= 2.6 - abs(da) * 0.2: put(x, y, J(C('b8bec6')), 5)
                if abs(da) <= 2.5 and 2.6 < ab <= 4.2 and abs(da) <= (4.2 - ab) * 2: put(x, y, C('8f959c'), 3)
                if r <= 1.3: put(x, y, C('4f86d8'), 7)
                if 3.2 < da <= 5.0 and ab <= (5 - da) * 0.7: put(x, y, C('d8dde3'), 4)
            elif K == 't3':  # 초승달 + 떠 있는 작은 수정
                rr = math.hypot(da, sb); rr2 = math.hypot(da - 1.8, sb - 1.2)
                if rr <= 5.0 and rr2 > 4.3: put(x, y, J(C('eafcff')), 3)
                if math.hypot(da - 0.8, sb - 1.0) <= 1.3: put(x, y, C('6fc8ff'), 6)
            elif K == 't4':  # 고리 열쇠(앙크) + 수정
                if 3.0 <= math.hypot(da - 1, sb * 1.2) <= 4.2: put(x, y, J(C('3a9a92')), 4)
                if ab <= 3.6 and abs(da + 3.6) <= 0.9: put(x, y, C('c8c8c8'), 4)
                if abs(da - 1) + ab * 0.9 <= 2.0: put(x, y, C('3dffcf') if abs(da - 1) + ab < 1.0 else C('1fc8a0'), 6)
            elif K == 't5':  # 흑요석 결정 덩어리 (가시 여러 개)
                for (ang, ln) in ((0, 9), (35, 6.5), (-30, 7), (70, 4.5), (-65, 5)):
                    ca, sa_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                    a2 = (sa - top) * ca + sb * sa_; b2 = -(sa - top) * sa_ + sb * ca
                    if 0 <= a2 <= ln and abs(b2) <= 1.6 * (1 - a2 / ln) + 0.3:
                        put(x, y, C('c09bff') if abs(b2) < 0.5 else J(C('3d3352')), 6 if ang == 0 else 4)
            elif K == 't6':  # 날개 달린 오각별
                ang = math.atan2(sb, da); k = (math.cos(5 * ang) + 1) / 2
                if r <= 2.2 + 2.8 * k: put(x, y, C('fff3c0') if r < 2.4 else C('f0cf62'), 6 if r < 2.4 else 4)
                if r <= 1.0: put(x, y, C('79b6ff'), 8)
                if -4 <= da <= 2 and 4.5 <= ab <= 9 and (int(ab * 1.3) % 2 == 0 or da > 0) and da >= -4 + (ab - 4.5) * 0.4: put(x, y, C('ffffff'), 2)
            elif K == 'star':  # 발톱이 쥔 보석구 + 떠다니는 조각
                if r <= 3.8: put(x, y, mix(C('ffffff'), C('7fb8ff'), min(1, r / 3.8)), 8 if r < 2.3 else 6)
                cosang = da / r if r else 1
                if 4.4 <= r <= 5.8 and cosang < 0.5: put(x, y, C('e3b14a'), 4)
                if 5.8 < r <= 7.0 and 0.3 < cosang < 0.55: put(x, y, C('f5c86a'), 3)
                if 8.0 <= r <= 8.8 and int(math.degrees(math.atan2(sb, da)) + 360) // 20 % 2 == 0: put(x, y, C('a8d0ff'), 1)
            elif K == 'frost':  # 눈꽃 결정 + 아래로 매달린 고드름
                ang = math.degrees(math.atan2(sb, da)) % 60
                if r <= 2.4 or (r <= 6.5 and (ang < 7 or ang > 53)) or (3.0 < r < 4.8 and (abs(ang - 30) < 5)):
                    put(x, y, mix(C('ffffff'), C('7fe0ff'), min(1, r / 6.5)), 6 if r < 2.4 else 3)
                if -6 < da < -2 and 2.5 < ab < 4 and int(ab * 2) % 2 == 0 and da > -6 + (4 - ab) * 1.5: put(x, y, C('cfefff'), 2)
            elif K == 'moon':  # 초승달이 품은 빛 구슬 + 작은 별들
                outer = math.hypot(da, sb); inner = math.hypot(da - 2.2, sb + 1.6)
                if outer <= 6.4 and inner > 5.0:
                    c = mix(C('f4f0ff'), C('9a8ad8'), min(1, (outer - 3) / 3.4)); put(x, y, c, 5)
                if 6.4 < outer <= 7.2 and inner > 5.4: put(x, y, C('e3c46a'), 3)          # 금 테두리
                ob = math.hypot(da - 1.4, sb + 1.0)
                if ob <= 2.2: put(x, y, mix(C('ffffff'), C('a8c8ff'), ob / 2.2), 8)
                for (sx, sy) in ((5.5, -4.5), (7.5, 1.5), (2.0, -7.0)):
                    if abs(da - sx) + abs(sb - sy) <= 1.1: put(x, y, C('fff6c0'), 3)
            elif K == 'sun':   # 태양 원반 + 빛살
                ang = math.atan2(sb, da); ray = (math.cos(12 * ang) + 1) / 2; ray2 = (math.cos(6 * ang) + 1) / 2
                if r <= 3.6: put(x, y, mix(C('ffffff'), C('ffcc33'), r / 3.6), 8)
                elif r <= 4.6: put(x, y, C('e39a1a'), 6)
                elif r <= 4.6 + 4.2 * ray ** 3 * (0.6 + 0.4 * ray2): put(x, y, mix(C('ffd84a'), C('ff6a1a'), min(1, (r - 4.6) / 4.2)), 4 if r < 6.5 else 2)
            elif K == 'lich':  # 뿔 달린 해골 + 보라 불꽃
                if 2.8 < da < 5.2 and ab < 3.6 and int(sb * 1.4 + 9) % 2 == 0 and da < 5.2 - abs(sb) * 0.3: put(x, y, C('c9a33a'), 5)   # 왕관 가시
                if r <= 3.6:
                    c = C('e8e2cf'); d = 7
                    if -1.2 < da < 0.8 and 0.6 < ab < 2.2: c = C('b04cff'); d = 8
                    if da < -2.0 and ab < 1.6 and int(sb * 2) % 2 == 0: c = C('8a8270')
                    put(x, y, c, d)
                if da > 0.5 and 2.6 < ab < 6.5 and abs(da - (ab - 2.6) ** 1.5 * 0.45 - 0.5) < 0.9: put(x, y, C('3a2a3a'), 4)   # 뿔
                if 4.5 < da < 9 and ab < 3.0 - (da - 4.5) * 0.6 and rnd.random() < 0.75: put(x, y, C('c070ff') if rnd.random() < .5 else C('7a2ab0'), 2)  # 불꽃
    return cv

# ════════ 개성 있는 활 ════════
def bow3(kind, seed=0):
    rnd = random.Random(seed); cv = Canvas()
    cx, cy = 4.0, N - 4.0
    def put(x, y, c, d):
        if 0 <= x < NF and 0 <= y < NF and (cv.col[y][x] is None or cv.dep[y][x] <= d * SUB): cv.put(x, y, c, d)
    def cput(xc, yc, c, d):     # 굵은 좌표로 칠하기 (SUB x SUB)
        for a in range(SUB):
            for b in range(SUB): put(int(xc * SUB) + a, int(yc * SUB) + b, c, d)
    J = lambda c: c
    cfg = {
     't1': dict(R=33, w=1.6, wood='8b5a2b', lt='b98a55', grip='4e3015', tip='d8c08a'),
     't2': dict(R=32, w=2.4, wood='8f959c', lt='d8dde3', grip='3f67a8', tip='d8dde3', plates=True, shield=True),
     't3': dict(R=38, w=1.4, wood='eafcff', lt='ffffff', grip='2b3d52', tip='6fc8ff', curl=True, leaf=True),
     't4': dict(R=35, w=2.0, wood='2f8f8a', lt='74d6cb', grip='174a47', tip='3dffcf', mshape=True),
     't5': dict(R=35, w=2.0, wood='2b2339', lt='5a4977', grip='120e18', tip='c09bff', blades=True),
     't6': dict(R=36, w=2.0, wood='f0cf62', lt='fff3c0', grip='a87f22', tip='79b6ff', bigwings=True, star=True),
     'harpy': dict(R=36, w=2.2, wood='d9b04a', lt='fff0b0', grip='6b4a2a', tip='fff27a', feathers=True, bigfeath=True),
     'frost': dict(R=35, w=2.0, wood='8fd4e8', lt='e8fbff', grip='2e3a48', tip='ffffff', icicles=True, crystals=True),
     'dragon': dict(R=37, w=2.6, wood='b4271f', lt='ff8a6a', grip='2a1a10', tip='e3b14a', spikes=True, head=True),
    }[kind]
    R, w = cfg['R'], cfg['w']
    Wd, Lt, Gp, Tp = C(cfg['wood']), C(cfg['lt']), C(cfg['grip']), C(cfg['tip'])
    for y in range(NF):
        for x in range(NF):
            px, py = (x + .5) / SUB - cx, cy - (y + .5) / SUB
            d = math.hypot(px, py); ang = math.degrees(math.atan2(py, px))
            if not (-6 <= ang <= 96): continue
            e = abs(ang - 45) / 45                     # 0=가운데(손잡이), 1=끝
            if cfg.get('angular'):                     # 각진 리커브: 각도 구간마다 반지름이 꺾임
                seg = min(3, int(e * 4)); rr = R - [0, 0.6, 1.8, 0.4][seg]
            else:
                rr = R
            if cfg.get('curl') and e > 0.85: rr = R + (e - 0.85) * 22    # 엘프 장궁: 끝이 말림
            if cfg.get('mshape'): rr = R - 3.2 * math.sin(e * math.pi) + 1.2  # M자: 손잡이와 끝은 바깥, 가운데는 안쪽
            tw = w * (1 - 0.45 * e)                     # 끝으로 갈수록 가늘게
            inside = rr - tw <= d <= rr + 0.4 and 0 <= ang <= 90
            if inside:
                c = Lt if d > rr - 0.4 else (Wd if int(ang) % 14 else sh(Wd, 0.72))
                th = 3 if e < 0.5 else 2
                if e < 0.12: c = Gp; th = 4                                   # 손잡이
                if cfg.get('plates') and abs(e - 0.35) < 0.05: c = C('d8dde3'); th = 4
                if cfg.get('shards') and (int(ang / 9) % 2 == 0) and d > rr - tw * 0.5: c = C('c09bff')
                put(x, y, J(c), th)
            out = d - (rr + 0.4); inn = (rr - tw) - d
            if 0 <= ang <= 90:
                if cfg.get('feathers') and 0 < out <= 2.6 - e and int(ang / 6) % 2 == 0 and e > 0.2: put(x, y, C('fffbe0') if out > 1.2 else C('f2d06a'), 2)
                if cfg.get('wings') and e > 0.45 and 0 < out <= 1 + (e - 0.45) * 9 and int(out * 1.4 + ang / 8) % 2 == 0: put(x, y, C('ffffff'), 2)
                if cfg.get('spikes') and 0 < out <= 2.4 and int(ang) % 12 < 3 and e > 0.2: put(x, y, Tp, 2)
                if cfg.get('shards') and 0 < out <= 1.8 and int(ang) % 18 < 5 and e > 0.2: put(x, y, C('3d3352'), 3)
                if cfg.get('icicles') and 0 < inn <= 2.8 * (1 - e) + 0.6 and int(ang) % 10 < 3 and 0.15 < e < 0.9: put(x, y, C('e8fbff'), 2)
            if cfg.get('head') and e < 0.18 and 0 < out <= 3.2: put(x, y, C('e3b14a') if out > 2.2 else C('b4271f'), 4)   # 손잡이 위 용머리 장식
            if 0 <= ang <= 90:
                if cfg.get('blades') and 0.25 < e < 0.95 and 0 < out <= 4.2 * math.sin((e - 0.25) / 0.7 * math.pi):    # 낫 날
                    put(x, y, C('c09bff') if out > 3.2 * math.sin((e - 0.25) / 0.7 * math.pi) else C('3d3352'), 3)
                if cfg.get('bigwings') and e > 0.35 and 0 < out <= (e - 0.35) * 14 and (int(out * 1.2) % 2 == 0 or out < 1.2):
                    put(x, y, C('ffffff') if out > 2 else C('fff3c0'), 2)
                if cfg.get('bigfeath') and e > 0.3 and 0 < out <= 4.5 * (1 - abs(((ang % 12) - 6) / 6)) and int(ang / 12) % 2 == 0:
                    put(x, y, C('fffbe0') if out > 2 else C('e9c25a'), 2)
                if cfg.get('crystals') and 0 < out <= 3.6 and (int(ang) % 16) < 4 and e > 0.15:
                    put(x, y, mix(C('ffffff'), C('7fe0ff'), out / 3.6), 3)
                if cfg.get('leaf') and e > 0.88 and 0 < out <= 3.5 * (1 - abs(e - 0.94) * 12):
                    put(x, y, C('9fe8b0'), 2)
            if cfg.get('shield') and e < 0.2 and abs(d - rr) < 4.2 - e * 18:           # 손잡이 마름모 방패 판
                put(x, y, C('d8dde3') if abs(d - rr) > 1.2 else C('4f86d8'), 5)
            if cfg.get('star') and e < 0.12:
                aa = math.atan2(py - math.sin(math.radians(45)) * rr, px - math.cos(math.radians(45)) * rr)
                rd = math.hypot(px - math.cos(math.radians(45)) * rr, py - math.sin(math.radians(45)) * rr)
                if rd <= 2.0 + 1.8 * ((math.cos(5 * aa) + 1) / 2): put(x, y, C('79b6ff') if rd < 1.4 else C('fff3c0'), 6)
    p0, p1 = (cx + R - 1, cy), (cx, cy - R + 1)
    if cfg.get('curl'): p0, p1 = (cx + R - 2, cy - 1), (cx + 1, cy - R + 2)
    for i in range(480):
        t = i / 479; x, y = int((p0[0] + (p1[0] - p0[0]) * t) * SUB), int((p0[1] + (p1[1] - p0[1]) * t) * SUB)
        if 0 <= x < NF and 0 <= y < NF and cv.col[y][x] is None: cv.put(x, y, C('f4f4f4'), 0.5)
    for (fx, fy) in [(p0[0] - 1, p0[1] - 1), (p1[0] + 1, p1[1] + 1)]:
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if abs(dx) + abs(dy) <= 1: cput(fx + dx, fy + dy, Tp, 3)
    return cv

STAFF3 = {'moon_staff': 'moon', 'sun_staff': 'sun', 't1_staff': 't1', 't2_staff': 't2', 't3_staff': 't3', 't4_staff': 't4', 't5_staff': 't5', 't6_staff': 't6',
          'star_staff': 'star', 'frost_staff': 'frost', 'lich_staff': 'lich'}
BOW3 = {'t1_bow': 't1', 't2_bow': 't2', 't3_bow': 't3', 't4_bow': 't4', 't5_bow': 't5', 't6_bow': 't6',
        'harpy_bow': 'harpy', 'frost_bow': 'frost', 'dragon_bow': 'dragon'}


def finish(cv):
    """빛(왼쪽 위)에 따른 4단계 금속 음영 + 발광 표시"""
    lx, ly = 0, -1
    for y in range(NF):
        for x in range(NF):
            c = cv.col[y][x]
            if c is None: continue
            g = c in cv.glowcols
            cv.glow[y][x] = g
            if g: continue
            dl = 0
            while dl < 30:
                xx, yy = x + lx * (dl + 1), y + ly * (dl + 1)
                if not (0 <= xx < NF and 0 <= yy < NF) or cv.col[yy][xx] is None: break
                dl += 1
            ds = 0
            while ds < 30:
                xx, yy = x - lx * (ds + 1), y - ly * (ds + 1)
                if not (0 <= xx < NF and 0 <= yy < NF) or cv.col[yy][xx] is None: break
                ds += 1
            if dl == 0: f = 1.32            # 빛 받는 가장자리 하이라이트
            elif dl == 1: f = 1.12
            elif ds == 0: f = 0.74          # 그늘진 가장자리
            else: f = 1.0
            cv.col[y][x] = sh(c, f)
    return cv

# ── 모델(JSON) 만들기 ──
class Palette:
    def __init__(s): s.cols = []
    def idx(s, c):
        if c not in s.cols: s.cols.append(c)
        return s.cols.index(c)
    def uv(s, c):
        i = s.idx(c); px, py = i % 128, i // 128
        a = 16 / 128
        return [px * a + a * 0.25, py * a + a * 0.25, px * a + a * 0.75, py * a + a * 0.75]

def to_elements(cv, pal):
    els = []
    used = [[False] * NF for _ in range(NF)]
    G = cv.glow
    for y in range(NF):
        x = 0
        while x < NF:
            c, d, g = cv.col[y][x], cv.dep[y][x], G[y][x]
            if c is None or used[y][x]: x += 1; continue
            x2 = x
            while x2 + 1 < NF and cv.col[y][x2 + 1] == c and cv.dep[y][x2 + 1] == d and G[y][x2 + 1] == g and not used[y][x2 + 1]: x2 += 1
            y2 = y   # 아래로도 같은 줄이면 합치기
            while y2 + 1 < NF and all(cv.col[y2 + 1][k] == c and cv.dep[y2 + 1][k] == d and G[y2 + 1][k] == g and not used[y2 + 1][k] for k in range(x, x2 + 1)): y2 += 1
            for yy in range(y, y2 + 1):
                for xx in range(x, x2 + 1): used[yy][xx] = True
            # 그림 y는 아래로 증가, 모델 y는 위로 증가
            fx, tx = OFF + x * VOX, OFF + (x2 + 1) * VOX
            fy, ty = OFF + (NF - 1 - y2) * VOX, OFF + (NF - y) * VOX
            half = d * VOX / 2
            fz, tz = 8 - half, 8 + half
            side = sh(c, 0.72); top = sh(c, 0.9)
            u_f, u_s, u_t = pal.uv(c), pal.uv(side), pal.uv(top)
            els.append({"from": [round(fx, 3), round(fy, 3), round(fz, 3)], "to": [round(tx, 3), round(ty, 3), round(tz, 3)],
                        "faces": {"north": {"uv": u_f, "texture": "#0"}, "south": {"uv": u_f, "texture": "#0"},
                                  "east": {"uv": u_s, "texture": "#0"}, "west": {"uv": u_s, "texture": "#0"},
                                  "up": {"uv": u_t, "texture": "#0"}, "down": {"uv": u_s, "texture": "#0"}}})
            if g: els[-1]["light_emission"] = 15
            x = x2 + 1
    return els

def save_png(path, w, h, rows):
    raw = b''.join(b'\x00' + bytes(r) for r in rows)
    def ch(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                           + ch(b'IDAT', zlib.compress(raw, 9)) + ch(b'IEND', b''))

def build_all():
    out = {}
    for i, (k, spec) in enumerate(SWORDS.items()): out[k] = sword2(spec, i)
    for i, (k, spec) in enumerate(DAGGERS.items()): out[k] = sword2(spec, 30 + i)
    for i, (k, kd) in enumerate(STAFF3.items()): out[k] = staff3(kd, 50 + i)
    for i, (k, kd) in enumerate(BOW3.items()): out[k] = bow3(kd, 80 + i)
    return out

# ════════ 지팡이 v4: 참고 그림 스타일 (가는 꼬인 자루 + 옆으로 뻗는 화려한 머리 장식) ════════
def staff4(design, seed=0):
    rnd = random.Random(seed); cv = Canvas()
    ax = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)
    def P(sa, sb): return (A[0] + ax[0] * sa + ax[1] * sb, A[1] + ax[1] * sa - ax[0] * sb)
    def dot(sa, sb, c, d, r=0.55):
        x0, y0 = P(sa, sb); x0 *= SUB; y0 *= SUB; rr = r * SUB
        for yy in range(int(y0 - rr - 1), int(y0 + rr + 2)):
            for xx in range(int(x0 - rr - 1), int(x0 + rr + 2)):
                if 0 <= xx < NF and 0 <= yy < NF and math.hypot(xx + .5 - x0, yy + .5 - y0) <= rr:
                    if cv.col[yy][xx] is None or cv.dep[yy][xx] <= d * SUB: cv.put(xx, yy, c, d)
    def disc(sa, sb, r, c1, c2=None, d=6):
        steps = int(r * 3) + 2
        for i in range(-steps, steps + 1):
            for j in range(-steps, steps + 1):
                a, b = i * r / steps, j * r / steps
                rr = math.hypot(a, b)
                if rr <= r:
                    cc = mix(c1, c2, rr / r) if c2 else c1
                    if d >= 7: cv.glowcols.add(cc)
                    dot(sa + a, sb + b, cc, d, 0.45)
    def bez(p0, p1, p2, t):
        return ((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
    def stroke(p0, p1, p2, w0, w1, c_fn, d, n=140):
        for i in range(n + 1):
            t = i / n; sa, sb = bez(p0, p1, p2, t); w = w0 + (w1 - w0) * t
            dot(sa, sb, c_fn(t), d, max(0.35, w))
    def ring(sa, sb, r0, r1, c, d):
        for i in range(120):
            a = i / 120 * 2 * math.pi
            for k in range(3):
                rr = r0 + (r1 - r0) * k / 2
                dot(sa + math.cos(a) * rr, sb + math.sin(a) * rr, c, d, 0.6)
    D = design; pal = {k: C(v) for k, v in D['pal'].items()}
    top = D.get('top', 44.0)
    # ── 자루 (무기마다 굵기·휨·재질이 다름) ──
    W = D.get('w', 0.8); bend = D.get('bend', 0.0); style = D.get('shaft', 'spiral')
    def off(sa): return bend * math.sin(sa / max(top, 1) * math.pi)
    for i in range(int(top * 8)):
        sa = 3 + i * 0.125; o = off(sa)
        nk = max(3, int(W * 6))
        for k in range(nk):
            sb = -W + k * (2 * W / (nk - 1))
            c = pal['shaft']
            if style == 'spiral' and (sa * 0.9 + sb * 1.2) % 2.2 < 0.45: c = mix(pal['shaft'], pal['shaft2'], 0.55)
            elif style == 'gnarl' and (math.sin(sa * 1.7 + sb * 3) > 0.6): c = pal['shaft2']
            elif style == 'bone':
                seg = sa % 3.2
                if seg > 2.4: c = pal['shaft2']
                if seg < 1.0 and abs(sb) > W * 0.6: continue
            elif style == 'crystal' and int(sa * 2) % 7 == 0: c = pal['shaft2']
            elif style == 'twist' and (sa * 1.6 + sb * 2.5) % 2 < 1: c = pal['shaft2']
            elif style == 'plain' and abs(sb) < W * 0.3: c = mix(pal['shaft'], C('ffffff'), 0.15)
            dot(sa, sb + o, c, 3, 0.3)
        if style == 'gnarl' and int(sa * 3) % 23 == 0:        # 옹이·잔가지
            stroke((sa, o), (sa + 1.5, o + 2.5), (sa + 3, o + 3.5), 0.6, 0.3, lambda t: pal['shaft'], 3, 20)
        if style == 'crystal' and int(sa * 4) % 37 == 0 and sa > 8:   # 자루에 박힌 얼음 결정
            side = 1 if int(sa) % 2 else -1
            stroke((sa, o), (sa + 1, o + side * 2), (sa + 2.4, o + side * 3.2), 0.9, 0.3, lambda t: mix(C('ffffff'), pal['wing'], t), 4, 20)
    for m in D.get('rings', (12.0,)):                       # 자루 장식 마디
        for k in range(5): dot(m + k * 0.3, off(m), pal['gold'], 4, W + 0.6)
    if D.get('butt', True):
        dot(3.0, 0, pal['gold'], 4, W + 0.5); dot(1.6, 0, pal['gem'], 5, W + 0.2)      # 아래 끝 보석
    for k in range(6): dot(top - 1 + k * 0.3, off(top), pal['gold'], 4, W + 0.7)      # 머리 받침
    h = top + 2
    kind = D['kind']
    if kind == 'wing':       # 깃털 날개가 한쪽으로 부채처럼 펼쳐짐
        ring(h + 3, 0, 2.2, 3.0, pal['gold'], 5)
        disc(h + 3, 0, 1.8, C('ffffff'), pal['gem'], 7)
        for k in range(D.get('n', 6)):
            ang = -0.25 + k * 0.32
            base = (h + 4, -1.5)
            tip = (h + 6 + 15 * math.cos(ang) * 0.75, -2 - 15 * math.sin(ang + 0.6))
            ctl = (h + 9 + k, -6 - k * 0.6)
            stroke(base, ctl, tip, 1.5, 0.3, lambda t, k=k: mix(pal['wing'], pal['wing2'], t), 4 - (k % 2))
            dot(tip[0], tip[1], pal['tip'], 3, 0.6)
        stroke((h + 4, 1.5), (h + 10, 4.5), (h + 15, 2.0), 1.3, 0.3, lambda t: pal['wing2'], 3)   # 반대쪽 작은 깃
    elif kind == 'crescent':  # 큰 초승달 + 바깥 가시 + 양 끝 보석 + 아래 작은 초승달
        cx, cr = h + 9, 8.0
        for i in range(140):
            a = math.radians(-60 + i * 240 / 140)
            for k in range(4):
                rr = cr - k * 0.6 + (1.2 * math.sin((i / 140) * math.pi))
                dot(cx + math.cos(a) * rr * 0.9, -2 + math.sin(a) * rr, pal['wing'] if k else pal['gold'], 5, 0.6)
            if i % 9 == 0: stroke((cx + math.cos(a) * cr * 0.9, -2 + math.sin(a) * cr), (0, 0), (cx + math.cos(a) * (cr + 2.6) * 0.9, -2 + math.sin(a) * (cr + 2.6)), 0.8, 0.3, lambda t: pal['tip'], 3, 8)
        a1, a2 = math.radians(-60), math.radians(180)
        disc(cx + math.cos(a1) * cr * 0.9, -2 + math.sin(a1) * cr, 1.8, C('ffffff'), pal['gem'], 7)
        disc(cx + math.cos(a2) * cr * 0.9, -2 + math.sin(a2) * cr, 1.5, C('ffffff'), pal['gem'], 7)
        disc(h + 2.5, 0, 1.6, C('ffffff'), pal['gem'], 7)
        for i in range(60):
            a = math.radians(100 + i * 160 / 60)
            dot(h + 2.5 + math.cos(a) * 3.2, math.sin(a) * 3.2, pal['gold'], 5, 0.7)
    elif kind == 'arrow':     # 뾰족한 삼각 틀 + 가운데 보석 + 아래로 늘어진 술
        tipp = (h + 16, 0)
        for side in (-1, 1):
            stroke((h + 2, side * 7), (h + 9, side * 6), tipp, 1.1, 0.6, lambda t: pal['gold'], 5)
            stroke((h + 3, side * 5), (h + 9, side * 3.8), (h + 13.5, 0), 0.7, 0.4, lambda t: pal['wing'], 4)
        stroke((h + 2, -7), (h + 1, 0), (h + 2, 7), 1.0, 1.0, lambda t: pal['gold'], 5)
        disc(h + 8, 0, 2.3, C('ffffff'), pal['gem'], 8)
        ring(h + 5, 0, 3.2, 3.8, pal['wing'], 4)
        for k, sb in enumerate((-6, -3.5, 3.5, 6)):           # 술 장식
            for j in range(16): dot(h + 1.5 - j * 0.45, sb, pal['tip'], 2, 0.45)
            disc(h + 1.5 - 7.6, sb, 0.9, pal['gem2'], None, 4)
    elif kind == 'swirl':     # 소용돌이 칼날 + 보석 두 개
        disc(h + 4, 0, 2.2, C('ffffff'), pal['gem'], 8)
        ring(h + 4, 0, 2.6, 3.4, pal['gold'], 6)
        stroke((h + 5, 2), (h + 14, 9), (h + 19, -3), 1.6, 0.3, lambda t: mix(pal['wing'], pal['wing2'], t), 5)
        stroke((h + 3, -2), (h - 3, -9), (h + 6, -10), 1.4, 0.3, lambda t: mix(pal['wing'], pal['wing2'], t), 5)
        stroke((h + 7, -1), (h + 12, -6), (h + 11, -10), 1.0, 0.3, lambda t: pal['wing2'], 4)
        disc(h + 11, 3, 1.6, C('ffffff'), pal['gem2'], 7)
        ring(h + 11, 3, 1.9, 2.4, pal['gold'], 5)
    elif kind == 'moon':      # 달 + 매달린 별 장식
        cx = h + 7
        for i in range(160):
            a = i / 160 * 2 * math.pi
            for k in range(8):
                rr = 7.5 - k * 0.45
                x2, y2 = math.cos(a) * rr, math.sin(a) * rr
                if math.hypot(x2 - 2.6, y2 + 2.0) > 6.0:
                    dot(cx + x2, y2, mix(pal['wing'], pal['wing2'], k / 8), 5, 0.55)
        disc(cx + 1.5, -1.0, 2.0, C('ffffff'), pal['gem'], 8)
        for i in range(100):
            a = i / 100 * 2 * math.pi
            if math.hypot(math.cos(a) * 8.3 - 2.6, math.sin(a) * 8.3 + 2.0) > 6.5: dot(cx + math.cos(a) * 8.3, math.sin(a) * 8.3, pal['gold'], 4, 0.5)
        for sb, ln in ((-4.5, 9), (-1.5, 12), (2.0, 8)):     # 늘어진 별 줄
            for j in range(int(ln * 2)): dot(h + 1 - j * 0.5, sb, pal['tip'], 2, 0.4)
            e = h + 1 - ln
            for (da, db) in ((0, 0), (0.8, 0), (-0.8, 0), (0, 0.8), (0, -0.8)): dot(e + da, sb + db, pal['gem2'], 4, 0.55)
    elif kind == 'sun':       # 태양 원반 + 긴 빛살 + 아래 술
        cx = h + 8
        for i in range(24):
            a = i / 24 * 2 * math.pi; ln = 9.5 if i % 2 == 0 else 6.5
            stroke((cx + math.cos(a) * 3.5, math.sin(a) * 3.5), (cx + math.cos(a) * 6, math.sin(a) * 6), (cx + math.cos(a) * ln, math.sin(a) * ln),
                   1.1, 0.3, lambda t: mix(pal['wing'], pal['wing2'], t), 4 if i % 2 == 0 else 3, 20)
        disc(cx, 0, 4.0, C('ffffff'), pal['gem'], 8)
        ring(cx, 0, 4.2, 4.9, pal['gold'], 6)
        for sb in (-3, 0, 3):
            for j in range(12): dot(h + 1 - j * 0.45, sb, pal['tip'], 2, 0.4)
            disc(h - 4.6, sb, 0.8, pal['gem2'], None, 4)
    elif kind == 'skull':     # 진짜 해골 얼굴 + 뼈 날개 + 늘어진 사슬
        cx = h + 9
        bone, bone_d, hole = pal['wing'], sh(pal['wing'], 0.7), C('140a14')
        for k in range(4):        # 뒤쪽 뼈 날개
            for side in (-1, 1):
                stroke((cx - 1, side * 3.5), (cx + 3 + k, side * (7 + k)), (cx + k * 2.4, side * (10 + k * 0.7)), 0.8, 0.35, lambda t: bone_d, 3, 50)
        for i in range(int(18 * 4)):
            for j in range(int(16 * 4)):
                da_, sb_ = -9 + i * 0.25, -8 + j * 0.25
                a_ = da_; b_ = sb_
                cran = (a_ - 1.2) ** 2 / 4.6 ** 2 + b_ ** 2 / 4.2 ** 2 <= 1          # 두개골
                jaw = -5.6 <= a_ <= -2.0 and abs(b_) <= 2.7 - max(0, -3.6 - a_) * 0.6   # 위턱·아래턱
                cheek = -2.8 <= a_ <= -0.8 and 2.6 <= abs(b_) <= 4.2 - (a_ + 2.8) * 0.3  # 광대뼈
                if not (cran or jaw or cheek): continue
                c = bone; d = 7
                if cheek: c = sh(bone, 1.08)
                eye = ((a_ + 0.2) ** 2 / 1.5 ** 2 + (abs(b_) - 1.8) ** 2 / 1.25 ** 2) <= 1 and a_ < 0.9 - (abs(b_) - 1.8) * 0.5   # 비스듬한 눈구멍
                nose = -2.6 <= a_ <= -1.0 and abs(b_) <= (-1.0 - a_) * 0.45 + 0.15
                teeth_row = -3.6 <= a_ <= -2.6 and abs(b_) <= 2.3
                mouth_gap = -3.9 <= a_ <= -3.6 and abs(b_) <= 2.0
                if eye:
                    c = hole; d = 8
                    if math.hypot(a_ + 0.3, abs(b_) - 1.8) < 0.45: c = pal['gem']; d = 9      # 눈빛
                elif nose: c = hole; d = 8
                elif mouth_gap: c = hole; d = 6
                elif teeth_row: c = bone if int((b_ + 3) * 2.2) % 2 == 0 else sh(bone, 0.55); d = 7
                elif a_ < -3.9: c = sh(bone, 0.92); d = 6                                       # 아래턱
                if abs(b_ - 0.6 * (a_ - 3.5)) < 0.14 and 1.5 < a_ < 4.5 and b_ > 0: c = sh(bone, 0.6)   # 금 간 자국
                dot(cx + da_ * 1.4, sb_ * 1.4, c, d, 0.26)
        for k in range(5): stroke((cx + 6.6, -3.4 + k * 1.7), (cx + 9.0, -3.9 + k * 1.95), (cx + 11.0 + (k % 2) * 1.0, -4.4 + k * 2.2), 0.8, 0.25, lambda t: pal['gold'], 7, 30)   # 왕관
        for sb in (-5.5, 5.5):    # 늘어진 사슬
            for j in range(20): dot(cx - 3 - j * 0.5, sb, pal['tip'] if j % 3 else pal['gold'], 3, 0.42)
        for i in range(36):       # 보라 불꽃
            a2 = rnd.random() * math.pi - math.pi / 2; rr = 5 + rnd.random() * 3
            dot(cx + 3 + math.cos(a2) * rr, math.sin(a2) * rr * 0.55, pal['gem2'], 2, 0.45)
    elif kind == 'snow':      # 눈꽃 결정 + 얼음 소용돌이
        cx = h + 7
        for i in range(6):
            a = i / 6 * 2 * math.pi
            stroke((cx, 0), (cx + math.cos(a) * 4, math.sin(a) * 4), (cx + math.cos(a) * 8, math.sin(a) * 8), 1.1, 0.4, lambda t: mix(C('ffffff'), pal['wing'], t), 5, 30)
            for s2 in (-1, 1):
                b = a + s2 * 0.6
                stroke((cx + math.cos(a) * 4.5, math.sin(a) * 4.5), (0, 0), (cx + math.cos(a) * 4.5 + math.cos(b) * 2.5, math.sin(a) * 4.5 + math.sin(b) * 2.5), 0.6, 0.3, lambda t: pal['wing2'], 4, 8)
        disc(cx, 0, 2.2, C('ffffff'), pal['gem'], 8)
        stroke((h + 1, 2), (h + 6, 11), (h + 15, 9), 1.0, 0.3, lambda t: pal['wing2'], 3)
    elif kind == 'trident':   # 삼지창: 가운데 긴 날 + 양옆 휘어진 날
        stroke((h, 0), (h + 7, 0), (h + 15, 0), 1.6, 0.2, lambda t: mix(pal['wing'], pal['wing2'], t), 5)
        for side in (-1, 1):
            stroke((h + 1, side * 1.5), (h + 3, side * 7), (h + 11, side * 5.5), 1.2, 0.2, lambda t: mix(pal['wing'], pal['wing2'], t), 5)
            stroke((h + 0.5, side * 1.5), (h - 1, side * 4.5), (h + 1.5, side * 6.5), 0.8, 0.3, lambda t: pal['gold'], 4, 40)
        disc(h + 2, 0, 1.6, C('ffffff'), pal['gem'], 8)
        disc(h + 18, 0, 1.4, C('ffffff'), pal['gem'], 8)          # 위에 떠 있는 구슬
    elif kind == 'spear':     # 가시 창날: 긴 흑요석 날 + 비대칭 가시들
        for k in range(30):
            t = k / 29; sa = h + t * 16; w = 2.6 * (1 - t) ** 0.7 + 0.2
            for j in range(9):
                sb = -w + j * (2 * w / 8); dot(sa, sb, mix(pal['wing'], pal['wing2'], abs(sb) / max(w, .1)), 5, 0.4)
        for (a, side, ln) in ((h + 2, 1, 6), (h + 5, -1, 5), (h + 9, 1, 4), (h + 12, -1, 3)):
            stroke((a, side * 1.5), (a + 1.5, side * (ln * 0.6)), (a + 3.5, side * ln), 0.9, 0.2, lambda t: pal['wing2'], 4, 30)
        disc(h + 4, 0, 1.2, C('ffffff'), pal['gem'], 8)
    elif kind == 'horns':     # 참고 그림의 붉은 지팡이: 뿔 모양 금 날개 + 붉은 구슬
        for side in (-1, 1):
            stroke((h + 1, side * 1.5), (h + 3, side * 8), (h + 13, side * 6.5), 1.6, 0.3, lambda t: mix(pal['gold'], pal['wing'], t * 0.5), 5)
            stroke((h + 2, side * 2.5), (h + 4, side * 6), (h + 11, side * 5), 0.7, 0.2, lambda t: pal['wing2'], 6)
            stroke((h + 3, side * 3), (h + 1, side * 7.5), (h + 5, side * 9.5), 0.8, 0.3, lambda t: pal['gold'], 4, 50)
        stroke((h, 0), (h + 6, 0), (h + 11, 0), 1.8, 0.4, lambda t: pal['gold'], 5)
        for k in range(5): stroke((h - 0.5, -2 + k), (h - 2.5, -3 + k * 1.5), (h - 3.5, -4 + k * 2), 0.7, 0.3, lambda t: pal['wing2'], 4, 20)
        disc(h + 16, 0, 2.6, C('ffffff'), pal['gem'], 8)
        for i in range(30):
            a = rnd.random() * math.pi; rr = 3 + rnd.random() * 2.5
            dot(h + 16 + math.sin(a) * rr, math.cos(a) * rr * 0.4, pal['gem2'], 2, 0.4)
    elif kind == 'holy':      # 성스러운 십자 + 뒤의 후광 고리 + 빛살
        cx = h + 8
        ring(cx, 0, 6.6, 7.4, pal['gold'], 3)
        for i in range(16):
            a = i / 16 * 2 * math.pi
            if i % 2 == 0: stroke((cx + math.cos(a) * 7.6, math.sin(a) * 7.6), (0, 0), (cx + math.cos(a) * 9.6, math.sin(a) * 9.6), 0.6, 0.2, lambda t: pal['tip'], 2, 12)
        for (a0, b0, a1, b1) in ((-6, 0, 9, 0), (0, -5.5, 0, 5.5)):
            stroke((cx + a0, b0), (cx + (a0 + a1) / 2, (b0 + b1) / 2), (cx + a1, b1), 1.6, 1.6, lambda t: pal['wing'], 5, 60)
            stroke((cx + a0, b0), (cx + (a0 + a1) / 2, (b0 + b1) / 2), (cx + a1, b1), 0.7, 0.7, lambda t: pal['gold'], 6, 60)
        for (a1, b1) in ((9, 0), (-6, 0), (0, 5.5), (0, -5.5)): disc(cx + a1, b1, 1.1, C('ffffff'), pal['gem2'], 7)
        disc(cx, 0, 2.0, C('ffffff'), pal['gem'], 8)
    elif kind == 'scepter':   # 플랜지 셉터 + 위에 떠 있는 빛 구슬
        for k in range(4):
            sb0 = (-1) ** k * (1.5 + (k // 2) * 1.6)
            stroke((h, sb0 * 0.4), (h + 4, sb0 * 1.3), (h + 7.5, sb0 * 0.8), 1.0, 0.4, lambda t: mix(pal['wing'], pal['wing2'], t), 5)
        for j in range(10): dot(h + j * 0.6, 0, pal['gold'], 5, 1.4 - j * 0.06)
        disc(h + 10.5, 0, 2.2, C('ffffff'), pal['gem'], 8)
        ring(h + 10.5, 0, 2.6, 3.0, pal['gold'], 4)
        for side in (-1, 1): stroke((h + 6, side * 2), (h + 9, side * 5.5), (h + 13, side * 4.5), 0.8, 0.3, lambda t: pal['tip'], 3)
    elif kind == 'branch':    # 견습: 휘어진 나뭇가지 + 잎 + 작은 구슬
        stroke((h - 2, 0), (h + 4, -3), (h + 9, -1), 1.2, 0.7, lambda t: pal['shaft'], 4)
        stroke((h + 1, -1), (h + 5, 3), (h + 8, 4), 0.9, 0.5, lambda t: pal['shaft'], 4)
        disc(h + 7.5, -1.5, 1.6, C('ffffff'), pal['gem'], 7)
        for (a, b) in ((h + 9, 4.8), (h + 4, -4.5), (h + 10, -2.5)): disc(a, b, 1.2, pal['wing'], pal['wing2'], 3)
    return cv

STAFF4 = {
 't1_staff': dict(kind='branch', shaft='gnarl', w=1.1, bend=2.2, butt=False, pal=dict(shaft='6b4a2a', shaft2='4e3620', gold='6b4a2a', gem='c9e88a', wing='6fbf4a', wing2='3f8a2a', tip='6fbf4a'), rings=()),
 't2_staff': dict(kind='scepter', shaft='plain', w=1.3, top=30.0, rings=(10.0, 20.0), pal=dict(shaft='8f959c', shaft2='5a5f66', gold='c8cdd3', gem='4f86d8', wing='aeb4bc', wing2='6e737a', tip='d8dde3')),
 't3_staff': dict(kind='wing', n=6, shaft='plain', w=0.6, top=34.0, rings=(20.0,), pal=dict(shaft='f4f0ea', shaft2='d8c8b8', gold='d9ac52', gem='ff7a8a', wing='f6b8b0', wing2='ffffff', tip='d9ac52')),
 't4_staff': dict(kind='trident', shaft='twist', w=0.9, pal=dict(shaft='1d4a46', shaft2='0e2a28', gold='c9a85a', gem='3dffcf', gem2='3dffcf', wing='2f8f8a', wing2='9af0e0', tip='3dffcf')),
 't5_staff': dict(kind='spear', shaft='crystal', w=0.9, top=40.0, pal=dict(shaft='241c30', shaft2='5a3a9a', gold='8a5cff', gem='d0b0ff', gem2='b04cff', wing='3d3352', wing2='8a5cff', tip='b089ff'), rings=(12.0, 26.0)),
 't6_staff': dict(kind='holy', shaft='twist', w=0.9, top=44.0, pal=dict(shaft='f0cf62', shaft2='ffffff', gold='e3b14a', gem='79b6ff', gem2='bfe0ff', wing='fffbe8', wing2='f0cf62', tip='fff3c0'), rings=(10.0, 24.0)),
 'star_staff': dict(kind='crescent', shaft='twist', w=0.8, bend=-1.0, pal=dict(shaft='2a3a6a', shaft2='c9a85a', gold='e3b14a', gem='7fb8ff', wing='1f2a5a', wing2='c9a85a', tip='e3b14a'), rings=(12.0, 26.0)),
 'frost_staff': dict(kind='snow', shaft='crystal', w=1.0, bend=-1.2, pal=dict(shaft='9fc6dc', shaft2='5a7f96', gold='e8fbff', gem='7fe0ff', wing='bfefff', wing2='7fd0f0', tip='ffffff')),
 'lich_staff': dict(kind='skull', shaft='bone', w=1.3, pal=dict(shaft='8a8270', shaft2='3a2a3a', gold='c9a33a', gem='b04cff', gem2='c070ff', wing='e8e2cf', tip='5a4a5a'), rings=(10.0, 22.0)),
 'moon_staff': dict(kind='moon', shaft='spiral', w=0.7, bend=1.0, pal=dict(shaft='3a2f6a', shaft2='cfd4ea', gold='e3c46a', gem='a8c8ff', gem2='fff6c0', wing='f4f0ff', wing2='9a8ad8', tip='c9b8ff'), rings=(12.0, 26.0)),
 'sun_staff': dict(kind='horns', shaft='plain', w=1.0, top=40.0, pal=dict(shaft='8a2a1a', shaft2='e3b14a', gold='e3b14a', gem='ffcc33', gem2='ff4a2a', wing='ffd84a', wing2='ff6a1a', tip='c9a33a'), rings=(12.0, 26.0)),
}

_old_build_all = build_all
def build_all():
    out = _old_build_all()
    for i, (k, d) in enumerate(STAFF4.items()): out[k] = staff4(d, 200 + i)
    for k in out: finish(out[k])
    return out


# ════════ 활 장식 강화 (금 소용돌이 장식 + 감은 손잡이) ════════
_bow3_orig = bow3
def bow3(kind, seed=0):
    cv = _bow3_orig(kind, seed)
    gold = {'t1': None, 't2': 'c8cdd3', 't3': 'd9ac52', 't4': 'c9a85a', 't5': '8a5cff', 't6': 'e3b14a',
            'harpy': 'e3b14a', 'frost': 'e8fbff', 'dragon': 'e3b14a'}[kind]
    if not gold: return cv
    G = C(gold); cx, cy = 4.0, N - 4.0
    R = {'t1': 33, 't2': 32, 't3': 38, 't4': 35, 't5': 35, 't6': 36, 'harpy': 36, 'frost': 35, 'dragon': 37}[kind]
    for ang0 in (24, 66):                       # 팔 가운데 금 소용돌이
        for i in range(90):
            t = i / 89; a = math.radians(ang0 + (t - 0.5) * 10); rr = R + 0.8 + 1.8 * math.sin(t * math.pi * 2)
            x, y = (cx + math.cos(a) * rr) * SUB, (cy - math.sin(a) * rr) * SUB
            if 0 <= int(x) < NF and 0 <= int(y) < NF: cv.put(int(x), int(y), G, 3)
        a = math.radians(ang0); x, y = (cx + math.cos(a) * (R - 0.8)) * SUB, (cy - math.sin(a) * (R - 0.8)) * SUB
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if abs(dx) + abs(dy) <= 2 and 0 <= int(x) + dx < NF and 0 <= int(y) + dy < NF: cv.put(int(x) + dx, int(y) + dy, G, 4)
    return cv

# ════════ 고서(마법서) ════════
def tome(d, seed=0):
    """두꺼운 고서: 엠보싱 가죽 + 장식 테두리선 + 모서리 금속·보석 + 문양 원판·징 + 책장 단면(오른쪽·아래) + 버클 끈 2줄"""
    cv = Canvas(); pal = {k: C(v) for k, v in d['pal'].items()}
    cv.glowcols.add(pal['sigil'])
    ang = math.radians(0); ca, sa_ = math.cos(ang), math.sin(ang)
    cxp, cyp = N * 0.5, N * 0.48
    Wb, Hb = 15.0, 19.0
    strap = pal.get('strap', sh(pal['cover'], 0.45))
    for y in range(NF):
        for x in range(NF):
            px, py = (x + .5) / SUB - cxp, (y + .5) / SUB - cyp
            u = px * ca - py * sa_; v = px * sa_ + py * ca
            au, av = abs(u), abs(v)
            if au > Wb + 2.2 or av > Hb + 2.0: continue
            if (u > Wb and av <= Hb - 0.6) or (v > Hb and -Wb + 3 < u <= Wb - 0.6):     # 책장 단면
                k = (u - Wb) if u > Wb else (v - Hb)
                c = pal['page'] if int(k * 4) % 2 == 0 else sh(pal['page'], 0.8)
                if u > Wb and any(abs(v - sv) < 1.2 for sv in (-8, 8)): c = strap            # 끈이 책장을 감쌈
                cv.put(x, y, c, 5); continue
            if au > Wb or av > Hb: continue
            c = pal['cover']; dep = 6
            # 가죽 엠보싱 (마름모 격자)
            edge = min(Wb - au, Hb - av)
            if edge < 1.4: c = pal['metal']; dep = 7                                    # 금속 테두리
            elif edge < 2.0: c = sh(pal['cover'], 0.7)
            elif 3.0 < edge < 3.5: c = pal['metal']; dep = 7                            # 안쪽 장식선
            cu, cvv = Wb - au, Hb - av
            if cu < 5 and cvv < 5 and cu + cvv < 7: c = pal['metal']; dep = 7          # 모서리 금속
            if cu < 5 and cvv < 5 and math.hypot(cu - 2.4, cvv - 2.4) < 1.1: c = pal['sigil']; dep = 8   # 모서리 보석
            if u < -Wb + 3.4:                                                          # 책등 + 띠
                c = sh(pal['cover'], 0.58); dep = 7
                if abs(((v + Hb) % 4.6) - 2.3) < 0.6: c = pal['metal']; dep = 8
            for sv in (-8, 8):                                                         # 버클 끈
                if abs(v - sv) < 1.2 and u > Wb - 6.5:
                    c = strap; dep = 8
                    if Wb - 4.6 < u < Wb - 2.4: c = pal['metal']; dep = 9            # 버클
                    if Wb - 4.0 < u < Wb - 3.0 and abs(v - sv) < 0.5: c = sh(pal['metal'], 0.5)
            r = math.hypot(u - 1.0, v)
            if 5.6 < r < 6.6: c = pal['metal']; dep = 8                                # 문양 원판 테
            elif r <= 5.6 and dep < 7: c = sh(pal['cover'], 0.7)
            for (su, sv2) in ((7.3, 0), (-5.3, 0), (1, 7.3), (1, -7.3)):              # 징 4개
                if math.hypot(u - su, v - sv2) < 0.8: c = pal['metal']; dep = 8
            sg = d['sigil'](u - 1.0, v, r * 1.25)
            if sg == 2: c = pal['sigil']; dep = 9
            elif sg == 1: c = pal['metal']; dep = 8
            cv.put(x, y, c, dep)
    return cv

def sig_flame(u, v, r):
    if r < 2.0: return 2
    if 3.6 < r < 4.4: return 1
    ang = math.atan2(v, u)
    return 2 if (r < 7.5 - 2.5 * abs(math.sin(ang * 3)) and v < 0 and r > 2) else 0
def sig_snow(u, v, r):
    a = math.degrees(math.atan2(v, u)) % 60
    if r < 1.8: return 2
    if r < 7.5 and (a < 6 or a > 54): return 2
    if 4 < r < 5.5 and abs(a - 30) < 6: return 1
    return 0
def sig_bolt(u, v, r):
    if 6.5 < r < 7.3: return 1
    x = u + v * 0.35
    if -7 < v < 7 and abs(x - (1.5 if v < 0 else -1.5)) < 1.1: return 2
    if abs(v) < 0.9 and abs(u) < 2.6: return 2
    return 0
def sig_leaf(u, v, r):
    if abs(u) < 0.5 and -7 < v < 7: return 1
    for k in (-4, -1, 2, 5):
        if math.hypot(u - 2.2, v - k) < 1.6 or math.hypot(u + 2.2, v - k - 1) < 1.6: return 2
    return 0
def sig_eye(u, v, r):
    if ((u / 6.5) ** 2 + (v / 3.6) ** 2) <= 1 and ((u / 6.5) ** 2 + (v / 3.6) ** 2) > 0.62: return 1
    if r < 2.4: return 2
    if 7.5 < r < 8.2: return 1
    return 0

TOMES = {
 'tome_fire': dict(sigil=sig_flame, pal=dict(cover='8a1e14', metal='d9ac52', sigil='ff8a2a', page='f0e2c0')),
 'tome_frost': dict(sigil=sig_snow, pal=dict(cover='1e4a7a', metal='dfe9f2', sigil='8fe8ff', page='eef4f8')),
 'tome_thunder': dict(sigil=sig_bolt, pal=dict(cover='3a2a5a', metal='c9a85a', sigil='fff27a', page='e8e0cc')),
 'tome_life': dict(sigil=sig_leaf, pal=dict(cover='2e5a2a', metal='b8a06a', sigil='9dff7a', page='f2ead0')),
 'tome_void': dict(sigil=lambda u, v, r: 0, cursed=True, pal=dict(cover='120a12', metal='3a2a30', sigil='ff2a4a', page='4a3a3a', strap='2a1a1a')),
}

_old_build_all2 = build_all
def build_all():
    out = _old_build_all2()
    for i, (k, d) in enumerate(TOMES.items()):
        out[k] = tome(d, 400 + i); finish(out[k])
    return out


# ════════ 저주받은 공허의 금서 ════════
_tome_base = tome
def tome(d, seed=0):
    cv = _tome_base(d, seed)
    if not d.get('cursed'): return cv
    rnd = random.Random(seed)
    blood, vein, eye_r, bone, chain = C('8a0a14'), C('ff2a4a'), C('ff1a2a'), C('e8e0c8'), C('4a4048')
    cv.glowcols.update({vein, eye_r, sh(vein, 0.8)})
    ang = math.radians(0); ca, sa_ = math.cos(ang), math.sin(ang)
    cxp, cyp = N * 0.5, N * 0.48
    Wb, Hb = 15.0, 19.0
    def at(u, v):      # 책 좌표 → 세밀 칸
        px = u * ca + v * sa_; py = -u * sa_ + v * ca
        return int((px + cxp) * SUB), int((py + cyp) * SUB)
    def put(u, v, c, dep):
        x, y = at(u, v)
        if 0 <= x < NF and 0 <= y < NF and (cv.col[y][x] is None or cv.dep[y][x] <= dep * SUB): cv.put(x, y, c, dep)
    step = 0.5 / SUB
    # 핏줄 균열: 가운데서 바깥으로 갈라짐
    for k in range(9):
        a0 = k / 9 * 2 * math.pi + rnd.random() * 0.4; uu, vv = 1 + math.cos(a0) * 6.5, math.sin(a0) * 6.5; a = a0
        for i in range(70):
            a += (rnd.random() - 0.5) * 0.5; uu += math.cos(a) * 0.25; vv += math.sin(a) * 0.25
            if abs(uu) > Wb - 2 or abs(vv) > Hb - 2: break
            put(uu, vv, vein if i < 40 else sh(vein, 0.8), 8)
    # 쇠사슬 X자
    for (u0, v0, u1, v1) in ((-Wb + 3, -Hb + 1, Wb - 1, Hb - 1), (-Wb + 3, Hb - 1, Wb - 1, -Hb + 1)):
        n = int(math.hypot(u1 - u0, v1 - v0) / step)
        for i in range(n):
            t = i / n; uu, vv = u0 + (u1 - u0) * t, v0 + (v1 - v0) * t
            if math.hypot(uu - 1, vv) < 7.0: continue
            link = int(t * 26) % 2
            for w in (-0.7, 0, 0.7):
                if link == 0 or abs(w) > 0.5: put(uu + w * 0.3, vv - w * 0.3, chain if link else sh(chain, 1.3), 9)
    # 붉은 세로 동공 눈 (원판 위)
    for i in range(-30, 31):
        for j in range(-20, 21):
            uu, vv = i * 0.2, j * 0.2
            e = (uu / 5.2) ** 2 + (vv / 3.4) ** 2
            if e > 1: continue
            c = C('f2e6d8')
            r = math.hypot(uu, vv)
            if r < 2.6: c = mix(eye_r, blood, r / 2.6)
            if abs(uu) < 0.45 and abs(vv) < 2.3: c = C('0a0408')               # 세로 동공
            if e > 0.82: c = blood
            put(1 + uu, vv, c, 10)
    # 책장 쪽 이빨
    for k in range(10):
        vv = -Hb + 3 + k * (2 * Hb - 6) / 9
        for i in range(int(3.0 / step)):
            t = i * step; w = 0.9 * (1 - t / 3.0)
            for ww in (-w, 0, w): put(Wb + 0.4 + t, vv + ww, bone, 6)
    # 아래로 흘러내리는 붉은 액체
    for k in range(6):
        uu = -Wb + 5 + k * 4.4 + rnd.random(); ln = 2 + rnd.random() * 4
        for i in range(int(ln / step)):
            t = i * step; put(uu, Hb + 0.3 + t, blood if t < ln - 0.6 else vein, 6)
        put(uu, Hb + 0.3 + ln, vein, 6)
    return cv


if __name__ == '__main__':
    root = sys.argv[1]            # .../assets/starserver
    prev = sys.argv[2] if len(sys.argv) > 2 else None
    cvs = build_all()
    total = 0
    for k, cv in cvs.items():
        pal = Palette()
        els = to_elements(cv, pal)
        total += len(els)
        rows = []
        for py in range(128):
            r = bytearray()
            for px in range(128):
                i = py * 128 + px
                r += bytes(pal.cols[i] + (255,)) if i < len(pal.cols) else b'\x00\x00\x00\x00'
            rows.append(r)
        save_png(os.path.join(root, 'textures/item/forge/vox', k + '.png'), 128, 128, rows)
        xs = [v for e in els for v in (e["from"][0], e["to"][0])]; ys = [v for e in els for v in (e["from"][1], e["to"][1])]
        cxm, cym = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        ext = max(max(xs) - min(xs), max(ys) - min(ys))
        gs = round(min(1.0, 15.0 / ext), 3)
        gt = [round(-(cxm - 8) * gs, 2), round(-(cym - 8) * gs, 2), 0]
        model = {"credit": "별빛서버 입체 무기 (voxel_weapons.py)", "parent": "minecraft:item/handheld", "gui_light": "side",
                 "textures": {"0": "starserver:item/forge/vox/" + k, "particle": "starserver:item/forge/vox/" + k},
                 "elements": els,
                 "display": {
                     "gui": {"rotation": [0, 0, 0], "translation": gt, "scale": [gs, gs, gs]},
                     "ground": {"rotation": [0, 0, 0], "translation": [gt[0] * 0.6, 2 + gt[1] * 0.6, 0], "scale": [gs * 0.6, gs * 0.6, gs * 0.6]},
                     "fixed": {"rotation": [0, 180, 0], "translation": [-gt[0], gt[1], 0], "scale": [gs, gs, gs]}}}
        if k.endswith('_bow'):
            model["parent"] = "minecraft:item/bow"
        os.makedirs(os.path.join(root, 'models/item/forge'), exist_ok=True)
        json.dump(model, open(os.path.join(root, 'models/item/forge', k + '.json'), 'w'), separators=(',', ':'))
        os.makedirs(os.path.join(root, 'items/forge'), exist_ok=True)
        json.dump({"model": {"type": "minecraft:model", "model": "starserver:item/forge/" + k}},
                  open(os.path.join(root, 'items/forge', k + '.json'), 'w'))
        if prev:   # 미리보기: 앞모습(색) 저장
            rows = []
            for y in range(NF):
                r = bytearray()
                for x in range(NF):
                    c = cv.col[y][x]; r += bytes(c + (255,)) if c else b'\x00\x00\x00\x00'
                rows.append(r)
            save_png(os.path.join(prev, k + '.png'), NF, NF, rows)
        print(k, len(els), 'elements,', len(pal.cols), 'colors')
    print('total elements', total)
