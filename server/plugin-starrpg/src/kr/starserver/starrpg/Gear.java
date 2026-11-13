package kr.starserver.starrpg;

import org.bukkit.*;
import org.bukkit.attribute.Attribute;
import org.bukkit.command.CommandSender;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.*;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.EntityShootBowEvent;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;

import java.util.*;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 무기·장비 등급: 일반 → 레어 → 유니크 → 고대 → 전설 → 영웅 → 초월 → 신화.
 * 몬스터를 잡으면 등급 장비가 떨어지고(보스는 고대 이상 확정), 등급에 따라
 * 무기는 피해 배율·치명타, 방어구는 받는 피해 감소가 붙는다.
 */
@SuppressWarnings("deprecation")
final class Gear implements Listener {

    enum Grade {
        COMMON("일반", "§f", 1.00, 1.0, 0, 5000),
        RARE("레어", "§9", 1.15, 2.0, 2, 2800),
        UNIQUE("유니크", "§5", 1.30, 3.5, 4, 1300),
        ANCIENT("고대", "§6", 1.50, 5.0, 6, 600),
        LEGEND("전설", "§e", 1.80, 7.0, 9, 240),
        HERO("영웅", "§c", 2.10, 9.0, 12, 50),
        TRANSCEND("초월", "§b", 2.60, 12.0, 16, 9),
        MYTH("신화", "§d", 3.20, 15.0, 22, 1);

        final String korean, color;
        final double weaponMult;   // 무기 피해 배율
        final double armorPct;     // 방어구 1부위당 받는 피해 감소 %
        final int maxCrit;         // 무기 치명타 확률 최대 %
        final int weight;          // 드롭 가중치 (합계 10000)

        Grade(String korean, String color, double weaponMult, double armorPct, int maxCrit, int weight) {
            this.korean = korean;
            this.color = color;
            this.weaponMult = weaponMult;
            this.armorPct = armorPct;
            this.maxCrit = maxCrit;
            this.weight = weight;
        }

        String tag() { return color + "§l[" + korean + "]"; }

        static Grade byName(String s) {
            for (Grade g : values()) if (g.name().equalsIgnoreCase(s) || g.korean.equals(s)) return g;
            return null;
        }
    }

    enum Kind { SWORD, AXE, BOW, CROSSBOW, TRIDENT, HELMET, CHEST, LEGS, BOOTS;
        boolean weapon() { return ordinal() <= TRIDENT.ordinal(); }
    }

    private static final String P = "§d[별빛] §f";
    private final StarRPG plugin;
    private final NamespacedKey GRADE, CRIT, PROJ_GRADE, PROJ_CRIT;

    Gear(StarRPG plugin) {
        this.plugin = plugin;
        GRADE = new NamespacedKey(plugin, "gear_grade");
        CRIT = new NamespacedKey(plugin, "gear_crit");
        PROJ_GRADE = new NamespacedKey(plugin, "gear_proj_grade");
        PROJ_CRIT = new NamespacedKey(plugin, "gear_proj_crit");
    }

    // ------------------------------------------------------------------ 이름·재료

    private static final Map<Kind, String[]> NAMES = Map.of(
            Kind.SWORD, new String[]{"모험가의 검", "기사의 장검", "별빛 세검", "용의 송곳니", "황혼의 검", "심연을 가르는 검", "플람베리온", "영겁의 검"},
            Kind.AXE, new String[]{"나무꾼의 도끼", "오크 전투도끼", "대지의 도끼", "거인의 도끼", "분노의 도끼", "천둥 도끼", "종말의 도끼", "태초의 도끼"},
            Kind.BOW, new String[]{"사냥꾼의 활", "엘프의 활", "질풍의 활", "달빛 장궁", "하늘 사수의 활", "이클립스 적월궁", "별을 쏘는 활", "영겁의 활"},
            Kind.CROSSBOW, new String[]{"낡은 석궁", "드워프 석궁", "강철 석궁", "용골 석궁", "폭풍 석궁", "차원 석궁", "초월자의 석궁", "신의 석궁"},
            Kind.TRIDENT, new String[]{"어부의 작살", "바다의 창", "세이렌의 삼지창", "해왕의 창", "포세이돈의 삼지창", "심해 군주의 창", "파도를 가르는 창", "영겁의 창"},
            Kind.HELMET, new String[]{"가죽 모자", "사슬 투구", "기사의 투구", "고대 왕의 관", "용비늘 투구", "영웅의 투구", "초월자의 관", "신의 왕관"},
            Kind.CHEST, new String[]{"가죽 조끼", "사슬 갑옷", "기사의 갑옷", "고대 수호자의 갑옷", "용비늘 갑옷", "영웅의 갑옷", "초월자의 갑주", "신의 갑주"},
            Kind.LEGS, new String[]{"가죽 바지", "사슬 각반", "기사의 각반", "고대 수호자의 각반", "용비늘 각반", "영웅의 각반", "초월자의 각반", "신의 각반"},
            Kind.BOOTS, new String[]{"가죽 장화", "사슬 장화", "기사의 장화", "고대 여행자의 장화", "용비늘 장화", "영웅의 장화", "바람을 걷는 장화", "신의 장화"});

    private static Material material(Kind k, Grade g) {
        int t = g.ordinal();   // 0..7
        return switch (k) {
            case SWORD -> new Material[]{Material.STONE_SWORD, Material.IRON_SWORD, Material.IRON_SWORD, Material.DIAMOND_SWORD,
                    Material.DIAMOND_SWORD, Material.NETHERITE_SWORD, Material.NETHERITE_SWORD, Material.NETHERITE_SWORD}[t];
            case AXE -> new Material[]{Material.STONE_AXE, Material.IRON_AXE, Material.IRON_AXE, Material.DIAMOND_AXE,
                    Material.DIAMOND_AXE, Material.NETHERITE_AXE, Material.NETHERITE_AXE, Material.NETHERITE_AXE}[t];
            case BOW -> Material.BOW;
            case CROSSBOW -> Material.CROSSBOW;
            case TRIDENT -> Material.TRIDENT;
            case HELMET -> new Material[]{Material.LEATHER_HELMET, Material.CHAINMAIL_HELMET, Material.IRON_HELMET, Material.IRON_HELMET,
                    Material.DIAMOND_HELMET, Material.DIAMOND_HELMET, Material.NETHERITE_HELMET, Material.NETHERITE_HELMET}[t];
            case CHEST -> new Material[]{Material.LEATHER_CHESTPLATE, Material.CHAINMAIL_CHESTPLATE, Material.IRON_CHESTPLATE, Material.IRON_CHESTPLATE,
                    Material.DIAMOND_CHESTPLATE, Material.DIAMOND_CHESTPLATE, Material.NETHERITE_CHESTPLATE, Material.NETHERITE_CHESTPLATE}[t];
            case LEGS -> new Material[]{Material.LEATHER_LEGGINGS, Material.CHAINMAIL_LEGGINGS, Material.IRON_LEGGINGS, Material.IRON_LEGGINGS,
                    Material.DIAMOND_LEGGINGS, Material.DIAMOND_LEGGINGS, Material.NETHERITE_LEGGINGS, Material.NETHERITE_LEGGINGS}[t];
            case BOOTS -> new Material[]{Material.LEATHER_BOOTS, Material.CHAINMAIL_BOOTS, Material.IRON_BOOTS, Material.IRON_BOOTS,
                    Material.DIAMOND_BOOTS, Material.DIAMOND_BOOTS, Material.NETHERITE_BOOTS, Material.NETHERITE_BOOTS}[t];
        };
    }

    // ------------------------------------------------------------------ 생성

    /** {모델 ID, 이름, 제작자} — 출처: models-src/third_party/hanmapo/CREDITS.txt */
    private static String[] look(Kind k, Grade g) {
        if (k == Kind.SWORD && g.ordinal() >= Grade.LEGEND.ordinal()) return new String[]{"fenrir_dagger", "펜리르의 단검", "철봉이"};
        if (k != Kind.CROSSBOW) return null;
        return switch (g) {
            case ANCIENT -> new String[]{"kriss_vector", "크리스 벡터", "카에데"};
            case LEGEND -> new String[]{"hk416", "HK416", "카에데"};
            case HERO -> new String[]{"mosin_nagant", "모신 나강", "looil"};
            case TRANSCEND, MYTH -> new String[]{"psg1", "PSG-1", "looil"};
            default -> null;
        };
    }

    ItemStack create(Grade g, Kind k) {
        ThreadLocalRandom r = ThreadLocalRandom.current();
        ItemStack it = new ItemStack(material(k, g));
        ItemMeta m = it.getItemMeta();
        m.setDisplayName(g.tag() + " " + g.color + NAMES.get(k)[g.ordinal()]);
        List<String> lore = new ArrayList<>();
        lore.add("§7등급: " + g.color + "§l" + g.korean);
        PersistentDataContainer pdc = m.getPersistentDataContainer();
        pdc.set(GRADE, PersistentDataType.STRING, g.name());
        if (k.weapon()) {
            int crit = g.maxCrit == 0 ? 0 : 1 + r.nextInt(g.maxCrit);
            pdc.set(CRIT, PersistentDataType.INTEGER, crit);
            lore.add("§c공격력 §f×" + String.format("%.2f", g.weaponMult));
            if (crit > 0) lore.add("§e치명타 확률 §f+" + crit + "%");
        } else {
            lore.add("§9받는 피해 §f-" + String.format("%.1f", g.armorPct) + "%");
        }
        // 추가 능력치 (Skript 능력치가 "▸ 힘 +N" 줄을 읽어 합산)
        int lines = new int[]{0, 1, 1, 2, 2, 3, 3, 3}[g.ordinal()];
        int base = new int[]{0, 2, 3, 5, 7, 9, 12, 16}[g.ordinal()];
        if (lines > 0) {
            String[] names = {"§c힘", "§a민첩", "§9지능", "§6체력", "§e행운"};
            List<Integer> pool = new ArrayList<>(k.weapon() ? List.of(0, 1, 2, 4, 0, 1, 2) : List.of(3, 3, 3, 0, 1, 2, 4));
            java.util.Collections.shuffle(pool);
            java.util.Set<Integer> used = new java.util.LinkedHashSet<>();
            for (int idx : pool) { if (used.size() >= lines) break; used.add(idx); }
            lore.add("§f추가 능력치");
            for (int idx : used) {
                int amt = base + r.nextInt(Math.max(1, base / 2 + 1));
                lore.add("§8 ▸ " + names[idx] + " §f+" + amt);
            }
        }
        lore.add("");
        lore.add(switch (g) {
            case COMMON -> "§8평범한 장비.";
            case RARE -> "§8조금은 좋은 장비. Lv.20쯤 쓰인다.";
            case UNIQUE -> "§8Lv.30 이후에 쓰다 버리는 장비.";
            case ANCIENT -> "§8Lv.35~45 모험가들이 즐겨 쓰는 장비.";
            case LEGEND -> "§8만렙 즈음의 기본 스펙이라 불린다.";
            case HERO -> "§8전설 이후의 장비. 아직 가진 자가 드물다.";
            case TRANSCEND -> "§8거의 끝판왕. 손에 꼽을 만큼만 존재한다.";
            case MYTH -> "§d§o세상에 단 몇 개뿐인 신화.";
        });
        String[] look = look(k, g);   // 고등급 무기는 한마포 모델로 보이게
        if (look != null) {
            m.setItemModel(new NamespacedKey("starserver", look[0]));
            m.setDisplayName(g.tag() + " " + g.color + look[1]);
            lore.add("§8모델: " + look[2] + " (한마포)");
        }
        m.setLore(lore);
        if (g.ordinal() >= Grade.LEGEND.ordinal()) {
            m.addEnchant(Enchantment.UNBREAKING, 3, true);
            m.addItemFlags(ItemFlag.HIDE_ENCHANTS);
        }
        if (g.ordinal() >= Grade.TRANSCEND.ordinal()) m.setUnbreakable(true);
        it.setItemMeta(m);
        return it;
    }

    Grade roll(int minGrade) {
        ThreadLocalRandom r = ThreadLocalRandom.current();
        int total = 0;
        for (Grade g : Grade.values()) if (g.ordinal() >= minGrade) total += g.weight;
        int x = r.nextInt(total);
        for (Grade g : Grade.values()) {
            if (g.ordinal() < minGrade) continue;
            x -= g.weight;
            if (x < 0) return g;
        }
        return Grade.COMMON;
    }

    ItemStack random(int minGrade) {
        Kind[] ks = Kind.values();
        return create(roll(minGrade), ks[ThreadLocalRandom.current().nextInt(ks.length)]);
    }

    Grade gradeOf(ItemStack it) {
        if (it == null || !it.hasItemMeta()) return null;
        String s = it.getItemMeta().getPersistentDataContainer().get(GRADE, PersistentDataType.STRING);
        if (s == null) return null;
        try { return Grade.valueOf(s); } catch (IllegalArgumentException e) { return null; }
    }

    private int critOf(ItemStack it) {
        if (it == null || !it.hasItemMeta()) return 0;
        return it.getItemMeta().getPersistentDataContainer().getOrDefault(CRIT, PersistentDataType.INTEGER, 0);
    }

    // ------------------------------------------------------------------ 드롭

    @EventHandler
    public void onDeath(EntityDeathEvent e) {
        LivingEntity dead = e.getEntity();
        Player killer = dead.getKiller();
        if (killer == null || !(dead instanceof Monster || dead instanceof Slime || dead instanceof Ghast || dead instanceof Phantom)) return;
        double max = dead.getAttribute(Attribute.MAX_HEALTH).getValue();
        boolean boss = max >= 300;
        boolean custom = dead.getCustomName() != null;
        double chance = boss ? 1.0 : custom ? 0.12 : 0.05;
        if (ThreadLocalRandom.current().nextDouble() >= chance) return;
        ItemStack it = random(boss ? Grade.ANCIENT.ordinal() : 0);
        dead.getWorld().dropItemNaturally(dead.getLocation(), it);
        Grade g = gradeOf(it);
        if (g != null && g.ordinal() >= Grade.LEGEND.ordinal()) {
            Bukkit.broadcastMessage(P + "§b" + killer.getName() + "§f님이 " + it.getItemMeta().getDisplayName() + "§f을(를) 획득했습니다!");
            killer.getWorld().playSound(killer.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 1f, 1.2f);
            killer.getWorld().spawnParticle(Particle.TOTEM_OF_UNDYING, dead.getLocation().add(0, 1, 0), 60, 0.5, 1, 0.5, 0.3);
        }
    }

    // ------------------------------------------------------------------ 효과

    @EventHandler(ignoreCancelled = true)
    public void onShoot(EntityShootBowEvent e) {
        if (!(e.getEntity() instanceof Player) || e.getBow() == null) return;
        Grade g = gradeOf(e.getBow());
        if (g == null) return;
        e.getProjectile().getPersistentDataContainer().set(PROJ_GRADE, PersistentDataType.STRING, g.name());
        e.getProjectile().getPersistentDataContainer().set(PROJ_CRIT, PersistentDataType.INTEGER, critOf(e.getBow()));
    }

    @EventHandler(ignoreCancelled = true, priority = EventPriority.HIGH)
    public void onHit(EntityDamageByEntityEvent e) {
        Grade g = null;
        int crit = 0;
        Player p = null;
        if (e.getDamager() instanceof Player pl
                && (e.getCause() == EntityDamageEvent.DamageCause.ENTITY_ATTACK || e.getCause() == EntityDamageEvent.DamageCause.ENTITY_SWEEP_ATTACK)) {
            ItemStack hand = pl.getInventory().getItemInMainHand();
            g = gradeOf(hand);
            crit = critOf(hand);
            p = pl;
        } else if (e.getDamager() instanceof Projectile pr && pr.getShooter() instanceof Player pl) {
            String s = pr.getPersistentDataContainer().get(PROJ_GRADE, PersistentDataType.STRING);
            if (s != null) {
                try { g = Grade.valueOf(s); } catch (IllegalArgumentException ignored) { }
                crit = pr.getPersistentDataContainer().getOrDefault(PROJ_CRIT, PersistentDataType.INTEGER, 0);
            }
            p = pl;
        }
        if (g == null || p == null) return;
        double dmg = e.getDamage() * g.weaponMult;
        if (crit > 0 && ThreadLocalRandom.current().nextInt(100) < crit) {
            dmg *= 1.5;
            e.getEntity().getWorld().spawnParticle(Particle.CRIT, e.getEntity().getLocation().add(0, 1, 0), 12, 0.3, 0.4, 0.3, 0.3);
        }
        e.setDamage(dmg);
    }

    @EventHandler(ignoreCancelled = true, priority = EventPriority.HIGH)
    public void onHurt(EntityDamageEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        double pct = 0;
        for (ItemStack a : p.getInventory().getArmorContents()) {
            Grade g = gradeOf(a);
            if (g != null) pct += g.armorPct;
        }
        if (pct > 0) e.setDamage(e.getDamage() * (1 - Math.min(60, pct) / 100.0));
    }

    // ------------------------------------------------------------------ 명령어

    void info(CommandSender s) {
        s.sendMessage("§d§m        §r §6§l장비 등급 §d§m        ");
        for (Grade g : Grade.values()) {
            s.sendMessage(" " + g.tag() + " §7무기 §f×" + String.format("%.2f", g.weaponMult)
                    + " §7· 방어구 §f-" + String.format("%.1f", g.armorPct) + "%/부위"
                    + " §8(드롭 " + String.format(g.weight >= 100 ? "%.0f" : "%.2f", g.weight / 100.0) + "%)");
        }
        s.sendMessage("§7몬스터 5%, 이름 있는 몹 12%, 보스는 §6고대 이상 확정§7으로 떨어져요.");
        if (s instanceof Player p) {
            ItemStack hand = p.getInventory().getItemInMainHand();
            Grade g = gradeOf(hand);
            if (g != null) s.sendMessage("§7손에 든 장비: " + hand.getItemMeta().getDisplayName());
            double pct = 0;
            for (ItemStack a : p.getInventory().getArmorContents()) { Grade ag = gradeOf(a); if (ag != null) pct += ag.armorPct; }
            if (pct > 0) s.sendMessage("§7입은 방어구 피해 감소: §9-" + String.format("%.1f", Math.min(60, pct)) + "%");
        }
    }

    /** /starrpg give <p> gear:<등급>[:<종류>] */
    ItemStack parse(String spec) {
        String[] parts = spec.split(":");
        Grade g = parts.length > 1 ? Grade.byName(parts[1]) : roll(0);
        if (g == null) return null;
        Kind k;
        if (parts.length > 2) {
            String kn = switch (parts[2]) {
                case "검", "칼" -> "SWORD"; case "도끼" -> "AXE"; case "활" -> "BOW"; case "석궁" -> "CROSSBOW"; case "삼지창" -> "TRIDENT";
                case "투구", "모자" -> "HELMET"; case "갑옷", "흉갑" -> "CHEST"; case "바지", "레깅스" -> "LEGS"; case "신발", "부츠" -> "BOOTS";
                default -> parts[2].toUpperCase(Locale.ROOT);
            };
            try { k = Kind.valueOf(kn); } catch (IllegalArgumentException e) { return null; }
        } else k = Kind.values()[ThreadLocalRandom.current().nextInt(Kind.values().length)];
        return create(g, k);
    }
}
