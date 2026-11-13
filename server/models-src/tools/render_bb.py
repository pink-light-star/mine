"""bbmodel 미리보기 렌더러: 뼈대 회전 + 큐브 회전 + 텍스처를 반영해 비스듬한 각도로 PNG를 그린다.
사용: python3 render_bb.py 모델.bbmodel 출력.png [시점각도] [폭] [높이]"""
import json, sys, math, base64, zlib, struct

def read_png(d):
    i = 8; idat = b''
    while i < len(d):
        ln = struct.unpack('>I', d[i:i+4])[0]; t = d[i+4:i+8]; c = d[i+8:i+8+ln]
        if t == b'IHDR': w, h = struct.unpack('>II', c[:8]); ct = c[9]
        if t == b'IDAT': idat += c
        i += 12 + ln
    raw = zlib.decompress(idat); bpp = 4 if ct == 6 else 3; st = w * bpp
    rows = []; prev = bytearray(st)
    for y in range(h):
        f = raw[y*(st+1)]; row = bytearray(raw[y*(st+1)+1:(y+1)*(st+1)])
        for x in range(st):
            a = row[x-bpp] if x >= bpp else 0; b = prev[x]; cc = prev[x-bpp] if x >= bpp else 0
            if f == 1: row[x] = (row[x] + a) & 255
            elif f == 2: row[x] = (row[x] + b) & 255
            elif f == 3: row[x] = (row[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - cc; pa, pb, pc = abs(p-a), abs(p-b), abs(p-cc)
                row[x] = (row[x] + (a if pa <= pb and pa <= pc else (b if pb <= pc else cc))) & 255
        rows.append(row); prev = row
    return w, h, bpp, rows

def rot(p, r, o):
    x, y, z = p[0]-o[0], p[1]-o[1], p[2]-o[2]
    rx, ry, rz = [math.radians(a) for a in r]
    y, z = y*math.cos(rx) - z*math.sin(rx), y*math.sin(rx) + z*math.cos(rx)
    x, z = x*math.cos(ry) + z*math.sin(ry), -x*math.sin(ry) + z*math.cos(ry)
    x, y = x*math.cos(rz) - y*math.sin(rz), x*math.sin(rz) + y*math.cos(rz)
    return (x+o[0], y+o[1], z+o[2])

def render(src, out, yaw=-35, W=900, H=700, alpha=False):
    m = json.load(open(src))
    TW, TH, bpp, px = read_png(base64.b64decode(m['textures'][0]['source'].split(',', 1)[1]))
    RW, RH = m['resolution']['width'], m['resolution']['height']
    groups = {g['uuid']: g for g in m.get('groups', [])}
    def _collect(n):
        if isinstance(n, dict):
            groups.setdefault(n['uuid'], n)
            for c in n.get('children', []): _collect(c)
    for r0 in m['outliner']: _collect(r0)
    parent = {}
    def walk(node, par):
        if isinstance(node, dict):
            parent[node['uuid']] = par
            for c in node.get('children', []): walk(c, node['uuid'])
        else:
            parent[node] = par
    for r in m['outliner']: walk(r, None)
    FN = {'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0), 'west': (-1, 0, 0), 'up': (0, 1, 0), 'down': (0, -1, 0)}
    faces = []
    for e in m['elements']:
        if 'from' not in e or 'faces' not in e: continue
        a, b = e['from'], e['to']; r = e.get('rotation', [0, 0, 0]); o = e.get('origin', [0, 0, 0])
        chain = []; g = parent.get(e['uuid'])
        while g: chain.append(groups[g]); g = parent.get(g)
        for fname, fd in e['faces'].items():
            if fname == 'north': q = [(b[0],a[1],a[2]),(a[0],a[1],a[2]),(a[0],b[1],a[2]),(b[0],b[1],a[2])]
            elif fname == 'south': q = [(a[0],a[1],b[2]),(b[0],a[1],b[2]),(b[0],b[1],b[2]),(a[0],b[1],b[2])]
            elif fname == 'east': q = [(b[0],a[1],b[2]),(b[0],a[1],a[2]),(b[0],b[1],a[2]),(b[0],b[1],b[2])]
            elif fname == 'west': q = [(a[0],a[1],a[2]),(a[0],a[1],b[2]),(a[0],b[1],b[2]),(a[0],b[1],a[2])]
            elif fname == 'up': q = [(a[0],b[1],b[2]),(b[0],b[1],b[2]),(b[0],b[1],a[2]),(a[0],b[1],a[2])]
            else: q = [(a[0],a[1],a[2]),(b[0],a[1],a[2]),(b[0],a[1],b[2]),(a[0],a[1],b[2])]
            n = FN[fname]
            q = [rot(p, r, o) for p in q]; n = rot(n, r, (0, 0, 0))
            for gr in chain:
                if any(gr.get('rotation', [0, 0, 0])):
                    q = [rot(p, gr['rotation'], gr['origin']) for p in q]; n = rot(n, gr['rotation'], (0, 0, 0))
            faces.append((q, n, fd['uv']))
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw)); pitch = math.radians(18)
    def view(p):
        x, y, z = p
        x, z = x*cy - z*sy, x*sy + z*cy
        y, z = y*math.cos(pitch) - z*math.sin(pitch), y*math.sin(pitch) + z*math.cos(pitch)
        return x, y, z
    pts = [view(p) for f in faces for p in f[0]]
    mnx = min(p[0] for p in pts); mxx = max(p[0] for p in pts); mny = min(p[1] for p in pts); mxy = max(p[1] for p in pts)
    sc = min((W - 60) / max(1e-6, mxx - mnx), (H - 60) / max(1e-6, mxy - mny))
    img = bytearray([232, 228, 245] * W * H); zb = [1e9] * (W * H)
    L = (0.4, 0.8, -0.45)
    for q, n, uv in faces:
        vq = [view(p) for p in q]; vn = view(n)
        if vn[2] > 0.05: continue
        lit = 0.55 + 0.45 * max(0, n[0]*L[0] + n[1]*L[1] + n[2]*L[2])
        sq = [((p[0]-mnx)*sc + 30, H - ((p[1]-mny)*sc + 30), p[2]) for p in vq]
        ax_, ay_ = sq[1][0]-sq[0][0], sq[1][1]-sq[0][1]; bx_, by_ = sq[3][0]-sq[0][0], sq[3][1]-sq[0][1]
        det = ax_*by_ - ay_*bx_
        ys = [p[1] for p in sq]
        for yy in range(max(0, int(min(ys))), min(H, int(max(ys)) + 1)):
            xi = []
            for k in range(4):
                p1, p2 = sq[k], sq[(k+1) % 4]
                if (p1[1] <= yy < p2[1]) or (p2[1] <= yy < p1[1]):
                    t = (yy - p1[1]) / (p2[1] - p1[1]); xi.append((p1[0] + t*(p2[0]-p1[0]), p1[2] + t*(p2[2]-p1[2])))
            if len(xi) < 2: continue
            xi.sort()
            (x0, z0), (x1, z1) = xi[0], xi[-1]
            for xx in range(max(0, int(x0)), min(W, int(x1) + 1)):
                t = (xx - x0) / (x1 - x0) if x1 > x0 else 0; z = z0 + t*(z1-z0)
                if z >= zb[yy*W+xx]: continue
                if abs(det) > 1e-6:
                    dx_, dy_ = xx - sq[0][0], yy - sq[0][1]
                    ss = (dx_*by_ - dy_*bx_) / det; tt = (ax_*dy_ - ay_*dx_) / det
                else: ss = tt = 0.5
                ss = min(1, max(0, ss)); tt = min(1, max(0, tt))
                u = uv[0] + (uv[2]-uv[0]) * ss; v = uv[3] + (uv[1]-uv[3]) * tt
                tx = min(TW-1, max(0, int(u * TW / RW))); ty = min(TH-1, max(0, int(v * TH / RH)))
                cc = px[ty][tx*bpp:tx*bpp+3]
                if bpp == 4 and px[ty][tx*bpp+3] == 0: continue
                zb[yy*W+xx] = z; img[(yy*W+xx)*3:(yy*W+xx)*3+3] = bytes(min(255, int(vv * lit)) for vv in cc)
    def ch(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    if alpha:   # 배경 투명 (도감 썸네일용)
        rows = []
        for y in range(H):
            r = bytearray(b'\x00')
            for x in range(W):
                r += img[(y*W+x)*3:(y*W+x)*3+3] + (b'\xff' if zb[y*W+x] < 1e9 else b'\x00')
            rows.append(bytes(r))
        open(out, 'wb').write(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 6, 0, 0, 0)) + ch(b'IDAT', zlib.compress(b''.join(rows), 9)) + ch(b'IEND', b''))
        return
    raw = b''.join(b'\x00' + bytes(img[y*W*3:(y+1)*W*3]) for y in range(H))
    open(out, 'wb').write(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b''))

def sheet(paths, out, cols=4, cw=450, chh=350):
    import os
    rows = (len(paths) + cols - 1) // cols
    W, H = cw * cols, chh * rows; img = bytearray([232, 228, 245] * W * H)
    for k, p in enumerate(paths):
        d = open(p, 'rb').read(); w, h, bpp, rr = read_png(d)
        ox = (k % cols) * cw; oy = (k // cols) * chh
        for y in range(chh):
            for x in range(cw):
                sx, sy = x * w // cw, y * h // chh
                img[((oy+y)*W+ox+x)*3:((oy+y)*W+ox+x)*3+3] = rr[sy][sx*bpp:sx*bpp+3]
    raw = b''.join(b'\x00' + bytes(img[y*W*3:(y+1)*W*3]) for y in range(H))
    def ch(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(out, 'wb').write(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b''))

if __name__ == '__main__':
    render(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else -35)
