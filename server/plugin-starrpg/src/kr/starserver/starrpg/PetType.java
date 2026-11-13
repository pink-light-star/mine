package kr.starserver.starrpg;

/** 아군 펫 종류. combatModel이 normalModel과 다르면 전투에 들어갈 때 복장(모델)이 바뀐다. */
public enum PetType {
    RICO("세컨드", "리코", "rico_normal", "rico_combat", false, "§a", Weapon.SWORD),
    RAPI("수영복", "라피", "rapi_normal", "rapi_combat", true, "§c", Weapon.GATLING),
    RED("레드후드", "레드후드", "pet_red", "pet_red", true, "§4", Weapon.RIFLE),
    BLUE("스노우화이트", "스노우화이트", "pet_blue", "pet_blue", true, "§9", Weapon.SNIPER),
    SILVER("신데렐라", "신데렐라", "pet_silver", "pet_silver", true, "§7", Weapon.SHIELD),
    PINK("엘리스", "엘리스", "pet_pink", "pet_pink", true, "§d", Weapon.PISTOL);

    /** 무기: 이름, 사거리, 멈춰서 쏘는 거리, 한 발 피해, 쿨타임(틱), 한 번에 쏘는 발수 */
    public enum Weapon {
        SWORD("검 (근접)", 0, 0, 9, 0, 0),
        RIFLE("소총 (원거리)", 18, 8, 6, 24, 1),
        GATLING("개틀링건 (연사)", 16, 7, 1.8, 36, 8),
        SNIPER("저격총 (장거리)", 32, 20, 18, 60, 1),
        PISTOL("권총 (속사)", 12, 5, 3.5, 12, 1),
        SHIELD("기계 방패 (원거리)", 18, 8, 6, 24, 1);

        public final String korean;
        public final double range, stop, damage;
        public final int cooldown, shots;

        Weapon(String korean, double range, double stop, double damage, int cooldown, int shots) {
            this.korean = korean;
            this.range = range;
            this.stop = stop;
            this.damage = damage;
            this.cooldown = cooldown;
            this.shots = shots;
        }
    }

    public final String normalName;
    public final String combatName;
    public final String normalModel;
    public final String combatModel;
    /** true = 원거리(총, 신데렐라는 방패 포구), false = 검(근접) */
    public final boolean gun;
    public final String color;
    public final Weapon weapon;

    PetType(String normalName, String combatName, String normalModel, String combatModel, boolean gun, String color, Weapon weapon) {
        this.weapon = weapon;
        this.normalName = normalName;
        this.combatName = combatName;
        this.normalModel = normalModel;
        this.combatModel = combatModel;
        this.gun = gun;
        this.color = color;
    }

    public boolean transforms() {
        return !normalModel.equals(combatModel);
    }

    public static PetType byName(String s) {
        for (PetType t : values()) {
            if (t.name().equalsIgnoreCase(s) || t.normalName.equals(s) || t.combatName.equals(s)) return t;
        }
        return null;
    }
}
