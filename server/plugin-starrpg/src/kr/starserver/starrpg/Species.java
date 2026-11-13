package kr.starserver.starrpg;

import org.bukkit.entity.EntityType;

/**
 * 탈것 종류.
 * speed: 블록/틱 (0.3 ≈ 6블록/초), jump: 점프 세기, capture: 그물총 기본 포획 확률 (0 = 야생 포획 불가)
 */
public enum Species {
    // ----- 육지 동물 -----
    COW("소", EntityType.COW, 0.28, 0.5, false, Grade.COMMON, 1.0),
    PIG("돼지", EntityType.PIG, 0.30, 0.5, false, Grade.COMMON, 1.0),
    SHEEP("양", EntityType.SHEEP, 0.28, 0.5, false, Grade.COMMON, 1.0),
    CHICKEN("왕닭", EntityType.CHICKEN, 0.30, 0.6, false, Grade.COMMON, 2.5),
    RABBIT("왕토끼", EntityType.RABBIT, 0.38, 0.9, false, Grade.RARE, 2.8),
    HORSE("말", EntityType.HORSE, 0.45, 0.8, false, Grade.UNIQUE, 1.0, "mount_horse"),
    DONKEY("당나귀", EntityType.DONKEY, 0.36, 0.6, false, Grade.RARE, 1.0),
    LLAMA("라마", EntityType.LLAMA, 0.34, 0.6, false, Grade.RARE, 1.0),
    CAMEL("낙타", EntityType.CAMEL, 0.36, 0.7, false, Grade.ANCIENT, 1.0),
    WOLF("늑대", EntityType.WOLF, 0.42, 0.6, false, Grade.ANCIENT, 1.8, "mount_wolf"),
    FOX("여우", EntityType.FOX, 0.44, 0.7, false, Grade.ANCIENT, 2.2, "mount_fox"),
    GOAT("산양", EntityType.GOAT, 0.36, 1.1, false, Grade.UNIQUE, 1.6),
    FROG("왕개구리", EntityType.FROG, 0.30, 1.2, false, Grade.UNIQUE, 3.0),
    PANDA("판다", EntityType.PANDA, 0.28, 0.5, false, Grade.UNIQUE, 1.2),
    POLAR_BEAR("북극곰", EntityType.POLAR_BEAR, 0.36, 0.6, false, Grade.ANCIENT, 1.3),
    SNIFFER("스니퍼", EntityType.SNIFFER, 0.26, 0.4, false, Grade.HERO, 1.0),
    STRIDER("스트라이더", EntityType.STRIDER, 0.30, 0.5, false, Grade.ANCIENT, 1.3),
    RAVAGER("라바저", EntityType.RAVAGER, 0.40, 0.6, false, Grade.HERO, 1.0),

    // ----- 비행 동물 -----
    BEE("왕꿀벌", EntityType.BEE, 0.45, 0, true, Grade.RARE, 3.0),
    PHANTOM("팬텀", EntityType.PHANTOM, 0.60, 0, true, Grade.HERO, 1.5),

    // ----- 특별한 나는 탈것 (보스 드롭·상점) -----
    WHALE("별빛 고래", EntityType.HORSE, 0.65, 0, true, Grade.LEGEND, 1.0, "sky_whale"),
    BROOM("마법 빗자루", EntityType.HORSE, 0.85, 0, true, Grade.LEGEND, 1.0, "broom"),
    DRAGON("흑룡", EntityType.HORSE, 0.80, 0, true, Grade.MYTH, 1.0, "mount_dragon");

    /** 탈것 등급: 그물총 기본 포획 확률 (0 = 야생 포획 불가) */
    public enum Grade {
        COMMON("일반", "§f", 0.60), RARE("레어", "§a", 0.40), UNIQUE("유니크", "§b", 0.25),
        ANCIENT("고대", "§d", 0.12), HERO("영웅", "§c", 0.05), LEGEND("전설", "§6", 0), MYTH("신화", "§5", 0);
        public final String korean, color;
        public final double capture;
        Grade(String korean, String color, double capture) { this.korean = korean; this.color = color; this.capture = capture; }
        public String display() { return color + "§l" + korean; }
    }

    public final String korean;
    public final EntityType type;
    public final double speed;
    public final double jump;
    public final boolean fly;
    public final Grade grade;
    public final double capture;
    public final double scale;
    /** BetterModel 모델 ID (없으면 바닐라 모습) */
    public final String model;

    Species(String korean, EntityType type, double speed, double jump, boolean fly, Grade grade, double scale) {
        this(korean, type, speed, jump, fly, grade, scale, null);
    }

    Species(String korean, EntityType type, double speed, double jump, boolean fly, Grade grade, double scale, String model) {
        this.grade = grade;
        this.model = model;
        this.korean = korean;
        this.type = type;
        this.speed = speed;
        this.jump = jump;
        this.fly = fly;
        this.capture = grade.capture;
        this.scale = scale;
    }

    public boolean legendary() {
        return capture <= 0;
    }

    /** 야생에서 그물총으로 잡을 수 있는 종류 */
    public static Species wild(EntityType t) {
        for (Species s : values()) {
            if (s.type == t && s.capture > 0) return s;
        }
        return null;
    }

    public static Species byName(String name) {
        for (Species s : values()) {
            if (s.name().equalsIgnoreCase(name) || s.korean.equals(name)) return s;
        }
        return null;
    }
}
