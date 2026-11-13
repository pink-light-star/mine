"""입체 무기 미리보기: 각 무기를 비스듬한 각도(3/4 시점)로 그려 한 장에 모은다."""
import sys, os, math, struct, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voxel_weapons as vw

out = sys.argv[1]
cvs = vw.build_all()
S = 7 / vw.SUB             # 블록 한 칸 크기(픽셀)
CW, CH = 380, 430
names = list(cvs.keys())
cols = 5; rows = (len(names) + cols - 1) // cols
W, H = cols * CW, rows * CH
img = bytearray(W * H * 3)
for i in range(W * H): img[i*3:i*3+3] = bytes((38, 40, 52))
def put(x, y, c):
    if 0 <= x < W and 0 <= y < H: img[(y*W+x)*3:(y*W+x)*3+3] = bytes(c)
def sh(c, f): return tuple(max(0, min(255, int(v*f))) for v in c)
for n_i, k in enumerate(names):
    cv = cvs[k]; ox = (n_i % cols) * CW + 40; oy = (n_i // cols) * CH + 110
    vox = []
    for y in range(vw.NF):
        for x in range(vw.NF):
            c = cv.col[y][x]
            if not c: continue
            d = cv.dep[y][x]
            for z in range(-(d // 2) - (d % 2), d // 2):
                vox.append((x, y, z, c, cv.glow[y][x]))
    occ = {(x, y, z) for x, y, z, _, _ in vox}
    # 시점: 오른쪽으로 30도 돌리고 위에서 약간 내려다봄
    ca, sa = math.cos(math.radians(32)), math.sin(math.radians(32))
    def proj(x, y, z):
        X = x * ca + z * sa * 2.2 / vw.SUB * vw.SUB; Y = y + (-x * sa + z * ca) * 0.25
        return X, Y
    vox.sort(key=lambda v: (v[2], -v[0] + v[1]))
    for x, y, z, c, g in vox:
        X, Y = proj(x, y, z)
        px, py = int(ox + X * S * 0.62), int(oy + Y * S * 0.62)
        if g: c = tuple(min(255, int(v * 1.15 + 20)) for v in c)
        front = c if (x, y, z + 1) not in occ else None
        sz = max(1, int(S * 0.62 + 0.99))
        for dy in range(sz):
            for dx in range(sz):
                put(px + dx, py + dy, front if front else sh(c, 0.7))
        if (x + 1, y, z) not in occ:
            for dy in range(sz): put(px + sz, py + dy, sh(c, 0.55))
        if (x, y - 1, z) not in occ:
            for dx in range(sz): put(px + dx, py - 1, sh(c, 1.15))
raw = b''.join(b'\x00' + bytes(img[y*W*3:(y+1)*W*3]) for y in range(H))
def ch(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
open(out, 'wb').write(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b''))
print(W, H)
