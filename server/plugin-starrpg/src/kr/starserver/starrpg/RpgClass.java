package kr.starserver.starrpg;

import org.bukkit.Material;

import java.util.List;

/**
 * 전투 직업.
 * tier 0 = 초보자, 1 = 1차 전직(Lv.10), 2 = 2차 전직(Lv.30), 4 = 3차 전직(Lv.45), 3 = 히든 직업.
 * skills: 스킬1(F), 스킬2(Shift+좌클릭), 스킬3(Shift+우클릭), 궁극기(Shift 두 번)
 */
public enum RpgClass {
    NOVICE("초보자", 0, null, "§f", Material.WOODEN_SWORD,
            "모든 모험의 시작. 레벨 10에 전직할 수 있어요.", "없음",
            List.of(Skill.TACKLE)),

    // ----- 1차 -----
    WARRIOR("전사", 1, NOVICE, "§c", Material.IRON_SWORD,
            "단단한 몸으로 앞에서 싸우는 근접 직업.", "최대 체력 +4",
            List.of(Skill.WHIRLWIND, Skill.LEAP_SLAM, Skill.IRON_WALL)),
    ARCHER("궁수", 1, NOVICE, "§a", Material.BOW,
            "멀리서 화살을 퍼붓는 원거리 직업.", "활 피해 +20%",
            List.of(Skill.MULTI_SHOT, Skill.ARROW_RAIN, Skill.BACKSTEP)),
    MAGE("마법사", 1, NOVICE, "§9", Material.BLAZE_ROD,
            "강력한 마법으로 적을 쓸어버리는 직업.", "최대 MP +50",
            List.of(Skill.FIREBALL, Skill.ICE_SPEAR, Skill.BLINK)),
    ROGUE("도적", 1, NOVICE, "§8", Material.IRON_SWORD,
            "빠르게 파고들어 급소를 노리는 직업.", "이동 속도 증가",
            List.of(Skill.AMBUSH, Skill.POISON_BLADE, Skill.VANISH)),
    CLERIC("성직자", 1, NOVICE, "§e", Material.GOLDEN_SHOVEL,
            "동료를 치유하고 신성한 힘으로 싸우는 직업.", "체력 자연 회복",
            List.of(Skill.HEAL_LIGHT, Skill.HOLY_SMITE, Skill.BLESSING)),

    SWORDSMAN("검사", 1, NOVICE, "§3", Material.IRON_SWORD,
            "검 하나로 승부하는 근접 직업. 2차에 서양검사(소드마스터)와 동양검사(검성)로 나뉜다.", "근접 피해 +10%",
            List.of(Skill.CROSS_SLASH, Skill.DRAW_SLASH, Skill.PARRY)),
    NINJA("닌자", 1, NOVICE, "§8", Material.SHEARS,
            "단검과 수리검을 쓰는 날쌘 직업.", "이동 속도 증가, 근접 피해 +5%",
            List.of(Skill.DEEP_PIERCE, Skill.SHURIKEN, Skill.BLADE_DASH)),
    MONK("무투가", 1, NOVICE, "§6", Material.BLAZE_POWDER,
            "맨주먹으로 싸우는 격투가. 손이 비어 있을 때 강하다.", "맨손 피해 +150%, 최대 체력 +2",
            List.of(Skill.IRON_FIST, Skill.COMBO_RUSH, Skill.QI_GUARD)),
    MOON_PRIEST("달의 사제", 1, NOVICE, "§9", Material.ENDER_EYE,
            "성직자가 버프를 준다면 달의 사제는 적에게 디버프를 건다.", "밤에 MP 회복 2배",
            List.of(Skill.MOON_CURSE, Skill.MOON_WEIGHT, Skill.MOONLIGHT)),
    GUNSLINGER("건슬링거", 1, NOVICE, "§7", Material.CROSSBOW,
            "총을 쏘는 원거리 직업. 스킬 대부분이 총격이다.", "스킬 피해 +10%",
            List.of(Skill.QUICK_SHOT, Skill.SCATTER_SHOT, Skill.ROLL)),
    LANCER("창술사", 1, NOVICE, "§c", Material.TRIDENT,
            "긴 창으로 앞을 휩쓰는 직업.", "최대 체력 +2, 근접 피해 +5%",
            List.of(Skill.SPEAR_THRUST, Skill.SPEAR_SWEEP, Skill.CHARGE)),
    BARD("음유시인", 1, NOVICE, "§d", Material.NOTE_BLOCK,
            "노래로 동료를 강하게, 적을 괴롭게 하는 지원 직업.", "최대 MP +40",
            List.of(Skill.SONG_COURAGE, Skill.SONG_SWIFT, Skill.DISSONANCE)),

    // ----- 2차 -----
    BERSERKER("광전사", 2, WARRIOR, "§4", Material.NETHERITE_AXE,
            "분노로 싸우는 전사. 맞을수록 강해진다.", "최대 체력 +6, 공격력 증가",
            List.of(Skill.WHIRLWIND, Skill.LEAP_SLAM, Skill.IRON_WALL, Skill.RAGE)),
    PALADIN("성기사", 2, WARRIOR, "§6", Material.SHIELD,
            "신성한 방패로 동료를 지키는 전사.", "최대 체력 +8",
            List.of(Skill.WHIRLWIND, Skill.LEAP_SLAM, Skill.IRON_WALL, Skill.HOLY_BARRIER)),
    SNIPER("저격수", 2, ARCHER, "§2", Material.CROSSBOW,
            "한 발에 모든 걸 거는 궁수.", "활 피해 +35%",
            List.of(Skill.MULTI_SHOT, Skill.ARROW_RAIN, Skill.BACKSTEP, Skill.PIERCING_SHOT)),
    RANGER("레인저", 2, ARCHER, "§a", Material.SPECTRAL_ARROW,
            "덫과 기동력으로 사냥하는 궁수.", "활 피해 +20%, 이동 속도 증가",
            List.of(Skill.MULTI_SHOT, Skill.ARROW_RAIN, Skill.BACKSTEP, Skill.SNARE_TRAP)),
    ELEMENTALIST("원소술사", 2, MAGE, "§b", Material.FIRE_CHARGE,
            "불·얼음·번개를 다루는 마법사.", "최대 MP +80",
            List.of(Skill.FIREBALL, Skill.ICE_SPEAR, Skill.BLINK, Skill.METEOR)),
    WARLOCK("흑마법사", 2, MAGE, "§5", Material.WITHER_ROSE,
            "생명을 빼앗아 힘으로 바꾸는 마법사.", "최대 MP +60, 처치 시 체력 회복",
            List.of(Skill.FIREBALL, Skill.ICE_SPEAR, Skill.BLINK, Skill.LIFE_DRAIN)),
    ASSASSIN("암살자", 2, ROGUE, "§0", Material.NETHERITE_SWORD,
            "그림자에서 나타나 한 번에 끝낸다.", "이동 속도 증가, 치명타 피해 증가",
            List.of(Skill.AMBUSH, Skill.POISON_BLADE, Skill.VANISH, Skill.SHADOW_EXECUTE)),
    SHADOW_DANCER("그림자무희", 2, ROGUE, "§7", Material.ECHO_SHARD,
            "분신과 함께 춤추듯 베는 도적.", "이동 속도 크게 증가",
            List.of(Skill.AMBUSH, Skill.POISON_BLADE, Skill.VANISH, Skill.BLADE_DANCE)),
    HIGH_PRIEST("대사제", 2, CLERIC, "§f", Material.TOTEM_OF_UNDYING,
            "기도로 모두를 살리는 성직자.", "체력 자연 회복 강화",
            List.of(Skill.HEAL_LIGHT, Skill.HOLY_SMITE, Skill.BLESSING, Skill.SANCTUARY)),
    JUDGE("심판자", 2, CLERIC, "§e", Material.LIGHTNING_ROD,
            "신의 번개로 악을 심판하는 성직자.", "체력 자연 회복, 신성 피해 증가",
            List.of(Skill.HEAL_LIGHT, Skill.HOLY_SMITE, Skill.BLESSING, Skill.DIVINE_STORM)),

    SWORD_MASTER("소드마스터", 2, SWORDSMAN, "§b", Material.DIAMOND_SWORD,
            "[서양검사] 검에 오러를 담아 고정된 강한 피해를 주는 검사.", "근접 피해 +20%, 최대 체력 +4",
            List.of(Skill.CROSS_SLASH, Skill.DRAW_SLASH, Skill.PARRY, Skill.IMPERIAL_FALL)),
    BLADE_SAINT("검성", 2, SWORDSMAN, "§3", Material.NETHERITE_SWORD,
            "[동양검사] 수련으로 강해지는 검의 성인.", "근접 피해 +15%, 치명타 확률 증가",
            List.of(Skill.CROSS_SLASH, Skill.DRAW_SLASH, Skill.PARRY, Skill.ABYSS_SLASH)),
    JONIN("상급 닌자", 2, NINJA, "§8", Material.BLACK_DYE,
            "분신술을 익힌 닌자.", "이동 속도 증가, 근접 피해 +10%",
            List.of(Skill.DEEP_PIERCE, Skill.SHURIKEN, Skill.BLADE_DASH, Skill.SHADOW_CLONE)),
    PHANTOM("환영검객", 2, NINJA, "§5", Material.PHANTOM_MEMBRANE,
            "환영처럼 빠른 연속 찌르기의 달인.", "이동 속도 크게 증가",
            List.of(Skill.DEEP_PIERCE, Skill.SHURIKEN, Skill.BLADE_DASH, Skill.PHANTOM_PIERCE)),
    FIST_KING("권왕", 2, MONK, "§6", Material.NETHERITE_INGOT,
            "주먹의 왕.", "맨손 피해 +250%, 최대 체력 +4",
            List.of(Skill.IRON_FIST, Skill.COMBO_RUSH, Skill.QI_GUARD, Skill.HUNDRED_FISTS)),
    CHI_MASTER("기공사", 2, MONK, "§e", Material.GLOWSTONE_DUST,
            "기를 모아 쏘아내는 무투가.", "맨손 피해 +150%, 최대 MP +50",
            List.of(Skill.IRON_FIST, Skill.COMBO_RUSH, Skill.QI_GUARD, Skill.QI_BLAST)),
    ECLIPSE_PRIEST("월식의 사제", 2, MOON_PRIEST, "§1", Material.BLACK_CONCRETE,
            "해와 달을 가리는 사제.", "밤에 MP 회복 2배, 최대 MP +40",
            List.of(Skill.MOON_CURSE, Skill.MOON_WEIGHT, Skill.MOONLIGHT, Skill.ECLIPSE)),
    CURSE_WEAVER("감정저주술사", 2, MOON_PRIEST, "§5", Material.FERMENTED_SPIDER_EYE,
            "현타·우울·불안·무기력을 다루는 디버퍼.", "공격한 적에게 가끔 나약함",
            List.of(Skill.MOON_CURSE, Skill.MOON_WEIGHT, Skill.MOONLIGHT, Skill.LETHARGY)),
    DEADEYE("데드아이", 2, GUNSLINGER, "§7", Material.SPYGLASS,
            "눈에 보이는 건 다 맞히는 총잡이.", "스킬 피해 +20%",
            List.of(Skill.QUICK_SHOT, Skill.SCATTER_SHOT, Skill.ROLL, Skill.DEAD_EYE)),
    ARTILLERY("포격수", 2, GUNSLINGER, "§8", Material.TNT,
            "대포로 다 날려버리는 건슬링거.", "스킬 피해 +15%, 최대 체력 +2",
            List.of(Skill.QUICK_SHOT, Skill.SCATTER_SHOT, Skill.ROLL, Skill.CANNON)),
    WARLORD("무신", 2, LANCER, "§4", Material.NETHERITE_AXE,
            "천하무쌍의 창술사.", "최대 체력 +6, 근접 피해 +10%",
            List.of(Skill.SPEAR_THRUST, Skill.SPEAR_SWEEP, Skill.CHARGE, Skill.GOD_OF_WAR)),
    VALKYRIE("발키리", 2, LANCER, "§f", Material.FEATHER,
            "하늘의 창을 부르는 전사.", "최대 체력 +4, 낙하 피해 없음",
            List.of(Skill.SPEAR_THRUST, Skill.SPEAR_SWEEP, Skill.CHARGE, Skill.SPEAR_RAIN)),
    MAESTRO("마에스트로", 2, BARD, "§d", Material.JUKEBOX,
            "모두를 살리는 교향곡의 지휘자.", "최대 MP +60, 주변 동료 체력 회복",
            List.of(Skill.SONG_COURAGE, Skill.SONG_SWIFT, Skill.DISSONANCE, Skill.SYMPHONY)),
    DANCER("무희", 2, BARD, "§c", Material.PINK_PETALS,
            "춤추며 싸우는 음유시인.", "이동 속도 증가, 최대 MP +40",
            List.of(Skill.SONG_COURAGE, Skill.SONG_SWIFT, Skill.DISSONANCE, Skill.SWORD_DANCE)),

    // ----- 3차 (Lv.45, 2차 직업에서) — 2차 직업 패시브 + 최대 체력 +4 -----
    BLOOD_LORD("블러드 로드", 4, BERSERKER, "§4§l", Material.NETHERITE_AXE,
            "피로 싸우는 광전사의 끝. 체력이 낮을수록 강해진다.", "2차 직업 능력 + 최대 체력 +4",
            BERSERKER.skills),
    CRUSADER("크루세이더", 4, PALADIN, "§4§l", Material.GOLDEN_SWORD,
            "빛의 방패로 전장을 지배하는 성기사의 끝.", "2차 직업 능력 + 최대 체력 +4",
            PALADIN.skills),
    HAWKEYE("호크아이", 4, SNIPER, "§2§l", Material.CROSSBOW,
            "매의 눈으로 단 한 발도 빗나가지 않는 저격수.", "2차 직업 능력 + 최대 체력 +4",
            SNIPER.skills),
    WINDWALKER("윈드워커", 4, RANGER, "§2§l", Material.FEATHER,
            "바람을 타고 숲을 누비는 사냥꾼.", "2차 직업 능력 + 최대 체력 +4",
            RANGER.skills),
    ARCHMAGE("아크메이지", 4, ELEMENTALIST, "§b§l", Material.NETHER_STAR,
            "모든 원소를 손끝에 둔 대마법사.", "2차 직업 능력 + 최대 체력 +4",
            ELEMENTALIST.skills),
    LICH_LORD("리치 로드", 4, WARLOCK, "§b§l", Material.WITHER_SKELETON_SKULL,
            "죽음마저 부리는 흑마법의 군주.", "2차 직업 능력 + 최대 체력 +4",
            WARLOCK.skills),
    NIGHTMARE("나이트메어", 4, ASSASSIN, "§8§l", Material.NETHERITE_SWORD,
            "악몽처럼 나타나 사라지는 암살자.", "2차 직업 능력 + 최대 체력 +4",
            ASSASSIN.skills),
    SHADOW_MASTER("섀도우 마스터", 4, SHADOW_DANCER, "§8§l", Material.ECHO_SHARD,
            "그림자를 군대처럼 부리는 무희.", "2차 직업 능력 + 최대 체력 +4",
            SHADOW_DANCER.skills),
    SAINT("세인트", 4, HIGH_PRIEST, "§e§l", Material.TOTEM_OF_UNDYING,
            "기적을 일으키는 살아 있는 성인.", "2차 직업 능력 + 최대 체력 +4",
            HIGH_PRIEST.skills),
    INQUISITOR("인퀴지터", 4, JUDGE, "§e§l", Material.BLAZE_ROD,
            "신의 이름으로 악을 불태우는 심문관.", "2차 직업 능력 + 최대 체력 +4",
            JUDGE.skills),
    GRAND_MASTER("그랜드 마스터", 4, SWORD_MASTER, "§3§l", Material.DIAMOND_SWORD,
            "오러 블레이드를 완성한 서양 검술의 정점.", "2차 직업 능력 + 최대 체력 +4",
            SWORD_MASTER.skills),
    SWORD_GOD("검신", 4, BLADE_SAINT, "§3§l", Material.NETHERITE_SWORD,
            "한 번 휘두르면 하늘이 갈라지는 동양 검의 신.", "2차 직업 능력 + 최대 체력 +4",
            BLADE_SAINT.skills),
    KAGE("카게", 4, JONIN, "§8§l", Material.BLACK_DYE,
            "마을 하나를 지키는 그림자 닌자의 우두머리.", "2차 직업 능력 + 최대 체력 +4",
            JONIN.skills),
    MUYEONG("무영", 4, PHANTOM, "§8§l", Material.PHANTOM_MEMBRANE,
            "그림자조차 남기지 않는 환영검의 끝.", "2차 직업 능력 + 최대 체력 +4",
            PHANTOM.skills),
    FIST_GOD("권신", 4, FIST_KING, "§6§l", Material.NETHERITE_INGOT,
            "주먹 하나로 산을 부수는 권법의 신.", "2차 직업 능력 + 최대 체력 +4",
            FIST_KING.skills),
    SAGE("선인", 4, CHI_MASTER, "§6§l", Material.GLOWSTONE_DUST,
            "천지의 기를 다루는 깨달은 자.", "2차 직업 능력 + 최대 체력 +4",
            CHI_MASTER.skills),
    LUNA_ORACLE("루나 오라클", 4, ECLIPSE_PRIEST, "§1§l", Material.ENDER_EYE,
            "달의 뜻을 전하는 예언자.", "2차 직업 능력 + 최대 체력 +4",
            ECLIPSE_PRIEST.skills),
    DESPAIR_LORD("절망의 군주", 4, CURSE_WEAVER, "§1§l", Material.FERMENTED_SPIDER_EYE,
            "모든 감정을 지배하는 저주의 왕.", "2차 직업 능력 + 최대 체력 +4",
            CURSE_WEAVER.skills),
    GUN_MASTER("건마스터", 4, DEADEYE, "§7§l", Material.SPYGLASS,
            "총알 한 발로 승부를 내는 사격의 달인.", "2차 직업 능력 + 최대 체력 +4",
            DEADEYE.skills),
    DEMOLISHER("데몰리셔", 4, ARTILLERY, "§7§l", Material.TNT,
            "전장을 통째로 날려버리는 포격의 왕.", "2차 직업 능력 + 최대 체력 +4",
            ARTILLERY.skills),
    OVERLORD("패왕", 4, WARLORD, "§c§l", Material.TRIDENT,
            "천하를 창 하나로 평정한 패자.", "2차 직업 능력 + 최대 체력 +4",
            WARLORD.skills),
    BRUNHILD("브륀힐드", 4, VALKYRIE, "§c§l", Material.ELYTRA,
            "전사자의 영혼을 이끄는 발키리의 여왕.", "2차 직업 능력 + 최대 체력 +4",
            VALKYRIE.skills),
    DIVA("디바", 4, MAESTRO, "§d§l", Material.JUKEBOX,
            "목소리 하나로 전장을 바꾸는 전설의 가수.", "2차 직업 능력 + 최대 체력 +4",
            MAESTRO.skills),
    BLADE_DANCER("블레이드 댄서", 4, DANCER, "§d§l", Material.PINK_PETALS,
            "칼날과 함께 춤추는 무희의 끝.", "2차 직업 능력 + 최대 체력 +4",
            DANCER.skills),

    // ----- 히든: 초초보자 계열 (모든 직업의 스킬을 배울 수 있다) -----
    ULTRA_NOVICE("초초보자", 3, null, "§f§l", Material.BOOK,
            "[히든] 초보자로 스킬 10개와 히든 스킬 1개를 모은 자. 직업에 상관없이 모든 스킬을 배울 수 있다.", "모든 직업군 교관에게서 스킬을 배움",
            List.of(Skill.TACKLE)),
    ULTRA_NOVICE2("초초초보자", 3, ULTRA_NOVICE, "§f§l§n", Material.WRITABLE_BOOK,
            "[히든] 초초보자의 2차 각성. 스킬을 파괴해 스킬 파편을 얻고, 파편 100개로 스킬을 진화시킨다.", "모든 스킬 + 스킬 파괴·진화",
            List.of(Skill.TACKLE)),

    // ----- 히든 -----
    DRAGON_KNIGHT("용기사", 3, null, "§c§l", Material.DRAGON_HEAD,
            "[히든] 적룡 이그니스를 쓰러뜨린 자만이 될 수 있다.", "최대 체력 +8, 화염 면역",
            List.of(Skill.DRAGON_BREATH, Skill.DRAGON_DIVE, Skill.IRON_WALL, Skill.DRAGON_ROAR)),
    SPELLBLADE("마검사", 3, null, "§9§l", Material.ENCHANTED_BOOK,
            "[히든] 마법과 검술을 함께 쓴다. 너무 어려워서 이도 저도 아니게 될 수 있지만, 극복하면 최강.", "근접 피해 +15%, 최대 MP +60",
            List.of(Skill.INFERNO_OVERLAY, Skill.OVERVOLT_DRIVE, Skill.GLACIAL_DOMINION, Skill.TEMPEST_CALL)),
    VAMPIRE("뱀파이어", 3, null, "§4§l", Material.REDSTONE,
            "[히든] 밤의 귀족. 강하지만 햇빛 아래에서는 약해진다.", "최대 체력 +6, 공격 시 흡혈, 햇빛 아래 나약함",
            List.of(Skill.BITE, Skill.BLOOD_RAIN, Skill.BAT_FORM, Skill.BLOOD_MOON)),
    ANGEL("천사", 3, null, "§f§l", Material.ELYTRA,
            "[히든] 성직자의 상위 호환. 빛의 여신의 힘을 쓴다.", "체력 자연 회복 강화, 최대 MP +60",
            List.of(Skill.HEAL_LIGHT, Skill.JUDGMENT_SPEAR, Skill.DIVINE_WING, Skill.GRACE)),
    DIMENSION_SNIPER("차원의 저격수", 3, null, "§3§l", Material.ENDER_PEARL,
            "[히든] 차원을 넘어온 저격총을 다루는 자.", "활·스킬 피해 +30%",
            List.of(Skill.PRECISION_SHOT, Skill.COVER, Skill.PIERCING_SHOT, Skill.DIMENSION_SHOT)),
    NEET_KING("백수왕", 3, null, "§d§l", Material.RED_BED,
            "[히든] 30레벨까지 전직을 안 하고 버틴 전설의 백수.", "가끔 이유 없이 체력이 찬다",
            List.of(Skill.LIE_DOWN, Skill.MOM_CHANCE, Skill.NEET_RAGE, Skill.NEET_ULT));

    public final String korean;
    public final int tier;
    public final RpgClass parent;
    public final String color;
    public final Material icon;
    public final String description;
    public final String passive;
    public final List<Skill> skills;

    RpgClass(String korean, int tier, RpgClass parent, String color, Material icon, String description, String passive, List<Skill> skills) {
        this.korean = korean;
        this.tier = tier;
        this.parent = parent;
        this.color = color;
        this.icon = icon;
        this.description = description;
        this.passive = passive;
        this.skills = skills;
    }

    public String display() {
        return color + korean;
    }

    /** 패시브 계산용: 3차 직업은 2차 직업의 패시브를 그대로 쓴다 */
    public RpgClass base() {
        return tier == 4 ? parent : this;
    }

    public String tierName() {
        return switch (tier) { case 0 -> "초보자"; case 1 -> "1차"; case 2 -> "2차"; case 4 -> "3차"; default -> "히든"; };
    }

    /** 이 직업 계열의 1차 직업 (히든은 자기 자신) */
    public RpgClass root() {
        RpgClass c = this;
        while (c.parent != null && c.parent != NOVICE) c = c.parent;
        return c;
    }
}
