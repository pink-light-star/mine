"""별빛서버 GUI 배경 그림 생성 (리소스팩 글꼴용).
상자 GUI 크기: 가로 176, 세로 114 + 줄수*18. 칸 위치는 바닐라와 같게 그린다."""
import struct, zlib, os, sys

OUT = sys.argv[1]

def png(path, w, h, px):
    raw = b''.join(b'\x00' + bytes(px[y*w*4:(y+1)*w*4]) for y in range(h))
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) \
        + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    open(path, 'wb').write(data)

def hexc(s, a=255): return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)

def make(rows, name, accent='c9a24a', top='2a1f4a', bot='120f22'):
    W, H = 176, 114 + rows * 18
    px = bytearray(W * H * 4)
    def put(x, y, c):
        if 0 <= x < W and 0 <= y < H:
            i = (y * W + x) * 4; px[i:i+4] = bytes(c)
    def rect(x0, y0, x1, y1, c):
        for y in range(y0, y1):
            for x in range(x0, x1): put(x, y, c)
    gold = hexc(accent); gold_d = hexc('6b5222'); gold_l = hexc('f3dc8f')
    t, b = hexc(top), hexc(bot)
    # 바탕: 세로 그라데이션
    for y in range(H):
        k = y / (H - 1)
        c = tuple(int(t[i] + (b[i] - t[i]) * k) for i in range(3)) + (255,)
        rect(0, y, W, y + 1, c)
    # 은은한 별무늬
    import random
    rnd = random.Random(rows * 7 + len(name))
    for _ in range(W * H // 90):
        x, y = rnd.randrange(3, W - 3), rnd.randrange(3, H - 3)
        put(x, y, hexc('3c3268'))
    # 머리 띠
    rect(3, 3, W - 3, 15, hexc('1a1430'))
    rect(3, 15, W - 3, 16, gold)
    # 테두리 (바깥 어두운 금, 안쪽 금, 하이라이트)
    for i, c in enumerate([gold_d, gold, gold_l]):
        rect(i, i, W - i, i + 1, c); rect(i, H - 1 - i, W - i, H - i, c)
        rect(i, i, i + 1, H - i, c); rect(W - 1 - i, i, W - i, H - i, c)
    # 둥근 모서리(투명)
    for (cx, cy) in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]:
        put(cx, cy, (0, 0, 0, 0))
    # 모서리 장식 (금 마름모)
    for (cx, cy) in [(6, 6), (W - 7, 6), (6, H - 7), (W - 7, H - 7)]:
        for d in range(-2, 3):
            for e in range(-(2 - abs(d)), 3 - abs(d)):
                put(cx + d, cy + e, gold_l if (d, e) == (0, 0) else gold)
    def slot(x, y):
        rect(x, y, x + 18, y + 18, hexc('0b0916'))
        rect(x, y, x + 18, y + 1, hexc('050409')); rect(x, y, x + 1, y + 18, hexc('050409'))
        rect(x, y + 17, x + 18, y + 18, hexc('4a3f7a')); rect(x + 17, y, x + 18, y + 18, hexc('4a3f7a'))
    for r in range(rows):
        for c in range(9): slot(7 + c * 18, 17 + r * 18)
    # 구분선 + '인벤토리' 글씨 받침(밝은 양피지, 바닐라 글씨가 잘 보이게)
    sep = 17 + rows * 18 + 1
    rect(6, sep, W - 6, sep + 1, gold_d)
    rect(5, rows * 18 + 18, 66, rows * 18 + 29, hexc('d8c79a'))
    rect(5, rows * 18 + 28, 66, rows * 18 + 29, gold_d)
    for r in range(3):
        for c in range(9): slot(7 + c * 18, rows * 18 + 30 + r * 18)
    for c in range(9): slot(7 + c * 18, rows * 18 + 88)
    png(os.path.join(OUT, name + '.png'), W, H, px)
    return H

os.makedirs(OUT, exist_ok=True)
sizes = {}
sizes['gui_6'] = make(6, 'gui_6')
sizes['gui_5'] = make(5, 'gui_5')
sizes['gui_3'] = make(3, 'gui_3')
sizes['gui_6_red'] = make(6, 'gui_6_red', accent='d8573a', top='3a1418', bot='140608')   # 던전
sizes['gui_3_red'] = make(3, 'gui_3_red', accent='d8573a', top='3a1418', bot='140608')
sizes['gui_6_gold'] = make(6, 'gui_6_gold', accent='e0b04a', top='2e2210', bot='120c05')  # 대장간
sizes['gui_3_gold'] = make(3, 'gui_3_gold', accent='e0b04a', top='2e2210', bot='120c05')
sizes['gui_5_green'] = make(5, 'gui_5_green', accent='7fd06a', top='12301e', bot='06120a')  # 능력치
sizes['gui_4_shop'] = make(4, 'gui_4_shop', accent='e8c25a', top='0f3a2c', bot='061a12')   # 상점
sizes['gui_6_shop'] = make(6, 'gui_6_shop', accent='e8c25a', top='0f3a2c', bot='061a12')
print(sizes)
