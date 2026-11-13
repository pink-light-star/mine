#!/usr/bin/env python3
"""plugins/BetterModel/models/*.bbmodel → models-src/preview/index.html (3D 미리보기 도감)"""
import json, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "plugins", "BetterModel", "models")
PREVIEW = os.path.join(ROOT, "models-src", "preview")

NAMES = {
    "orc_warrior": "오크 전사", "orc_archer": "오크 궁수", "orc_shaman": "오크 주술사", "orc_chief": "오크 대족장 크루가",
    "medusa": "메두사", "minotaur": "미노타우로스", "cyclops": "키클롭스", "siren": "사이렌", "harpy": "하피",
    "cerberus": "케르베로스", "dragon": "적룡 이그니스", 
    "sky_whale": "별빛 고래 (탈것)", "broom": "마법 빗자루 (탈것)",
    "mount_horse": "왕실 기사마 (탈것)", "mount_wolf": "늑대왕 (탈것)", "mount_fox": "신령 여우 (탈것)", "mount_dragon": "비룡 (신화 탈것)",
    "rico_normal": "세컨드 (평소)", "rico_combat": "리코 (전투)", "rapi_normal": "수영복 (평소)",
    "rapi_combat": "라피 (전투)", "pet_red": "레드후드", "pet_blue": "스노우화이트", "pet_silver": "신데렐라", "pet_pink": "엘리스",
}

data = {}
for key, name in NAMES.items():
    path = os.path.join(SRC, key + ".bbmodel")
    if not os.path.exists(path):
        continue
    m = json.load(open(path, encoding="utf-8"))
    data[key] = {"name": name, "res": m["resolution"]["width"], "elements": m["elements"], "groups": m["groups"],
                 "outliner": m["outliner"], "texture": m["textures"][0]["source"], "animations": m["animations"]}
tpl = open(os.path.join(PREVIEW, "template.html"), encoding="utf-8").read()
blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
open(os.path.join(PREVIEW, "index.html"), "w", encoding="utf-8").write(tpl.replace("__MODELS__", blob))
print(f"미리보기 갱신: {len(data)}개 모델")
