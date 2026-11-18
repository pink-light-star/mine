"""별빛서버 보라 테마 UI (참고: 어두운 보라 바탕 + 은빛 라벤더 테두리 + 마름모·별 장식)
리소스팩 그림을 만든다.
  · starserver/textures/font/gui_*.png  : 서버 메뉴 배경 (글꼴 트릭, 크기는 기존과 같음)
  · minecraft/textures/gui/container/generic_54.png, inventory.png : 바닐라 상자·인벤토리
  · minecraft/textures/gui/sprites/hud/hotbar*.png, experience_bar_*.png : 단축바·경험치 바
  · minecraft/textures/gui/sprites/tooltip/*.png : 아이템 설명창
  · minecraft/textures/gui/sprites/widget/button*.png : 버튼
  · minecraft/textures/gui/sprites/boss_bar/*.png : 보스바
쓰는 법: python3 make_ui_theme.py <pack-extra/assets>"""
import struct, zlib, os, sys, json, random

ASSETS = sys.argv[1]

def hexc(s, a=255):
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)

# ── 색 ──
BG_T, BG_B = hexc('231b3a'), hexc('120e1f')
LINE = hexc('c9baf0')       # 은빛 라벤더 테두리
LINE_D = hexc('6e5caa')     # 어두운 테두리
LINE_DD = hexc('2c2348')
GLOW = hexc('efe6ff')       # 빛나는 점
SLOT_BG, SLOT_SH, SLOT_HI = hexc('0e0b18'), hexc('07050d'), hexc('5a4b96')
PLATE, PLATE_D = hexc('d8ccf6'), hexc('8c78cc')   # 바닐라 진회색 글씨 받침
CLEAR = (0, 0, 0, 0)


class Img:
    def __init__(s, w, h, fill=CLEAR):
        s.w, s.h = w, h
        s.px = bytearray(bytes(fill) * (w * h))

    def put(s, x, y, c):
        if 0 <= x < s.w and 0 <= y < s.h:
            i = (y * s.w + x) * 4
            if c[3] == 255 or c[3] == 0:
                s.px[i:i + 4] = bytes(c)
            else:   # 반투명 섞기
                a = c[3] / 255
                for k in range(3):
                    s.px[i + k] = int(s.px[i + k] * (1 - a) + c[k] * a)
                s.px[i + 3] = max(s.px[i + 3], c[3])

    def rect(s, x0, y0, x1, y1, c):
        for y in range(y0, y1):
            for x in range(x0, x1):
                s.put(x, y, c)

    def grad(s, x0, y0, x1, y1, ct, cb):
        for y in range(y0, y1):
            k = (y - y0) / max(1, y1 - y0 - 1)
            c = tuple(int(ct[i] + (cb[i] - ct[i]) * k) for i in range(3)) + (255,)
            s.rect(x0, y, x1, y + 1, c)

    def box(s, x0, y0, x1, y1, c):          # 1픽셀 테두리
        s.rect(x0, y0, x1, y0 + 1, c); s.rect(x0, y1 - 1, x1, y1, c)
        s.rect(x0, y0, x0 + 1, y1, c); s.rect(x1 - 1, y0, x1, y1, c)

    def diamond(s, cx, cy, r, c, core=None):
        for d in range(-r, r + 1):
            for e in range(-(r - abs(d)), r - abs(d) + 1):
                s.put(cx + d, cy + e, c)
        if core:
            s.put(cx, cy, core)

    def sparkle(s, cx, cy, r, c):            # 4갈래 별빛
        for k in range(1, r + 1):
            a = max(60, 255 - k * 70)
            for dx, dy in ((k, 0), (-k, 0), (0, k), (0, -k)):
                s.put(cx + dx, cy + dy, c[:3] + (a,))
        s.put(cx, cy, c)

    def save(s, path, mcmeta=None):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        raw = b''.join(b'\x00' + bytes(s.px[y * s.w * 4:(y + 1) * s.w * 4]) for y in range(s.h))
        def ch(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
        open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', s.w, s.h, 8, 6, 0, 0, 0))
                               + ch(b'IDAT', zlib.compress(raw, 9)) + ch(b'IEND', b''))
        if mcmeta:
            json.dump(mcmeta, open(path + '.mcmeta', 'w'))


def panel(im, x0, y0, x1, y1, line=LINE, top=BG_T, bot=BG_B, stars=True, ornament=True, seed=1):
    """장식 테두리 판: 그라데이션 바탕 + 겹테두리 + 모서리 마름모 + (위 가운데 장식)"""
    im.grad(x0, y0, x1, y1, top, bot)
    if stars:   # 은은한 별가루
        rnd = random.Random(seed)
        for _ in range((x1 - x0) * (y1 - y0) // 110):
            x, y = rnd.randrange(x0 + 3, x1 - 3), rnd.randrange(y0 + 3, y1 - 3)
            im.put(x, y, hexc('3d3266'))
        for _ in range((x1 - x0) * (y1 - y0) // 1800):
            im.put(rnd.randrange(x0 + 4, x1 - 4), rnd.randrange(y0 + 4, y1 - 4), hexc('8f7fd0', 160))
    im.box(x0, y0, x1, y1, LINE_DD)                # 바깥 그림자선
    im.box(x0 + 1, y0 + 1, x1 - 1, y1 - 1, line)   # 은빛 테두리
    im.box(x0 + 3, y0 + 3, x1 - 3, y1 - 3, line[:3] + (70,))   # 안쪽 가는 선
    for (cx, cy) in ((x0, y0), (x1 - 1, y0), (x0, y1 - 1), (x1 - 1, y1 - 1)):
        im.put(cx, cy, CLEAR)
    for (cx, cy) in ((x0 + 3, y0 + 3), (x1 - 4, y0 + 3), (x0 + 3, y1 - 4), (x1 - 4, y1 - 4)):
        im.diamond(cx, cy, 2, line, GLOW)
    if ornament and x1 - x0 > 60:
        cx = (x0 + x1) // 2
        im.rect(cx - 14, y0 + 1, cx + 15, y0 + 2, GLOW[:3] + (200,))
        im.diamond(cx, y0 + 1, 3, line, GLOW)
        im.sparkle(cx, y0 + 1, 4, GLOW)


def slot(im, x, y, line=SLOT_HI):
    im.rect(x, y, x + 18, y + 18, SLOT_BG)
    im.rect(x, y, x + 18, y + 1, SLOT_SH); im.rect(x, y, x + 1, y + 18, SLOT_SH)
    im.rect(x, y + 17, x + 18, y + 18, line); im.rect(x + 17, y, x + 18, y + 18, line)
    im.put(x + 1, y + 1, hexc('1a1530'))


def plate(im, x0, y0, x1, y1):
    """바닐라 진회색 글씨가 보이도록 연보라 받침"""
    im.rect(x0, y0, x1, y1, PLATE)
    im.rect(x0, y1 - 1, x1, y1, PLATE_D)
    im.rect(x1 - 1, y0, x1, y1, PLATE_D)
    im.diamond(x1 + 2, (y0 + y1) // 2, 2, LINE, GLOW)


# ───────────────────────── 서버 메뉴 배경 (글꼴 트릭) ─────────────────────────
VARIANTS = {   # 이름: (줄 수, 테두리 색, 위 바탕, 아래 바탕)
    'gui_6': (6, LINE, BG_T, BG_B), 'gui_5': (5, LINE, BG_T, BG_B), 'gui_3': (3, LINE, BG_T, BG_B),
    'gui_6_red': (6, hexc('f0a8b4'), hexc('3a1726'), hexc('170811')),      # 던전
    'gui_3_red': (3, hexc('f0a8b4'), hexc('3a1726'), hexc('170811')),
    'gui_6_gold': (6, hexc('f0d79a'), hexc('2e2236'), hexc('130d17')),     # 대장간
    'gui_3_gold': (3, hexc('f0d79a'), hexc('2e2236'), hexc('130d17')),
    'gui_5_green': (5, hexc('b6ecd0'), hexc('1b2b38'), hexc('0a121a')),    # 능력치
    'gui_4_shop': (4, hexc('f3dd9c'), hexc('1d2440'), hexc('0b0e1d')),     # 상점
    'gui_6_shop': (6, hexc('f3dd9c'), hexc('1d2440'), hexc('0b0e1d')),
}

def font_gui(name, rows, line, top, bot):
    W, H = 176, 114 + rows * 18
    im = Img(W, H)
    panel(im, 0, 0, W, H, line, top, bot, seed=rows * 13 + len(name))
    im.rect(4, 15, W - 4, 16, line[:3] + (150,))           # 머리 띠 아래 선
    for r in range(rows):
        for c in range(9):
            slot(im, 7 + c * 18, 17 + r * 18)
    sep = 17 + rows * 18 + 1
    im.rect(6, sep, W - 6, sep + 1, line[:3] + (110,))
    im.diamond(W // 2, sep, 2, line, GLOW)
    plate(im, 5, rows * 18 + 18, 64, rows * 18 + 29)        # '인벤토리' 글씨 받침
    for r in range(3):
        for c in range(9):
            slot(im, 7 + c * 18, rows * 18 + 30 + r * 18)
    for c in range(9):
        slot(im, 7 + c * 18, rows * 18 + 88)
    im.save(os.path.join(ASSETS, 'starserver', 'textures', 'font', name + '.png'))


# ───────────────────────── 바닐라 상자 (generic_54) ─────────────────────────
def generic_54():
    im = Img(256, 256)
    W = 176
    # 위쪽(칸 6줄): 0..125, 아래쪽(내 인벤토리): 126..222 — 바닐라는 줄 수에 맞춰 위·아래를 잘라 붙인다
    panel(im, 0, 0, W, 126, seed=54)
    plate(im, 5, 4, 90, 15)                                  # 상자 이름 받침
    for r in range(6):
        for c in range(9):
            slot(im, 7 + c * 18, 17 + r * 18)
    panel(im, 0, 126, W, 222, ornament=False, seed=55)
    im.rect(0, 126, W, 129, BG_T)                            # 위·아래가 이어 붙도록 윗변 테두리 지우기
    im.rect(1, 126, 2, 129, LINE); im.rect(W - 2, 126, W - 1, 129, LINE)
    im.rect(0, 126, 1, 129, LINE_DD); im.rect(W - 1, 126, W, 129, LINE_DD)
    plate(im, 5, 127, 64, 138)                               # '인벤토리' 받침
    for r in range(3):
        for c in range(9):
            slot(im, 7 + c * 18, 139 + r * 18)
    for c in range(9):
        slot(im, 7 + c * 18, 197)
    im.save(os.path.join(ASSETS, 'minecraft', 'textures', 'gui', 'container', 'generic_54.png'))


# ───────────────────────── 바닐라 내 인벤토리 ─────────────────────────
def inventory():
    im = Img(256, 256)
    W, H = 176, 166
    panel(im, 0, 0, W, H, seed=77)
    for i in range(4):
        slot(im, 7, 7 + i * 18)                              # 갑옷
    slot(im, 76, 61)                                         # 왼손
    im.rect(25, 7, 76, 79, hexc('07050d'))                   # 캐릭터 창
    im.box(25, 7, 76, 79, LINE_D)
    im.diamond(50, 7, 2, LINE, GLOW)
    plate(im, 95, 5, 150, 15)                                # '제작' 받침
    for r in range(2):
        for c in range(2):
            slot(im, 97 + c * 18, 17 + r * 18)
    im.rect(137, 34, 147, 36, LINE_D); im.rect(145, 32, 147, 38, LINE_D)   # 화살표
    slot(im, 153, 27)                                        # 결과 칸
    im.box(152, 26, 172, 46, LINE)
    for r in range(3):
        for c in range(9):
            slot(im, 7 + c * 18, 83 + r * 18)
    for c in range(9):
        slot(im, 7 + c * 18, 141)
    im.rect(6, 139, W - 6, 140, LINE[:3] + (90,))
    im.save(os.path.join(ASSETS, 'minecraft', 'textures', 'gui', 'container', 'inventory.png'))


# ───────────────────────── 단축바·경험치 바 ─────────────────────────
def hud():
    base = os.path.join(ASSETS, 'minecraft', 'textures', 'gui', 'sprites', 'hud')
    im = Img(182, 22)
    im.grad(0, 0, 182, 22, hexc('241c3c', 230), hexc('120e1f', 230))
    im.box(0, 0, 182, 22, LINE)
    for i in range(9):
        x = 1 + i * 20
        im.box(x + 1, 1 + 1, x + 19, 21 - 1 + 0, LINE_D)
        im.rect(x + 2, 3, x + 18, 19, hexc('0e0b18', 200))
        if i:
            im.diamond(x, 11, 1, LINE, GLOW)
    for (cx, cy) in ((0, 0), (181, 0), (0, 21), (181, 21)):
        im.put(cx, cy, CLEAR)
    im.save(os.path.join(base, 'hotbar.png'))
    sel = Img(24, 23)
    sel.box(0, 0, 24, 23, GLOW)
    sel.box(1, 1, 23, 22, LINE)
    sel.box(2, 2, 22, 21, hexc('a58cf0', 140))
    for (cx, cy) in ((0, 0), (23, 0), (0, 22), (23, 22)):
        sel.diamond(cx, cy, 1, GLOW)
    sel.sparkle(12, 0, 3, GLOW)
    sel.save(os.path.join(base, 'hotbar_selection.png'))
    bg = Img(182, 5)
    bg.rect(0, 0, 182, 5, hexc('120e1f'))
    bg.box(0, 0, 182, 5, LINE_D)
    bg.save(os.path.join(base, 'experience_bar_background.png'))
    pr = Img(182, 5)
    for x in range(182):
        k = x / 181
        c = (int(110 + 70 * k), int(80 + 40 * k), int(220 + 30 * k), 255)
        pr.rect(x, 1, x + 1, 4, c)
        pr.put(x, 1, (min(255, c[0] + 60), min(255, c[1] + 60), 255, 255))
    pr.box(0, 0, 182, 5, LINE)
    pr.save(os.path.join(base, 'experience_bar_progress.png'))


# ───────────────────────── 설명창(툴팁) ─────────────────────────
def tooltip():
    base = os.path.join(ASSETS, 'minecraft', 'textures', 'gui', 'sprites', 'tooltip')
    nine = lambda w, h, b: {"gui": {"scaling": {"type": "nine_slice", "width": w, "height": h, "border": b}}}
    bg = Img(100, 100)
    bg.grad(0, 0, 100, 100, hexc('231b3a', 245), hexc('120e1f', 245))
    bg.save(os.path.join(base, 'background.png'), nine(100, 100, 9))
    fr = Img(100, 100)
    fr.box(0, 0, 100, 100, LINE_DD)
    fr.box(1, 1, 99, 99, LINE)
    fr.box(3, 3, 97, 97, LINE[:3] + (60,))
    for (cx, cy) in ((3, 3), (96, 3), (3, 96), (96, 96)):
        fr.diamond(cx, cy, 2, LINE, GLOW)
    fr.save(os.path.join(base, 'frame.png'), nine(100, 100, 9))


# ───────────────────────── 버튼 ─────────────────────────
def buttons():
    base = os.path.join(ASSETS, 'minecraft', 'textures', 'gui', 'sprites', 'widget')
    meta = {"gui": {"scaling": {"type": "nine_slice", "width": 200, "height": 20, "border": 3}}}
    for name, top, bot, line in (('button', '2b2248', '17122a', LINE_D), ('button_highlighted', '5b45a8', '3a2b78', GLOW),
                                 ('button_disabled', '1a1626', '120f1b', LINE_DD)):
        im = Img(200, 20)
        im.grad(0, 0, 200, 20, hexc(top), hexc(bot))
        im.box(0, 0, 200, 20, line)
        im.rect(1, 1, 199, 2, line[:3] + (90,))
        for (cx, cy) in ((0, 0), (199, 0), (0, 19), (199, 19)):
            im.put(cx, cy, CLEAR)
        im.save(os.path.join(base, name + '.png'), meta)


# ───────────────────────── 보스바 ─────────────────────────
def bossbars():
    base = os.path.join(ASSETS, 'minecraft', 'textures', 'gui', 'sprites', 'boss_bar')
    cols = {'purple': ('b089ff', '6b48d8'), 'red': ('ff8a9a', 'c43a52'), 'blue': ('9ec4ff', '4a6fd8'),
            'pink': ('ffaee0', 'd65aa8'), 'green': ('a8f0b8', '3fae6a'), 'yellow': ('ffe39a', 'd8a63a'),
            'white': ('ffffff', 'b8b0d8')}
    for name, (hi, lo) in cols.items():
        bg = Img(182, 5)
        bg.rect(0, 0, 182, 5, hexc('120e1f'))
        bg.box(0, 0, 182, 5, LINE_D)
        bg.save(os.path.join(base, f'{name}_background.png'))
        pr = Img(182, 5)
        h, l = hexc(hi), hexc(lo)
        for x in range(182):
            k = x / 181
            c = tuple(int(l[i] + (h[i] - l[i]) * k) for i in range(3)) + (255,)
            pr.rect(x, 1, x + 1, 4, c)
        pr.rect(0, 1, 182, 2, GLOW[:3] + (120,))
        pr.box(0, 0, 182, 5, LINE)
        pr.save(os.path.join(base, f'{name}_progress.png'))


if __name__ == '__main__':
    for name, (rows, line, top, bot) in VARIANTS.items():
        font_gui(name, rows, line, top, bot)
    generic_54(); inventory(); hud(); tooltip(); buttons(); bossbars()
    print('보라 테마 UI 그림 완료')
