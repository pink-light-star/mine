#!/usr/bin/env python3
"""직업군 스킬 트리 데이터 → starrpg-src/resources/skills.yml
직업군(1차 직업) 12개 × 21개: 기본(F)·쉬좌(SL)·쉬우(SR)·패시브(P) 각 4개(1~4단계) + 쉬쉬(SS) 5개
  1단계 = 1차 Lv.10 · 2단계 = Lv.20 · 3단계 = 2차 Lv.30 · 4단계 = 3차 Lv.45
기존 손으로 만든 스킬은 kind: legacy (Skill enum 이름)
효과 종류(kind): nova 주변 폭발 · cone 앞 부채꼴 · beam 일직선 · dash 돌진 · leap 도약 강타 · rain 낙하 연타
                 pull 끌어당겨 폭발 · orb 날아가는 구체 · mark 지속 피해 · buff 강화 · heal 회복
쓰는 법: python3 gen_skills.py"""
import os, json

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "starrpg-src", "resources", "skills.yml")

# 직업군별 분위기: (입자, 보조 입자, 소리)
THEME = {
    "WARRIOR": ("SWEEP_ATTACK", "CRIT", "entity.player.attack.strong"),
    "ARCHER": ("CRIT", "END_ROD", "entity.arrow.shoot"),
    "MAGE": ("FLAME", "ELECTRIC_SPARK", "entity.blaze.shoot"),
    "ROGUE": ("SMOKE", "SQUID_INK", "entity.player.attack.sweep"),
    "CLERIC": ("END_ROD", "GLOW", "block.beacon.power_select"),
    "SWORDSMAN": ("SWEEP_ATTACK", "ENCHANTED_HIT", "entity.player.attack.sweep"),
    "NINJA": ("CLOUD", "SMOKE", "entity.ender_dragon.flap"),
    "MONK": ("CRIT", "POOF", "entity.player.attack.knockback"),
    "MOON_PRIEST": ("WITCH", "REVERSE_PORTAL", "block.amethyst_block.resonate"),
    "GUNSLINGER": ("SMOKE", "FIREWORK", "entity.generic.explode"),
    "LANCER": ("SWEEP_ATTACK", "CRIT", "item.trident.throw"),
    "BARD": ("NOTE", "HAPPY_VILLAGER", "block.note_block.chime"),
}

# 직업군: 기존 1단계 3개(F/SL/SR), 2차 분기(직업 → 기존 궁극기), 3차(2차 → (ID, 이름, 설명))
LINES = {
    "WARRIOR": dict(legacy=("WHIRLWIND", "LEAP_SLAM", "IRON_WALL"),
                    branch={"BERSERKER": "RAGE", "PALADIN": "HOLY_BARRIER"},
                    third={"BERSERKER": ("BLOOD_LORD", "블러드 로드", "피로 싸우는 광전사의 끝. 체력이 낮을수록 강해진다."),
                           "PALADIN": ("CRUSADER", "크루세이더", "빛의 방패로 전장을 지배하는 성기사의 끝.")}),
    "ARCHER": dict(legacy=("MULTI_SHOT", "ARROW_RAIN", "BACKSTEP"),
                   branch={"SNIPER": "PIERCING_SHOT", "RANGER": "SNARE_TRAP"},
                   third={"SNIPER": ("HAWKEYE", "호크아이", "매의 눈으로 단 한 발도 빗나가지 않는 저격수."),
                          "RANGER": ("WINDWALKER", "윈드워커", "바람을 타고 숲을 누비는 사냥꾼.")}),
    "MAGE": dict(legacy=("FIREBALL", "ICE_SPEAR", "BLINK"),
                 branch={"ELEMENTALIST": "METEOR", "WARLOCK": "LIFE_DRAIN"},
                 third={"ELEMENTALIST": ("ARCHMAGE", "아크메이지", "모든 원소를 손끝에 둔 대마법사."),
                        "WARLOCK": ("LICH_LORD", "리치 로드", "죽음마저 부리는 흑마법의 군주.")}),
    "ROGUE": dict(legacy=("AMBUSH", "POISON_BLADE", "VANISH"),
                  branch={"ASSASSIN": "SHADOW_EXECUTE", "SHADOW_DANCER": "BLADE_DANCE"},
                  third={"ASSASSIN": ("NIGHTMARE", "나이트메어", "악몽처럼 나타나 사라지는 암살자."),
                         "SHADOW_DANCER": ("SHADOW_MASTER", "섀도우 마스터", "그림자를 군대처럼 부리는 무희.")}),
    "CLERIC": dict(legacy=("HEAL_LIGHT", "HOLY_SMITE", "BLESSING"),
                   branch={"HIGH_PRIEST": "SANCTUARY", "JUDGE": "DIVINE_STORM"},
                   third={"HIGH_PRIEST": ("SAINT", "세인트", "기적을 일으키는 살아 있는 성인."),
                          "JUDGE": ("INQUISITOR", "인퀴지터", "신의 이름으로 악을 불태우는 심문관.")}),
    "SWORDSMAN": dict(legacy=("CROSS_SLASH", "DRAW_SLASH", "PARRY"),
                      branch={"SWORD_MASTER": "IMPERIAL_FALL", "BLADE_SAINT": "ABYSS_SLASH"},
                      third={"SWORD_MASTER": ("GRAND_MASTER", "그랜드 마스터", "오러 블레이드를 완성한 서양 검술의 정점."),
                             "BLADE_SAINT": ("SWORD_GOD", "검신", "한 번 휘두르면 하늘이 갈라지는 동양 검의 신.")}),
    "NINJA": dict(legacy=("DEEP_PIERCE", "SHURIKEN", "BLADE_DASH"),
                  branch={"JONIN": "SHADOW_CLONE", "PHANTOM": "PHANTOM_PIERCE"},
                  third={"JONIN": ("KAGE", "카게", "마을 하나를 지키는 그림자 닌자의 우두머리."),
                         "PHANTOM": ("MUYEONG", "무영", "그림자조차 남기지 않는 환영검의 끝.")}),
    "MONK": dict(legacy=("IRON_FIST", "COMBO_RUSH", "QI_GUARD"),
                 branch={"FIST_KING": "HUNDRED_FISTS", "CHI_MASTER": "QI_BLAST"},
                 third={"FIST_KING": ("FIST_GOD", "권신", "주먹 하나로 산을 부수는 권법의 신."),
                        "CHI_MASTER": ("SAGE", "선인", "천지의 기를 다루는 깨달은 자.")}),
    "MOON_PRIEST": dict(legacy=("MOON_CURSE", "MOON_WEIGHT", "MOONLIGHT"),
                        branch={"ECLIPSE_PRIEST": "ECLIPSE", "CURSE_WEAVER": "LETHARGY"},
                        third={"ECLIPSE_PRIEST": ("LUNA_ORACLE", "루나 오라클", "달의 뜻을 전하는 예언자."),
                               "CURSE_WEAVER": ("DESPAIR_LORD", "절망의 군주", "모든 감정을 지배하는 저주의 왕.")}),
    "GUNSLINGER": dict(legacy=("QUICK_SHOT", "SCATTER_SHOT", "ROLL"),
                       branch={"DEADEYE": "DEAD_EYE", "ARTILLERY": "CANNON"},
                       third={"DEADEYE": ("GUN_MASTER", "건마스터", "총알 한 발로 승부를 내는 사격의 달인."),
                              "ARTILLERY": ("DEMOLISHER", "데몰리셔", "전장을 통째로 날려버리는 포격의 왕.")}),
    "LANCER": dict(legacy=("SPEAR_THRUST", "SPEAR_SWEEP", "CHARGE"),
                   branch={"WARLORD": "GOD_OF_WAR", "VALKYRIE": "SPEAR_RAIN"},
                   third={"WARLORD": ("OVERLORD", "패왕", "천하를 창 하나로 평정한 패자."),
                          "VALKYRIE": ("BRUNHILD", "브륀힐드", "전사자의 영혼을 이끄는 발키리의 여왕.")}),
    "BARD": dict(legacy=("SONG_COURAGE", "SONG_SWIFT", "DISSONANCE"),
                 branch={"MAESTRO": "SYMPHONY", "DANCER": "SWORD_DANCE"},
                 third={"MAESTRO": ("DIVA", "디바", "목소리 하나로 전장을 바꾸는 전설의 가수."),
                        "DANCER": ("BLADE_DANCER", "블레이드 댄서", "칼날과 함께 춤추는 무희의 끝.")}),
}

# 새 스킬: 직업군 → (F2, F3, F4, SL2, SL3, SL4, SR2, SR3, SR4, SS2, SS4a, SS4b) 각 (이름, 설명, kind, 값)
# SS4a/SS4b 는 THIRD 순서(분기 순서)와 같다. 값은 kind 마다: nova(r,d) cone(len,d) beam(len,d) dash(len,d) leap(r,d)
#   rain(r,n,d) pull(r,d) orb(r,d) mark(d,sec) buff(효과목록,초,범위) heal(양,범위)
N = {
    "WARRIOR": [
        ("대지 가르기", "앞쪽 땅을 갈라 부채꼴로 베어냄.", "cone", (6, 10)),
        ("광폭 연타", "주변을 세 번 연달아 후려침.", "nova", (4, 14)),
        ("파멸의 일격", "앞의 모든 것을 짓부수는 거대한 내려찍기.", "cone", (8, 26)),
        ("돌진 베기", "앞으로 돌진하며 지나간 적을 벰.", "dash", (8, 10)),
        ("지진", "높이 뛰어올라 땅을 내려찍어 큰 지진을 일으킴.", "leap", (6, 18)),
        ("천지 붕괴", "하늘에서 떨어지며 넓은 땅을 무너뜨림.", "leap", (9, 30)),
        ("전투 함성", "함성을 질러 나와 주변 동료에게 힘을 줌.", "buff", ("strength:1", 10, 8)),
        ("강철 피부", "잠시 피부가 강철처럼 단단해짐.", "buff", ("resistance:2,slowness:0", 8, 0)),
        ("불굴", "쓰러지지 않는 의지로 체력을 크게 회복.", "heal", (24, 0)),
        ("전쟁의 군주", "주변 적을 날려버리고 10초 동안 힘 III.", "nova", (6, 22, "strength:2:10")),
        ("피의 축제", "주변을 피바다로 만드는 연속 베기.", "nova", (7, 40)),
        ("심판의 방패", "빛의 방패를 내리꽂아 주변 적을 심판.", "nova", (8, 36, "resistance:2:8")),
    ],
    "ARCHER": [
        ("관통 화살", "일직선을 꿰뚫는 화살.", "beam", (20, 9)),
        ("폭발 화살", "맞은 곳에서 폭발하는 화살.", "orb", (3, 15)),
        ("유성 화살", "별처럼 빛나며 모든 것을 꿰뚫는 화살.", "beam", (40, 28)),
        ("화살 폭풍", "바라보는 곳에 화살이 쏟아짐.", "rain", (4, 8, 5)),
        ("얼음 화살비", "얼음 화살비로 적을 느리게 함.", "rain", (5, 10, 7, "slowness:2:4")),
        ("천공의 화살비", "하늘을 뒤덮는 화살비.", "rain", (7, 16, 9)),
        ("바람 걸음", "바람처럼 빨라짐.", "buff", ("speed:2", 8, 0)),
        ("매의 눈", "잠시 모든 화살이 강해지고 적이 빛남.", "buff", ("strength:1,night_vision:0", 12, 0)),
        ("자연의 가호", "자연의 힘으로 체력 회복.", "heal", (16, 0)),
        ("사냥꾼의 표식", "적에게 표식을 남겨 계속 피해를 줌.", "mark", (6, 6)),
        ("호크아이 샷", "60칸 밖까지 닿는 절대 명중의 한 발.", "beam", (60, 60)),
        ("폭풍의 사냥", "바람과 함께 화살을 퍼부어 넓은 곳을 휩쓺.", "rain", (8, 22, 12)),
    ],
    "MAGE": [
        ("번개 화살", "바라보는 적에게 번개를 내림.", "beam", (18, 12)),
        ("화염 폭발", "주변에 불길이 폭발함.", "nova", (5, 16, "fire")),
        ("뇌신의 창", "번개로 만든 창이 일직선을 꿰뚫음.", "beam", (30, 30)),
        ("서리 폭풍", "바라보는 곳에 얼음 폭풍.", "rain", (5, 10, 6, "slowness:2:4")),
        ("블랙홀", "적들을 한곳으로 빨아들여 터뜨림.", "pull", (7, 18)),
        ("절대 영도", "넓은 범위를 얼려버림.", "nova", (8, 26, "slowness:4:5")),
        ("마나 보호막", "마나로 몸을 감싸 피해를 줄임.", "buff", ("resistance:1,absorption:2", 10, 0)),
        ("시간 가속", "시간을 빠르게 흘려 몸이 가벼워짐.", "buff", ("speed:1,haste:2", 10, 0)),
        ("비전 충전", "마력을 모아 체력을 회복.", "heal", (14, 0)),
        ("원소 폭주", "불·얼음·번개가 동시에 쏟아짐.", "rain", (6, 14, 10)),
        ("천체 붕괴", "하늘의 별을 떨어뜨려 모든 것을 태움.", "rain", (9, 24, 16, "fire")),
        ("죽음의 손길", "주변의 생명을 빨아들이는 검은 파동.", "nova", (8, 34, "wither:1:5")),
    ],
    "ROGUE": [
        ("급소 찌르기", "앞의 적 급소를 찌름.", "cone", (4, 12)),
        ("연속 베기", "주변을 빠르게 여러 번 벰.", "nova", (3.5, 16)),
        ("암흑 일섬", "그림자를 가르는 단 한 번의 베기.", "dash", (12, 30)),
        ("연막탄", "연막을 터뜨려 적을 눈멀게 함.", "nova", (5, 6, "blindness:0:4")),
        ("독 안개", "독 안개로 주변 적을 중독시킴.", "nova", (6, 8, "poison:1:6")),
        ("죽음의 안개", "치명적인 독구름을 퍼뜨림.", "pull", (7, 22, "poison:2:6")),
        ("그림자 걸음", "그림자 속으로 빠르게 이동.", "dash", (10, 6)),
        ("민첩", "몸놀림이 빨라짐.", "buff", ("speed:2,jump_boost:1", 8, 0)),
        ("응급 처치", "상처를 빠르게 묶어 회복.", "heal", (18, 0)),
        ("독사의 이빨", "적에게 독을 새겨 계속 피해.", "mark", (7, 6)),
        ("악몽", "그림자 속에서 모든 적을 베어냄.", "nova", (7, 42, "blindness:0:3")),
        ("그림자 군단", "그림자 분신들이 사방을 벰.", "rain", (7, 18, 12)),
    ],
    "CLERIC": [
        ("빛의 화살", "빛의 화살로 적을 꿰뚫음.", "beam", (18, 10)),
        ("신성한 파동", "주변 적에게 신성한 피해, 아군은 회복.", "nova", (5, 14, "heal")),
        ("천상의 빛", "하늘의 빛기둥이 적을 태움.", "rain", (6, 10, 16)),
        ("정화", "나와 주변 동료의 나쁜 효과를 지움.", "heal", (8, 8, "cleanse")),
        ("수호의 빛", "주변 동료에게 보호막.", "buff", ("absorption:2,resistance:0", 12, 8)),
        ("기적", "주변 동료를 크게 회복하고 나쁜 효과 제거.", "heal", (30, 10, "cleanse")),
        ("신의 은총", "체력이 서서히 회복됨.", "buff", ("regeneration:2", 10, 8)),
        ("천벌의 망치", "앞의 적을 신성한 망치로 내려침.", "cone", (6, 20)),
        ("심판의 불꽃", "넓은 곳에 신성한 불꽃.", "nova", (7, 26, "fire")),
        ("빛의 장막", "주변 동료 재생·저항.", "buff", ("regeneration:1,resistance:1", 12, 10)),
        ("성인의 기적", "주변 모두를 되살리듯 완전 회복.", "heal", (60, 12, "cleanse")),
        ("이단 심문", "주변 적을 불태우는 심판의 화염.", "nova", (8, 40, "fire")),
    ],
    "SWORDSMAN": [
        ("삼연격", "앞을 세 번 연속 벰.", "cone", (5, 12)),
        ("월광참", "달빛 같은 검기로 주변을 벰.", "nova", (4.5, 18)),
        ("오러 블레이드", "검기를 날려 일직선을 가름.", "beam", (24, 30)),
        ("섬광 베기", "빛처럼 앞으로 돌진하며 벰.", "dash", (9, 12)),
        ("검기 폭풍", "주변을 검기로 휩쓸어버림.", "nova", (6, 20)),
        ("천지 일검", "하늘에서 떨어지며 땅을 가르는 일검.", "leap", (8, 32)),
        ("간파", "적의 움직임을 읽어 몸을 지킴.", "buff", ("resistance:2", 5, 0)),
        ("검의 의지", "검에 의지를 실어 힘이 강해짐.", "buff", ("strength:1,speed:1", 10, 0)),
        ("명상", "호흡을 가다듬어 회복.", "heal", (16, 0)),
        ("만검귀종", "수많은 검기가 하늘에서 떨어짐.", "rain", (6, 14, 12)),
        ("오러 엠페러", "거대한 오러 검을 내리꽂음.", "beam", (40, 60)),
        ("천검무", "하늘을 가르는 천 개의 검.", "rain", (8, 24, 14)),
    ],
    "NINJA": [
        ("쿠나이 투척", "쿠나이를 일직선으로 던짐.", "beam", (16, 10)),
        ("화둔: 화염구", "입에서 화염구를 뿜음.", "orb", (3, 16, "fire")),
        ("뇌둔: 천둥", "번개를 내려 주변을 지짐.", "rain", (5, 8, 16)),
        ("순보", "순식간에 앞으로 이동하며 벰.", "dash", (10, 10)),
        ("연막 분신", "연막과 함께 주변을 벰.", "nova", (4, 14, "blindness:0:2")),
        ("팔문 둔갑", "몸의 한계를 풀어 주변을 쓸어버림.", "nova", (6, 30)),
        ("변신술", "모습을 숨기고 빨라짐.", "buff", ("invisibility:0,speed:2", 5, 0)),
        ("인술: 회복", "인술로 상처를 회복.", "heal", (16, 0)),
        ("수리검 폭풍", "수리검을 비처럼 뿌림.", "rain", (5, 12, 8)),
        ("나선 수리검", "회전하는 거대한 수리검이 적을 빨아들임.", "pull", (6, 20)),
        ("카게 분신술", "수많은 분신이 동시에 공격.", "rain", (7, 22, 12)),
        ("무영참", "보이지 않는 칼날로 모든 것을 벰.", "dash", (16, 50)),
    ],
    "MONK": [
        ("정권 찌르기", "기를 실은 정권을 내지름.", "cone", (4, 14)),
        ("선풍각", "회전하며 주변을 걷어참.", "nova", (4, 16)),
        ("붕권", "산을 무너뜨리는 일격.", "cone", (6, 30)),
        ("비연각", "날아올라 앞으로 차며 돌진.", "dash", (8, 12)),
        ("진각", "땅을 굴러 주변을 띄움.", "leap", (5, 16)),
        ("천붕지열", "하늘이 무너지고 땅이 갈라짐.", "leap", (8, 30)),
        ("금강불괴", "몸을 금강처럼 단단하게.", "buff", ("resistance:2,strength:0", 6, 0)),
        ("기 회복", "기를 돌려 체력 회복.", "heal", (18, 0)),
        ("파동권", "기를 모아 일직선으로 쏨.", "beam", (20, 20)),
        ("나한권", "주먹이 비처럼 쏟아짐.", "rain", (5, 12, 12)),
        ("권신강림", "주먹 하나로 주변을 날려버림.", "nova", (7, 44)),
        ("천지 합일", "천지의 기를 모아 거대한 파동을 일으킴.", "nova", (9, 36, "regen_self")),
    ],
    "MOON_PRIEST": [
        ("달빛 화살", "달빛을 모아 일직선으로 쏨.", "beam", (18, 10)),
        ("초승달 낫", "초승달 모양의 기운으로 주변을 벰.", "nova", (5, 14, "weakness:0:4")),
        ("만월 낙하", "보름달이 떨어지는 듯한 큰 폭발.", "rain", (6, 10, 16, "slowness:1:3")),
        ("월식 저주", "주변 적을 나약하게 만듦.", "nova", (6, 6, "weakness:1:6")),
        ("밤의 장막", "적을 어둠에 빠뜨림.", "nova", (6, 8, "darkness:0:5")),
        ("달의 감옥", "적들을 끌어모아 묶어버림.", "pull", (7, 18, "slowness:4:4")),
        ("달의 가호", "달의 힘으로 회복.", "heal", (16, 0)),
        ("야행", "밤의 힘으로 빨라짐.", "buff", ("speed:1,night_vision:0", 10, 0)),
        ("불안의 씨앗", "적에게 불안을 심어 계속 피해.", "mark", (6, 6)),
        ("달의 노래", "달빛이 쏟아져 적을 괴롭힘.", "rain", (6, 12, 10, "weakness:1:4")),
        ("달의 신탁", "하늘의 달빛이 모든 적을 꿰뚫음.", "rain", (8, 20, 14)),
        ("절망", "모든 감정을 앗아가는 검은 파동.", "nova", (8, 32, "wither:1:5")),
    ],
    "GUNSLINGER": [
        ("헤드샷", "적의 머리를 노린 강한 한 발.", "beam", (24, 14)),
        ("파쇄탄", "맞은 곳에서 터지는 탄.", "orb", (3, 16)),
        ("레일건", "모든 것을 관통하는 레일건.", "beam", (40, 34)),
        ("난사", "앞으로 탄을 마구 쏟아냄.", "cone", (7, 12)),
        ("수류탄", "수류탄을 던져 폭발.", "orb", (4, 20)),
        ("융단 폭격", "넓은 곳에 포탄이 쏟아짐.", "rain", (7, 14, 14)),
        ("전술 회피", "몸을 굴려 피하며 빨라짐.", "dash", (6, 0)),
        ("조준", "숨을 고르고 조준해 강해짐.", "buff", ("strength:1", 10, 0)),
        ("응급 키트", "구급 키트로 회복.", "heal", (16, 0)),
        ("탄막", "주변에 탄을 퍼부음.", "nova", (6, 18)),
        ("데드샷", "절대 빗나가지 않는 한 발.", "beam", (60, 64)),
        ("핵탄두", "거대한 폭발로 모든 것을 날려버림.", "orb", (8, 50, "fire")),
    ],
    "LANCER": [
        ("삼단 찌르기", "창을 세 번 찔러 앞을 꿰뚫음.", "beam", (8, 12)),
        ("회전창", "창을 돌려 주변을 휩쓺.", "nova", (5, 16)),
        ("천공창", "하늘을 꿰뚫는 창.", "beam", (24, 30)),
        ("돌격", "창을 앞세워 돌진.", "dash", (10, 12)),
        ("도약 찌르기", "뛰어올라 창을 내리꽂음.", "leap", (5, 18)),
        ("창룡 강림", "용처럼 떨어지며 땅을 꿰뚫음.", "leap", (8, 32)),
        ("방진", "창을 세워 몸을 지킴.", "buff", ("resistance:2", 6, 0)),
        ("투지", "싸울 의지로 힘이 솟음.", "buff", ("strength:1,speed:0", 10, 0)),
        ("전장의 숨결", "숨을 고르고 회복.", "heal", (18, 0)),
        ("창의 폭풍", "창이 비처럼 쏟아짐.", "rain", (6, 12, 12)),
        ("패왕창", "한 번의 찌르기로 전장을 꿰뚫음.", "beam", (40, 56)),
        ("발할라의 창", "하늘에서 영혼의 창이 쏟아짐.", "rain", (8, 22, 14)),
    ],
    "BARD": [
        ("음파", "음파를 일직선으로 쏨.", "beam", (16, 10)),
        ("불협 화음", "주변 적을 괴롭히는 소리.", "nova", (5, 12, "nausea:0:4")),
        ("포르티시모", "가장 큰 소리로 주변을 날려버림.", "nova", (7, 26)),
        ("행진곡", "주변 동료가 빨라짐.", "buff", ("speed:1", 12, 8)),
        ("자장가", "적을 잠재워 느리게 함.", "nova", (6, 6, "slowness:3:5")),
        ("광시곡", "음표가 비처럼 쏟아짐.", "rain", (6, 12, 12)),
        ("치유의 노래", "주변 동료 회복.", "heal", (14, 8)),
        ("용기의 노래", "주변 동료에게 힘.", "buff", ("strength:1", 12, 8)),
        ("수호의 노래", "주변 동료에게 보호막.", "buff", ("absorption:2,resistance:0", 12, 8)),
        ("앙코르", "주변 동료 재생·신속.", "buff", ("regeneration:1,speed:1", 12, 10)),
        ("디바의 아리아", "모두를 살리고 적을 쓰러뜨리는 노래.", "heal", (40, 12, "cleanse")),
        ("칼날의 원무", "칼날과 함께 주변을 휩쓰는 춤.", "nova", (7, 40)),
    ],
}

# 패시브: 직업군 → 4개 (이름, 설명, 보너스) — 키: hp mp spd mel rng skl reg mpr crit steal def
P = {
    "WARRIOR": [("단련된 몸", "최대 체력 +4", "hp:4"), ("투사의 기술", "근접 피해 +10%", "mel:10"),
                ("강철 의지", "받는 피해 -8%", "def:8"), ("전장의 지배자", "최대 체력 +8, 근접 피해 +10%", "hp:8,mel:10")],
    "ARCHER": [("예리한 눈", "원거리 피해 +10%", "rng:10"), ("가벼운 발", "이동 속도 +5%", "spd:5"),
               ("급소 사격", "치명타 확률 +10%", "crit:10"), ("명궁", "원거리 피해 +20%, 치명타 +5%", "rng:20,crit:5")],
    "MAGE": [("마력 증폭", "최대 MP +30", "mp:30"), ("마나 순환", "초당 MP 회복 +1", "mpr:1"),
             ("주문 강화", "스킬 피해 +10%", "skl:10"), ("대마법사의 지혜", "스킬 피해 +20%, 최대 MP +40", "skl:20,mp:40")],
    "ROGUE": [("날렵함", "이동 속도 +6%", "spd:6"), ("급소 찌르기", "치명타 확률 +10%", "crit:10"),
              ("피의 갈증", "준 피해의 5% 회복", "steal:5"), ("그림자의 주인", "치명타 +10%, 근접 피해 +15%", "crit:10,mel:15")],
    "CLERIC": [("신앙", "초당 체력 회복 +0.3", "reg:0.3"), ("기도", "최대 MP +30", "mp:30"),
               ("가호", "받는 피해 -8%", "def:8"), ("성자의 빛", "초당 체력 회복 +0.6, 스킬 피해 +15%", "reg:0.6,skl:15")],
    "SWORDSMAN": [("검술 수련", "근접 피해 +10%", "mel:10"), ("호흡법", "초당 MP 회복 +1", "mpr:1"),
                  ("일섬", "치명타 확률 +8%", "crit:8"), ("검의 극의", "근접 피해 +20%, 치명타 +8%", "mel:20,crit:8")],
    "NINJA": [("은밀함", "이동 속도 +6%", "spd:6"), ("암기 달인", "스킬 피해 +10%", "skl:10"),
              ("급소", "치명타 확률 +10%", "crit:10"), ("그림자 인술", "이동 속도 +8%, 스킬 피해 +15%", "spd:8,skl:15")],
    "MONK": [("단련", "최대 체력 +4", "hp:4"), ("철권", "근접 피해 +12%", "mel:12"),
             ("내공", "초당 체력 회복 +0.3", "reg:0.3"), ("무극", "근접 피해 +20%, 받는 피해 -8%", "mel:20,def:8")],
    "MOON_PRIEST": [("달의 은총", "최대 MP +30", "mp:30"), ("저주 숙련", "스킬 피해 +10%", "skl:10"),
                    ("밤의 숨결", "초당 MP 회복 +1", "mpr:1"), ("달의 화신", "스킬 피해 +20%, 최대 MP +40", "skl:20,mp:40")],
    "GUNSLINGER": [("사격 훈련", "원거리·스킬 피해 +8%", "rng:8,skl:8"), ("민첩한 손", "이동 속도 +5%", "spd:5"),
                   ("정조준", "치명타 확률 +10%", "crit:10"), ("총의 신", "스킬 피해 +20%, 치명타 +5%", "skl:20,crit:5")],
    "LANCER": [("창술 수련", "근접 피해 +10%", "mel:10"), ("굳센 몸", "최대 체력 +4", "hp:4"),
               ("기세", "받는 피해 -6%", "def:6"), ("천하무쌍", "근접 피해 +20%, 최대 체력 +6", "mel:20,hp:6")],
    "BARD": [("맑은 목소리", "최대 MP +30", "mp:30"), ("울림", "스킬 피해 +10%", "skl:10"),
             ("박자감", "이동 속도 +5%", "spd:5"), ("전설의 음유시인", "스킬 피해 +15%, 초당 MP 회복 +2", "skl:15,mpr:2")],
}

# 히든 스킬 (히든 직업 스킬 — 보스가 떨어뜨리는 히든 스킬서로만 얻는다)
HIDDEN = [("DRAGON_BREATH", "SL"), ("DRAGON_DIVE", "SR"), ("DRAGON_ROAR", "SS"),
          ("INFERNO_OVERLAY", "F"), ("OVERVOLT_DRIVE", "SL"), ("GLACIAL_DOMINION", "SR"), ("TEMPEST_CALL", "SS"),
          ("BITE", "F"), ("BLOOD_RAIN", "SL"), ("BAT_FORM", "SR"), ("BLOOD_MOON", "SS"),
          ("JUDGMENT_SPEAR", "SL"), ("DIVINE_WING", "SR"), ("GRACE", "SS"),
          ("PRECISION_SHOT", "F"), ("COVER", "SR"), ("DIMENSION_SHOT", "SS"),
          ("LIE_DOWN", "F"), ("MOM_CHANCE", "SL"), ("NEET_RAGE", "SR"), ("NEET_ULT", "SS")]

RANK_LV = {1: 10, 2: 20, 3: 30, 4: 45}
SLOT_ORDER = ("F", "SL", "SR")


def mpcd(kind, rank, slot):
    base_mp = {1: 15, 2: 25, 3: 35, 4: 50}[rank]
    base_cd = {1: 6, 2: 10, 3: 14, 4: 20}[rank]
    if slot == "SS":
        base_mp, base_cd = {2: 40, 3: 50, 4: 70}[rank], {2: 35, 3: 45, 4: 60}[rank]
    if kind in ("buff", "heal"):
        base_cd = int(base_cd * 1.6)
    return base_mp, base_cd


def entry(sid, line, slot, rank, name, desc, kind, val, branch=None, hidden=False, legacy=None):
    e = {"id": sid, "line": line, "slot": slot, "rank": rank, "level": RANK_LV.get(rank, 30)}
    if legacy:
        e.update(kind="legacy", legacy=legacy)
    else:
        mp, cd = mpcd(kind, rank, slot)
        e.update(name=name, desc=desc, kind=kind, mp=mp, cd=cd, val=[str(v) for v in val])
        th = THEME.get(line, ("END_ROD", "CRIT", "entity.player.attack.strong"))
        e.update(p1=th[0], p2=th[1], snd=th[2])
    if branch:
        e["branch"] = branch
    if hidden:
        e["hidden"] = True
    return e


def main():
    out = []
    for line, L in LINES.items():
        new = N[line]
        # 1단계: 기존 스킬
        for slot, leg in zip(SLOT_ORDER, L["legacy"]):
            out.append(entry(f"{line}_{slot}1", line, slot, 1, None, None, None, None, legacy=leg))
        # 2~4단계 F/SL/SR
        k = 0
        for slot in SLOT_ORDER:
            for rank in (2, 3, 4):
                n, d, kind, val = new[k]; k += 1
                out.append(entry(f"{line}_{slot}{rank}", line, slot, rank, n, d, kind, val))
        # 쉬쉬: 2단계 새 궁극기, 3단계 분기별 기존 궁극기, 4단계 3차별 새 각성기
        n, d, kind, val = new[9]
        out.append(entry(f"{line}_SS2", line, "SS", 2, n, d, kind, val))
        for br, leg in L["branch"].items():
            out.append(entry(f"{line}_SS3_{br}", line, "SS", 3, None, None, None, None, branch=br, legacy=leg))
        for i, (br, (tid, tname, tdesc)) in enumerate(L["third"].items()):
            n, d, kind, val = new[10 + i]
            out.append(entry(f"{line}_SS4_{tid}", line, "SS", 4, n, d, kind, val, branch=tid))
        # 패시브
        for i, (n, d, bonus) in enumerate(P[line]):
            e = {"id": f"{line}_P{i + 1}", "line": line, "slot": "P", "rank": i + 1, "level": RANK_LV[i + 1],
                 "name": n, "desc": d, "kind": "passive", "bonus": bonus}
            out.append(e)
    for leg, slot in HIDDEN:
        out.append(entry(f"HIDDEN_{leg}", "HIDDEN", slot, 3, None, None, None, None, hidden=True, legacy=leg))
    third = {L2: [] for L2 in LINES}
    classes = []
    for line, L in LINES.items():
        for br, (tid, tname, tdesc) in L["third"].items():
            classes.append({"id": tid, "name": tname, "parent": br, "desc": tdesc, "line": line})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # YAML 대신 JSON (YAML 의 부분집합이라 그대로 읽힌다)
    json.dump({"skills": out, "third": classes}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lines = {}
    for e in out:
        lines[e["line"]] = lines.get(e["line"], 0) + 1
    print(len(out), "개 스킬", lines)


if __name__ == "__main__":
    main()
