#!/usr/bin/env python3
"""
별빛 서버 커스텀 몹 모델 생성기 (Blockbench .bbmodel, BetterModel용)

실행:  python3 models-src/generate_models.py
출력:  plugins/BetterModel/models/*.bbmodel

좌표: 1 = 1픽셀 (16 = 1블록), 발바닥 y=0, 정면 = -Z
텍스처: 모델마다 64x64 팔레트(8x8칸, 칸당 8px 노이즈 색)를 자동 생성
"""
import base64, json, math, os, random, re, struct, sys, uuid, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pngread import read_png

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugins", "BetterModel", "models")

# ---------------------------------------------------------------- PNG

def png_bytes(w, h, pixels):
    raw = b"".join(b"\x00" + bytes(c for px in pixels[y * w:(y + 1) * w] for c in px) for y in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))

def hexrgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

# ---------------------------------------------------------------- 스킨 보정

OVERLAY_RECTS = [(32, 0, 64, 16), (16, 32, 40, 48), (40, 32, 56, 48), (0, 32, 16, 48), (0, 48, 16, 64), (48, 48, 64, 64)]

def fix_skin_alpha(skin):
    """투명도 없이 저장된(RGB) 스킨은 겉 레이어의 순수 검정(#000000)을 투명으로 바꾼다"""
    w, h, px = skin
    if any(p[3] < 255 for p in px):
        return skin
    px = list(px)
    for x0, y0, x1, y1 in OVERLAY_RECTS:
        for y in range(y0, min(y1, h)):
            for x in range(x0, min(x1, w)):
                r, g, b, a = px[y * w + x]
                if r == 0 and g == 0 and b == 0:
                    px[y * w + x] = (0, 0, 0, 0)
    return (w, h, px)

def is_slim(skin_path):
    w, h, px = fix_skin_alpha(read_png(skin_path))
    col = [px[y * w + x] for x in (54, 55) for y in range(20, 32)]
    return all(p[3] == 0 or p[:3] == (0, 0, 0) for p in col)

# ---------------------------------------------------------------- Model builder

def uid():
    return str(uuid.uuid4())

class Model:
    CELL = 8
    GRID = 16       # 색 칸: 16x8칸 (위쪽 절반)
    SIZE = 128      # 텍스처 128x128, 아래쪽 절반은 16x16 픽셀아트(얼굴) 자리

    def __init__(self, name, seed=0, skin=None):
        self.name = name
        self.skin = fix_skin_alpha(read_png(skin)) if skin else None   # 스킨이 있으면 텍스처 왼쪽 위 64x64에 넣는다
        self.groups = {}       # name -> group dict
        self.children = {}     # name -> list of (kind, id/name)
        self.parent = {}
        self.roots = []
        self.elements = []
        self.colors = []       # hex list → cell index
        self.arts = {}         # key -> {"uv", "rows", "pal"}
        self.anims = []
        self.rng = random.Random(seed or hash(name) & 0xffff)

    # 색 → 텍스처 칸
    def cell(self, color):
        if color not in self.colors:
            assert len(self.colors) < self.GRID * 8, "too many colors"
            self.colors.append(color)
        i = self.colors.index(color)
        if self.skin:   # 스킨 모델: 색 칸은 오른쪽 위 64x64 (8x8칸)
            assert i < 64, "too many colors for skinned model"
            x, y = 64 + (i % 8) * self.CELL, (i // 8) * self.CELL
            return [x + 0.5, y + 0.5, x + self.CELL - 0.5, y + self.CELL - 0.5]
        x, y = (i % self.GRID) * self.CELL, (i // self.GRID) * self.CELL
        return [x + 0.5, y + 0.5, x + self.CELL - 0.5, y + self.CELL - 0.5]

    def art(self, key, rows, pal):
        """16x16 픽셀아트 등록 (얼굴 등). rows: 16글자 x 16줄, pal: 글자→색"""
        if key in self.arts:
            return key
        assert len(rows) == 16 and all(len(r) == 16 for r in rows), (key, [len(r) for r in rows])
        j = len(self.arts)
        assert j < 32, "too many arts"
        x, y = (j % 8) * 16, 64 + (j // 8) * 16
        self.arts[key] = {"uv": [x, y, x + 16, y + 16], "rows": rows, "pal": pal}
        return key

    def bone(self, name, origin, parent=None, rotation=(0, 0, 0)):
        g = {"uuid": uid(), "export": True, "locked": False, "origin": list(map(float, origin)),
             "rotation": list(map(float, rotation)), "color": 0, "name": name, "children": [],
             "reset": False, "shade": True, "mirror_uv": False, "selected": False, "visibility": True,
             "autouv": 0, "isOpen": True, "primary_selected": False}
        self.groups[name] = g
        self.children[name] = []
        self.parent[name] = parent
        if parent:
            self.children[parent].append(("g", name))
        else:
            self.roots.append(name)
        return name

    def cube(self, bone, frm, to, color, rot=None, pivot=None, faces=None):
        frm, to = [min(a, b) for a, b in zip(frm, to)], [max(a, b) for a, b in zip(frm, to)]
        uv = self.cell(color)
        fs = {}
        for f in ("north", "east", "south", "west", "up", "down"):
            c = faces.get(f, color) if faces else color
            if isinstance(c, tuple) and c[0] == "art":
                fs[f] = {"uv": list(self.arts[c[1]]["uv"]), "texture": 0}
            else:
                fs[f] = {"uv": self.cell(c) if c != color else uv, "texture": 0}
        e = {"name": "cube", "box_uv": False, "render_order": "default", "locked": False,
             "allow_mirror_modeling": True, "from": list(map(float, frm)), "to": list(map(float, to)),
             "autouv": 0, "color": 0,
             "origin": list(map(float, pivot or [(a + b) / 2 for a, b in zip(frm, to)])),
             "faces": fs, "type": "cube", "uuid": uid()}
        if rot:
            e["rotation"] = list(map(float, rot))
        self.elements.append(e)
        self.children[bone].append(("e", e["uuid"]))
        return e

    def cube_uv(self, bone, frm, to, uvs, inflate=0.0):
        """면마다 UV를 직접 지정하는 큐브 (스킨용)"""
        frm = [a - inflate for a in frm]
        to = [a + inflate for a in to]
        e = {"name": "cube", "box_uv": False, "render_order": "default", "locked": False,
             "allow_mirror_modeling": True, "from": list(map(float, frm)), "to": list(map(float, to)),
             "autouv": 0, "color": 0, "origin": [(a + b) / 2 for a, b in zip(frm, to)],
             "faces": {f: {"uv": list(map(float, uv)), "texture": 0} for f, uv in uvs.items()},
             "type": "cube", "uuid": uid()}
        self.elements.append(e)
        self.children[bone].append(("e", e["uuid"]))
        return e

    def anim(self, name, length, channels, loop="loop"):
        """channels: {bone: {"rotation": (x,y,z), "position": (x,y,z)}} molang 문자열 허용"""
        animators = {}
        for bone, chans in channels.items():
            if bone not in self.groups:
                continue
            kfs = []
            for ch, xyz in chans.items():
                fmt = lambda v: re.sub(r"\d+\.\d{4,}", lambda mm: ("%.3f" % float(mm.group())).rstrip("0").rstrip("."), str(v))
                kfs.append({"channel": ch, "data_points": [{"x": fmt(xyz[0]), "y": fmt(xyz[1]), "z": fmt(xyz[2])}],
                            "uuid": uid(), "time": 0, "color": -1, "interpolation": "linear"})
            animators[self.groups[bone]["uuid"]] = {"name": bone, "type": "bone", "rotation_global": False,
                                                    "quaternion_interpolation": False, "keyframes": kfs}
        self.anims.append({"uuid": uid(), "name": name, "loop": loop, "override": False, "length": length,
                           "snapping": 24, "selected": False, "anim_time_update": "", "blend_weight": "",
                           "start_delay": "", "loop_delay": "", "animators": animators})

    def texture(self):
        S = self.SIZE
        px = [(0, 0, 0, 0)] * (S * S)
        if self.skin:
            sw, sh, spx = self.skin
            for y in range(min(sh, 64)):
                for x in range(min(sw, 64)):
                    px[y * S + x] = spx[y * sw + x]
        for i, col in enumerate(self.colors):
            r, g, b = hexrgb(col)
            if self.skin:
                ox, oy = 64 + (i % 8) * self.CELL, (i // 8) * self.CELL
            else:
                ox, oy = (i % self.GRID) * self.CELL, (i // self.GRID) * self.CELL
            for y in range(self.CELL):
                for x in range(self.CELL):
                    n = self.rng.randint(-14, 14)
                    edge = -10 if (x in (0, self.CELL - 1) or y in (0, self.CELL - 1)) else 0
                    px[(oy + y) * S + ox + x] = (max(0, min(255, r + n + edge)), max(0, min(255, g + n + edge)),
                                                 max(0, min(255, b + n + edge)), 255)
        for a in self.arts.values():
            ox, oy = a["uv"][0], a["uv"][1]
            for y, row in enumerate(a["rows"]):
                for x, ch in enumerate(row):
                    r, g, b = hexrgb(a["pal"][ch])
                    n = self.rng.randint(-5, 5) if ch in a["pal"].get("_noisy", "") else 0
                    px[(oy + y) * S + ox + x] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)), 255)
        return png_bytes(S, S, px)

    def outliner(self, name):
        node = {"uuid": self.groups[name]["uuid"], "isOpen": True, "children": []}
        for kind, ref in self.children[name]:
            node["children"].append(self.outliner(ref) if kind == "g" else ref)
        return node

    def save(self):
        S = self.SIZE
        data = {
            "meta": {"format_version": "5.0", "model_format": "free", "box_uv": False},
            "name": self.name, "model_identifier": "", "visible_box": [1, 1, 0],
            "variable_placeholders": "", "variable_placeholder_buttons": [], "timeline_setups": [],
            "unhandled_root_fields": {}, "resolution": {"width": S, "height": S},
            "elements": self.elements, "groups": list(self.groups.values()),
            "outliner": [self.outliner(r) for r in self.roots],
            "textures": [{"name": self.name + ".png", "path": "", "folder": "", "namespace": "", "id": "0",
                          "group": "", "width": S, "height": S, "uv_width": S, "uv_height": S,
                          "particle": False, "use_as_default": False, "layers_enabled": False,
                          "sync_to_project": "", "render_mode": "default", "render_sides": "auto",
                          "pbr_channel": "color", "frame_time": 1, "frame_order_type": "loop",
                          "frame_order": "", "frame_interpolate": False, "visible": True, "internal": True,
                          "saved": False, "uuid": uid(),
                          "source": "data:image/png;base64," + base64.b64encode(self.texture()).decode()}],
            "animations": self.anims,
        }
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, self.name + ".bbmodel"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        print(f"  {self.name}.bbmodel  (뼈대 {len(self.groups)}, 큐브 {len(self.elements)}, 애니 {len(self.anims)})")

# ---------------------------------------------------------------- 도우미

def box(m, bone, cx, cy, cz, w, h, d, color, **kw):
    """중심(cx, 바닥 cy, cz) 기준 w×h×d 상자"""
    return m.cube(bone, [cx - w / 2, cy, cz - d / 2], [cx + w / 2, cy + h, cz + d / 2], color, **kw)

def hitbox(m, w, h):
    """BetterModel은 'b_' 접두사가 붙은 뼈만 히트박스로 쓴다. 이름이 틀리면 흰 상자가 그대로 보이므로
    히트박스 상자는 만들지 않고 바탕 몹의 기본 히트박스를 쓴다."""
    return

SWING = "math.sin(q.anim_time * 360 * {f}) * {a}"


# ---------------------------------------------------------------- 얼굴 픽셀아트 (16x16, 정면)

FACE_ART = {
    # 사이렌: 큰 눈 + 속눈썹 + 하이라이트, 볼터치, 입술, 앞머리, 진주 머리핀
    "siren": ([
        "HHHHHHHHHHHHHHHH",
        "HHHhHHHHHHHHhHHH",
        "HHHHHhHHHHhHHHHH",
        "HHHHssHHHHssHHHH",
        "HHHssssHHsssssHH",
        "HHssssssssssssph",
        "HsKKKKssssKKKKsH",
        "HsKWIIssssIIWKsH",
        "HssIDIssssIDIssH",
        "HsPsIsssssssIsPH",
        "HsPPssssSSssPPsH",
        "HssssssssssssssH",
        "HHssssLssLsssshH",
        "HHsssssLLsssssHH",
        "HHHsssssssssssHH",
        "HHHHssssssssHHHH",
    ], {"H": "#1fa39a", "h": "#5fe0d2", "s": "#f9e0d4", "S": "#efc6b6", "K": "#1b2233", "W": "#ffffff",
        "I": "#1fc2d6", "D": "#0b3d5c", "P": "#f7a8b8", "L": "#e0577a", "l": "#f39bb3", "p": "#fff4e0"}),
    # 오크: 찡그린 눈썹, 붉은 눈, 넓은 코, 송곳니 입
    "orc": ([
        "gggggggggggggggg",
        "gggggggggggggggg",
        "gGggggggggggggGg",
        "gggggggggggggggg",
        "gBBBggggggggBBBg",
        "ggBBBBggggBBBBgg",
        "ggKRRKggggKRRKgg",
        "ggKYRKggggKRYKgg",
        "gggKKggGGggKKggg",
        "ggggggGNNGgggggg",
        "gggggGGNNGGggggg",
        "gggggggggggggggg",
        "ggMMMMMMMMMMMMgg",
        "ggMTMMMMMMMMTMgg",
        "gggTggggggggTggg",
        "gggggggggggggggg",
    ], {"g": "#6a9a3a", "G": "#557f2c", "B": "#2c4318", "K": "#1c1c1c", "R": "#ff3b1f", "Y": "#ffd36b",
        "N": "#2f4a1a", "M": "#2a1a10", "T": "#efe6c8", "_noisy": "gG"}),
    # 메두사: 금색 뱀눈(세로 동공), 짙은 입술
    "medusa": ([
        "vvvvvvvvvvvvvvvv",
        "vvvvvvvvvvvvvvvv",
        "vvvvvvvvvvvvvvvv",
        "vvvvvvvvvvvvvvvv",
        "vvKKKKvvvvKKKKvv",
        "vKYYYYKvvKYYYYKv",
        "vKYYDYKvvKYDYYKv",
        "vKOYDYKvvKYDYOKv",
        "vvKKKKvvvvKKKKvv",
        "vvvvvvvVVvvvvvvv",
        "vvvvvvvVVvvvvvvv",
        "vvvvvvvvvvvvvvvv",
        "vvvvvLLLLLLvvvvv",
        "vvvvvvLLLLvvvvvv",
        "vvvvvvvvvvvvvvvv",
        "vvvvvvvvvvvvvvvv",
    ], {"v": "#a8d1a3", "V": "#8bb987", "K": "#163016", "Y": "#ffd200", "O": "#ff9a00", "D": "#111111",
        "L": "#5b2a5a", "_noisy": "vV"}),
    # 미노타우로스: 털 무늬 + 붉게 빛나는 눈
    "bull": ([
        "bbbbbbbbbbbbbbbb",
        "bBbbbbbbbbbbbbBb",
        "bbbbbbbbbbbbbbbb",
        "bKKKbbbbbbbbKKKb",
        "bbKKKKbbbbKKKKbb",
        "bbKRRKbbbbKRRKbb",
        "bbKOWKbbbbKWOKbb",
        "bbbKKbbbbbbKKbbb",
        "bbbbbbbBBbbbbbbb",
        "bbbbbbBBBBbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
    ], {"b": "#7a5232", "B": "#5e3e24", "K": "#1a0f08", "R": "#ff2020", "O": "#ff8a00", "W": "#ffd0a0",
        "_noisy": "bB"}),
    # 키클롭스: 얼굴 가운데 커다란 눈 하나
    "cyclops": ([
        "cccccccccccccccc",
        "cccccccccccccccc",
        "ccBBBBBBBBBBBBcc",
        "cccBBccccccBBccc",
        "ccccKKKKKKKKcccc",
        "cccKWWWWWWWWKccc",
        "ccKWWWIIIIWWWKcc",
        "ccKWWIIDDIIWWKcc",
        "ccKWWIDDHIIWWKcc",
        "ccKWWWIIIIWWWKcc",
        "cccKWWWWWWWWKccc",
        "ccccKKKKKKKKcccc",
        "cccccccCCccccccc",
        "ccccCMMMMMMCcccc",
        "cccccMTTTTMccccc",
        "cccccccccccccccc",
    ], {"c": "#c8a07a", "C": "#a8805a", "B": "#5a3a1e", "K": "#3a2414", "W": "#f6f6f0", "I": "#3b8a3b",
        "D": "#0d0d0d", "H": "#ffffff", "M": "#3a2010", "T": "#e8e0c8", "_noisy": "cC"}),
    # 하피: 맹금류 노란 눈, 날카로운 눈매
    "harpy": ([
        "FFFFFFFFFFFFFFFF",
        "FFFfFFFFFFFFfFFF",
        "FFFFFfFFFFfFFFFF",
        "FFsssFFFFFFsssFF",
        "FsssssssssssssFF",
        "FsKKKKssssKKKKsF",
        "FsKYYDssssDYYKsF",
        "FssKYYssssYYKssF",
        "FssssssssssssssF",
        "FsssssssOOsssssF",
        "FsssssssOOsssssF",
        "FssssssssssssssF",
        "FsssssMMMMsssssF",
        "FFssssssssssssFF",
        "FFFssssssssssFFF",
        "FFFFssssssssFFFF",
    ], {"F": "#7a5232", "f": "#a8865a", "s": "#ead0b0", "K": "#1c1208", "Y": "#ffcc00", "D": "#111111",
        "O": "#d4a85a", "M": "#8a3a3a"}),
    # 개/늑대 (케르베로스, 워그) 정면: 붉은 눈 (아래쪽은 주둥이가 가림)
    "wolf": ([
        "ffffffffffffffff",
        "ffffffffffffffff",
        "fFffffffffffffFf",
        "ffffffffffffffff",
        "ffKKKffffffKKKff",
        "fKRRRKffffKRRRKf",
        "fKRYRKffffKRYRKf",
        "ffKKKffffffKKKff",
        "ffffffffffffffff",
        "ffffffffffffffff",
        "ffffffffffffffff",
        "ffffffffffffffff",
        "ffffffffffffffff",
        "ffffffffffffffff",
        "ffffffffffffffff",
        "ffffffffffffffff",
    ], None),
    # 드래곤(탈것): 크고 둥근 순한 눈, 하늘색 홍채 + 반짝이는 하이라이트 (앞쪽 = 오른쪽)
    "eye_kind": ([
        "dddddddddddddddd",
        "dddddddddddddddd",
        "dddddddddddddddd",
        "ddddBBBBBBBBBddd",
        "dddBBBBBBBBBBBdd",
        "ddddKCCCCCCCKBdd",
        "dddKCCCcDcCCWKdd",
        "dddKCCccDccCCKdd",
        "ddddKCCcDcCCKddd",
        "dddddKKKKKKKdddd",
        "dddddddddddddddd",
        "dddddddddddddddd",
        "ddeddddddddddedd",
        "dddddddddddddddd",
        "ddddeddddddedddd",
        "dddddddddddddddd",
    ], None),
    # 이그니스: 사납게 찢어진 눈, 붉은 테두리 + 금빛 홍채 + 세로 동공, 두꺼운 눈썹뼈 (앞쪽 = 오른쪽)
    "eye_fierce": ([
        "dddddddddddddddd",
        "ddBBBddddddddddd",
        "dddBBBBBdddddddd",
        "ddddBBBBBBBBdddd",
        "ddddddRRRBBBBBdd",
        "dddddROOOORRBBdd",
        "ddddROYYDYYOORdd",
        "dddROYYYDYYWYORd",
        "ddddROYYDYYYORdd",
        "dddddRROOOORRddd",
        "dddddddRRRRddddd",
        "dddddddddddddddd",
        "ddeddddeddddeddd",
        "dddddddddddddddd",
        "dededdeddededded",
        "dddddddddddddddd",
    ], None),
    # 옆얼굴 눈 (드래곤·말·독수리): 머리 양옆에 붙인다
    "side_eye": ([
        "dddddddddddddddd",
        "dddddddddddddddd",
        "ddddddeeeeeedddd",
        "dddddeKKKKKKeddd",
        "ddddeKYYYYYYKedd",
        "ddddKYYYDYYYKddd",
        "ddddKYYDDDYYKddd",
        "ddddKYYYDYYYKddd",
        "dddddKKKKKKKdddd",
        "dddddddddddddddd",
        "ddeddddddddddedd",
        "dddddddddddddddd",
        "ddddeddddddedddd",
        "dddddddddddddddd",
        "dddddddddddddddd",
        "dddddddddddddddd",
    ], None),
}

def face(m, kind, base=None, eye=None, extra=None, mirror=False):
    """얼굴 아트를 모델에 등록하고 키를 돌려준다. base/eye로 털·눈 색을 바꿀 수 있다.
    mirror=True면 좌우 반전 (머리 왼쪽 면용)"""
    rows, pal = FACE_ART[kind]
    if pal is None:
        pal = {"f": base, "F": shade(base, -18), "d": base, "e": shade(base, -22), "K": "#141414",
               "R": eye, "Y": eye, "D": "#0a0a0a", "_noisy": "fFde",
               # eye_kind / eye_fierce 전용
               "C": eye, "c": shade(eye, 45), "W": "#ffffff", "B": shade(base, -45), "O": "#ff7a00"}
        if kind == "eye_fierce":
            pal.update({"R": "#c4140c", "Y": "#ffd000", "D": "#140400"})
        if kind == "eye_kind":
            pal.update({"D": "#0b1a3a"})
    if extra:
        pal = dict(pal, **extra)
    if mirror:
        rows = [r[::-1] for r in rows]
    return m.art(kind + "_" + (base or "") + (eye or "") + ("_m" if mirror else ""), rows, pal)

def shade(hexc, d):
    r, g, b = hexrgb(hexc)
    return "#%02x%02x%02x" % tuple(max(0, min(255, c + d)) for c in (r, g, b))

# ---------------------------------------------------------------- 인간형

def humanoid(name, s=1.0, skin="#6a9a3a", shirt="#6b4a2b", pants="#4a3a28", boots="#2e2218",
             body_w=8, head="orc", weapon=None, extras=(), legs="legs", seed=0, face_skin=None):
    m = Model(name, seed, skin=face_skin)
    L, B, A, H = 12 * s, 12 * s, 12 * s, 8 * s   # 다리, 몸통, 팔, 머리
    bw = body_w * s
    lw = 4 * s
    hip = L
    m.bone("body", [0, hip, 0])
    # 하체
    if legs == "legs":
        for side, x in (("left_leg", -lw / 2 - 0.1 * s), ("right_leg", lw / 2 + 0.1 * s)):
            m.bone(side, [x, hip, 0], "body")
            box(m, side, x, 2 * s, 0, lw, L - 2 * s, lw, pants)
            box(m, side, x, 0, -0.5 * s, lw + 0.4 * s, 3 * s, lw + 1 * s, boots)
    elif legs == "bird":
        for side, x in (("left_leg", -2 * s), ("right_leg", 2 * s)):
            m.bone(side, [x, hip, 0], "body")
            box(m, side, x, 5 * s, 0, 3 * s, L - 5 * s, 3 * s, shirt)
            box(m, side, x, 0, 0, 1.5 * s, 5 * s, 1.5 * s, "#d8b23a")
            for dx in (-1, 0, 1):
                box(m, side, x + dx * 1.2 * s, 0, -1.8 * s, 0.8 * s, 0.8 * s, 3 * s, "#d8b23a")
    # 몸통
    m.bone("torso", [0, hip, 0], "body")
    if head == "siren":
        box(m, "torso", 0, hip, 0, bw - 1 * s, B, 4 * s, skin)                       # 날씬한 상체
        for sx in (-1, 1):                                                              # 조개껍데기 상의
            box(m, "torso", sx * 1.8 * s, hip + B - 5 * s, -2.2 * s, 3.2 * s, 2.6 * s, 0.8 * s, "#f7a8c4")
            box(m, "torso", sx * 1.8 * s, hip + B - 4.4 * s, -2.6 * s, 2 * s, 1.4 * s, 0.4 * s, "#ffd1e3")
        box(m, "torso", 0, hip + B - 3.6 * s, -2.1 * s, 0.6 * s, 0.6 * s, 0.4 * s, "#fff4e0")  # 진주
        box(m, "torso", 0, hip + B - 1.2 * s, -2.05 * s, bw - 3 * s, 0.4 * s, 0.3 * s, "#fff4e0")  # 진주 목걸이
    else:
        box(m, "torso", 0, hip, 0, bw, B, 4.5 * s, shirt)
        box(m, "torso", 0, hip, 0, bw + 0.4 * s, 1.5 * s, 5 * s, "#3a2a1a")  # 벨트
        box(m, "torso", 0, hip + 1.5 * s, -0.3 * s, bw - 2 * s, B - 4 * s, 4.6 * s, skin)  # 가슴 노출
    top = hip + B
    # 팔
    for side, sx in (("left_arm", -1), ("right_arm", 1)):
        x = sx * (bw / 2 + 2 * s)
        m.bone(side, [x, top - 1.5 * s, 0], "torso")
        if "wings" in extras:
            box(m, side, x, top - A, 0, 3 * s, A, 3 * s, shirt)
            for i in range(5):
                box(m, side, x + sx * (2 + i * 2.2) * s, top - A - i * 1.5 * s, 0, 2.2 * s, A + 2 * s, 1 * s,
                    "#8b6a45" if i % 2 else "#a8865a")
        elif head == "siren":
            box(m, side, x - sx * 0.6 * s, top - A, 0, 3 * s, A, 3 * s, skin)
            box(m, side, x - sx * 0.6 * s, top - A + 2 * s, 0, 3.3 * s, 1 * s, 3.3 * s, "#fff4e0")  # 진주 팔찌
        else:
            box(m, side, x, top - A, 0, 4 * s, A, 4 * s, skin)
            box(m, side, x, top - A + 2 * s, 0, 4.4 * s, 2 * s, 4.4 * s, "#a07a3a")  # 팔찌
            box(m, side, x, top - 4 * s, 0, 4.6 * s, 4 * s, 4.6 * s, shirt)  # 어깨
    # 머리
    m.bone("head", [0, top, 0], "torso")
    if face_skin:   # 받은 스킨의 머리(얼굴 + 겉 레이어)를 그대로 씌운다
        m.cube_uv("head", [-H / 2, top, -H / 2], [H / 2, top + H, H / 2], skin_uv(0, 0, 8, 8, 8))
        m.cube_uv("head", [-H / 2, top, -H / 2], [H / 2, top + H, H / 2], skin_uv(32, 0, 8, 8, 8), inflate=0.5 * s)
    else:
        fkey = face(m, head) if head in FACE_ART else None
        box(m, "head", 0, top, 0, H, H, H, skin, faces={"north": ("art", fkey)} if fkey else None)
    eye_y = top + H * 0.55
    if head == "orc":
        box(m, "head", 0, top, -0.5 * s, H + 1 * s, 3 * s, H + 0.6 * s, skin)              # 턱
        box(m, "head", -2.2 * s, top + 2.2 * s, -H / 2 - 1.2 * s, 1 * s, 2.5 * s, 1 * s, "#efe6c8")  # 송곳니
        box(m, "head", 2.2 * s, top + 2.2 * s, -H / 2 - 1.2 * s, 1 * s, 2.5 * s, 1 * s, "#efe6c8")
        for sx in (-1, 1):
            box(m, "head", sx * (H / 2 + 1 * s), top + H * 0.5, 0.5 * s, 2 * s, 2 * s, 1 * s, skin,
                rot=[0, 0, sx * -25])  # 귀
        box(m, "head", 0, top + H, 1 * s, 2 * s, 1.5 * s, H - 2 * s, "#1e1e1e")  # 상투
    elif head == "bull":
        box(m, "head", 0, top + 1 * s, -H / 2 - 2 * s, H * 0.7, H * 0.55, 4 * s, "#5a3a22")  # 주둥이
        box(m, "head", 0, top + 1.6 * s, -H / 2 - 4.2 * s, 2.6 * s, 1.2 * s, 0.6 * s, "#f0c040")  # 코뚜레
        for sx in (-1, 1):
            box(m, "head", sx * (H / 2 + 2 * s), top + H * 0.75, 0, 5 * s, 1.6 * s, 1.6 * s, "#ece3c8")
            box(m, "head", sx * (H / 2 + 4.2 * s), top + H * 0.75, 0, 1.6 * s, 4 * s, 1.6 * s, "#ece3c8")
    elif head == "cyclops":
        box(m, "head", 0, top + H, 0, H + 0.4 * s, 1 * s, H + 0.4 * s, "#3a2a1a")
    elif head == "medusa":
        if not face_skin:
            box(m, "head", 0, top + H - 1 * s, 0, H + 1 * s, 2 * s, H + 1 * s, "#d4af37")  # 금관
        else:
            box(m, "head", 0, top + H + 0.3 * s, 0, H + 1.2 * s, 0.8 * s, H + 1.2 * s, "#d4af37")  # 얇은 금 머리띠
        for i, (hx, hz) in enumerate([(-3, -2), (0, -3), (3, -2), (-3.5, 1.5), (0, 2.5), (3.5, 1.5), (-1.5, 0), (1.5, 0)]):
            b = m.bone(f"snake{i}", [hx * s, top + H, hz * s], "head")
            for j in range(3):
                box(m, b, hx * s, top + H + j * 2.2 * s, hz * s, 1.4 * s, 2.4 * s, 1.4 * s,
                    ("#6f7556" if j % 2 == 0 else "#798158") if face_skin else ("#2f7d32" if j % 2 == 0 else "#4caf50"))
            box(m, b, hx * s, top + H + 6.6 * s, hz * s - 0.4 * s, 2 * s, 1.4 * s, 2.4 * s, "#555a43" if face_skin else "#1b5e20")
            box(m, b, hx * s - 0.5 * s, top + H + 7.4 * s, hz * s - 1.65 * s, 0.4 * s, 0.4 * s, 0.1 * s, "#ffd200")
            box(m, b, hx * s + 0.5 * s, top + H + 7.4 * s, hz * s - 1.65 * s, 0.4 * s, 0.4 * s, 0.1 * s, "#ffd200")
    elif head == "siren":
        hair, hl = "#1fa39a", "#5fe0d2"
        box(m, "head", 0, top + H * 0.35, 0.6 * s, H + 1 * s, H * 0.75, H + 0.2 * s, hair)          # 머리 뒤·옆
        box(m, "head", 0, top + H, 0, H + 0.6 * s, 0.8 * s, H + 0.6 * s, hair)                        # 정수리
        box(m, "head", 0, top + H * 0.82, -H / 2 - 0.25 * s, H + 0.6 * s, H * 0.2, 0.5 * s, hair)    # 앞머리
        for sx in (-1, 1):
            box(m, "head", sx * (H / 2 + 0.25 * s), top - 4 * s, -H / 2 + 1.2 * s, 1 * s, H * 0.9 + 4 * s, 1.6 * s, hair)  # 옆 머리카락
            box(m, "head", sx * (H / 2 + 0.3 * s), top - 4 * s, -H / 2 + 1.2 * s, 0.6 * s, 2 * s, 1.2 * s, hl)
        box(m, "head", 0, top - 9 * s, H / 2 + 0.6 * s, H + 0.4 * s, 9 * s + H * 0.4, 1.4 * s, hair)  # 긴 뒷머리
        box(m, "head", 0, top - 9.4 * s, H / 2 + 0.6 * s, H - 1 * s, 1.2 * s, 1.2 * s, hl)
        box(m, "head", H / 2 + 0.2 * s, top + H * 0.7, -1 * s, 0.8 * s, 2.4 * s, 2.4 * s, "#f7a8c4")  # 조개 머리핀
        box(m, "head", H / 2 + 0.5 * s, top + H * 0.72, -0.4 * s, 0.4 * s, 1 * s, 1 * s, "#fff4e0")
    elif head == "harpy":
        box(m, "head", 0, top + H * 0.4, 1 * s, H + 1 * s, H * 0.8, H, "#7a5232")
        for i in range(3):
            box(m, "head", (i - 1) * 2 * s, top + H, 2 * s, 1 * s, 4 * s, 1 * s, "#c9a36b", rot=[-20, 0, (i - 1) * 15])
    # 소품
    if "horned_helmet" in extras:
        box(m, "head", 0, top + H * 0.55, 0, H + 1 * s, H * 0.5, H + 1 * s, "#5d5d5d")
        for sx in (-1, 1):
            box(m, "head", sx * (H / 2 + 2.5 * s), top + H * 0.8, 0, 4 * s, 1.6 * s, 1.6 * s, "#e8e0c8", rot=[0, 0, sx * 30])
            box(m, "head", sx * (H / 2 + 4 * s), top + H * 1.1, 0, 1.4 * s, 4 * s, 1.4 * s, "#e8e0c8")
    if "pauldrons" in extras:
        for sx, side in ((-1, "left_arm"), (1, "right_arm")):
            x = sx * (bw / 2 + 2 * s)
            box(m, side, x, top - 3 * s, 0, 6 * s, 3 * s, 6 * s, "#5d5d5d")
            box(m, side, x + sx * 1 * s, top, 0, 1 * s, 2.5 * s, 1 * s, "#cfcfcf")
    if "skull_mask" in extras:
        box(m, "head", 0, top + 1 * s, -H / 2 - 0.6 * s, H - 1 * s, H - 2 * s, 0.6 * s, "#efe6c8")
        for x in (-1.8, 1.8):
            box(m, "head", x * s, top + H * 0.5, -H / 2 - 0.8 * s, 1.6 * s, 1.6 * s, 0.4 * s, "#2b8a2b")
        for i in range(4):
            box(m, "head", (i - 1.5) * 2 * s, top + H, 1 * s, 1 * s, 5 * s, 1 * s, "#d33" if i % 2 else "#eee",
                rot=[-15, 0, (i - 1.5) * 12])
    if "hood" in extras:
        box(m, "head", 0, top + 1 * s, 0.6 * s, H + 1.2 * s, H + 0.6 * s, H + 1 * s, "#3d5a2a")
    if "fish_tail" in extras or "snake_tail" in extras:
        snake = "snake_tail" in extras
        main, alt = (("#5d6b45", "#798158") if face_skin else ("#2f6b2f", "#4f8f3a")) if snake else ("#13897e", "#29b3a5")
        prev = "body"
        y, z = hip, 0
        for i in range(5):
            b = m.bone(f"tail{i}", [0, y, z], prev)
            w = (bw - i * 1.2 * s)
            box(m, b, 0, max(0, y - 3.5 * s), z, w, 4 * s, 5 * s, main if i % 2 == 0 else alt)
            y = max(0, y - 3.5 * s)
            z += 4 * s if i >= 2 else 1 * s
            prev = b
        if not snake:
            box(m, prev, 0, y, z + 2 * s, 9 * s, 1 * s, 5 * s, "#58d6c8")  # 꼬리 지느러미
    # 무기
    hand_x = bw / 2 + 2 * s
    hy = top - A
    # 주먹(팔 끝 바로 위)을 자루가 앞뒤로 관통하고, 무기 머리는 앞(-Z) 끝에 붙는다.
    # 평소 자세에서 팔을 앞으로 들어 올리므로 무기가 앞쪽 위를 향한다.
    fy = hy + 1.2 * s          # 주먹 높이
    R = "right_arm"
    def W(bone, y, z, w, h, d, c, x=None):
        box(m, bone, hand_x if x is None else x, y * s + fy, z * s, w * s, h * s, d * s, c)
    STEEL, STEEL_L, STEEL_D, EDGE = "#9a9ea6", "#b8bcc4", "#5a5d63", "#eef2f6"
    GOLD, LEATHER, BONE_C = "#d4af37", "#3a2414", "#e8e0c8"
    if weapon == "axe":
        W(R, -0.6, -5.5, 1.2, 1.2, 15, "#6b4a2b")                 # 자루
        for z in (0.6, -2.2):
            W(R, -0.75, z, 1.5, 1.5, 1.6, LEATHER)                 # 손잡이 감개
        W(R, -0.9, 2.4, 1.8, 1.8, 1.2, STEEL_D)                    # 자루 끝 쇠
        W(R, -0.9, -11.5, 1.6, 1.8, 2.4, STEEL_D)                  # 날 소켓
        W(R, 0.9, -11.6, 0.8, 1.8, 2.6, STEEL)                     # 날 목
        W(R, 2.7, -12.0, 0.8, 1.8, 3.8, STEEL)                     # 날 몸통
        W(R, 4.5, -12.4, 0.8, 1.4, 5.2, STEEL_L)                   # 수염처럼 벌어진 날
        W(R, 5.9, -12.5, 0.7, 0.7, 6.0, EDGE)                      # 번뜩이는 날 끝
        W(R, 2.9, -12.0, 1.0, 0.6, 0.6, GOLD)                      # 리벳
        W(R, -2.5, -11.5, 0.8, 1.6, 1.2, STEEL)                    # 뒤쪽 스파이크
        W(R, -3.5, -11.5, 0.5, 1.0, 0.6, EDGE)
    elif weapon == "great_axe":
        W(R, -0.8, -8.5, 1.6, 1.6, 22, "#3b2a1a")                  # 긴 자루
        for z in (0.4, -2.6, -5.6):
            W(R, -1.0, z, 2.0, 2.0, 1.4, LEATHER)                  # 감개
        W(R, -1.2, 2.8, 2.2, 2.2, 1.0, STEEL_D)
        W(R, -1.0, 4.0, 1.2, 1.2, 1.6, STEEL)                      # 자루 끝 가시
        W(R, -1.3, -16.5, 2.2, 2.6, 3.2, STEEL_D)                  # 소켓
        W(R, 1.3, -16.5, 1.0, 2.0, 4.0, "#7d8188")                 # 초승달 날 (안쪽부터)
        W(R, 3.3, -16.8, 1.0, 2.4, 6.6, STEEL)
        W(R, 5.7, -17.0, 1.0, 2.4, 9.0, STEEL_L)
        W(R, 8.1, -17.0, 0.9, 0.8, 9.4, EDGE)                      # 날 끝
        for z in (-12.0, -22.0):
            W(R, 7.0, z, 0.9, 3.4, 1.4, STEEL_L)                   # 초승달 뿔
            W(R, 10.4, z + (0.4 if z > -17 else -0.4), 0.7, 1.0, 1.0, EDGE)
        W(R, 4.6, -17.0, 1.2, 0.5, 4.4, "#b02020")                 # 붉은 룬
        W(R, 6.2, -17.0, 1.2, 0.5, 2.0, "#b02020")
        W(R, -4.3, -16.5, 1.0, 3.0, 4.0, STEEL)                    # 아래쪽 보조날
        W(R, -4.9, -16.5, 0.9, 0.6, 4.6, EDGE)
        W(R, -0.7, -16.5, 2.8, 2.2, 2.0, BONE_C)                   # 해골 장식
        W(R, 0.1, -16.0, 3.0, 0.6, 0.5, "#1a1a1a")                 # 눈구멍
        W(R, 0.1, -17.0, 3.0, 0.6, 0.5, "#1a1a1a")
        W(R, -1.3, -16.5, 2.2, 0.6, 1.6, "#cfc6ac")                # 턱
    elif weapon == "double_axe":
        W(R, -0.7, -6.5, 1.4, 1.4, 19, "#5a3a22")                  # 자루
        for z in (0.2, -2.6):
            W(R, -0.85, z, 1.7, 1.7, 1.6, LEATHER)
        W(R, -1.0, 3.4, 1.8, 1.8, 1.0, GOLD)
        for sy in (1, -1):                                          # 위·아래 굽은 양날
            def Y(a, h): return a if sy > 0 else -a - h
            W(R, Y(1.0, 2.0), -13.5, 1.0, 2.0, 3.2, STEEL)
            W(R, Y(3.0, 2.2), -13.5, 1.0, 2.2, 5.0, STEEL_L)
            W(R, Y(5.2, 0.8), -13.5, 0.9, 0.8, 6.0, EDGE)
            for z in (-10.2, -16.8):
                W(R, Y(5.0, 2.0), z, 0.9, 2.0, 1.2, STEEL_L)       # 끝이 휘어 올라감
        W(R, -1.3, -13.5, 2.0, 2.6, 2.6, "#6a6a6a")                # 중앙 고정쇠
        W(R, -0.5, -13.5, 2.2, 1.0, 1.0, GOLD)                     # 문양
        W(R, -2.6, -13.5, 0.6, 1.4, 0.6, GOLD)
        W(R, 1.5, -13.5, 0.6, 1.4, 0.6, GOLD)
    elif weapon == "bow":
        # 왼손이 활 가운데를 쥐고, 활대는 팔과 수직(로컬 Z). 활 끝은 리커브로 다시 바깥으로 휜다.
        lx, gy = -hand_x, fy - 0.6 * s
        def BW(y, z, w, h, d, c):
            box(m, "left_arm", lx, gy + y * s, z * s, w * s, h * s, d * s, c)
        BW(-0.5, 0, 1.6, 2.0, 2.4, LEATHER)                          # 손잡이 감개
        BW(-0.2, 0, 1.8, 0.4, 2.6, GOLD)
        for zc, dy in [(2.4, 0.0), (4.8, 0.5), (7.0, 1.3), (8.8, 2.3)]:
            for sg in (-1, 1):
                BW(dy, sg * zc, 1.0, 1.1, 2.6, "#7a5232")           # 활대
        for sg in (-1, 1):
            BW(0.4, sg * 3.6, 1.2, 1.3, 0.6, GOLD)                  # 금테
            BW(1.7, sg * 6.0, 1.2, 1.2, 0.6, "#2f5d3a")             # 녹색 감개
            BW(2.6, sg * 10.1, 0.9, 1.0, 1.2, BONE_C)               # 리커브 뿔 끝
            BW(2.0, sg * 11.0, 0.8, 1.0, 0.9, BONE_C)
            BW(1.4, sg * 11.6, 0.6, 0.8, 0.6, "#cfc6ac")
        BW(2.9, 0, 0.25, 0.25, 20.4, "#eeeeee")                     # 시위
        BW(0.5, 0, 0.3, 0.3, 6.0, "#8a6a3a")                        # 걸어 둔 화살대
        BW(0.3, -3.4, 0.6, 0.7, 0.9, STEEL_L)                       # 화살촉
        BW(0.4, 3.0, 0.7, 0.6, 1.0, "#c0392b")                      # 깃
    elif weapon == "staff":
        for i in range(5):                                          # 울퉁불퉁한 나무 마디
            dx = (0.25 if i % 2 else -0.25) * s
            box(m, R, hand_x + dx, fy + (-8 + i * 5.1) * s, -2.6 * s, 1.3 * s, 5.4 * s, 1.3 * s,
                "#5a3a22" if i % 2 else "#4a2f1a")
        for y in (2.0, 10.2):
            W(R, y, -2.6, 1.9, 1.0, 1.9, "#3e2814")                # 옹이
        W(R, -0.6, -2.6, 1.8, 2.2, 1.8, LEATHER)                   # 손잡이 감개
        for dz in (-1.5, 1.5):
            W(R, 17.6, -2.6 + dz, 0.8, 4.4, 0.8, "#4a2f1a")         # 두 갈래 가지
            W(R, 21.6, -2.6 + dz * 0.6, 0.7, 1.0, 0.7, "#4a2f1a")
        W(R, 16.6, -2.6, 2.6, 2.4, 2.6, BONE_C)                    # 해골
        W(R, 16.0, -2.6, 2.0, 0.7, 2.0, "#cfc6ac")                 # 턱
        for dx in (-0.6, 0.6):
            W(R, 17.6, -3.95, 0.7, 0.6, 0.2, "#7CFC00", x=hand_x + dx * s)   # 빛나는 눈
        W(R, 19.4, -2.6, 2.2, 2.2, 2.2, "#7CFC00")                 # 초록 보주
        W(R, 19.9, -2.6, 2.6, 1.2, 1.2, "#b6ff7a")
        W(R, 14.8, -2.6, 0.3, 2.0, 0.3, "#d8cfb0", x=hand_x + 1.3 * s)
        W(R, 12.6, -2.6, 0.3, 2.4, 1.0, "#c0392b", x=hand_x + 1.3 * s)   # 깃털
        W(R, 14.8, -2.6, 0.3, 2.0, 0.3, "#d8cfb0", x=hand_x - 1.3 * s)
        W(R, 12.4, -2.6, 0.3, 2.6, 1.0, "#f1c40f", x=hand_x - 1.3 * s)
        W(R, 13.0, -2.6, 1.0, 1.0, 1.0, BONE_C, x=hand_x - 1.3 * s)       # 뼈 구슬
    elif weapon == "club":
        W(R, -1.0, -2.5, 2.0, 2.0, 8, "#6b4a2b")                   # 손잡이
        W(R, -1.2, -0.4, 2.4, 2.4, 2.6, LEATHER)
        W(R, -1.6, -7.8, 3.6, 3.6, 3.6, "#5a3d22")                 # 굵어지는 목
        W(R, -2.7, -13.4, 5.4, 5.4, 7.6, "#5a3d22")                # 몽둥이 머리
        W(R, -2.2, -17.6, 4.4, 4.4, 1.0, "#4b3219")
        for z in (-10.4, -15.6):
            W(R, -3.0, z, 6.0, 6.0, 0.9, STEEL_D)                  # 쇠테
        for z in (-12.0, -15.0):                                    # 사방 대못
            W(R, 3.0, z, 0.9, 1.4, 0.9, STEEL_L)
            W(R, -4.1, z, 0.9, 1.4, 0.9, STEEL_L)
            W(R, -0.4, z, 0.9, 0.9, 0.9, STEEL_L, x=hand_x + 3.3 * s)
            W(R, -0.4, z, 0.9, 0.9, 0.9, STEEL_L, x=hand_x - 3.3 * s)
        W(R, -0.4, -18.6, 0.9, 0.9, 1.2, STEEL_L)                  # 끝 대못
        W(R, 1.6, -13.4, 1.2, 1.0, 1.2, "#3e2a16")                 # 옹이
    elif weapon == "trident":
        W(R, -8, -2.6, 1, 26, 1, "#3fb6a8")
        W(R, -8.6, -2.6, 1.4, 1.2, 1.4, GOLD)                      # 물미
        for y in (-1.0, 1.2):
            W(R, y, -2.6, 1.4, 0.6, 1.4, GOLD)                     # 손잡이 금테
        W(R, 16.4, -2.6, 1.8, 1.4, 1.8, GOLD)                      # 금 고리
        W(R, 17.8, -2.6, 0.9, 0.9, 5.6, GOLD)                      # 가로대
        W(R, 18.6, -2.6, 0.8, 6.0, 0.8, "#e0c050")                 # 가운데 갈래
        W(R, 24.6, -2.6, 0.5, 1.0, 0.5, EDGE)
        for dz in (-2.4, 2.4):
            W(R, 18.6, -2.6 + dz, 0.8, 4.4, 0.8, "#e0c050")        # 양쪽 갈래
            W(R, 21.4, -2.6 + dz * 1.3, 0.6, 1.0, 0.7, GOLD)       # 바깥 미늘
            W(R, 23.0, -2.6 + dz, 0.5, 0.8, 0.5, EDGE)
        W(R, 17.0, -2.6, 2.0, 0.5, 0.5, "#3fd0ff", x=hand_x)       # 보석
    hold_r = {"axe": "-40", "great_axe": "-40", "double_axe": "-40", "club": "-40", "staff": "-12", "trident": "-12"}.get(weapon)
    hold_l = "-80" if weapon == "bow" else None
    hitbox(m, max(bw, 8 * s) + 2 * s, (L + B + H) if legs != "none" else B + H)
    # 애니메이션
    walk = {"left_leg": {"rotation": (SWING.format(f=1, a=30), 0, 0)},
            "right_leg": {"rotation": ("-" + SWING.format(f=1, a=30), 0, 0)},
            "left_arm": {"rotation": ("-" + SWING.format(f=1, a=25), 0, 0)},
            "right_arm": {"rotation": (SWING.format(f=1, a=25), 0, 0)},
            "head": {"rotation": (SWING.format(f=2, a=3), 0, 0)}}
    idle = {"torso": {"rotation": (SWING.format(f=0.5, a=2), 0, 0)},
            "left_arm": {"rotation": (0, 0, SWING.format(f=0.5, a=-3))},
            "right_arm": {"rotation": (0, 0, SWING.format(f=0.5, a=3))}}
    for i in range(8):
        idle[f"snake{i}"] = {"rotation": (SWING.format(f=1, a=20), 0, f"math.cos(q.anim_time * 360 + {i * 45}) * 20")}
        walk[f"snake{i}"] = idle[f"snake{i}"]
    for i in range(5):
        wag = {"rotation": (0, f"math.sin(q.anim_time * 360 + {i * 50}) * {6 + i * 3}", 0)}
        idle[f"tail{i}"] = wag
        walk[f"tail{i}"] = wag
    if hold_r:   # 무기를 든 팔은 앞으로 들고 있는다
        idle["right_arm"] = {"rotation": (f"{hold_r} + " + SWING.format(f=0.5, a=3), 0, 0)}
        walk["right_arm"] = {"rotation": (f"{hold_r} + " + SWING.format(f=1, a=8), 0, 0)}
    if hold_l:
        idle["left_arm"] = {"rotation": (f"{hold_l} + " + SWING.format(f=0.5, a=2), "10", 0)}
        walk["left_arm"] = {"rotation": (f"{hold_l} + " + SWING.format(f=1, a=6), "10", 0)}
    if "wings" in extras:
        flap = {"left_arm": {"rotation": (0, 0, "-30 - " + SWING.format(f=2, a=35))},
                "right_arm": {"rotation": (0, 0, "30 + " + SWING.format(f=2, a=35))}}
        idle.update(flap)
        walk.update(flap)
    m.anim("idle", 2, idle)
    m.anim("walk", 1, walk)
    swing0 = hold_r or "0"
    if weapon == "bow":
        m.anim("attack", 0.7, {"left_arm": {"rotation": ("-85", "10", 0)},
                               "right_arm": {"rotation": ("-85", "-30 + math.sin(q.anim_time * 257) * 25", 0)},
                               "head": {"rotation": (0, "8", 0)}}, loop="once")
        return m
    m.anim("attack", 0.5, {"right_arm": {"rotation": (f"{swing0} - 100 * math.sin(q.anim_time * 360)", 0, 0)},
                           "left_arm": {"rotation": (f"{hold_l or '0'} - 50 * math.sin(q.anim_time * 360)", 0, 0)},
                           "torso": {"rotation": ("10 * math.sin(q.anim_time * 360)", 0, 0)}}, loop="once")
    return m

# ---------------------------------------------------------------- 네발짐승

def quadruped(name, s=1.0, fur="#555555", belly=None, length=24, width=12, height=10, leg=12,
              heads=1, head_kind="wolf", wings=None, tail="bushy", tail_len=4, neck=0, extras=(), seed=0):
    m = Model(name, seed)
    belly = belly or fur
    L, W, Hh, LG = length * s, width * s, height * s, leg * s
    m.bone("body", [0, LG, 0])
    box(m, "body", 0, LG, 0, W, Hh, L, fur)
    box(m, "body", 0, LG - 0.5 * s, 0, W - 2 * s, 1 * s, L - 4 * s, belly)
    if "mane" in extras:
        box(m, "body", 0, LG + Hh - 1 * s, -L / 2 + 4 * s, W + 2 * s, 5 * s, 9 * s, extras_color(extras, "mane"))
    if "spikes" in extras:
        for i in range(5):
            box(m, "body", 0, LG + Hh, -L / 2 + (i + 1) * L / 6, 1.4 * s, 3 * s, 2 * s, "#e8dcc0", rot=[20, 0, 0])
    # 다리
    lw = max(3, W / 3.2)
    for nm, sx, sz in (("leg_fl", -1, -1), ("leg_fr", 1, -1), ("leg_bl", -1, 1), ("leg_br", 1, 1)):
        x, z = sx * (W / 2 - lw / 2), sz * (L / 2 - lw / 2 - 1 * s)
        m.bone(nm, [x, LG, z], "body")
        box(m, nm, x, 1.5 * s, z, lw, LG - 1.5 * s + 1, lw, fur)
        foot = "#d8b23a" if ("talons" in extras and sz < 0) else extras_color(extras, "hoof", fur if head_kind != "horse" else "#3a3a3a")
        box(m, nm, x, 0, z - 0.4 * s, lw + 0.6 * s, 2 * s, lw + 1.2 * s, foot)
    # 목/머리
    front_z = -L / 2
    top = LG + Hh
    head_specs = [(0, 0)] if heads == 1 else [(-W / 3, 18), (0, 0), (W / 3, -18)]
    for hi, (hx, yaw) in enumerate(head_specs):
        prev = "body"
        y, z = top - 3 * s, front_z
        for ni in range(neck):
            nb = m.bone(f"neck{hi}_{ni}", [hx, y, z], prev)
            box(m, nb, hx, y - 1 * s, z - 3 * s, W * 0.45, 6 * s, 7 * s, fur, rot=[-35, 0, 0], pivot=[hx, y, z])
            y += 4 * s
            z -= 3.5 * s
            prev = nb
        hb = m.bone(f"head{hi}" if heads > 1 else "head", [hx, y, z], prev, rotation=(0, yaw, 0))
        hs = (8 if head_kind != "dragon" else 9) * s
        eye_c = "#ff2a00" if "red_eyes" in extras else "#ffd24a"
        if head_kind in ("wolf", "dog"):
            hf = {"north": ("art", face(m, "wolf", fur, eye_c))}
        elif head_kind == "dragon":
            style = "eye_kind" if "kind_eyes" in extras else "eye_fierce"
            ec = "#4fc3ff" if style == "eye_kind" else "#ffd000"
            hf = {"east": ("art", face(m, style, fur, ec)), "west": ("art", face(m, style, fur, ec, mirror=True))}
        elif head_kind == "horse":
            k = face(m, "side_eye", fur, "#2a2140", extra={"D": "#ffffff", "e": shade(fur, -30)})
            hf = {"east": ("art", k), "west": ("art", k)}
        elif head_kind == "eagle":
            k = face(m, "side_eye", "#f2eee2", "#ffb000")
            hf = {"east": ("art", k), "west": ("art", k)}
        else:
            hf = None
        box(m, hb, hx, y - 2 * s, z - hs / 2, hs, hs, hs, fur, faces=hf)
        snout_c = fur if head_kind not in ("eagle",) else "#e9e2d0"
        if head_kind in ("wolf", "dog"):
            box(m, hb, hx, y - 2 * s, z - hs - 2 * s, hs * 0.55, hs * 0.45, 4 * s, belly)
            box(m, hb, hx, y + hs * 0.18 - 2 * s, z - hs - 4.1 * s, 1.6 * s, 1.2 * s, 0.4 * s, "#111111")
            for sx in (-1, 1):
                box(m, hb, hx + sx * hs * 0.3, y + hs - 2 * s, z - hs / 2 + 1 * s, 2 * s, 3 * s, 1.2 * s, fur)
                box(m, hb, hx + sx * 1.0 * s, y - 2.6 * s, z - hs - 3.4 * s, 0.6 * s, 1.4 * s, 0.6 * s, "#f0ead8")
        elif head_kind == "horse":
            box(m, hb, hx, y - 3 * s, z - hs - 3 * s, hs * 0.6, hs * 0.6, 6 * s, fur)
            for sx in (-1, 1):
                box(m, hb, hx + sx * hs * 0.28, y + hs - 2 * s, z - hs / 2 + 1 * s, 1.4 * s, 3 * s, 1.2 * s, fur)
            box(m, hb, hx, y + hs * 0.2 - 2 * s, z + 1 * s, 1.6 * s, hs + 2 * s, 4 * s, extras_color(extras, "mane"))
            if "horn" in extras:
                box(m, hb, hx, y + hs - 2 * s, z - hs + 1 * s, 1 * s, 5 * s, 1 * s, "#ffe680", rot=[-25, 0, 0])
        elif head_kind == "eagle":
            box(m, hb, hx, y - 2.1 * s, z - hs / 2, hs + 0.2 * s, hs + 0.2 * s, hs + 0.2 * s, "#f2eee2", faces=hf)
            box(m, hb, hx, y - 1 * s, z - hs - 2.5 * s, 2.6 * s, 3 * s, 4 * s, "#f0b400")
            box(m, hb, hx, y - 2.4 * s, z - hs - 4 * s, 2 * s, 2 * s, 1.5 * s, "#f0b400")
            for i in range(3):
                box(m, hb, hx + (i - 1) * 2 * s, y + hs - 2 * s, z + 1 * s, 1.4 * s, 1 * s, 5 * s, "#d8cdb2", rot=[25, 0, 0])
        elif head_kind == "dragon":
            box(m, hb, hx, y - 2.5 * s, z - hs - 4 * s, hs * 0.7, hs * 0.45, 8 * s, fur)          # 위 주둥이
            m.bone("jaw", [hx, y - 2 * s, z - hs / 2], hb)
            box(m, "jaw", hx, y - 4.5 * s, z - hs - 3 * s, hs * 0.62, 2 * s, 7.5 * s, belly)      # 아래턱
            for sx in (-1, 1):
                box(m, hb, hx + sx * hs * 0.3, y + hs - 2 * s, z + 1 * s, 1.6 * s, 1.6 * s, 7 * s, "#eadfc4", rot=[25, 0, 0])
                box(m, hb, hx + sx * 1.2 * s, y - 2.2 * s, z - hs - 7.6 * s, 0.8 * s, 0.8 * s, 0.4 * s, "#1a1a1a")
            for i in range(3):
                box(m, hb, hx, y + hs - 2 * s, z - hs / 2 + 2 + i * 2.5 * s, 1 * s, 2 * s, 1.4 * s, "#eadfc4")
    # 날개
    if wings:
        mem, arm = wings
        for side, sx in (("wing_l", -1), ("wing_r", 1)):
            x0 = sx * W / 2
            wz = front_z + L * 0.3
            m.bone(side, [x0, top - 1 * s, wz], "body")
            span = (26 if head_kind == "dragon" else 18) * s
            box(m, side, x0 + sx * span / 2, top - 1 * s, wz, span, 1.4 * s, 2 * s, arm)
            box(m, side, x0 + sx * span / 2, top - 0.8 * s, wz + (7 if head_kind == "dragon" else 5) * s, span - 2 * s, 0.6 * s,
                (12 if head_kind == "dragon" else 9) * s, mem)
            m.bone(side + "_tip", [x0 + sx * span, top - 1 * s, wz], side)
            box(m, side + "_tip", x0 + sx * (span + span * 0.4), top - 1 * s, wz, span * 0.8, 1.2 * s, 1.6 * s, arm)
            box(m, side + "_tip", x0 + sx * (span + span * 0.38), top - 0.8 * s, wz + 5 * s, span * 0.75, 0.6 * s, 9 * s, mem)
    # 꼬리: 마디가 이전 마디 끝에서 바로 이어지고 살짝 겹쳐서 틈이 없다
    #   (두께, 길이, 처짐 각도°, 색) — 각도는 +면 아래로 처진다
    mane_c = extras_color(extras, "mane")
    if tail == "bushy":
        spec = [(3.0, 5.0, 25, fur), (3.8, 5.0, 38, fur), (3.4, 4.6, 50, "#d9d0c0")]
    elif tail == "dragon":
        spec = [(max(2, (W / s * 0.5 - i * 1.6)), 7.0, 6 + i * 2, fur) for i in range(tail_len)]
    elif tail == "tuft":
        spec = [(1.5, 5.0, 30 + i * 12, fur) for i in range(tail_len)]
    elif tail == "horse":
        spec = [(3.2, 6.0, 55, mane_c), (3.0, 6.0, 72, mane_c)]
    else:
        spec = []
    spec = spec[:max(tail_len, 1)] if tail != "horse" else spec
    prev = "body"
    tz = L / 2 - 1.0 * s
    ty = top - 2.5 * s
    for i, (th, ln, ang, col) in enumerate(spec):
        th, ln = th * s, ln * s
        tb = m.bone(f"tail{i}", [0, ty, tz], prev)
        m.cube(tb, [-th / 2, ty - th / 2, tz - 0.6 * s], [th / 2, ty + th / 2, tz + ln + 0.6 * s], col,
               rot=[ang, 0, 0], pivot=[0, ty, tz])
        if tail == "dragon":   # 등 가시
            m.cube(tb, [-0.5 * s, ty + th / 2 - 0.2 * s, tz + ln * 0.3], [0.5 * s, ty + th / 2 + 1.8 * s, tz + ln * 0.6],
                   "#eadfc4", rot=[ang, 0, 0], pivot=[0, ty, tz])
        r = math.radians(ang)
        ty, tz = ty - ln * math.sin(r), tz + ln * math.cos(r)
        prev = tb
    if tail == "tuft" and spec:   # 꼬리 끝 털뭉치
        m.cube(prev, [-1.6 * s, ty - 1.6 * s, tz - 1.0 * s], [1.6 * s, ty + 1.6 * s, tz + 2.2 * s], "#6b4a2b")
    tail_len = len(spec)
    hitbox(m, max(W, 12 * s), LG + Hh + 4 * s)
    # 애니메이션
    legsw = lambda f, a: {"leg_fl": {"rotation": (SWING.format(f=f, a=a), 0, 0)},
                          "leg_br": {"rotation": (SWING.format(f=f, a=a), 0, 0)},
                          "leg_fr": {"rotation": ("-" + SWING.format(f=f, a=a), 0, 0)},
                          "leg_bl": {"rotation": ("-" + SWING.format(f=f, a=a), 0, 0)}}
    tailwag = {f"tail{i}": {"rotation": (0, f"math.sin(q.anim_time * 360 + {i * 40}) * {5 + i * 3}", 0)} for i in range(tail_len)}
    flap = {}
    if wings:
        flap = {"wing_l": {"rotation": (0, 0, SWING.format(f=1.5, a=35))},
                "wing_r": {"rotation": (0, 0, "-" + SWING.format(f=1.5, a=35))},
                "wing_l_tip": {"rotation": (0, 0, SWING.format(f=1.5, a=20))},
                "wing_r_tip": {"rotation": (0, 0, "-" + SWING.format(f=1.5, a=20))}}
        fold = {"wing_l": {"rotation": (0, "-20", "40 + " + SWING.format(f=0.5, a=4))},
                "wing_r": {"rotation": (0, "20", "-40 - " + SWING.format(f=0.5, a=4))},
                "wing_l_tip": {"rotation": (0, 0, "-120")}, "wing_r_tip": {"rotation": (0, 0, "120")}}
    idle = dict(tailwag)
    heads_names = ["head"] if heads == 1 else [f"head{i}" for i in range(heads)]
    for i, h in enumerate(heads_names):
        idle[h] = {"rotation": (SWING.format(f=0.5, a=4), f"math.sin(q.anim_time * 180 + {i * 70}) * 8", 0)}
    if wings:
        idle.update(fold)
    walk = dict(tailwag)
    walk.update(legsw(1, 28))
    walk.update(flap)
    for h in heads_names:
        walk[h] = {"rotation": (SWING.format(f=2, a=4), 0, 0)}
    m.anim("idle", 2, idle)
    m.anim("walk", 1, walk)
    atk = {h: {"rotation": ("-25 * math.sin(q.anim_time * 360)", 0, 0)} for h in heads_names}
    atk["jaw"] = {"rotation": ("30 * math.sin(q.anim_time * 360)", 0, 0)}
    m.anim("attack", 0.5, atk, loop="once")
    if wings:
        fly = dict(flap)
        fly.update(tailwag)
        m.anim("fly", 1, fly)
    return m

def extras_color(extras, key, default="#e0e0e0"):
    for e in extras:
        if isinstance(e, tuple) and e[0] == key:
            return e[1]
    return default



# ---------------------------------------------------------------- 동양풍 용 (이그니스)

def eastern_dragon(name, s=1.6, red="#b3221b", red2="#8a1711", gold="#f2b632", mane="#ff8a1e",
                   antler="#f1e3c0", whisker="#ffd36b", pearl="#bfe8ff", segments=10, seed=21):
    """뱀처럼 긴 몸, 짧은 네 다리, 사슴뿔, 수염, 갈기, 여의주"""
    m = Model(name, seed)
    y0 = 22 * s              # 떠 있는 높이
    seg_len = 7 * s
    m.bone("body", [0, y0, 0])
    # 몸통 마디 (앞 → 뒤 = +Z), 서로 중첩된 뼈대라서 물결치듯 움직인다
    prev, z = "body", 0.0
    for i in range(segments):
        t = i / (segments - 1)
        w = (8.5 - 5.5 * t * t) * s
        b = m.bone(f"seg{i}", [0, y0, z], prev)
        box(m, b, 0, y0 - w / 2, z + seg_len / 2, w, w, seg_len + 0.6 * s, red if i % 2 == 0 else red2)
        box(m, b, 0, y0 - w / 2 - 0.15 * s, z + seg_len / 2, w * 0.7, 0.6 * s, seg_len, gold)          # 금빛 배
        if i < segments - 1:                                                                             # 등 갈기
            box(m, b, 0, y0 + w / 2 - 0.2 * s, z + seg_len / 2, 0.8 * s, (2.6 - 1.2 * t) * s, seg_len * 0.8,
                mane if i % 2 == 0 else gold, rot=[-12, 0, 0])
        for sx in (-1, 1):                                                                               # 옆 비늘 줄
            box(m, b, sx * (w / 2 + 0.05 * s), y0 - 0.4 * s, z + seg_len / 2, 0.3 * s, 0.8 * s, seg_len * 0.7, shade(red, 30))
        # 다리 (2번째, 7번째 마디)
        if i in (1, 6):
            for sx, side in ((-1, "l"), (1, "r")):
                lb = m.bone(f"leg{i}{side}", [sx * w / 2, y0 - w / 4, z + seg_len / 2], b)
                box(m, lb, sx * (w / 2 + 1.2 * s), y0 - w / 4 - 6 * s, z + seg_len / 2, 2.2 * s, 6 * s, 2.4 * s, red2)
                box(m, lb, sx * (w / 2 + 1.2 * s), y0 - w / 4 - 7 * s, z + seg_len / 2 - 0.8 * s, 2.8 * s, 1.2 * s, 3.4 * s, gold)
                for k in (-1, 0, 1):                                                                       # 발톱
                    box(m, lb, sx * (w / 2 + 1.2 * s) + k * 0.9 * s, y0 - w / 4 - 7.4 * s, z + seg_len / 2 - 2.6 * s,
                        0.5 * s, 0.6 * s, 1.4 * s, antler)
                box(m, lb, sx * (w / 2 + 0.4 * s), y0 - w / 4 - 1.2 * s, z + seg_len / 2 + 1.4 * s, 0.6 * s, 2.4 * s, 2.4 * s, mane)  # 다리 털
        if i == 1:   # 오른 앞발에 여의주
            box(m, "leg1r", w / 2 + 1.2 * s, y0 - w / 4 - 9.6 * s, z + seg_len / 2 - 2.2 * s, 3.2 * s, 3.2 * s, 3.2 * s, pearl)
            box(m, "leg1r", w / 2 + 1.2 * s, y0 - w / 4 - 9.0 * s, z + seg_len / 2 - 3.85 * s, 1.0 * s, 1.0 * s, 0.2 * s, "#ffffff")
        z += seg_len
        prev = b
    # 꼬리 끝 불꽃 술
    tb = m.bone("tail_tip", [0, y0, z], prev)
    for k, (dy, rz) in enumerate([(0, 0), (1.2, 30), (-1.2, -30)]):
        box(m, tb, 0, y0 - 1 * s + dy * s, z + 3 * s, 0.6 * s, 2.4 * s, 6 * s, mane if k == 0 else gold, rot=[rz, 0, 0], pivot=[0, y0, z])

    # 머리 (몸 앞쪽 -Z)
    hs = 8 * s
    hb = m.bone("head", [0, y0, 0], "body")
    eye = {"east": ("art", face(m, "eye_fierce", red, "#ffd000")),
           "west": ("art", face(m, "eye_fierce", red, "#ffd000", mirror=True))}
    box(m, hb, 0, y0 - hs / 2 + 0.6 * s, -hs / 2, hs, hs * 0.85, hs, red, faces=eye)                 # 머리
    box(m, hb, 0, y0 - hs / 2 + 1.4 * s, -hs - 4 * s, hs * 0.72, hs * 0.5, 8 * s, red)               # 긴 주둥이
    box(m, hb, 0, y0 + 0.2 * s, -hs - 7.4 * s, hs * 0.6, 1.2 * s, 1.2 * s, red2)                     # 콧등
    for sx in (-1, 1):
        box(m, hb, sx * 1.4 * s, y0 + 0.1 * s, -hs - 8.1 * s, 1.0 * s, 0.8 * s, 0.3 * s, "#1a0505")   # 콧구멍
        box(m, hb, sx * (hs * 0.38), y0 + hs * 0.32, -hs * 0.55, 1.0 * s, 1.2 * s, hs * 0.75, red2)   # 눈썹뼈
    m.bone("jaw", [0, y0 - hs / 2 + 1.4 * s, -hs * 0.6], hb)
    box(m, "jaw", 0, y0 - hs / 2 - 0.2 * s, -hs - 3.6 * s, hs * 0.62, 1.6 * s, 7.6 * s, gold)         # 아래턱
    for k in range(4):
        for sx in (-1, 1):
            box(m, "jaw", sx * hs * 0.24, y0 - hs / 2 + 1.4 * s, -hs - 1.4 * s - k * 1.6 * s, 0.6 * s, 0.9 * s, 0.6 * s, "#fff8e8")  # 이빨
    box(m, "jaw", 0, y0 - hs / 2 - 3.2 * s, -hs - 0.6 * s, 2.4 * s, 3.2 * s, 1.6 * s, mane)          # 턱수염
    # 사슴뿔 (가지 친 뿔)
    for sx in (-1, 1):
        ab = m.bone("antler_l" if sx < 0 else "antler_r", [sx * hs * 0.3, y0 + hs * 0.38, -hs * 0.1], hb)
        box(m, ab, sx * hs * 0.34, y0 + hs * 0.38, 1.6 * s, 1.1 * s, 1.1 * s, 7 * s, antler, rot=[-40, sx * 12, 0], pivot=[sx * hs * 0.3, y0 + hs * 0.38, -hs * 0.1])
        box(m, ab, sx * hs * 0.4, y0 + hs * 0.38 + 3 * s, 2 * s, 0.9 * s, 3.6 * s, 0.9 * s, antler, rot=[-15, 0, sx * -20])
        box(m, ab, sx * hs * 0.44, y0 + hs * 0.38 + 4.8 * s, 5 * s, 0.9 * s, 3.4 * s, 0.9 * s, antler, rot=[-30, 0, sx * -15])
        box(m, ab, sx * hs * 0.36, y0 + hs * 0.38 + 1.4 * s, 4.4 * s, 0.8 * s, 2.6 * s, 0.8 * s, antler, rot=[10, 0, sx * 25])
    # 수염 (길게 늘어지는 두 가닥, 흔들림)
    for sx in (-1, 1):
        wb = m.bone("whisker_l" if sx < 0 else "whisker_r", [sx * hs * 0.3, y0 + 0.4 * s, -hs - 7 * s], hb)
        box(m, wb, sx * (hs * 0.3 + 3 * s), y0 + 0.4 * s, -hs - 6.6 * s, 6 * s, 0.5 * s, 0.5 * s, whisker)
        box(m, wb, sx * (hs * 0.3 + 6.4 * s), y0 - 1.6 * s, -hs - 6.0 * s, 0.5 * s, 4 * s, 0.5 * s, whisker)
        box(m, wb, sx * (hs * 0.3 + 7.4 * s), y0 - 2.0 * s, -hs - 5.6 * s, 2 * s, 0.5 * s, 0.5 * s, whisker)
    # 머리 갈기 (뒤로 휘날림)
    mb = m.bone("mane", [0, y0 + hs * 0.2, hs * 0.2], hb)
    for k, (sx, dy, c) in enumerate([(-1, 0, mane), (1, 0, mane), (-1, 2, gold), (1, 2, gold), (0, 3, mane)]):
        box(m, mb, sx * hs * 0.32, y0 + hs * 0.05 + dy * s, hs * 0.2 + 3 * s, 2.2 * s, 2.0 * s, 7 * s, c,
            rot=[-20 - dy * 4, sx * 18, 0], pivot=[0, y0 + hs * 0.2, hs * 0.2])
    hitbox(m, 14 * s, 18 * s)

    # 애니메이션: 몸이 물결치듯
    def wave(speed, amp, ampx):
        ch = {f"seg{i}": {"rotation": (f"math.cos(q.anim_time * 360 * {speed} - {i * 40}) * {ampx}",
                                       f"math.sin(q.anim_time * 360 * {speed} - {i * 40}) * {amp}", 0)}
              for i in range(segments)}
        ch["tail_tip"] = {"rotation": (0, f"math.sin(q.anim_time * 360 * {speed} - {segments * 40}) * {amp * 1.5}", 0)}
        ch["head"] = {"rotation": (f"math.sin(q.anim_time * 360 * {speed}) * 5", f"math.sin(q.anim_time * 360 * {speed} + 40) * -{amp}", 0)}
        for wn, ph in (("whisker_l", 0), ("whisker_r", 90)):
            ch[wn] = {"rotation": (f"math.sin(q.anim_time * 360 * {speed * 1.5} + {ph}) * 15", 0, f"math.cos(q.anim_time * 360 * {speed} + {ph}) * 10")}
        ch["mane"] = {"rotation": (f"math.sin(q.anim_time * 360 * {speed * 2}) * 8", 0, 0)}
        for leg in ("leg1l", "leg1r", "leg6l", "leg6r"):
            ch[leg] = {"rotation": (f"math.sin(q.anim_time * 360 * {speed} + {0 if leg.endswith('l') else 180}) * 25", 0, 0)}
        return ch
    m.anim("idle", 3, wave(0.33, 6, 2))
    m.anim("walk", 1.5, wave(0.67, 12, 4))
    m.anim("fly", 1.5, wave(0.67, 12, 4))
    m.anim("attack", 0.6, {"head": {"rotation": ("-30 * math.sin(q.anim_time * 300)", 0, 0)},
                           "jaw": {"rotation": ("40 * math.sin(q.anim_time * 300)", 0, 0)},
                           "seg0": {"rotation": ("15 * math.sin(q.anim_time * 300)", 0, 0)}}, loop="once")
    return m


def _scale_rows():
    rows = []
    for y in range(16):
        r = ""
        for x in range(16):
            cx = (x + (y // 4 % 2) * 2) % 4; cy = y % 4
            if cy == 3 or (cy == 2 and cx in (0, 3)): r += "d"
            elif cy == 0 and cx in (1, 2): r += "l"
            elif cy == 1 and cx == 1: r += "h"
            else: r += "s"
        rows.append(r)
    return rows

def _belly_rows():
    return ["".join("d" if y % 4 == 3 else ("l" if y % 4 == 0 else "s") for x in range(16)) for y in range(16)]

def _membrane_rows():
    rows = []
    for y in range(16):
        r = ""
        for x in range(16):
            v = (abs((x * 2 + y) % 11 - 5) < 1) or (abs((x - y * 2) % 13 - 6) < 1)
            r += "v" if v else ("m" if (x + y) % 7 else "n")
        rows.append(r)
    return rows

def _horn_rows():
    return ["".join("d" if (x + y // 2) % 5 == 0 else ("l" if x < 4 else "s") for x in range(16)) for y in range(16)]

def western_dragon(name, s=1.5, red="#a51e16", red_d="#6e120d", belly="#d9a04a", horn="#e8dcc0", horn_d="#4a3428",
                   mem="#7d1a12", mem2="#5a0f0a", spike="#2e1c16", seed=33):
    """서양풍 드래곤: 비늘 질감, S자 목(5마디), 큰 뿔·볏·뺨 갑판, 박쥐 날개(물결 가장자리), 네 다리, 가시 꼬리"""
    m = Model(name, seed)
    S = lambda v: v * s
    def AF(key):
        return {f: ("art", key) for f in ("north", "south", "east", "west", "up", "down")}
    SC = AF(m.art("scale_red", _scale_rows(), {"s": red, "d": shade(red, -45), "l": shade(red, 30), "h": shade(red, 55)}))
    SD = AF(m.art("scale_dark", _scale_rows(), {"s": red_d, "d": shade(red_d, -35), "l": shade(red_d, 28), "h": shade(red_d, 45)}))
    BE = AF(m.art("belly", _belly_rows(), {"s": belly, "d": shade(belly, -60), "l": shade(belly, 30)}))
    ME = AF(m.art("membrane", _membrane_rows(), {"m": mem, "n": shade(mem, -12), "v": shade(mem, -40)}))
    ME2 = AF(m.art("membrane2", _membrane_rows(), {"m": mem2, "n": shade(mem2, -10), "v": shade(mem2, -30)}))
    HO = AF(m.art("horn", _horn_rows(), {"s": horn, "d": shade(horn, -60), "l": shade(horn, 20)}))
    m.bone("body", [0, S(18), 0])
    box(m, "body", 0, S(14), S(2), S(14), S(12), S(24), red, faces=SC)                          # 몸통
    box(m, "body", 0, S(19), S(-9.5), S(12), S(8), S(3), red, faces=SC)                          # 가슴 근육
    box(m, "body", 0, S(13.4), S(0), S(10), S(1.2), S(20), belly, faces=BE)                      # 배 비늘판
    box(m, "body", 0, S(16), S(-10.4), S(8), S(6), S(1), belly, faces=BE)                        # 가슴 비늘판
    for k in range(7):                                                                           # 등가시 (가운데 큰 것 + 양옆 작은 것)
        h = 3.6 - k * 0.3
        box(m, "body", 0, S(26), S(-10 + k * 3.6), S(1.0), S(h), S(2.6), spike, rot=[-25, 0, 0], pivot=[0, S(26), S(-10 + k * 3.6)])
        for sx in (-1, 1):
            box(m, "body", sx * S(2.4), S(25.8), S(-8.5 + k * 3.6), S(0.7), S(h * 0.5), S(1.6), spike, rot=[-25, 0, sx * 15], pivot=[sx * S(2.4), S(25.8), S(-8.5 + k * 3.6)])
    # ── 목 (5마디 S자) ──
    prev = "body"
    segs = [(23, -10, 8.0, -30), (25.6, -13.4, 7.4, -42), (28.8, -16.0, 6.9, -55), (32.0, -18.0, 6.5, -45), (34.6, -20.0, 6.2, -25)]
    for i, (y, z, w, rx) in enumerate(segs):
        b = m.bone(f"neck{i}", [0, S(y), S(z)], prev)
        box(m, b, 0, S(y - w / 2), S(z - 2.6), S(w), S(w), S(5.6), red, rot=[rx, 0, 0], pivot=[0, S(y), S(z)], faces=SC)
        box(m, b, 0, S(y + w / 2 - 0.2), S(z - 2.4), S(0.9), S(2.6 - i * 0.2), S(1.8), spike, rot=[rx - 20, 0, 0], pivot=[0, S(y), S(z)])
        box(m, b, 0, S(y - w / 2 - 0.1), S(z - 2.6), S(w * 0.6), S(0.5), S(4.6), belly, rot=[rx, 0, 0], pivot=[0, S(y), S(z)], faces=BE)
        prev = b
    # ── 머리 ──
    hb = m.bone("head", [0, S(36), S(-22)], prev)
    # 무서운 드래곤 눈: 깊은 눈구멍 + 무거운 눈썹뼈 + 빛나는 홍채 + 세로로 찢어진 동공 + 붉은 핏줄
    ER = ["BBBBBBBBBBBBBBBB",
          "SBBBBBBBBBBBBBBS",
          "dSKKBBBBBBBBKKSd",
          "ddKKKKKKKKKKKKdd",
          "dKKRRROOOORRRKKd",
          "KKROOYYYDYYOORKK",
          "KROYYWYYDYYWYORK",
          "KROYYYYYDYYYYORK",
          "KROYYYYYDYYYYORK",
          "KKROOYYYDYYOORKK",
          "dKKRROOOOOORRKKd",
          "ddKKKRRRRRRKKKdd",
          "dVddKKKKKKKKddVd",
          "ddVddddddddddVdd",
          "dSdVdSddSdVdSddd",
          "dddddddddddddddd"]
    EP = {"d": red, "S": shade(red, -45), "B": "#1a0806", "K": "#050101", "R": "#c4140c", "O": "#ff7a00",
          "Y": "#ffd000", "W": "#fff6c8", "D": "#000000", "V": "#ff3a1a"}
    eye = {"east": ("art", m.art("dragon_eye", ER, EP)), "west": ("art", m.art("dragon_eye_m", [r[::-1] for r in ER], EP))}
    skull = dict(SC); skull.update(eye)
    box(m, hb, 0, S(33), S(-25), S(8.4), S(7), S(9), red, faces=skull)                           # 두개골
    box(m, hb, 0, S(33.2), S(-32.5), S(6.2), S(4.6), S(7), red, faces=SC)                         # 주둥이
    box(m, hb, 0, S(37.6), S(-31), S(5), S(0.8), S(5), red_d, faces=SD)                           # 콧등
    for k in range(4):                                                                             # 뒤통수 볏
        box(m, hb, 0, S(39.6 - k * 0.6), S(-21 + k * 1.6), S(0.6), S(2.4 - k * 0.4), S(1.4), spike, rot=[-30, 0, 0])
    for sx in (-1, 1):
        box(m, hb, sx * S(1.6), S(36.4), S(-36.1), S(1.0), S(0.8), S(0.3), "#1a0505")             # 콧구멍
        box(m, hb, sx * S(1.6), S(37.2), S(-35), S(1.2), S(0.6), S(1.6), red_d)                    # 콧구멍 돌기
        box(m, hb, sx * S(3.9), S(38.6), S(-25.5), S(1.8), S(1.6), S(7), red_d, faces=SD)          # 눈썹뼈 (튀어나옴)
        box(m, hb, sx * S(4.3), S(39.6), S(-28.6), S(0.8), S(1.4), S(1.2), spike, rot=[20, 0, sx * 25])   # 눈썹 가시
        box(m, hb, sx * S(4.4), S(33.6), S(-24), S(0.6), S(3.2), S(5), red_d, faces=SD)            # 뺨 갑판
        for k in range(4):                                                                         # 윗니
            box(m, hb, sx * S(2.5), S(32.3), S(-29.5 - k * 1.6), S(0.6), S(1.1 if k else 1.8), S(0.6), "#fff8e8")
        box(m, hb, sx * S(3.2), S(38.8), S(-20), S(1.8), S(1.8), S(6), horn, rot=[12, sx * 12, 0], pivot=[sx * S(3.2), S(39.7), S(-23)], faces=HO)
        box(m, hb, sx * S(3.9), S(39.4), S(-15.5), S(1.4), S(1.4), S(5), horn, rot=[-12, sx * 16, 0], pivot=[sx * S(3.6), S(40.1), S(-18)], faces=HO)
        box(m, hb, sx * S(4.4), S(40.2), S(-12.0), S(1.0), S(1.0), S(3.4), horn_d, rot=[-35, sx * 20, 0], pivot=[sx * S(4.2), S(40.7), S(-13.6)])
        for k in range(3):                                                                         # 뺨 뿔
            box(m, hb, sx * S(4.6), S(34 + k * 1.6), S(-21.5 + k * 0.8), S(0.8), S(0.8), S(3.2 - k * 0.6), horn_d, rot=[30, sx * 35, 0])
    m.bone("jaw", [0, S(33), S(-27)], hb)
    box(m, "jaw", 0, S(31.4), S(-32), S(5.6), S(1.8), S(8.5), red_d, faces=SD)                    # 아래턱
    box(m, "jaw", 0, S(31.2), S(-31), S(3.6), S(0.4), S(6), belly, faces=BE)
    for sx in (-1, 1):
        for k in range(4):
            box(m, "jaw", sx * S(2.2), S(33.1), S(-29.6 - k * 1.6), S(0.6), S(0.9 if k else 1.5), S(0.6), "#fff8e8")
        box(m, "jaw", sx * S(2.4), S(30.4), S(-29), S(0.7), S(1.6), S(0.7), spike, rot=[25, 0, sx * 20])   # 턱 가시
    # ── 날개 ──
    for sx, sd in ((-1, "l"), (1, "r")):
        wb = m.bone(f"wing_{sd}", [sx * S(6), S(25), S(-4)], "body", rotation=(0, 0, sx * 24))
        box(m, wb, sx * S(12), S(24.8), S(-4), S(12), S(1.8), S(2.0), red_d, faces=SD)            # 위팔뼈
        for k in range(3):                                                                         # 날개막 1 (물결 가장자리)
            box(m, wb, sx * S(8 + k * 4), S(25.4), S(4.5 - (k % 2) * 1.2), S(4), S(0.3), S(15 - (k % 2) * 2.4), mem, faces=ME)
        fb = m.bone(f"wingf_{sd}", [sx * S(18), S(25), S(-4)], wb, rotation=(0, 0, -sx * 12))
        box(m, fb, sx * S(27), S(25.2), S(-4), S(18), S(1.3), S(1.5), red_d, faces=SD)            # 아래팔뼈
        box(m, fb, sx * S(36.4), S(25.8), S(-5.2), S(1.0), S(1.6), S(1.2), horn, faces=HO)       # 날개 발톱
        for k in range(4):                                                                         # 손가락뼈 + 물결 막
            fx = sx * S(20 + k * 5)
            ln = 20 - k * 3
            box(m, fb, fx, S(25.5), S(-3 + ln / 2), S(0.8), S(0.7), S(ln), red_d)
            box(m, fb, fx, S(25.3), S(-3 + ln + 0.6), S(1.0), S(0.9), S(1.2), horn)                # 손가락 끝 발톱
            for j in range(2):
                dl = ln - 2 - j * 2.2
                box(m, fb, fx + sx * S(1.25 + j * 2.5), S(25.6), S(-3 + dl / 2), S(2.5), S(0.3), S(dl),
                    mem if (k + j) % 2 == 0 else mem2, faces=ME if (k + j) % 2 == 0 else ME2)
    # ── 다리 ──
    for sx, sd in ((-1, "l"), (1, "r")):
        fl = m.bone(f"legf_{sd}", [sx * S(6), S(16), S(-7)], "body")
        box(m, fl, sx * S(7), S(1.6), S(-7), S(3.6), S(15), S(4), red_d, faces=SD)
        box(m, fl, sx * S(7.2), S(9), S(-7.4), S(4.2), S(4), S(4.6), red, faces=SC)               # 팔꿈치 근육
        box(m, fl, sx * S(7), S(0), S(-8), S(4.6), S(2), S(6), red_d, faces=SD)
        for k in (-1, 0, 1):
            box(m, fl, sx * S(7) + k * S(1.3), S(0), S(-11.6), S(0.7), S(1.1), S(1.8), horn, faces=HO)
        hl = m.bone(f"legh_{sd}", [sx * S(6.5), S(16), S(10)], "body")
        box(m, hl, sx * S(8), S(1.8), S(10), S(5.4), S(15.5), S(7), red, faces=SC)                # 허벅지
        box(m, hl, sx * S(8.4), S(10), S(11), S(6.2), S(6), S(8), red, faces=SC)                  # 허벅지 근육
        box(m, hl, sx * S(8), S(0), S(9), S(5), S(2.2), S(7.5), red_d, faces=SD)
        box(m, hl, sx * S(8), S(15), S(14), S(0.8), S(2.2), S(1.4), spike, rot=[-30, 0, 0])       # 허벅지 가시
        for k in (-1, 0, 1):
            box(m, hl, sx * S(8) + k * S(1.5), S(0), S(4.6), S(0.8), S(1.2), S(2.0), horn, faces=HO)
    # ── 꼬리 ──
    prev = "body"; z = 14.0
    for i in range(7):
        w = 7 - i * 0.8
        b = m.bone(f"tail{i}", [0, S(20 - i * 0.6), S(z)], prev)
        box(m, b, 0, S(20 - i * 0.6 - w / 2), S(z + 2.8), S(w), S(w), S(5.8), red, faces=SC if i % 2 == 0 else SD)
        box(m, b, 0, S(20 - i * 0.6 - w / 2 - 0.1), S(z + 2.8), S(w * 0.6), S(0.4), S(5), belly, faces=BE)
        box(m, b, 0, S(20 - i * 0.6 + w / 2 - 0.2), S(z + 2.6), S(0.8), S(2.4 - i * 0.22), S(2.0), spike, rot=[-25, 0, 0], pivot=[0, S(20 - i * 0.6 + w / 2), S(z + 2)])
        prev = b; z += 5.4
    tb = m.bone("tail_tip", [0, S(15.8), S(z)], prev)
    box(m, tb, 0, S(15.4), S(z + 2.4), S(5.6), S(0.8), S(5.6), spike, rot=[0, 45, 0], pivot=[0, S(15.8), S(z + 2.4)])
    box(m, tb, 0, S(15.2), S(z + 2.4), S(3), S(1.2), S(3), red_d, rot=[0, 45, 0], pivot=[0, S(15.8), S(z + 2.4)])
    hitbox(m, S(16), S(16))
    # ── 애니메이션 ──
    def base(speed, wamp, famp, tamp, legamp):
        ch = {}
        ch["wing_l"] = {"rotation": (0, 0, f"math.sin(q.anim_time * 360 * {speed}) * {wamp} - 10")}
        ch["wing_r"] = {"rotation": (0, 0, f"math.sin(q.anim_time * 360 * {speed}) * -{wamp} + 10")}
        ch["wingf_l"] = {"rotation": (0, 0, f"math.sin(q.anim_time * 360 * {speed} - 50) * {famp}")}
        ch["wingf_r"] = {"rotation": (0, 0, f"math.sin(q.anim_time * 360 * {speed} - 50) * -{famp}")}
        for i in range(7):
            ch[f"tail{i}"] = {"rotation": (f"math.sin(q.anim_time * 360 * {speed * 0.5} - {i * 30}) * 3", f"math.sin(q.anim_time * 360 * {speed * 0.5} - {i * 35}) * {tamp}", 0)}
        for i in range(5):
            ch[f"neck{i}"] = {"rotation": (f"math.sin(q.anim_time * 360 * {speed * 0.5} - {i * 25}) * 2.5", f"math.sin(q.anim_time * 180 * {speed * 0.5} - {i * 20}) * 2", 0)}
        ch["head"] = {"rotation": (f"math.sin(q.anim_time * 360 * {speed * 0.5}) * 4", f"math.sin(q.anim_time * 180 * {speed * 0.5}) * 8", 0)}
        ch["jaw"] = {"rotation": (f"math.max(0, math.sin(q.anim_time * 360 * {speed * 0.25})) * 8", 0, 0)}
        for leg, ph in (("legf_l", 0), ("legf_r", 180), ("legh_l", 180), ("legh_r", 0)):
            ch[leg] = {"rotation": (f"math.sin(q.anim_time * 360 * {speed} + {ph}) * {legamp}", 0, 0)}
        ch["body"] = {"rotation": (f"math.sin(q.anim_time * 360 * {speed}) * 1.5", 0, 0)}
        return ch
    m.anim("idle", 4, base(0.25, 6, 4, 6, 0))
    m.anim("walk", 1.6, base(0.62, 8, 5, 10, 18))
    fly = base(0.7, 38, 24, 8, 0)
    for leg in ("legf_l", "legf_r", "legh_l", "legh_r"):
        fly[leg] = {"rotation": (35, 0, 0)}
    m.anim("fly", 1.43, fly)
    m.anim("attack", 0.8, {"head": {"rotation": ("-35 * math.sin(q.anim_time * 225)", 0, 0)},
                           "neck4": {"rotation": ("-12 * math.sin(q.anim_time * 225)", 0, 0)},
                           "neck3": {"rotation": ("-8 * math.sin(q.anim_time * 225)", 0, 0)},
                           "jaw": {"rotation": ("45 * math.sin(q.anim_time * 225)", 0, 0)},
                           "wing_l": {"rotation": (0, 0, "-40 * math.sin(q.anim_time * 225)")},
                           "wing_r": {"rotation": (0, 0, "40 * math.sin(q.anim_time * 225)")}}, loop="once")
    return m


def _mat_rows(kind, rnd):
    """재질별 16x16 무늬 (글자: s 바탕, l 밝음, d 어두움, k 아주 어두움, h 하이라이트)"""
    R = []
    for y in range(16):
        r = ""
        for x in range(16):
            c = "s"
            if kind == "metal":
                if x == 0 or y == 0: c = "h"
                elif x == 15 or y == 15: c = "k"
                elif x == 1 or y == 1: c = "l"
                elif x == 14 or y == 14: c = "d"
                if (x, y) in ((2, 2), (13, 2), (2, 13), (13, 13)): c = "h"
                if (x, y) in ((3, 3), (14, 3), (3, 14), (14, 14)): c = "k"
                if c == "s" and (x + y * 3) % 17 == 0: c = "l"
            elif kind == "leather":
                if (x in (1, 14) or y in (1, 14)) and (x + y) % 3 == 0: c = "l"
                elif rnd.random() < 0.12: c = "d"
                elif rnd.random() < 0.06: c = "l"
            elif kind == "cloth":
                c = "l" if (x // 2 + y // 2) % 2 == 0 else "s"
                if (x % 2 == 0 and y % 4 == 1) or (y % 2 == 0 and x % 4 == 3): c = "d"
            elif kind == "skin":
                v = rnd.random()
                c = "d" if v < 0.1 else ("l" if v < 0.22 else "s")
                if rnd.random() < 0.03: c = "k"
            elif kind == "fur":
                col = (x * 7 + (y // 3) * 3) % 5
                c = "d" if col == 0 else ("l" if col == 3 else "s")
                if y % 5 == 4 and x % 3 == 1: c = "k"
            elif kind == "bone":
                c = "l" if rnd.random() < 0.15 else "s"
                if abs(x - (y * 0.6 + 3)) < 0.6 and y > 3: c = "d"
            elif kind == "scale":
                cx = (x + (y // 4 % 2) * 2) % 4; cy = y % 4
                if cy == 3 or (cy == 2 and cx in (0, 3)): c = "d"
                elif cy == 0 and cx in (1, 2): c = "l"
            r += c
        R.append(r)
    return R

def _material_of(hexc):
    r, g, b = hexrgb(hexc)
    mx, mn = max(r, g, b), min(r, g, b)
    v = mx / 255; sat = 0 if mx == 0 else (mx - mn) / mx
    if mx == mn: hue = 0
    elif mx == r: hue = (60 * (g - b) / (mx - mn)) % 360
    elif mx == g: hue = 60 * (b - r) / (mx - mn) + 120
    else: hue = 60 * (r - g) / (mx - mn) + 240
    if sat < 0.12 and v > 0.78: return "bone"
    if sat < 0.18: return "metal"
    if 15 <= hue <= 45 and v < 0.55: return "leather"
    if 15 <= hue <= 45 and v >= 0.55: return "skin"
    if 70 <= hue <= 160 and sat > 0.3: return "skin"
    return "cloth"

def texturize(m, override=None, seed=7):
    """모델의 단색 칸을 재질 무늬로 바꾼다. 많이 쓰인 색부터 최대 (32 - 기존 아트) 개.
    override: {색: 재질} 로 직접 지정 가능"""
    rnd = random.Random(seed)
    use = {}
    cellmap = {}
    for col in m.colors:
        cellmap[tuple(m.cell(col))] = col
    for e in m.elements:
        for f in e["faces"].values():
            col = cellmap.get(tuple(f["uv"]))
            if col:
                a, b = e["from"], e["to"]
                area = max(abs(b[0] - a[0]), abs(b[1] - a[1]), abs(b[2] - a[2]))
                use[col] = use.get(col, 0) + area
    room = 32 - len(m.arts)
    tops = sorted(use, key=lambda c: -use[c])[:room]
    keys = {}
    for col in tops:
        mat = (override or {}).get(col) or _material_of(col)
        rows = _mat_rows(mat, rnd)
        pal = {"s": col, "l": shade(col, 22), "d": shade(col, -28), "k": shade(col, -55), "h": shade(col, 45)}
        keys[col] = m.art("mat_" + col.strip("#") + "_" + mat, rows, pal)
    for e in m.elements:
        a, b = e["from"], e["to"]
        small = max(abs(b[0] - a[0]), abs(b[1] - a[1]), abs(b[2] - a[2])) < 1.2
        if small: continue                      # 아주 작은 조각(이빨·눈 등)은 단색 유지
        for fn, f in e["faces"].items():
            col = cellmap.get(tuple(f["uv"]))
            if col in keys:
                f["uv"] = list(m.arts[keys[col]]["uv"])
    return m

def face_detail(m, kind, s, body_w, skin):
    """얼굴(눈썹뼈·코·턱·귀)과 주먹·장화 앞코를 입체로 덧붙인다"""
    L, B, A, H = 12 * s, 12 * s, 12 * s, 8 * s
    hip = L; top = hip + B; bw = body_w * s; ax = bw / 2 + 2 * s
    fz = -H / 2
    dk = shade(skin, -25)
    if kind in ("orc_warrior", "orc_archer", "orc_chief", "orc_shaman"):
        if kind != "orc_shaman":   # 주술사는 해골 가면
            box(m, "head", 0, top + H * 0.66, fz - 0.5 * s, H * 0.9, 0.9 * s, 1.0 * s, dk)                  # 눈썹뼈
            box(m, "head", 0, top + H * 0.32, fz - 0.6 * s, 1.8 * s, 1.8 * s, 1.2 * s, dk)                  # 코
            box(m, "head", 0, top - 0.2 * s, fz - 0.5 * s, H * 0.86, H * 0.26, 1.4 * s, dk)                 # 주걱턱
        for sx in (-1, 1):                                                                                  # 뾰족한 귀
            box(m, "head", sx * (H / 2 + 0.7 * s), top + H * 0.45, 0, 1.4 * s, 1.8 * s, 2.6 * s, skin, rot=[0, sx * 25, 0])
            box(m, "head", sx * (H / 2 + 1.9 * s), top + H * 0.62, 0.8 * s, 1.0 * s, 1.0 * s, 2.0 * s, skin, rot=[15, sx * 35, 0])
    if kind == "minotaur":
        box(m, "head", 0, top + H * 0.08, fz - 2.2 * s, H * 0.62, H * 0.42, 3.0 * s, shade(skin, 15))     # 주둥이
        for sx in (-1, 1):
            box(m, "head", sx * 1.1 * s, top + H * 0.26, fz - 3.75 * s, 0.9 * s, 0.9 * s, 0.2 * s, "#1a0e08")   # 콧구멍
            box(m, "head", sx * (H / 2 + 1.4 * s), top + H * 0.82, 0, 2.6 * s, 1.6 * s, 1.6 * s, "#e8dcc0")     # 뿔 1
            box(m, "head", sx * (H / 2 + 3.4 * s), top + H * 0.98, -0.4 * s, 1.4 * s, 2.6 * s, 1.4 * s, "#e8dcc0", rot=[0, 0, sx * -25])
            box(m, "head", sx * (H / 2 + 4.2 * s), top + H * 1.22, -1.0 * s, 1.0 * s, 1.8 * s, 1.0 * s, "#4a3428", rot=[-20, 0, sx * -45])
            box(m, "head", sx * (H / 2 + 0.6 * s), top + H * 0.5, 0.6 * s, 1.2 * s, 2.4 * s, 1.0 * s, skin, rot=[0, 0, sx * 40])   # 처진 귀
        box(m, "head", 0, top + H * 0.7, fz - 0.4 * s, H * 0.92, 1.0 * s, 0.8 * s, dk)                    # 눈썹뼈
    if kind == "cyclops":
        box(m, "head", 0, top + H * 0.8, fz - 0.6 * s, H * 0.8, 1.2 * s, 1.2 * s, dk)                     # 외눈 위 눈썹뼈
        box(m, "head", 0, top + H * 0.17, fz - 0.7 * s, 2.0 * s, 1.3 * s, 1.4 * s, dk)                     # 뭉툭한 코 (눈 아래)
        box(m, "head", 0, top - 0.7 * s, fz - 0.6 * s, H * 0.8, H * 0.16, 1.2 * s, dk)                    # 턱
        for k in range(5):
            box(m, "head", (k - 2) * 1.3 * s, top + H * 0.02, fz - 1.25 * s, 0.7 * s, 0.7 * s, 0.2 * s, "#e8e0c8")   # 아랫니
        for sx in (-1, 1):
            box(m, "head", sx * (H / 2 + 0.6 * s), top + H * 0.45, 0, 1.2 * s, 2.2 * s, 2.0 * s, skin)        # 귀
    # 주먹과 장화 앞코 (모든 사람형)
    for side, sx in (("left_arm", -1), ("right_arm", 1)):
        box(m, side, sx * ax, top - A - 1.4 * s, -0.2 * s, 4.3 * s, 1.6 * s, 4.3 * s, skin)
        for k in range(3):
            box(m, side, sx * ax + (k - 1) * 1.2 * s, top - A - 0.6 * s, -2.25 * s, 0.9 * s, 0.9 * s, 0.3 * s, dk)   # 손가락 마디
    if kind != "medusa":
        for side, sx in (("left_leg", -1), ("right_leg", 1)):
            box(m, side, sx * (2 * s + 0.1 * s), 0, -3.0 * s, 4.4 * s, 2.0 * s, 1.6 * s, "#2a1e14")          # 장화 앞코

def decorate(m, kind, s, body_w=8, skin="#6a9a3a"):
    """보스·몬스터 디테일 추가 (사람형 기본 틀 위에 장비·특징 덧붙이기)"""
    face_detail(m, kind, s, body_w, skin)
    L, B, A, H = 12 * s, 12 * s, 12 * s, 8 * s
    hip = L; top = hip + B; bw = body_w * s; ax = bw / 2 + 2 * s
    iron, iron_d, leather, leather_d, bone_c, gold = "#8a8f96", "#4e5258", "#6b4526", "#3e2614", "#e8e0c8", "#e3b14a"
    def pauldron(col, spikes=2, big=1.0):
        for side, sx in (("left_arm", -1), ("right_arm", 1)):
            box(m, side, sx * ax, top - 2.2 * s, 0, 5.4 * s * big, 2.6 * s * big, 5.4 * s * big, col)
            box(m, side, sx * (ax + 0.2 * s), top - 2.8 * s, 0, 5.8 * s * big, 0.8 * s, 5.8 * s * big, shade(col, -30))
            for k in range(spikes):
                box(m, side, sx * (ax + 1.2 * s), top + 0.2 * s * big, (k - (spikes - 1) / 2) * 2.2 * s, 0.9 * s, 2.6 * s * big, 0.9 * s, bone_c, rot=[0, 0, -sx * 20])
    def bracers(col):
        for side, sx in (("left_arm", -1), ("right_arm", 1)):
            box(m, side, sx * ax, top - A + 0.6 * s, 0, 4.7 * s, 3.4 * s, 4.7 * s, col)
            box(m, side, sx * ax, top - A + 2.2 * s, -2.4 * s, 1.0 * s, 0.6 * s, 0.4 * s, iron)
    def kneepads(col):
        for side, sx in (("left_leg", -1), ("right_leg", 1)):
            box(m, side, sx * (2 * s + 0.1 * s), 4.4 * s, -2.2 * s, 4.4 * s, 2.4 * s, 0.6 * s, col)
    def belt_skull():
        box(m, "torso", 0, hip + 0.1 * s, -2.7 * s, 2.2 * s, 1.9 * s, 0.4 * s, bone_c)
        for sx in (-1, 1): box(m, "torso", sx * 0.5 * s, hip + 0.9 * s, -2.95 * s, 0.5 * s, 0.5 * s, 0.1 * s, "#1a1010")
    if kind == "orc_warrior":
        pauldron(iron, 2); bracers(leather_d); kneepads(iron); belt_skull()
        box(m, "torso", 0, hip + 2 * s, -2.45 * s, 1.0 * s, 10 * s, 0.4 * s, leather_d, rot=[0, 0, 38])     # 가슴 끈
        box(m, "torso", 0, hip + 1.2 * s, 2.5 * s, bw - 1 * s, 0.6 * s, 0.5 * s, leather_d)
    elif kind == "orc_archer":
        bracers(leather); kneepads(leather_d)
        box(m, "torso", 0, hip - 2 * s, 2.5 * s, bw + 0.8 * s, B + 1.5 * s, 0.4 * s, "#2e4a22")             # 망토
        box(m, "torso", 2 * s, hip + 3 * s, 3.2 * s, 2.6 * s, 8 * s, 2.6 * s, leather, rot=[0, 0, 18])   # 화살통
        for k in range(3):
            box(m, "torso", 2.6 * s + k * 0.6 * s, hip + 11 * s, 3.2 * s, 0.4 * s, 2 * s, 1.2 * s, "#d23a2a" if k % 2 else "#f2f2f2", rot=[0, 0, 18])
        box(m, "torso", 0, hip + 4 * s, -2.45 * s, 0.8 * s, 11 * s, 0.4 * s, leather_d, rot=[0, 0, -40])
    elif kind == "orc_shaman":
        box(m, "body", 0, hip - 7 * s, 0, bw + 1.4 * s, 7.5 * s, 5.4 * s, "#4a2240")                       # 로브 치마
        box(m, "body", 0, hip - 7.2 * s, 0, bw + 1.6 * s, 0.6 * s, 5.6 * s, gold)
        for k in range(7):                                                                                  # 뼈 목걸이
            a = math.radians(-60 + k * 20)
            box(m, "torso", math.sin(a) * 3 * s, top - 1.5 * s - math.cos(a) * 1.2 * s, -2.5 * s, 0.6 * s, 1.0 * s, 0.4 * s, bone_c)
        for k in range(5):                                                                                  # 깃털 머리장식
            box(m, "head", (k - 2) * 1.4 * s, top + H, 0.5 * s, 0.6 * s, (3 + (2 - abs(k - 2))) * s, 1.2 * s,
                ["#3fa8ff", "#ff7a2a", "#ffd23a", "#ff7a2a", "#3fa8ff"][k], rot=[-15, 0, (k - 2) * -12], pivot=[(k - 2) * 1.4 * s, top + H, 0.5 * s])
    elif kind == "orc_chief":
        pauldron(iron_d, 3, 1.15); bracers(iron); kneepads(iron_d); belt_skull()
        box(m, "torso", 0, hip - 4 * s, 2.7 * s, bw + 2 * s, B + 3 * s, 0.4 * s, "#8a1a14")                # 망토
        box(m, "torso", 0, top - 2.4 * s, 0, bw + 2.4 * s, 2.6 * s, 6 * s, "#5a4030")                      # 털 목도리
        box(m, "torso", 0, hip + 4 * s, -2.55 * s, bw - 2.5 * s, 6 * s, 0.5 * s, iron)                     # 가슴판
        box(m, "torso", 0, hip + 6 * s, -2.85 * s, 2.6 * s, 2.4 * s, 0.4 * s, bone_c)                      # 가슴 해골
        for sx in (-1, 1): box(m, "torso", sx * 0.6 * s, hip + 7 * s, -3.1 * s, 0.6 * s, 0.6 * s, 0.1 * s, "#c41a1a")
    elif kind == "medusa":
        box(m, "torso", 0, hip + 6.5 * s, -2.4 * s, bw - 1 * s, 3.4 * s, 0.6 * s, gold)                   # 금 흉갑
        box(m, "torso", 0, hip + 7.6 * s, -2.75 * s, 1.4 * s, 1.4 * s, 0.4 * s, "#3aff8a")                 # 에메랄드
        box(m, "torso", 0, hip, 0, bw + 0.6 * s, 1.4 * s, 5 * s, gold)                                      # 금 허리띠
        bracers(gold)
        for k in range(5):                                                                                  # 금 티아라
            box(m, "head", (k - 2) * 1.6 * s, top + H - 0.4 * s, -H / 2 - 0.3 * s, 1.0 * s, (1.2 + (2 - abs(k - 2)) * 0.6) * s, 0.4 * s, gold)
    elif kind == "minotaur":
        kneepads(iron_d); bracers(leather_d)
        box(m, "torso", 0, top - 3.4 * s, 0.4 * s, bw + 1.6 * s, 4.4 * s, 5.8 * s, "#3e2616")             # 갈기
        box(m, "body", 0, hip - 5 * s, -2.6 * s, 5 * s, 5.5 * s, 0.4 * s, "#5a2a1a")                       # 허리천
        box(m, "body", 0, hip - 5 * s, 2.6 * s, 5 * s, 5.5 * s, 0.4 * s, "#5a2a1a")
        for dx, dy, w_, h_ in ((0, -0.4, 2.4, 0.4), (-1.0, 0, 0.4, 1.4), (1.0, 0, 0.4, 1.4)):             # 코뚜레
            box(m, "head", dx * s, top + 0.9 * s + dy * s, -H / 2 - 1.6 * s, w_ * s, h_ * s, 0.4 * s, gold)
        for side, sx in (("left_leg", -1), ("right_leg", 1)):                                              # 발굽
            box(m, side, sx * 2.1 * s, 0, -0.4 * s, 4.6 * s, 1.6 * s, 5.2 * s, "#1e1814")
    elif kind == "cyclops":
        box(m, "body", 0, hip - 6 * s, 0, bw + 1.2 * s, 6.5 * s, 5.4 * s, "#7a5a3a")                       # 털 허리옷
        for k in range(6): box(m, "body", (k - 2.5) * 1.8 * s, hip - 7 * s, -2.8 * s, 1.2 * s, 1.6 * s, 0.4 * s, "#5a3e24")
        for k in range(5):                                                                                  # 이빨 목걸이
            a = math.radians(-50 + k * 25)
            box(m, "torso", math.sin(a) * 3.5 * s, top - 1.8 * s - math.cos(a) * 1.4 * s, -2.5 * s, 0.6 * s, 1.4 * s, 0.4 * s, bone_c)
        box(m, "head", 0, top + H, 0, 2 * s, 1.6 * s, 3 * s, "#3a2a1a")                                     # 머리 털 뭉치
        kneepads("#5a3e24")
    return texturize(m)

def decorate_cerberus(m, s):
    # 머리·몸 실제 크기를 큐브에서 읽어 바깥쪽에 장식을 붙인다
    def bounds(bone):
        cubes = [e for e in m.elements if any(c[1] == e["uuid"] for c in m.children[bone] if c[0] == "e")]
        xs = [v for e in cubes for v in (e["from"][0], e["to"][0])]; ys = [v for e in cubes for v in (e["from"][1], e["to"][1])]
        zs = [v for e in cubes for v in (e["from"][2], e["to"][2])]
        return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
    for k in range(3):
        hb = f"head{k}"
        x0, x1, y0, y1, z0, z1 = bounds(hb)
        cx = (x0 + x1) / 2; w = x1 - x0 + 0.8; zc = z1 - 0.4
        box(m, hb, cx, y0 + 0.4, zc, w, 1.6 * s, 1.6 * s, "#2a2a2a")                                      # 가시 목걸이 (목 뒤쪽)
        for j in range(4):
            box(m, hb, cx + (j - 1.5) * w / 4, y0 + 0.4 + 1.6 * s, zc, 0.6 * s, 1.4 * s, 0.6 * s, "#c8c8c8")   # 위로 솟은 가시
        box(m, hb, cx, y0 - 0.6 * s, z0 + (z1 - z0) * 0.6, 1.2 * s, 1.0 * s, 1.0 * s, "#ff3a1a")         # 늘어진 붉은 보석
    x0, x1, y0, y1, z0, z1 = bounds("body")
    for k in range(7):                                                                                     # 등 불꽃 갈기
        z = z0 + 2 + k * (z1 - z0 - 4) / 6
        box(m, "body", 0, y1 - 0.4, z, 1.4 * s, (3.4 - k * 0.3) * s, 2.4 * s, "#ff6a1a" if k % 2 else "#ffb02a", rot=[-25, 0, 0], pivot=[0, y1, z])
    for sx in (-1, 1):                                                                                     # 옆구리 쇠사슬
        for k in range(5):
            box(m, "body", sx * (x1 - x0) / 2 * 1.02, y0 + (y1 - y0) * 0.55, z0 + 3 + k * 2.4, 0.4 * s, 0.8 * s, 1.6 * s, "#6a6a6a" if k % 2 else "#8a8a8a")
    return texturize(m, override={"#2b2b2b": "fur", "#3d3030": "fur"})

# ---------------------------------------------------------------- 마인크래프트 스킨 모델

def skin_uv(u, v, w, h, d):
    """마인크래프트 스킨 레이아웃(박스 w×h×d, 시작점 u,v) → Blockbench 면 UV (정면 = north)"""
    return {
        "north": (u + d, v + d, u + d + w, v + d + h),
        "east": (u, v + d, u + d, v + d + h),
        "south": (u + 2 * d + w, v + d, u + 2 * d + 2 * w, v + d + h),
        "west": (u + d + w, v + d, u + 2 * d + w, v + d + h),
        "up": (u + d + w, v + d, u + d, v),
        "down": (u + d + 2 * w, v, u + d + w, v + d),
    }

def skinned_siren(name="siren", skin_path=None):
    """플레이어 스킨을 그대로 입히고, 다리 대신 인어 꼬리 + 손에 삼지창"""
    m = Model(name, seed=8, skin=skin_path)
    navy, navy2, navy3 = "#3b3e54", "#494a5f", "#2a2d3c"
    mint, mint2, pink, pink2 = "#6cefdc", "#a8f7ec", "#ff9c9c", "#ffc7c7"
    hip, top = 12, 24
    m.bone("body", [0, hip, 0])
    # 몸통 + 겉옷 레이어
    m.bone("torso", [0, hip, 0], "body")
    m.cube_uv("torso", [-4, hip, -2], [4, top, 2], skin_uv(16, 16, 8, 12, 4))
    m.cube_uv("torso", [-4, hip, -2], [4, top, 2], skin_uv(16, 32, 8, 12, 4), inflate=0.25)
    # 머리 + 모자 레이어
    m.bone("head", [0, top, 0], "torso")
    m.cube_uv("head", [-4, top, -4], [4, top + 8, 4], skin_uv(0, 0, 8, 8, 8))
    m.cube_uv("head", [-4, top, -4], [4, top + 8, 4], skin_uv(32, 0, 8, 8, 8), inflate=0.5)
    # 팔 (슬림 3px) + 소매 레이어
    m.bone("right_arm", [5, top - 2, 0], "torso")
    m.cube_uv("right_arm", [4, hip, -2], [7, top, 2], skin_uv(40, 16, 3, 12, 4))
    m.cube_uv("right_arm", [4, hip, -2], [7, top, 2], skin_uv(40, 32, 3, 12, 4), inflate=0.25)
    m.bone("left_arm", [-5, top - 2, 0], "torso")
    m.cube_uv("left_arm", [-7, hip, -2], [-4, top, 2], skin_uv(32, 48, 3, 12, 4))
    m.cube_uv("left_arm", [-7, hip, -2], [-4, top, 2], skin_uv(48, 48, 3, 12, 4), inflate=0.25)

    # ----- 인어 꼬리 (다리 대신) -----
    box(m, "body", 0, hip - 1.2, 0, 8.6, 1.6, 4.6, pink)            # 허리 장식 띠
    box(m, "body", 0, hip - 1.0, -2.4, 1.2, 1.2, 0.4, mint)          # 띠 보석
    segs = [  # (폭, 높이, 깊이, 색, 다음 이동 y, z, 기울기)
        (7.6, 3.8, 4.4, navy, -3.0, 0.2),
        (6.8, 3.6, 4.2, navy2, -2.8, 0.6),
        (5.8, 3.4, 4.0, navy, -2.4, 1.0),
        (4.6, 3.0, 3.8, navy2, -1.8, 1.4),
        (3.4, 2.4, 3.6, navy, -0.8, 1.8),
    ]
    prev, y, z = "body", hip - 1.2, 0.0
    for i, (w, h, d, c, dy, dz) in enumerate(segs):
        b = m.bone(f"tail{i}", [0, y, z], prev)
        box(m, b, 0, y - h, z, w, h, d, c)
        box(m, b, 0, y - h * 0.55, z - d / 2 - 0.05, w * 0.6, 0.6, 0.2, mint)        # 앞쪽 비늘 줄
        box(m, b, 0, y - h * 0.9, z + d / 2 + 0.05, w * 0.5, 0.5, 0.2, pink)         # 뒤쪽 비늘 점
        for sx in (-1, 1):                                                             # 옆 지느러미
            if i in (1, 3):
                box(m, b, sx * (w / 2 + 0.6), y - h * 0.8, z + 0.4, 1.2, h * 0.6, 0.3, mint2, rot=[0, 0, sx * -25])
        y, z, prev = y + dy, z + dz, b
    # 꼬리 지느러미 (두 갈래)
    fin = m.bone("tail_fin", [0, y, z], prev)
    for sx in (-1, 1):
        box(m, fin, sx * 3.0, y - 0.6, z + 2.6, 5.4, 0.8, 4.0, mint, rot=[0, sx * 28, sx * 12], pivot=[0, y, z])
        box(m, fin, sx * 4.6, y - 0.55, z + 4.6, 2.6, 0.7, 1.4, pink, rot=[0, sx * 28, sx * 12], pivot=[0, y, z])
    box(m, fin, 0, y - 0.9, z + 0.6, 2.0, 1.4, 2.0, navy3)

    # ----- 삼지창 (오른손): 자루가 주먹을 앞뒤로 관통, 창날은 앞(-Z) 끝 -----
    # 팔을 앞으로 들면(-60°) 창끝이 앞쪽 위를 향해 겨누는 자세가 된다.
    hx, gy = 5.5, hip + 1.0
    box(m, "right_arm", hx, gy - 0.5, -9.0, 1.0, 1.0, 26.0, navy2)           # 자루 (z +4 ~ -22)
    box(m, "right_arm", hx, gy - 0.75, -1.0, 1.5, 1.5, 2.0, pink)            # 손잡이 감개 (주먹)
    box(m, "right_arm", hx, gy - 0.75, 3.2, 1.5, 1.5, 1.4, pink)             # 자루 끝 장식
    box(m, "right_arm", hx, gy - 0.5, -21.4, 6.4, 1.0, 1.0, mint)            # 가로대
    box(m, "right_arm", hx, gy - 0.9, -20.6, 1.8, 1.8, 1.8, pink2)           # 보석
    box(m, "right_arm", hx, gy - 0.5, -24.9, 1.0, 1.0, 6.0, mint)            # 가운데 날
    box(m, "right_arm", hx, gy - 0.25, -28.4, 0.5, 0.5, 1.2, mint2)
    for sx in (-1, 1):
        box(m, "right_arm", hx + sx * 2.7, gy - 0.5, -23.9, 1.0, 1.0, 4.0, mint)    # 양쪽 날
        box(m, "right_arm", hx + sx * 2.7, gy - 0.25, -26.4, 0.5, 0.5, 1.0, mint2)

    hitbox(m, 8, 32)
    tail_wag = lambda f, a: {f"tail{i}": {"rotation": (f"math.sin(q.anim_time * 360 * {f} + {i * 45}) * {a + i * 2}", 0, 0)} for i in range(5)}
    idle = tail_wag(0.5, 4)
    idle["tail_fin"] = {"rotation": ("math.sin(q.anim_time * 180 + 225) * 12", 0, 0)}
    idle["left_arm"] = {"rotation": (0, 0, SWING.format(f=0.5, a=-4))}
    idle["right_arm"] = {"rotation": ("-60 + " + SWING.format(f=0.5, a=3), 0, 0)}
    idle["head"] = {"rotation": (0, "math.sin(q.anim_time * 90) * 6", 0)}
    walk = tail_wag(1.2, 8)
    walk["tail_fin"] = {"rotation": ("math.sin(q.anim_time * 432 + 225) * 20", 0, 0)}
    walk["left_arm"] = {"rotation": ("-" + SWING.format(f=1, a=20), 0, 0)}
    walk["right_arm"] = {"rotation": ("-60 + " + SWING.format(f=1, a=6), 0, 0)}
    m.anim("idle", 2, idle)
    m.anim("walk", 1, walk)
    m.anim("attack", 0.5, {"right_arm": {"rotation": ("-60 - 40 * math.sin(q.anim_time * 360)", 0, 0)},
                           "torso": {"rotation": ("12 * math.sin(q.anim_time * 360)", 0, 0)}}, loop="once")
    return m


def skinned_harpy(name="harpy", skin_path=None):
    """플레이어 스킨 그대로 + 팔에 깃털 날개 + 발에 새 발톱"""
    m = Model(name, seed=9, skin=skin_path)
    f1, f2, f3, tip = "#967167", "#a77d72", "#73645e", "#ccb2aa"
    claw = "#d8b23a"
    hip, top = 12, 24
    m.bone("body", [0, hip, 0])
    m.bone("torso", [0, hip, 0], "body")
    m.cube_uv("torso", [-4, hip, -2], [4, top, 2], skin_uv(16, 16, 8, 12, 4))
    m.cube_uv("torso", [-4, hip, -2], [4, top, 2], skin_uv(16, 32, 8, 12, 4), inflate=0.25)
    m.bone("head", [0, top, 0], "torso")
    m.cube_uv("head", [-4, top, -4], [4, top + 8, 4], skin_uv(0, 0, 8, 8, 8))
    m.cube_uv("head", [-4, top, -4], [4, top + 8, 4], skin_uv(32, 0, 8, 8, 8), inflate=0.5)
    # 팔 (클래식 4px) + 소매 + 깃털 날개
    for side, sx, base, sleeve in (("right_arm", 1, (40, 16), (40, 32)), ("left_arm", -1, (32, 48), (48, 48))):
        x0, x1 = (4, 8) if sx > 0 else (-8, -4)
        m.bone(side, [sx * 5, top - 2, 0], "torso")
        m.cube_uv(side, [x0, hip, -2], [x1, top, 2], skin_uv(*base, 4, 12, 4))
        m.cube_uv(side, [x0, hip, -2], [x1, top, 2], skin_uv(*sleeve, 4, 12, 4), inflate=0.25)
        ox = sx * 8.2   # 팔 바깥쪽
        # 깃털: 어깨→손목으로 갈수록 길어지는 날개깃 (뒤쪽 +Z로 뻗음)
        for k in range(6):
            yk = top - 1.5 - k * 2.0
            ln = 5 + k * 1.6
            col = (f1, f2, f3)[k % 3]
            box(m, side, ox + sx * 0.3 * k, yk - 1.6, 1.5 + ln / 2, 1.0, 1.8, ln, col, rot=[18 + k * 4, 0, 0], pivot=[ox, yk, 1.5])
            box(m, side, ox + sx * 0.3 * k, yk - 1.6, 1.5 + ln - 0.6, 1.1, 1.8, 1.4, tip, rot=[18 + k * 4, 0, 0], pivot=[ox, yk, 1.5])
        box(m, side, ox, top - 4, 0, 1.4, 3.4, 4.4, f2)                                   # 어깨 깃털
    # 다리 (스킨) + 무릎 깃털 + 새 발톱
    for side, sx, base, pants in (("right_leg", 1, (0, 16), (0, 32)), ("left_leg", -1, (16, 48), (0, 48))):
        x0, x1 = (0, 4) if sx > 0 else (-4, 0)
        m.bone(side, [sx * 2, hip, 0], "body")
        m.cube_uv(side, [x0, 0, -2], [x1, hip, 2], skin_uv(*base, 4, 12, 4))
        m.cube_uv(side, [x0, 0, -2], [x1, hip, 2], skin_uv(*pants, 4, 12, 4), inflate=0.25)
        cx = sx * 2
        box(m, side, cx, 4.5, 0, 4.8, 1.6, 4.8, f2)                                       # 발목 깃털
        for k in (-1, 0, 1):                                                               # 앞 발톱 3개
            box(m, side, cx + k * 1.3, 0, -2.6, 0.8, 0.8, 2.4, claw)
            box(m, side, cx + k * 1.3, 0, -3.9, 0.6, 0.6, 0.6, "#3a2a1a")
        box(m, side, cx, 0, 2.4, 0.8, 0.8, 1.6, claw)                                      # 뒤 발톱
    hitbox(m, 8, 32)
    flap = lambda f, a, base: {"right_arm": {"rotation": (0, 0, f"{base} + math.sin(q.anim_time * 360 * {f}) * {a}")},
                               "left_arm": {"rotation": (0, 0, f"-{base} - math.sin(q.anim_time * 360 * {f}) * {a}")}}
    idle = flap(0.5, 6, 8)
    idle["head"] = {"rotation": (0, "math.sin(q.anim_time * 120) * 10", 0)}
    walk = flap(2, 30, 35)
    walk["left_leg"] = {"rotation": (SWING.format(f=1, a=25), 0, 0)}
    walk["right_leg"] = {"rotation": ("-" + SWING.format(f=1, a=25), 0, 0)}
    m.anim("idle", 2, idle)
    m.anim("walk", 1, walk)
    m.anim("attack", 0.5, {"right_arm": {"rotation": ("-100 * math.sin(q.anim_time * 360)", 0, "20")},
                           "left_arm": {"rotation": ("-100 * math.sin(q.anim_time * 360)", 0, "-20")}}, loop="once")
    return m


def skinned_pet(name, skin_path, weapon=None, accent="#ff9c9c", metal="#3a3d4a", seed=30):
    """스킨 그대로 + (선택) 오른손 무기. weapon: None | 'gun' | 'sword'
    무기는 팔 방향(아래)으로 뻗어 있어서, 팔을 앞으로 들면 총구/칼끝이 앞을 향한다."""
    slim = is_slim(skin_path)
    aw = 3 if slim else 4
    m = Model(name, seed=seed, skin=skin_path)
    hip, top = 12, 24
    m.bone("body", [0, hip, 0])
    m.bone("torso", [0, hip, 0], "body")
    m.cube_uv("torso", [-4, hip, -2], [4, top, 2], skin_uv(16, 16, 8, 12, 4))
    m.cube_uv("torso", [-4, hip, -2], [4, top, 2], skin_uv(16, 32, 8, 12, 4), inflate=0.25)
    m.bone("head", [0, top, 0], "torso")
    m.cube_uv("head", [-4, top, -4], [4, top + 8, 4], skin_uv(0, 0, 8, 8, 8))
    m.cube_uv("head", [-4, top, -4], [4, top + 8, 4], skin_uv(32, 0, 8, 8, 8), inflate=0.5)
    for side, sx, base, sleeve in (("right_arm", 1, (40, 16), (40, 32)), ("left_arm", -1, (32, 48), (48, 48))):
        x0, x1 = (4, 4 + aw) if sx > 0 else (-4 - aw, -4)
        m.bone(side, [sx * (4 + aw / 2), top - 2, 0], "torso")
        m.cube_uv(side, [x0, hip, -2], [x1, top, 2], skin_uv(*base, aw, 12, 4))
        m.cube_uv(side, [x0, hip, -2], [x1, top, 2], skin_uv(*sleeve, aw, 12, 4), inflate=0.25)
    for side, sx, base, pants in (("right_leg", 1, (0, 16), (0, 32)), ("left_leg", -1, (16, 48), (0, 48))):
        x0, x1 = (0, 4) if sx > 0 else (-4, 0)
        m.bone(side, [sx * 2, hip, 0], "body")
        m.cube_uv(side, [x0, 0, -2], [x1, hip, 2], skin_uv(*base, 4, 12, 4))
        m.cube_uv(side, [x0, 0, -2], [x1, hip, 2], skin_uv(*pants, 4, 12, 4), inflate=0.25)

    hx = 4 + aw / 2      # 오른손 중심 x
    hy = hip             # 손 끝 높이
    if weapon == "gun":
        # 소총: 손에서 아래(-Y)로 총열이 뻗음 (팔을 들면 앞을 향함)
        box(m, "right_arm", hx, hy - 1.5, -1.6, 1.4, 3.0, 1.6, metal)                 # 손잡이
        box(m, "right_arm", hx, hy - 6.5, -2.6, 2.0, 7.0, 3.2, metal)                 # 몸통(리시버)
        box(m, "right_arm", hx, hy - 6.0, -2.6 - 1.9, 1.2, 3.0, 0.8, accent)          # 탄창
        box(m, "right_arm", hx, hy - 12.5, -2.9, 1.0, 6.0, 1.0, "#22242c")            # 총열
        box(m, "right_arm", hx, hy - 13.0, -2.9, 1.4, 1.0, 1.4, accent)               # 총구
        box(m, "right_arm", hx, hy - 5.5, -1.2 + 0.2, 1.4, 4.0, 1.0, "#5a5e6e")       # 개머리 연결
        box(m, "right_arm", hx, hy - 1.0, 0.6, 1.6, 4.0, 1.8, metal)                  # 개머리판(뒤쪽)
        box(m, "right_arm", hx, hy - 6.0, -4.6, 1.2, 3.0, 0.8, "#22242c")             # 스코프 받침
        box(m, "right_arm", hx, hy - 7.0, -5.4, 1.4, 4.0, 1.2, accent)                # 스코프
        box(m, "right_arm", hx, hy - 3.2, -5.4, 1.5, 0.4, 1.3, "#bfe8ff")             # 스코프 렌즈
        box(m, "right_arm", hx, hy - 11.0, -2.9, 1.6, 4.0, 1.6, "#3a3d4a")            # 총열 덮개
        box(m, "right_arm", hx, hy - 10.6, -3.8, 0.4, 3.2, 0.2, accent)               # 덮개 발광선
        box(m, "right_arm", hx, hy - 9.5, -4.1, 0.8, 3.0, 0.4, "#22242c")             # 위쪽 레일
        box(m, "right_arm", hx + 1.05, hy - 7.0, -2.6, 0.1, 4.0, 0.4, accent)         # 옆 줄무늬
    elif weapon == "gatling":
        # 개틀링건: 팔 방향(아래)으로 총열 6개가 원형으로 묶여 있고, 총열 뭉치는 따로 돌아간다
        box(m, "right_arm", hx, hy - 1.6, -1.6, 1.4, 3.2, 1.6, metal)                 # 손잡이
        box(m, "right_arm", hx, hy - 7.0, -3.0, 4.2, 6.0, 4.2, metal)                 # 몸통
        box(m, "right_arm", hx - 2.6, hy - 6.0, -3.0, 1.4, 4.0, 3.6, accent)          # 탄통
        box(m, "right_arm", hx, hy - 8.4, -0.4, 2.4, 1.2, 1.2, "#5a5e6e")             # 탄띠
        m.bone("barrels", [hx, hy - 7, -3.0], "right_arm")
        for k in range(6):
            a = math.radians(k * 60)
            bx, bz = hx + math.cos(a) * 1.2, -3.0 + math.sin(a) * 1.2
            box(m, "barrels", bx, hy - 18.0, bz, 0.7, 11.0, 0.7, "#22242c")           # 총열
        box(m, "barrels", hx, hy - 18.6, -3.0, 3.6, 0.8, 3.6, accent)                 # 총구 링
        box(m, "barrels", hx, hy - 12.0, -3.0, 3.4, 0.8, 3.4, "#5a5e6e")              # 중간 링
    elif weapon == "sniper":
        # 저격총: 아주 긴 총열 + 큰 스코프 + 양각대
        box(m, "right_arm", hx, hy - 1.5, -1.6, 1.4, 3.0, 1.6, metal)                 # 손잡이
        box(m, "right_arm", hx, hy - 7.0, -2.6, 1.8, 7.0, 2.6, metal)                 # 몸통
        box(m, "right_arm", hx, hy - 19.0, -2.8, 0.8, 12.0, 0.8, "#22242c")           # 긴 총열
        box(m, "right_arm", hx, hy - 20.0, -2.8, 1.3, 1.6, 1.3, "#22242c")            # 소음기
        box(m, "right_arm", hx, hy - 7.4, -5.0, 1.6, 6.0, 1.6, accent)                # 큰 스코프
        box(m, "right_arm", hx, hy - 4.6, -5.0, 1.9, 0.8, 1.9, "#bfe8ff")             # 스코프 렌즈
        box(m, "right_arm", hx, hy - 1.0, 0.8, 1.6, 5.0, 2.0, metal)                  # 개머리판
        box(m, "right_arm", hx - 0.8, hy - 13.0, -1.6, 0.4, 3.0, 0.4, "#5a5e6e")      # 양각대
        box(m, "right_arm", hx + 0.8, hy - 13.0, -1.6, 0.4, 3.0, 0.4, "#5a5e6e")
    elif weapon == "pistol":
        # 권총: 손에 쏙 들어가는 작은 총
        box(m, "right_arm", hx, hy - 1.6, -1.4, 1.2, 3.0, 1.4, metal)                 # 손잡이
        box(m, "right_arm", hx, hy - 4.6, -2.2, 1.4, 3.6, 2.6, metal)                 # 슬라이드
        box(m, "right_arm", hx, hy - 5.4, -2.2, 0.7, 1.2, 0.7, "#22242c")             # 총구
        box(m, "right_arm", hx, hy - 3.2, -3.6, 0.4, 0.6, 0.4, accent)                # 가늠쇠
        box(m, "right_arm", hx, hy - 2.0, -0.4, 1.0, 1.2, 0.3, accent)                # 방아쇠울
        box(m, "right_arm", hx, hy - 6.4, -2.6, 1.0, 1.8, 1.0, "#3a3d4a")             # 소음기
        box(m, "right_arm", hx + 0.75, hy - 4.4, -2.2, 0.1, 3.0, 0.4, accent)         # 슬라이드 발광선
        box(m, "right_arm", hx - 0.75, hy - 4.4, -2.2, 0.1, 3.0, 0.4, accent)
    elif weapon == "wing_shields":
        # 몸 양옆에 떠 있는 기계 방패 2장 (은백색 판 + 푸른 육각 셀 + 빛나는 십자)
        silver, silver2, dark, cell, cell2, glow = "#e3e7ee", "#c4cad6", "#34384a", "#5fa8ff", "#a9d6ff", "#8ff4ff"
        for sx, side in ((-1, "shield_l"), (1, "shield_r")):
            cx = sx * 12.5
            m.bone(side, [sx * 6, 22, 2], "body", rotation=(0, sx * -12, sx * 4))
            box(m, side, cx, 3, 3, 5.5, 26, 1.6, silver)                      # 바깥 판
            for fz, out in ((3.9, 0.3), (2.1, -0.3)):                          # 뒷면·앞면 둘 다 장식
                box(m, side, cx + sx * 0.4, 5, fz, 3.6, 21, 0.4, dark)        # 안쪽 프레임
                for k in range(7):                                            # 육각 에너지 셀 (세로로)
                    box(m, side, cx + sx * 0.4 + (0.6 if k % 2 else -0.6), 5.6 + k * 2.4, fz + out, 1.5, 1.8, 0.3, cell if k % 2 else cell2)
                box(m, side, cx, 24.5, fz + out * 1.7, 3.8, 1.0, 0.3, glow)   # 십자 가로
                box(m, side, cx, 22.6, fz + out * 1.7, 1.0, 4.8, 0.3, glow)   # 십자 세로
            box(m, side, cx - sx * 3.6, 6, 3, 1.6, 20, 2.4, silver2)          # 안쪽 날개
            box(m, side, cx + sx * 3.4, 10, 3, 1.4, 14, 2.0, dark)            # 바깥 장갑
            box(m, side, cx, 29, 3, 4.4, 4, 1.4, silver, rot=[0, 0, sx * 18])  # 위쪽 뾰족한 끝
            box(m, side, cx - sx * 1.8, 31.5, 3, 1.6, 3.5, 1.2, silver2, rot=[0, 0, sx * 30])
            box(m, side, cx, 1.5, 3, 3.6, 2.5, 1.4, dark, rot=[0, 0, sx * -15])  # 아래쪽 끝
            box(m, side, cx, 3.0, 3.6, 2.0, 0.6, 0.3, glow)                    # 아래 발광부
    elif weapon == "shield":
        # 왼손 대형 방패 (앞면에 포구가 달려 있어 원거리 공격)
        sx_ = -hx
        box(m, "left_arm", sx_, hy - 3.0, -3.3, 7.6, 13.0, 1.0, "#d9dde6")            # 방패 판
        box(m, "left_arm", sx_, hy - 3.6, -3.5, 8.4, 14.2, 0.6, accent)               # 테두리
        box(m, "left_arm", sx_, hy - 2.0, -3.9, 5.6, 11.0, 0.4, "#eef1f7")            # 안쪽 판
        box(m, "left_arm", sx_, hy + 2.0, -4.2, 3.0, 3.0, 0.4, accent)                # 문양(유리구두 보석)
        box(m, "left_arm", sx_, hy + 2.6, -4.4, 1.6, 1.6, 0.3, "#bfe8ff")
        box(m, "left_arm", sx_, hy - 1.2, -5.2, 1.6, 1.6, 2.0, "#5a6070")             # 포구
        box(m, "left_arm", sx_, hy - 1.4, -6.3, 2.2, 2.2, 0.6, "#bfe8ff")             # 포구 끝(빛)
        box(m, "left_arm", sx_, hy + 7.0, -3.3, 2.0, 1.0, 1.0, accent)                # 위쪽 장식
    elif weapon == "sword":
        # 주먹(팔 끝)을 손잡이가 앞뒤로 관통하고, 칼날은 주먹에서 앞(-Z)으로 뻗는다.
        # 대기 자세에서 팔을 앞으로 들어 올리면 칼날이 위를 향한다.
        gy = hy + 1.0                                                                 # 주먹 높이
        box(m, "right_arm", hx, gy - 0.6, 1.4, 1.4, 1.4, 1.0, accent)                 # 손잡이 끝(뒤)
        box(m, "right_arm", hx, gy - 0.5, 0.0, 1.2, 1.2, 3.4, "#3a2418")              # 손잡이 (주먹 관통)
        box(m, "right_arm", hx, gy - 1.8, -2.6, 1.6, 3.8, 0.9, accent)                # 코등이
        box(m, "right_arm", hx, gy - 0.3, -9.2, 0.6, 1.6, 12.0, "#e8eef5")            # 칼날
        box(m, "right_arm", hx, gy - 0.35, -9.2, 0.7, 0.5, 12.0, "#b9c6d6")           # 칼날 가운데 홈
        box(m, "right_arm", hx, gy - 0.1, -15.75, 0.5, 0.7, 0.6, "#f6fbff")           # 칼끝
        box(m, "right_arm", hx, gy + 1.2, -9.2, 0.5, 0.3, 11.0, "#ffffff")            # 날 끝 하이라이트
        for z in (-0.9, 0.9):
            box(m, "right_arm", hx, gy - 0.65, z, 1.3, 1.3, 0.3, accent)              # 손잡이 감개
        box(m, "right_arm", hx, gy - 0.4, -2.6, 2.0, 1.0, 1.0, "#ffffff")             # 코등이 보석 테
        box(m, "right_arm", hx, gy - 0.3, -2.6, 2.1, 0.7, 0.7, accent)                # 코등이 보석
        box(m, "right_arm", hx, gy - 2.6, -2.6, 1.2, 1.0, 0.7, accent)                # 아래쪽 가지
    hitbox(m, 8, 32)

    hold = {"gun": "-25", "sniper": "-25", "pistol": "-20", "gatling": "-35", "sword": "-75"}.get(weapon, "0")
    idle = {"right_arm": {"rotation": (f"{hold} + math.sin(q.anim_time * 180) * 3", 0, 0)},
            "left_arm": {"rotation": (0, 0, SWING.format(f=0.5, a=-3))},
            "head": {"rotation": (0, "math.sin(q.anim_time * 90) * 8", 0)}}
    walk = {"left_leg": {"rotation": (SWING.format(f=1, a=30), 0, 0)},
            "right_leg": {"rotation": ("-" + SWING.format(f=1, a=30), 0, 0)},
            "left_arm": {"rotation": ("-" + SWING.format(f=1, a=25), 0, 0)},
            "right_arm": {"rotation": (f"{hold} + " + SWING.format(f=1, a=10 if weapon else 25), 0, 0)}}
    if weapon == "wing_shields":   # 양옆 방패가 천천히 떠다님
        for side, ph in (("shield_l", 0), ("shield_r", 180)):
            idle[side] = {"rotation": (f"math.sin(q.anim_time * 180 + {ph}) * 4", f"math.cos(q.anim_time * 180 + {ph}) * 3", 0)}
            walk[side] = {"rotation": (f"math.sin(q.anim_time * 360 + {ph}) * 6", f"math.cos(q.anim_time * 360 + {ph}) * 4", 0)}
    if weapon == "shield":   # 방패는 왼손에 들고 몸 앞쪽으로
        idle["left_arm"] = {"rotation": ("-20 + math.sin(q.anim_time * 180) * 2", "15", 0)}
        walk["left_arm"] = {"rotation": ("-20 + " + SWING.format(f=1, a=6), "15", 0)}
    m.anim("idle", 2, idle)
    m.anim("walk", 1, walk)
    if weapon == "wing_shields":   # 두 방패가 앞으로 모이며 발사, 손은 지휘하듯 앞으로
        m.anim("attack", 0.7, {"shield_l": {"rotation": ("-10", "math.sin(q.anim_time * 257) * -35", 0)},
                               "shield_r": {"rotation": ("-10", "math.sin(q.anim_time * 257) * 35", 0)},
                               "right_arm": {"rotation": ("-80", "-10", 0)},
                               "head": {"rotation": ("-4", 0, 0)}}, loop="once")
    elif weapon == "shield":   # 방패를 앞으로 내밀고 포구에서 발사 (반동)
        m.anim("attack", 0.6, {"left_arm": {"rotation": ("-45 + math.sin(q.anim_time * 1200) * 5", "25", 0)},
                               "right_arm": {"rotation": ("-30", "-20", 0)},
                               "torso": {"rotation": ("6", "-10", 0)}}, loop="once")
    elif weapon == "gatling":   # 허리춤에서 들고 연사, 총열이 빙글빙글 돈다
        m.anim("attack", 1.0, {"right_arm": {"rotation": ("-80 + math.sin(q.anim_time * 3600) * 2", "-10", 0)},
                               "left_arm": {"rotation": ("-70", "35", 0)},
                               "barrels": {"rotation": (0, "q.anim_time * 1440", 0)},
                               "torso": {"rotation": ("-4", 0, 0)}}, loop="once")
    elif weapon == "sniper":   # 천천히 조준했다가 한 발, 크게 반동
        m.anim("attack", 0.9, {"right_arm": {"rotation": ("-90 + math.sin(q.anim_time * 400) * 7", "-6", 0)},
                               "left_arm": {"rotation": ("-85", "28", 0)},
                               "head": {"rotation": ("-4", "-8", 0)}}, loop="once")
    elif weapon == "pistol":   # 한 손으로 빠르게 두 발
        m.anim("attack", 0.4, {"right_arm": {"rotation": ("-90 + math.sin(q.anim_time * 1800) * 8", "-5", 0)},
                               "left_arm": {"rotation": (0, 0, "-10")}}, loop="once")
    elif weapon == "gun":   # 조준 + 반동 (짧게 3번 흔들림)
        m.anim("attack", 0.6, {"right_arm": {"rotation": ("-90 + math.sin(q.anim_time * 1800) * 6", "-8", 0)},
                               "left_arm": {"rotation": ("-80", "30", 0)},
                               "head": {"rotation": ("-5", "-10", 0)}}, loop="once")
    elif weapon == "sword":   # 칼을 머리 위로 치켜들었다가 앞으로 내려베기
        m.anim("attack", 0.5, {"right_arm": {"rotation": ("-150 + q.anim_time * 260", "-15", 0)},
                               "torso": {"rotation": ("q.anim_time * 20", "math.sin(q.anim_time * 360) * 20", 0)}}, loop="once")
    else:
        m.anim("attack", 0.4, {"right_arm": {"rotation": ("-70 * math.sin(q.anim_time * 450)", 0, 0)}}, loop="once")
    return m


# ---------------------------------------------------------------- 나는 탈것

def sky_whale(name="sky_whale"):
    """별빛 고래: 하늘을 헤엄치는 거대한 고래. 등에 사람이 탄다 (등 높이 ≈ 22px)"""
    m = Model(name, seed=40)
    navy, navy2, belly, star, fin = "#1d2b5a", "#26386f", "#c9d6f0", "#ffe9a8", "#3a5aa8"
    top = 21.0
    m.bone("body", [0, 12, 0])
    box(m, "body", 0, 4, 0, 18, 17, 30, navy)                                   # 몸통
    box(m, "body", 0, 3.5, -1, 15, 3, 26, belly)                                # 배
    for i, (x, z) in enumerate([(-5, -8), (4, -3), (-2, 4), (6, 9), (-6, 11), (2, -11), (7, 2), (-4, -1)]):
        box(m, "body", x, top - 0.6 + (i % 2) * 0.2, z, 1.2, 0.8, 1.2, star)    # 등의 별 무늬
    for sx in (-1, 1):
        for i, z in enumerate((-6, 1, 8)):
            box(m, "body", sx * 9.05, 12 + i * 1.5, z, 0.3, 1.2, 1.2, star)      # 옆구리 별
    box(m, "body", 0, top - 0.5, 0, 9, 1.0, 9, "#2f3f7a")                       # 안장 자리
    saddle(m, top + 0.4, 0, 7, 7, leather="#3b2a6b", trim="#ffd86b", stirrup="#ffd86b", drop=9)   # 별빛 안장
    for sx in (-1, 1):
        box(m, "body", sx * 9.1, 6, 0, 0.3, 14, 1.4, "#3b2a6b")                  # 안장 띠 (몸통을 두름)
    box(m, "body", 0, 3.9, 0, 15.2, 0.3, 1.4, "#3b2a6b")
    box(m, "body", 0, top - 0.6, -12, 2.4, 0.8, 1.6, "#0b1430")                 # 숨구멍
    box(m, "body", 0, top + 0.2, -12, 1.2, 1.4, 0.6, "#9fe3ff")                 # 별빛 물보라
    box(m, "body", 0, top + 1.6, -12, 0.6, 1.0, 0.6, "#ffffff")
    for x, z, h in [(-4, 9, 2.4), (-3, 10.5, 1.6), (4.5, 8, 2.0), (5, 12, 1.4), (0, 13, 2.8)]:
        box(m, "body", x, top - 0.4, z, 1.0, h, 1.0, "#9fe3ff")                 # 등에 돋은 별 수정
        box(m, "body", x, top - 0.4 + h, z, 0.6, 0.6, 0.6, "#ffffff")
    for i in range(5):
        box(m, "body", -6 + i * 3, 3.4, -9 + i * 4.5, 1.6, 0.3, 1.6, star)       # 배의 별자리 점
    # 머리: 몸통에서 앞으로 갈수록 좁아지는 둥근 주둥이 + 양옆 입선 + 목 주름
    mouth = "#0b1430"
    hk = face(m, "eye_kind", navy, "#7fc8ff")
    m.bone("head", [0, 12, -15], "body")
    box(m, "head", 0, 4.5, -20.5, 17, 15, 11, navy,
        faces={"east": ("art", hk), "west": ("art", face(m, "eye_kind", navy, "#7fc8ff", mirror=True))})   # 머리
    box(m, "head", 0, 5.0, -27.5, 15, 12.5, 3.2, navy)                           # 주둥이 1단
    box(m, "head", 0, 5.6, -29.8, 12, 10.0, 1.6, navy2)                          # 주둥이 끝 (둥글게)
    box(m, "head", 0, 4.0, -21.0, 17.3, 4.2, 11.4, belly)                        # 아래턱: 옆면까지 밝게
    box(m, "head", 0, 4.4, -27.5, 15.3, 3.8, 3.4, belly)
    box(m, "head", 0, 5.0, -29.8, 12.3, 3.2, 1.8, belly)                          # 아래턱 끝
    for sx in (-1, 1):
        box(m, "head", sx * 8.7, 8.1, -21.0, 0.2, 0.7, 11.4, mouth)              # 옆 입선 (어두운 위·밝은 아래 경계)
        box(m, "head", sx * 7.7, 8.1, -27.5, 0.2, 0.7, 3.4, mouth)
        box(m, "head", sx * 6.2, 8.1, -29.8, 0.2, 0.7, 1.8, mouth)
        box(m, "head", sx * 8.7, 8.1, -15.4, 0.2, 2.0, 0.8, mouth)               # 입꼬리 (살짝 올라감)
    box(m, "head", 0, 8.1, -30.75, 12.4, 0.7, 0.2, mouth)                        # 앞쪽 입선
    for i in range(4):
        box(m, "head", -4.5 + i * 3, 3.95, -22.5, 0.5, 0.2, 12, "#a9bbdf")       # 목 주름 (아래쪽 줄무늬)
    # 지느러미
    for sx, side in ((-1, "fin_l"), (1, "fin_r")):
        m.bone(side, [sx * 9, 9, -6], "body")
        box(m, side, sx * 14, 8, -5, 10, 1.4, 6, fin, rot=[0, 0, sx * -15], pivot=[sx * 9, 9, -6])
        box(m, side, sx * 19, 7.2, -4, 3, 1.2, 4, star, rot=[0, 0, sx * -15], pivot=[sx * 9, 9, -6])
    # 꼬리 (두 마디) + 꼬리지느러미
    m.bone("tail0", [0, 13, 15], "body")
    box(m, "tail0", 0, 7, 21, 12, 11, 12, navy2)
    m.bone("tail1", [0, 12.5, 27], "tail0")
    box(m, "tail1", 0, 9, 31, 7, 7, 9, navy)
    m.bone("fluke", [0, 12.5, 35], "tail1")
    box(m, "fluke", 0, 12, 38, 22, 1.4, 6, fin)
    for sx in (-1, 1):
        box(m, "fluke", sx * 9, 12.1, 40.5, 5, 1.2, 3, star)
    swim = lambda f, a: {
        "tail0": {"rotation": (f"math.sin(q.anim_time * 360 * {f}) * {a}", 0, 0)},
        "tail1": {"rotation": (f"math.sin(q.anim_time * 360 * {f} - 50) * {a * 1.3}", 0, 0)},
        "fluke": {"rotation": (f"math.sin(q.anim_time * 360 * {f} - 100) * {a * 1.6}", 0, 0)},
        "fin_l": {"rotation": (0, 0, f"math.sin(q.anim_time * 360 * {f}) * {a}")},
        "fin_r": {"rotation": (0, 0, f"-math.sin(q.anim_time * 360 * {f}) * {a}")},
        "head": {"rotation": (f"math.sin(q.anim_time * 360 * {f} + 90) * 2", 0, 0)},
    }
    m.anim("idle", 3, swim(0.33, 8))
    m.anim("walk", 1.5, swim(0.67, 14))
    m.anim("fly", 1.5, swim(0.67, 14))
    m.anim("attack", 0.6, {"head": {"rotation": ("-12 * math.sin(q.anim_time * 300)", 0, 0)}}, loop="once")
    return m

def broom(name="broom"):
    """마법 빗자루: 손잡이에 걸터앉는다 (손잡이 높이 ≈ 20px). 앞=-Z"""
    m = Model(name, seed=41)
    wood, wood2, straw, straw2, band, gem = "#7a4f2a", "#5e3b1e", "#e8c15a", "#c99a35", "#7b3fbf", "#9be7ff"
    y = 19.0
    m.bone("body", [0, y, 0])
    box(m, "body", 0, y, -6, 1.6, 1.6, 30, wood)                                # 손잡이
    box(m, "body", 0, y + 0.05, -20.5, 1.9, 1.9, 1.5, band)                     # 손잡이 끝 장식
    box(m, "body", 0, y - 0.4, -22, 2.4, 2.4, 2.4, gem)                         # 보석
    box(m, "body", 0, y - 0.1, -2, 2.2, 2.2, 1.0, band)                          # 띠
    box(m, "body", 0, y - 0.6, 3, 1.0, 3.0, 4, wood2)                            # 발받침 기둥
    box(m, "body", 0, y - 3.0, 3, 8, 0.8, 2.4, wood2)                            # 발받침
    m.bone("bristles", [0, y + 0.8, 9], "body")
    box(m, "bristles", 0, y - 2.2, 10, 4.5, 6, 2, band)                          # 묶은 끈
    box(m, "bristles", 0, y - 3.2, 15, 7, 8, 9, straw)                           # 빗자루 털
    box(m, "bristles", 0, y - 3.6, 19.5, 8.4, 8.8, 1.2, straw2)                  # 털 끝
    for sx in (-1, 1):
        box(m, "bristles", sx * 3.8, y - 2.5, 14, 0.8, 6.4, 7, straw2)
    for k in range(5):
        box(m, "body", 0, y - 0.05, -16 + k * 3.2, 1.8, 1.8, 0.6, "#4a7a3a")      # 손잡이를 감은 덩굴
        box(m, "body", 0.9 if k % 2 else -0.9, y + 1.5, -15 + k * 3.2, 0.6, 0.4, 1.0, "#6fb04a")   # 잎사귀
    box(m, "body", 0, y - 0.7, -17.8, 0.3, 1.6, 0.3, "#d4af37")                  # 랜턴 고리
    box(m, "body", 0, y - 3.5, -17.8, 1.8, 2.6, 1.8, "#d4af37")                  # 랜턴 틀
    box(m, "body", 0, y - 3.2, -17.8, 2.0, 2.0, 1.4, "#ffd86b")                  # 랜턴 불빛
    box(m, "body", 0, y - 0.9, -17.8, 1.2, 0.4, 1.2, "#d4af37")
    for sx in (-1, 1):
        box(m, "body", sx * 1.4, y - 2.0, -8, 0.2, 2.0, 0.2, "#d4af37")          # 별 부적 줄
        box(m, "body", sx * 1.4, y - 2.9, -8, 0.3, 0.9, 0.9, "#9be7ff")          # 별 부적
    box(m, "bristles", 0, y - 0.6, 10, 5.0, 0.6, 2.2, "#d4af37")                  # 금 고리
    sway = lambda f, a: {
        "body": {"rotation": (f"math.sin(q.anim_time * 360 * {f}) * {a * 0.4}", 0, f"math.cos(q.anim_time * 360 * {f}) * {a * 0.5}")},
        "bristles": {"rotation": (f"math.sin(q.anim_time * 360 * {f * 2}) * {a}", f"math.cos(q.anim_time * 360 * {f * 2}) * {a}", 0)},
    }
    m.anim("idle", 2, sway(0.5, 3))
    m.anim("walk", 1, sway(1.5, 7))
    m.anim("fly", 1, sway(1.5, 7))
    return m

# ---------------------------------------------------------------- 장식 탈것 (그물로 잡는 인기 탈것 + 신화 비룡)

def crown(m, bone, cx, cy, cz, w, d, gold="#f2c14e", gem="#e0303a", gem2="#3fa8ff", h=1.6, spikes=True):
    """바닥 (cx, cy, cz) 중심 왕관: 금 테두리 + 뾰족한 장식 + 보석"""
    t = 0.6
    box(m, bone, cx, cy, cz - d / 2 + t / 2, w, h, t, gold)          # 앞
    box(m, bone, cx, cy, cz + d / 2 - t / 2, w, h, t, gold)          # 뒤
    box(m, bone, cx - w / 2 + t / 2, cy, cz, t, h, d, gold)          # 왼
    box(m, bone, cx + w / 2 - t / 2, cy, cz, t, h, d, gold)          # 오른
    if spikes:
        for x, z in ((-w / 2 + t / 2, -d / 2 + t / 2), (w / 2 - t / 2, -d / 2 + t / 2), (-w / 2 + t / 2, d / 2 - t / 2),
                     (w / 2 - t / 2, d / 2 - t / 2), (0, -d / 2 + t / 2), (0, d / 2 - t / 2)):
            box(m, bone, cx + x, cy + h, cz + z, t, h * 0.8, t, gold)
            box(m, bone, cx + x, cy + h * 1.8, cz + z, t * 0.7, 0.5, t * 0.7, "#fff2b0")
    box(m, bone, cx, cy + h * 0.25, cz - d / 2 - 0.05, 1.0, 1.0, 0.3, gem)       # 앞 보석
    box(m, bone, cx - w / 2 - 0.05, cy + h * 0.25, cz, 0.3, 1.0, 1.0, gem2)
    box(m, bone, cx + w / 2 + 0.05, cy + h * 0.25, cz, 0.3, 1.0, 1.0, gem2)


def saddle(m, cy, cz, w, d, leather="#6b2f1a", trim="#f2c14e", stirrup="#d9d9d9", drop=5):
    """등(cy) 위 안장 + 양옆 등자"""
    box(m, "body", 0, cy, cz, w + 0.4, 1.2, d, leather)
    box(m, "body", 0, cy + 1.2, cz - d / 2 + 0.8, w * 0.5, 1.6, 1.4, leather)     # 앞 손잡이
    box(m, "body", 0, cy + 1.2, cz + d / 2 - 0.8, w * 0.7, 1.4, 1.2, leather)     # 뒤 등받이
    box(m, "body", 0, cy + 1.2, cz - d / 2 + 0.8, w * 0.5 + 0.2, 0.4, 1.6, trim)
    for sx in (-1, 1):
        box(m, "body", sx * (w / 2 + 0.25), cy - drop, cz, 0.3, drop, 0.6, "#3a2414")   # 끈
        box(m, "body", sx * (w / 2 + 0.4), cy - drop - 0.8, cz, 0.6, 0.8, 1.8, stirrup)  # 등자


# 아래 세 모델은 '장식만' 있다: 바닐라 몹 모습은 그대로 두고(숨기지 않음) 왕관·망토 등을 얹는다.
# 좌표는 바닐라 자바 모델(1.21) 기준, 앞 = -Z. 'h_' 뼈는 BetterModel이 몹 머리 방향을 따라 돌린다.

def mount_horse(name="mount_horse"):
    """말 장식: 루비 왕관 + 붉은 깃털 (머리 기울기 30° 반영)"""
    m = Model(name, seed=70)
    m.bone("h_head", [0, 20, -12], rotation=(-30, 0, 0))     # 바닐라 말 head_parts 피벗
    crown(m, "h_head", 0, 31, -11, 5.6, 5.0, h=1.4)           # 머리 윗면(로컬 y+11), 귀(뒤쪽) 앞
    box(m, "h_head", 0, 33.2, -9.2, 1.2, 4.0, 2.2, "#d42a3a", rot=[25, 0, 0])   # 깃털
    return m


def mount_wolf(name="mount_wolf"):
    """늑대 장식: 루비 왕관 + 흰 털 테두리 붉은 망토 + 금 걸쇠"""
    red, red2, ermine, gold = "#a8182a", "#7d0f1e", "#f4f1ea", "#f2c14e"
    m = Model(name, seed=71)
    m.bone("body", [0, 0, 0])
    box(m, "body", 0, 13.0, 4.5, 6.8, 0.6, 8.6, red)                    # 등 망토
    for sx in (-1, 1):
        box(m, "body", sx * 3.45, 10.4, 4.5, 0.5, 2.8, 8.6, red)          # 옆으로 늘어진 망토
        box(m, "body", sx * 3.5, 9.8, 4.5, 0.7, 0.8, 8.8, ermine)         # 아래 흰 털
        for z in (1.5, 4.5, 7.5):
            box(m, "body", sx * 3.86, 10.0, z, 0.1, 0.4, 0.4, "#1a1a1a")  # 털 점무늬
    box(m, "body", 0, 13.3, 0.0, 8.6, 1.0, 1.4, ermine)                 # 목둘레 털
    box(m, "body", 0, 12.9, -0.8, 1.6, 1.6, 0.4, gold)                  # 걸쇠
    box(m, "body", 0, 13.6, 4.5, 3.6, 0.4, 3.6, red2)                   # 앉는 자리
    m.bone("h_head", [0, 10.5, -7])                                     # 바닐라 늑대 머리 피벗
    crown(m, "h_head", 0, 13.5, -8.1, 4.4, 2.6, h=1.3)                  # 머리 윗면, 귀 앞
    return m


def mount_fox(name="mount_fox"):
    """여우 장식: 벚꽃 화관 + 붉은 매듭 목줄과 금방울"""
    m = Model(name, seed=72)
    m.bone("h_head", [0, 7.5, -3])                                      # 바닐라 여우 머리 피벗
    ring = [(-3.4, -7.4), (-1.8, -7.8), (0, -7.9), (1.8, -7.8), (3.4, -7.4), (3.7, -5.6), (3.4, -3.8),
            (-3.4, -3.8), (-3.7, -5.6), (-1.6, -3.4), (1.6, -3.4)]
    for i, (x, z) in enumerate(ring):
        c = ("#ffb7d0", "#ffffff", "#ff8fb5")[i % 3]
        box(m, "h_head", x, 9.5, z, 1.5, 1.1, 1.5, c)
        box(m, "h_head", x, 10.3, z, 0.5, 0.5, 0.5, "#ffe46b")
        box(m, "h_head", x * 0.9, 9.4, z + 0.3, 1.0, 0.4, 0.9, "#5aa04a")
    box(m, "h_head", 0, 3.0, -2.6, 8.6, 1.2, 1.6, "#d42a3a")             # 목줄
    box(m, "h_head", 0, 2.6, -3.6, 2.4, 1.6, 0.8, "#ffffff")             # 매듭
    box(m, "h_head", 0, 1.1, -3.6, 1.6, 1.6, 1.6, "#f2c14e")             # 방울
    return m


def _seg(m, bone, a, b, w, h, color, faces=None, extra=0.6):
    """점 a→b를 잇는 단면 w×h 막대 (회전 상자). (중심, 회전, 위쪽 벡터, 길이) 반환"""
    dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    if dz < 0 or (dz == 0 and dx < 0):
        dx, dy, dz = -dx, -dy, -dz
    L = math.sqrt(dx * dx + dy * dy + dz * dz)
    hl = math.hypot(dx, dz)
    rx, ry = math.atan2(-dy, hl), math.atan2(dx, dz)
    up = (math.sin(rx) * math.sin(ry), math.cos(rx), math.sin(rx) * math.cos(ry))
    c = [(a[i] + b[i]) / 2 for i in range(3)]
    rot = [round(math.degrees(rx), 2), round(math.degrees(ry), 2), 0]
    box(m, bone, c[0], c[1] - h / 2, c[2], w, h, L + extra, color,
        rot=rot if abs(rot[0]) + abs(rot[1]) > 0.01 else None, pivot=c, faces=faces)
    return c, rot, up, L


def _tube(m, bone, pts, radii, color, faces=None, belly=None, belly_faces=None, spikes=None, spike_from=0):
    """점들을 따라 굵기가 변하는 몸통. belly: 배 비늘판 색, spikes: (색 목록, 높이 배수) 등지느러미"""
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        r = (radii[i] + radii[i + 1]) / 2
        c, rot, up, L = _seg(m, bone, a, b, 2 * r, 2 * r, color, faces)
        R = rot if abs(rot[0]) + abs(rot[1]) > 0.01 else None
        sg = -1 if up[1] >= 0 else 1                   # 배 쪽 = 아래(또는 앞)
        if belly:
            bc = [c[k] + up[k] * sg * (r - 0.2) for k in range(3)]
            box(m, bone, bc[0], bc[1] - 0.4, bc[2], 2 * r * 0.74, 0.8, L * 0.96, belly, rot=R, pivot=bc, faces=belly_faces)
        if spikes and i >= spike_from:
            cols, k = spikes
            for j, t in enumerate((0.25, 0.7)):
                sh = max(0.9, r * k * (1.0 if j == 0 else 0.75))
                p0 = [a[q] + (b[q] - a[q]) * t for q in range(3)]
                sc = [p0[q] - up[q] * sg * (r + sh / 2 - 0.3) for q in range(3)]
                box(m, bone, sc[0], sc[1] - sh / 2, sc[2], 0.7, sh, max(1.0, r * 0.7), cols[(i + j) % len(cols)], rot=R, pivot=sc)


def black_dragon(name, black="#1b1b22", belly="#4a4038", flame=("#c81e1e", "#ff5a1a", "#e8341a"),
                 flame_tip="#ffb02e", horn="#8a7a5c", horn_tip="#e8dcc0", gold="#c9a24a", eye="#ffd000", seed=74):
    """흑룡: S자로 높이 세운 목, 똬리 튼 몸통, 말려 올라간 꼬리, 불꽃 갈기·등지느러미, 뒤로 휜 뿔, 긴 수염.
    등(안장) 높이 ≈ 23px, 앞 = -Z"""
    m = Model(name, seed)
    def AF(key):
        return {f: ("art", key) for f in ("north", "south", "east", "west", "up", "down")}
    SC = AF(m.art("scale_black", _scale_rows(), {"s": black, "d": shade(black, -20), "l": shade(black, 22), "h": "#4a2626"}))
    BE = AF(m.art("belly_black", _belly_rows(), {"s": belly, "d": shade(belly, -40), "l": shade(belly, 25)}))
    FL = (list(flame), 0.85)

    # ── 몸통: 안장 자리(수평) ──
    m.bone("body", [0, 18.5, 0])
    _tube(m, "body", [(0, 18.5, -6), (0, 18.5, 4)], [4.8, 4.6], black, SC, belly, BE)
    # 안장 + 붉은 비단
    box(m, "body", 0, 22.9, -0.5, 7.6, 0.5, 8.5, "#7a0f14")
    box(m, "body", 0, 22.8, -0.5, 7.9, 0.3, 8.9, gold)
    for sx in (-1, 1):
        box(m, "body", sx * 4.9, 19.4, -0.5, 0.4, 3.6, 8.5, "#7a0f14")
        box(m, "body", sx * 5.0, 19.0, -0.5, 0.5, 0.6, 8.7, gold)
        box(m, "body", sx * 5.2, 20.6, -0.5, 0.3, 1.4, 1.4, "#ff5a1a")      # 불꽃 보석
    saddle(m, 23.3, -0.5, 5.6, 7, leather="#2a1416", trim=gold, stirrup=gold, drop=8)
    # 가슴 갑판 (참고 그림의 비늘 갑옷)
    box(m, "body", 0, 13.8, -9.2, 6.4, 7.0, 1.4, "#2a2a32", rot=[-18, 0, 0])
    box(m, "body", 0, 16.6, -9.9, 4.2, 1.6, 0.4, gold, rot=[-18, 0, 0])

    # ── 목: S자로 높이 선다 ──
    m.bone("neck", [0, 19, -6], "body")
    _tube(m, "neck", [(0, 18.5, -4), (0, 21.5, -8.6), (0, 26.5, -11.2), (0, 31.5, -11.4), (0, 35.5, -12.4)],
          [4.6, 4.2, 3.8, 3.5, 3.3], black, SC, belly, BE, spikes=FL)
    for y, z in ((24.5, -12.9), (29.5, -14.0)):
        box(m, "neck", 0, y, z, 4.2, 2.4, 0.8, "#2a2a32")                   # 목 앞 갑판
        box(m, "neck", 0, y + 2.0, z - 0.3, 4.4, 0.4, 0.6, gold)

    # ── 머리 ──
    hb = m.bone("head", [0, 35.5, -12.4], "neck")
    # 참고 그림의 눈: 무거운 눈썹뼈 아래 가늘고 비스듬히 찢어진 눈, 금빛으로 번지는 안광 (앞 = 오른쪽)
    ER = ["bbbbbbbbbbbbbbbb",
          "bbbbbbbbbbbbbbbb",
          "bbBBBbbbbbbbbbbb",
          "bbsBBBBBbbbbbbbb",
          "bbbskkBBBBBbbbbb",
          "bbbbkGGkkBBBBbbb",
          "bbbbkGYYGGkkBBBb",
          "bbbbbkGYWWYGGkkb",
          "bbbbbbkGYWWWYGkb",
          "bbbbbbbkkGYYYGkb",
          "bbbbbbbbbkkkkkbb",
          "bbbbbbbbbbbbsbbb",
          "bbbbbbbbbbbbbbbb",
          "bbsbbbbbbbbbbbbb",
          "bbbbbbbbbsbbbbbb",
          "bbbbbbbbbbbbbbbb"]
    EP = {"b": black, "s": shade(black, -20), "B": shade(black, 30), "k": "#050505",
          "G": "#ff9a00", "Y": eye, "W": "#fffbe0"}
    eyes = {"east": ("art", m.art("bd_eye", ER, EP)), "west": ("art", m.art("bd_eye_m", [r[::-1] for r in ER], EP))}
    skull = dict(SC); skull.update(eyes)
    box(m, hb, 0, 35.3, -15.0, 6.4, 5.4, 6.4, black, faces=skull)               # 두개골
    box(m, hb, 0, 35.7, -20.2, 4.8, 3.4, 4.4, black, faces=SC)                   # 주둥이
    box(m, hb, 0, 39.1, -20.4, 3.4, 0.9, 4.6, shade(black, 18))                 # 콧등
    box(m, hb, 0, 36.2, -22.6, 4.2, 2.6, 0.8, shade(black, -10))                # 코끝
    for sx in (-1, 1):
        box(m, hb, sx * 1.2, 38.5, -23.05, 0.9, 0.6, 0.2, "#160404")           # 콧구멍
        box(m, hb, sx * 2.6, 40.4, -16.2, 1.6, 1.3, 4.6, shade(black, 12), rot=[0, 0, sx * -12])   # 눈썹뼈 (안쪽이 내려온 성난 눈썹)
        box(m, hb, sx * 3.2, 41.2, -18.2, 0.6, 1.4, 0.8, horn_tip, rot=[25, 0, sx * 20])   # 눈썹 가시
        box(m, hb, sx * 3.7, 36.0, -14.2, 0.8, 1.3, 3.4, horn, rot=[0, sx * 25, 0])         # 뺨 가시
        box(m, hb, sx * 3.9, 37.6, -12.8, 0.7, 1.0, 2.6, horn, rot=[0, sx * 35, 0])
        for k in range(4):
            box(m, hb, sx * 1.9, 34.4 if k == 0 else 34.8, -18.6 - k * 1.2, 0.5, 1.4 if k == 0 else 0.9, 0.5, "#fff4dc")   # 윗니(송곳니)
        # 뒤로 휘는 뿔
        _tube(m, hb, [(sx * 2.0, 40.4, -14.6), (sx * 2.6, 42.6, -13.0), (sx * 3.1, 43.9, -10.4),
                      (sx * 3.3, 43.7, -7.4), (sx * 3.0, 42.5, -4.8)], [1.0, 0.9, 0.75, 0.6, 0.45], horn)
        _seg(m, hb, (sx * 3.0, 42.5, -4.8), (sx * 2.6, 41.2, -3.0), 0.6, 0.6, horn_tip)
        _seg(m, hb, (sx * 2.8, 43.2, -11.5), (sx * 4.2, 45.0, -11.0), 0.6, 0.6, horn)        # 곁가지 뿔
    # 아래턱 (벌린 입)
    m.bone("jaw", [0, 36.0, -16.6], hb)
    JR, JP = [-16, 0, 0], [0, 36.0, -16.6]
    box(m, "jaw", 0, 34.0, -19.6, 4.2, 1.4, 5.8, black, rot=JR, pivot=JP, faces=SC)
    box(m, "jaw", 0, 35.3, -19.6, 3.2, 0.3, 5.0, "#8a1a1a", rot=JR, pivot=JP)          # 혀·입속
    for sx in (-1, 1):
        for k in range(3):
            box(m, "jaw", sx * 1.7, 35.4, -18.8 - k * 1.4, 0.5, 0.8, 0.5, "#fff4dc", rot=JR, pivot=JP)
    for k, (dx, c) in enumerate(((0, flame[0]), (-1.0, flame[1]), (1.0, flame[1]), (0, flame_tip))):   # 불꽃 턱수염
        box(m, "jaw", dx, 30.8 + (k == 3) * -1.4, -17.6 + abs(dx) * 0.4, 1.2 if k < 3 else 0.7, 3.4, 1.0, c, rot=[-30, 0, dx * 12], pivot=JP)
    # 불꽃 갈기 (머리 뒤로 휘날림)
    m.bone("mane", [0, 39, -12], hb)
    tufts = [(0, 41.3, -11.6, 1.6, 4.2, 1.4, flame[1], [-45, 0, 0]), (0, 44.6, -9.0, 0.8, 1.8, 0.8, flame_tip, [-55, 0, 0])]
    for sx in (-1, 1):
        tufts += [(sx * 3.4, 37.4, -11.2, 1.4, 4.4, 1.4, flame[0], [-35, 0, sx * 28]),
                  (sx * 2.8, 40.2, -11.0, 1.2, 4.0, 1.2, flame[2], [-55, 0, sx * 15]),
                  (sx * 4.0, 34.6, -12.2, 1.2, 3.4, 1.2, flame[1], [-20, 0, sx * 45]),
                  (sx * 5.6, 39.6, -9.4, 0.7, 1.6, 0.7, flame_tip, [-35, 0, sx * 28]),
                  (sx * 6.2, 36.2, -11.2, 0.7, 1.4, 0.7, flame_tip, [-20, 0, sx * 45])]
    for x, y, z, w, h, d, c, r in tufts:
        box(m, "mane", x, y, z, w, h, d, c, rot=r, pivot=[x, y, z])
    # 긴 수염 (흔들림)
    for sx in (-1, 1):
        wb = m.bone("whisker_l" if sx < 0 else "whisker_r", [sx * 2.2, 37.4, -22], hb)
        _tube(m, wb, [(sx * 2.2, 37.4, -22), (sx * 5.0, 36.8, -21.2), (sx * 7.6, 35.2, -19.0),
                      (sx * 9.0, 32.8, -16.4), (sx * 9.4, 30.6, -13.4)], [0.25] * 5, "#e0401a")

    # ── 앞다리 ──
    for sx, sd in ((-1, "l"), (1, "r")):
        lb = m.bone(f"fleg_{sd}", [sx * 4.4, 17, -4], "body")
        _tube(m, lb, [(sx * 4.8, 17, -4), (sx * 5.8, 12.6, -6.8), (sx * 5.6, 10.0, -9.6)], [2.0, 1.6, 1.3], black, SC)
        box(m, lb, sx * 5.6, 8.6, -10.6, 3.2, 1.8, 3.6, black, faces=SC)                    # 발
        for k in (-1, 0, 1):
            box(m, lb, sx * 5.6 + k * 1.0, 8.6, -12.8, 0.6, 0.8, 1.2, horn_tip)              # 발톱
        box(m, lb, sx * 5.4, 14.0, -4.6, 3.0, 3.6, 4.4, "#2a2a32")                       # 어깨 갑판
        box(m, lb, sx * 5.4, 17.4, -4.6, 3.2, 0.5, 4.6, gold)
        box(m, lb, sx * 6.8, 11.6, -6.0, 0.6, 2.6, 1.2, flame[0], rot=[40, 0, sx * -20])   # 팔꿈치 불꽃
        box(m, lb, sx * 7.0, 13.6, -5.2, 0.5, 1.8, 1.0, flame_tip, rot=[45, 0, sx * -25])

    # ── 똬리 튼 몸통 → 말려 올라간 꼬리 ──
    m.bone("coil", [0, 18.5, 4], "body")
    _tube(m, "coil", [(0, 18.5, 4), (2, 16.5, 10), (6, 13, 14.5), (9.5, 10, 19.5), (9, 8, 25.5), (4, 7, 29),
                      (-3, 7, 29.5), (-8.5, 8, 26.5), (-11, 10, 21.5)],
          [4.6, 4.4, 4.1, 3.8, 3.5, 3.2, 2.9, 2.6, 2.4], black, SC, belly, BE, spikes=FL, spike_from=1)
    for sx, base, knee, foot in ((-1, (-1.8, 14.5, 11), (-4.0, 10.6, 9.6), (-4.2, 8.2, 7.8)),
                                 (1, (7.2, 11.5, 14.5), (9.0, 7.8, 12.8), (9.2, 5.4, 11.0))):
        lb = m.bone("rleg_l" if sx < 0 else "rleg_r", list(base), "coil")
        _tube(m, lb, [base, knee, foot], [2.2, 1.7, 1.3], black, SC)
        box(m, lb, foot[0], foot[1] - 1.4, foot[2] - 0.8, 3.0, 1.8, 3.6, black, faces=SC)
        for k in (-1, 0, 1):
            box(m, lb, foot[0] + k * 1.0, foot[1] - 1.4, foot[2] - 3.0, 0.6, 0.8, 1.2, horn_tip)
    m.bone("tail", [-11, 10, 21.5], "coil")
    _tube(m, "tail", [(-11, 10, 21.5), (-12, 14.5, 18.5), (-12, 19.5, 17.5), (-11, 23.5, 18.5)],
          [2.4, 2.1, 1.8, 1.5], black, SC, belly, BE, spikes=FL)
    m.bone("tail_tip", [-11, 23.5, 18.5], "tail")
    _tube(m, "tail_tip", [(-11, 23.5, 18.5), (-9.5, 26.5, 21), (-7.5, 27.5, 24)], [1.5, 1.1, 0.8], black, SC, spikes=FL)
    for k, (dy, dz, c, r) in enumerate(((0, 0, flame[0], -60), (1.6, -0.4, flame[1], -35), (-1.4, 0.6, flame[2], -85),
                                        (3.0, 0.4, flame_tip, -25), (-2.6, 1.6, flame_tip, -100))):
        x, y, z = -7.2, 27.0 + dy, 24.6 + dz
        box(m, "tail_tip", x, y, z, 1.0 if k < 3 else 0.6, 4.6 if k < 3 else 2.6, 1.2, c, rot=[r, 0, 0], pivot=[x, y, z])   # 꼬리 끝 불꽃

    # ── 애니메이션 ──
    def base(f, a, legs):
        T = lambda ph=0, mul=1: f"math.sin(q.anim_time * 360 * {f * mul} + {ph})"
        ch = {"neck": {"rotation": (f"{T()} * {a * 0.5}", f"{T(60)} * {a * 0.4}", 0)},
              "head": {"rotation": (f"{T(90)} * {a * 0.6}", f"{T(120)} * {a * 0.8}", 0)},
              "jaw": {"rotation": (f"{T(0, 2)} * 4", 0, 0)},
              "mane": {"rotation": (f"{T(0, 2)} * 8", 0, f"{T(90, 2)} * 5")},
              "coil": {"rotation": (0, f"{T(30)} * {a * 0.3}", 0)},
              "tail": {"rotation": (f"{T(80)} * {a * 0.5}", f"{T(60)} * {a * 1.2}", 0)},
              "tail_tip": {"rotation": (f"{T(140)} * {a * 0.8}", f"{T(120)} * {a * 1.6}", 0)},
              "whisker_l": {"rotation": (f"{T(0, 1.5)} * 14", 0, f"{T(90)} * 10")},
              "whisker_r": {"rotation": (f"{T(90, 1.5)} * 14", 0, f"{T(180)} * -10")}}
        if legs == "walk":
            for n, ph in (("fleg_l", 0), ("fleg_r", 180), ("rleg_l", 180), ("rleg_r", 0)):
                ch[n] = {"rotation": (f"{T(ph)} * 22", 0, 0)}
        elif legs == "fly":
            for n in ("fleg_l", "fleg_r", "rleg_l", "rleg_r"):
                ch[n] = {"rotation": (f"35 + {T()} * 6", 0, 0)}
        return ch
    m.anim("idle", 4, base(0.25, 5, None))
    m.anim("walk", 1.2, base(0.83, 7, "walk"))
    m.anim("fly", 1.5, base(0.67, 9, "fly"))
    m.anim("attack", 0.6, {"neck": {"rotation": ("12 * math.sin(q.anim_time * 300)", 0, 0)},
                           "head": {"rotation": ("-28 * math.sin(q.anim_time * 300)", 0, 0)},
                           "jaw": {"rotation": ("-30 * math.sin(q.anim_time * 300)", 0, 0)}}, loop="once")
    return m


def dark_rider(name="dark_rider", steel="#56616b", dark="#262c33", light="#93a3ae", glow="#3fe0ff", glow2="#b8f6ff",
               cloth="#174450", horse="#1e2227", horse2="#30363d", seed=81):
    """흑기사: 검은 판금 갑옷에 청록 빛줄기, 장창을 든 기사가 갑옷 입은 검은 군마를 탄 보스. 앞 = -Z"""
    m = Model(name, seed)
    # ── 말 몸통 ──
    m.bone("body", [0, 16, 0])
    box(m, "body", 0, 11, 0, 10, 10, 22, horse)                                    # 몸통
    box(m, "body", 0, 12.5, -8.5, 9, 8, 6, horse2)                                 # 가슴
    box(m, "body", 0, 12, 8, 9.6, 9, 7, horse2)                                    # 엉덩이
    for sx in (-1, 1):                                                              # 마갑 (옆 판금 + 청록 빛줄)
        box(m, "body", sx * 5.15, 12, -2, 0.6, 7.5, 14, steel)
        box(m, "body", sx * 5.5, 15.5, -2, 0.3, 0.5, 13.5, glow)
        box(m, "body", sx * 5.5, 12.2, -2, 0.3, 0.6, 14.2, dark)
        for z in (-7, -2, 3):
            box(m, "body", sx * 5.55, 13.5, z, 0.3, 1.2, 1.2, light)               # 리벳
    box(m, "body", 0, 20.8, 1, 10.4, 0.6, 12, cloth)                               # 안장 천
    for sx in (-1, 1):
        box(m, "body", sx * 5.3, 16.5, 1, 0.4, 4.6, 11, cloth)
        box(m, "body", sx * 5.45, 16.3, 1, 0.3, 0.5, 11.2, glow)                   # 천 끝 빛줄
    box(m, "body", 0, 21.2, 1, 6, 1.0, 7, dark)                                    # 안장
    box(m, "body", 0, 22.0, -2.6, 4, 1.6, 1.2, dark)
    box(m, "body", 0, 22.0, 4.4, 5, 1.4, 1.2, dark)
    box(m, "body", 0, 13.2, -11.6, 7, 6, 1.0, steel)                               # 가슴 판금
    box(m, "body", 0, 15.6, -12.2, 2, 2, 0.4, glow)                                # 가슴 문장
    # ── 목·머리 ──
    m.bone("neck", [0, 19, -10], "body")
    _seg(m, "neck", (0, 18.5, -10), (0, 26, -15), 5.2, 5.6, horse)
    _seg(m, "neck", (0, 19.5, -11.5), (0, 26.5, -16.2), 4.4, 0.8, steel)           # 목 판금 (위)
    for k in range(5):                                                              # 갈기 (가시 + 청록 끝)
        y, z = 21 + k * 1.4, -9.2 - k * 1.1
        box(m, "neck", 0, y, z, 0.8, 2.2, 1.2, dark, rot=[30, 0, 0], pivot=[0, y, z])
        box(m, "neck", 0, y + 2.0, z + 1.1, 0.5, 0.6, 0.6, glow)
    m.bone("head", [0, 26, -15], "neck")
    _seg(m, "head", (0, 27.5, -15), (0, 23.5, -23.5), 4.6, 4.8, horse)             # 머리 (아래로 숙임)
    _seg(m, "head", (0, 29.6, -15.2), (0, 25.6, -23.2), 4.0, 0.7, steel)           # 투구 판 (chanfron)
    box(m, "head", 0, 28.6, -19.8, 0.8, 0.8, 4.2, dark, rot=[-25, 0, 0], pivot=[0, 29, -18])   # 이마 뿔
    box(m, "head", 0, 29.6, -22.4, 0.5, 0.5, 1.4, glow2, rot=[-25, 0, 0], pivot=[0, 29, -18])
    for sx in (-1, 1):
        box(m, "head", sx * 2.42, 26.2, -17.8, 0.2, 0.8, 1.6, glow)                # 빛나는 눈
        box(m, "head", sx * 1.3, 29.4, -14.6, 0.9, 2.2, 0.9, dark, rot=[-15, 0, sx * 10])   # 귀
        box(m, "head", sx * 2.5, 24.0, -20.5, 0.3, 0.4, 3, light)                  # 굴레
    box(m, "head", 0, 22.6, -23.6, 3.6, 1.2, 1.6, horse2)                          # 주둥이
    # ── 다리 ──
    for nm, x, z in (("fleg_l", -3.2, -8), ("fleg_r", 3.2, -8), ("bleg_l", -3.2, 8), ("bleg_r", 3.2, 8)):
        m.bone(nm, [x, 12, z], "body")
        box(m, nm, x, 1.2, z, 2.8, 11, 2.8, horse)
        box(m, nm, x, 5.0, z, 3.2, 4.4, 3.2, steel)                                # 정강이 판금
        box(m, nm, x, 7.2, z - 1.5, 2.2, 0.5, 0.3, glow)
        box(m, nm, x, 0, z, 3.2, 1.4, 3.2, dark)                                   # 발굽
        box(m, nm, x, 1.4, z, 3.4, 0.7, 3.4, light)
    # ── 꼬리 ──
    m.bone("tail", [0, 19, 11.5], "body")
    for k, (dx, c) in enumerate(((0, horse2), (-0.8, horse), (0.8, horse))):
        _seg(m, "tail", (dx * 0.3, 19, 11.5), (dx, 9.5, 15 + k * 0.4), 1.2, 1.2, c)
    box(m, "tail", 0, 9.0, 15.4, 0.6, 1.2, 0.6, glow)

    # ── 기사 ──
    m.bone("rider", [0, 24, 1], "body")
    for sx in (-1, 1):                                                              # 다리 (말 옆구리를 감쌈)
        _seg(m, "rider", (sx * 3.0, 24, 1.2), (sx * 5.8, 21, -2.2), 2.6, 2.6, steel)
        _seg(m, "rider", (sx * 5.9, 21.4, -2.0), (sx * 6.2, 15.4, -1.2), 2.4, 2.4, steel)
        box(m, "rider", sx * 6.2, 14.6, -2.0, 2.6, 1.4, 3.6, dark)                 # 철 장화
        box(m, "rider", sx * 6.0, 20.3, -2.9, 2.0, 1.6, 0.6, light)                # 무릎 보호대
        box(m, "rider", sx * 6.0, 20.9, -3.2, 0.8, 0.5, 0.2, glow)
    box(m, "rider", 0, 24, 1.2, 7.4, 9.6, 4.4, steel)                              # 흉갑
    box(m, "rider", 0, 26.8, -1.1, 5.4, 5.6, 0.6, dark)                            # 가슴 판
    box(m, "rider", 0, 28.6, -1.5, 1.6, 1.6, 0.4, glow)                            # 청록 핵
    box(m, "rider", 0, 29.0, -1.7, 0.8, 0.8, 0.3, glow2)
    for sx in (-1, 1):
        box(m, "rider", sx * 1.6, 24.4, -1.2, 0.3, 4.2, 0.3, glow)                 # 흉갑 빛줄
    box(m, "rider", 0, 23.2, 1.2, 7.8, 1.2, 4.8, dark)                             # 허리띠
    for sx in (-1, 1):
        box(m, "rider", sx * 2.4, 21.4, -1.2, 2.4, 2.6, 0.6, steel, rot=[-15, 0, 0])   # 앞 갑판
    # 망토
    m.bone("cape", [0, 33, 3.6], "rider")
    box(m, "cape", 0, 23, 3.8, 7.6, 10, 0.5, cloth)
    box(m, "cape", 0, 17.5, 6.4, 8.4, 6.2, 0.5, cloth, rot=[38, 0, 0], pivot=[0, 23, 3.8])
    box(m, "cape", 0, 17.3, 6.5, 8.5, 0.5, 0.6, glow, rot=[38, 0, 0], pivot=[0, 23, 3.8])
    # 투구
    m.bone("rhead", [0, 33.6, 1.2], "rider")
    box(m, "rhead", 0, 33.6, 1.2, 5.2, 5.6, 5.2, steel)
    box(m, "rhead", 0, 35.8, -1.45, 4.0, 0.7, 0.2, glow)                           # 눈 틈 (빛남)
    box(m, "rhead", 0, 34.0, -1.5, 1.0, 1.6, 0.3, dark)                            # 숨구멍 판
    box(m, "rhead", 0, 33.4, 1.2, 5.6, 1.0, 5.6, dark)                             # 목 가리개
    for k, (y, z, h) in enumerate(((39.2, 1.4, 2.4), (38.6, 3.0, 2.8), (37.6, 4.4, 2.2))):   # 뒤로 솟은 볏 가시
        box(m, "rhead", 0, y, z, 0.8, h, 0.9, dark, rot=[-30, 0, 0], pivot=[0, y, z])
    for sx in (-1, 1):
        box(m, "rhead", sx * 2.9, 36.4, 1.6, 0.8, 0.8, 3.6, dark, rot=[0, sx * -20, 20 * sx], pivot=[sx * 2.6, 36.8, 1.6])   # 옆 뿔
    # 어깨 (층층 가시 견갑)
    for sx, arm in ((-1, "larm"), (1, "rarm")):
        m.bone(arm, [sx * 4.4, 32.4, 1.2], "rider")
        box(m, arm, sx * 5.2, 30.4, 1.2, 3.6, 3.4, 4.6, steel)
        box(m, arm, sx * 5.6, 32.6, 1.2, 4.4, 1.2, 5.4, dark)
        box(m, arm, sx * 5.8, 33.6, 1.2, 3.6, 1.0, 4.6, steel)
        box(m, arm, sx * 7.2, 32.8, 1.2, 0.3, 0.6, 5.0, glow)                      # 견갑 빛줄
        for z in (-0.6, 1.4, 3.2):
            box(m, arm, sx * 6.2, 34.3, z, 0.7, 2.0, 0.7, dark, rot=[0, 0, sx * -20], pivot=[sx * 6.2, 34.3, z])   # 가시
    # 오른팔: 장창을 앞으로 비스듬히 세워 듦
    _seg(m, "rarm", (5.4, 30.6, 1.2), (5.8, 26.2, -2.6), 2.4, 2.4, steel)
    box(m, "rarm", 5.8, 25.0, -3.0, 2.8, 2.4, 2.8, dark)                           # 건틀릿
    _seg(m, "rarm", (5.8, 21.0, 2.0), (5.8, 45.0, -14.0), 0.8, 0.8, dark)          # 창대
    _seg(m, "rarm", (5.8, 27.0, -2.0), (5.8, 29.6, -3.8), 1.4, 1.4, light)         # 손잡이 고리
    _seg(m, "rarm", (5.8, 44.6, -13.7), (5.8, 49.0, -16.6), 1.4, 0.5, glow)        # 창날 (빛남)
    _seg(m, "rarm", (5.8, 48.4, -16.2), (5.8, 50.4, -17.6), 0.7, 0.4, glow2)
    _seg(m, "rarm", (5.8, 43.6, -13.0), (5.8, 44.8, -13.8), 2.4, 0.6, light)        # 창날 받침
    # 왼팔: 고삐를 잡음
    _seg(m, "larm", (-5.4, 30.6, 1.2), (-4.6, 26.0, -3.4), 2.4, 2.4, steel)
    box(m, "larm", -4.0, 24.6, -4.2, 2.6, 2.2, 2.6, dark)
    _seg(m, "larm", (-3.4, 25.4, -5.0), (-1.6, 25.0, -14.0), 0.3, 0.3, light)       # 고삐

    hitbox(m, 16, 40)
    # ── 애니메이션 ──
    T = lambda f, ph=0: f"math.sin(q.anim_time * 360 * {f} + {ph})"
    def ride(f, leg, bob):
        ch = {"body": {"rotation": (f"{T(f * 2)} * {bob * 0.3}", 0, 0)},
              "neck": {"rotation": (f"{T(f, 60)} * {bob}", 0, 0)},
              "head": {"rotation": (f"{T(f, 120)} * {bob * 0.8}", 0, 0)},
              "tail": {"rotation": (f"{T(f, 30)} * {4 + bob}", f"{T(f * 0.5)} * 8", 0)},
              "cape": {"rotation": (f"{T(f * 2, 40)} * {3 + bob}", 0, 0)},
              "rider": {"rotation": (f"{T(f * 2, 90)} * {bob * 0.4}", 0, 0)},
              "rhead": {"rotation": (0, f"{T(f * 0.5)} * 6", 0)}}
        if leg:
            for nm, ph in (("fleg_l", 0), ("fleg_r", 180), ("bleg_l", 200), ("bleg_r", 20)):
                ch[nm] = {"rotation": (f"{T(f, ph)} * {leg}", 0, 0)}
        return ch
    m.anim("idle", 4, ride(0.25, 0, 2))
    m.anim("walk", 0.9, ride(1.1, 32, 4))
    m.anim("attack", 0.7, {"rarm": {"rotation": ("40 * math.sin(q.anim_time * 257)", 0, 0)},
                           "rider": {"rotation": ("-10 * math.sin(q.anim_time * 257)", 0, 0)},
                           "fleg_l": {"rotation": ("-35 * math.sin(q.anim_time * 257)", 0, 0)},
                           "fleg_r": {"rotation": ("-35 * math.sin(q.anim_time * 257)", 0, 0)}}, loop="once")
    return m


def mount_dragon(name="mount_dragon"):
    """신화 탈것 흑룡"""
    return black_dragon(name)

# ---------------------------------------------------------------- 모델 목록

def build_all():
    print("모델 생성 중...")
    # 오크 부족
    decorate(humanoid("orc_warrior", 1.1, weapon="axe", seed=1), "orc_warrior", 1.1, 8, "#6a9a3a").save()
    decorate(humanoid("orc_archer", 1.05, shirt="#3d5a2a", weapon="bow", extras=("hood",), seed=2), "orc_archer", 1.05, 8, "#6a9a3a").save()
    decorate(humanoid("orc_shaman", 1.0, shirt="#5a2a4a", weapon="staff", extras=("skull_mask",), seed=3), "orc_shaman", 1.0, 8, "#6a9a3a").save()
    decorate(humanoid("orc_chief", 1.6, shirt="#4a2a1a", body_w=10, weapon="great_axe",
             extras=("horned_helmet", "pauldrons"), seed=4), "orc_chief", 1.6, 10, "#6a9a3a").save()
    # 그리스 신화
    medusa_skin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skins", "medusa.png")
    if os.path.exists(medusa_skin):   # 받은 스킨 얼굴 + 스킨 색에 맞춘 몸
        decorate(humanoid("medusa", 1.2, skin="#cdb9a2", shirt="#5d6b45", head="medusa", legs="none",
                 extras=("snake_tail",), weapon="bow", seed=5, face_skin=medusa_skin), "medusa", 1.2, 8, "#cdb9a2").save()
    else:
        humanoid("medusa", 1.2, skin="#9cc59a", shirt="#3a6b3a", head="medusa", legs="none",
                 extras=("snake_tail",), weapon="bow", seed=5).save()
    decorate(humanoid("minotaur", 1.45, skin="#7a5232", shirt="#4a3020", pants="#7a5232", boots="#2a2a2a",
             body_w=10, head="bull", weapon="double_axe", seed=6), "minotaur", 1.45, 10, "#7a5232").save()
    decorate(humanoid("cyclops", 1.9, skin="#c8a07a", shirt="#7a5a3a", pants="#6a4a2a", body_w=10,
             head="cyclops", weapon="club", seed=7), "cyclops", 1.9, 10, "#c8a07a").save()
    siren_skin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skins", "siren.png")
    if os.path.exists(siren_skin):
        skinned_siren("siren", siren_skin).save()      # 받은 스킨 + 꼬리 + 삼지창
    else:
        humanoid("siren", 1.0, skin="#bfe6ef", shirt="#1fa39a", head="siren", legs="none",
                 extras=("fish_tail",), weapon="trident", seed=8).save()
    harpy_skin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skins", "harpy.png")
    if os.path.exists(harpy_skin):
        skinned_harpy("harpy", harpy_skin).save()      # 받은 스킨 + 깃털 날개 + 새 발톱
    else:
        humanoid("harpy", 0.95, skin="#e6c9a8", shirt="#8b6a45", head="harpy", legs="bird",
                 extras=("wings",), seed=9).save()
    decorate_cerberus(quadruped("cerberus", 1.5, fur="#2b2b2b", belly="#3d3030", length=22, width=12, height=10, leg=11,
              heads=3, head_kind="dog", tail="tuft", tail_len=3, extras=("red_eyes", "spikes"), seed=10), 1.5).save()
    # 드래곤 (보스 / 탈것)
    texturize(eastern_dragon("dragon_east")).save()               # (예전 이그니스: 동양풍 용)
    western_dragon("dragon").save()                    # 이그니스: 서양풍 드래곤
    # 아군 펫 (받은 스킨)
    pets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skins", "pets")
    for mid, weapon, accent in [("rico_normal", None, "#9be37a"), ("rico_combat", "sword", "#9be37a"),
                                ("rapi_normal", None, "#ff6b6b"), ("rapi_combat", "gatling", "#e0303a"),
                                ("pet_red", "gun", "#ff3b3b"), ("pet_blue", "sniper", "#8aa6ff"),
                                ("pet_silver", "wing_shields", "#8ff4ff"), ("pet_pink", "pistol", "#ff6fb1")]:
        path = os.path.join(pets, mid + ".png")
        if os.path.exists(path):
            skinned_pet(mid, path, weapon, accent).save()
    # 마을 NPC (NameMC 스킨)
    npcs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skins", "npcs")
    if os.path.isdir(npcs):
        for f in sorted(os.listdir(npcs)):
            if f.endswith(".png"):
                skinned_pet("npc_" + f[:-4], os.path.join(npcs, f), None, seed=60).save()
    texturize(sky_whale()).save()                                 # 나는 탈것: 별빛 고래
    texturize(broom()).save()                                     # 나는 탈것: 마법 빗자루
    mount_horse().save()                               # 장식 탈것: 왕실 기사마
    mount_wolf().save()                                # 장식 탈것: 늑대왕
    mount_fox().save()                                 # 장식 탈것: 신령 여우
    texturize(dark_rider()).save()                         # 보스: 흑기사 (기마)
    mount_dragon().save()                                 # 신화 탈것: 비룡
    print("완료:", os.path.abspath(OUT))

if __name__ == "__main__":
    build_all()
