package kr.starserver.starrpg;

import org.bukkit.*;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.*;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.entity.*;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.*;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

import java.util.*;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 전투 레벨(1~50)·전직·MP·직업 스킬.
 * 스킬 키: F = 스킬1, Shift+좌클릭 = 스킬2, Shift+우클릭 = 스킬3, Shift 두 번 = 궁극기(2차·히든) · Shift+F = 메뉴
 */
@SuppressWarnings("deprecation")
final class Rpg implements Listener {
    static final int MAX_LEVEL = 50;
    private static final String P = "§d[별빛] §f";

    private final StarRPG plugin;
    private final Skills skills;
    private final NamespacedKey NIGHT_KILLS;
    private final NamespacedKey LEVEL, XP, CLASS, BOSSES, HP_MOD, SPD_MOD, SKILL_PROJ, SKILL_DMG, SKILL_RAD;
    private final Map<UUID, Double> mp = new HashMap<>();
    private final Map<UUID, Map<Skill, Long>> cooldowns = new HashMap<>();
    private final Map<UUID, Long> confirm = new HashMap<>();
    private final Map<UUID, RpgClass> confirmClass = new HashMap<>();
    final Map<UUID, Long> vanishUntil = new HashMap<>();
    private final Map<UUID, Map<String, Long>> weaponCd = new HashMap<>();

    Rpg(StarRPG plugin, Pets pets) {
        this.plugin = plugin;
        this.skills = new Skills(plugin, pets);
        LEVEL = new NamespacedKey(plugin, "rpg_level");
        XP = new NamespacedKey(plugin, "rpg_xp");
        CLASS = new NamespacedKey(plugin, "rpg_class");
        BOSSES = new NamespacedKey(plugin, "rpg_bosses");
        NIGHT_KILLS = new NamespacedKey(plugin, "rpg_night_kills");
        HP_MOD = new NamespacedKey(plugin, "rpg_hp");
        SPD_MOD = new NamespacedKey(plugin, "rpg_speed");
        SKILL_PROJ = new NamespacedKey(plugin, "skill_proj");
        SKILL_DMG = new NamespacedKey(plugin, "skill_dmg");
        SKILL_RAD = new NamespacedKey(plugin, "skill_rad");
        Bukkit.getScheduler().runTaskTimer(plugin, this::secondTick, 20L, 20L);
    }

    Skills skills() { return skills; }

    // ================================================================== 데이터

    int level(Player p) {
        return Math.max(1, p.getPersistentDataContainer().getOrDefault(LEVEL, PersistentDataType.INTEGER, 1));
    }

    int xp(Player p) {
        return p.getPersistentDataContainer().getOrDefault(XP, PersistentDataType.INTEGER, 0);
    }

    RpgClass rpgClass(Player p) {
        String s = p.getPersistentDataContainer().get(CLASS, PersistentDataType.STRING);
        try { return s == null ? RpgClass.NOVICE : RpgClass.valueOf(s); } catch (IllegalArgumentException e) { return RpgClass.NOVICE; }
    }

    /** 다음 레벨까지 필요한 경험치 */
    static int need(int level) {
        return 30 + level * level * 3;
    }

    double maxMp(Player p) {
        RpgClass c = rpgClass(p);
        double bonus = switch (c) {
            case MAGE -> 50; case ELEMENTALIST -> 80; case WARLOCK -> 60;
            case BARD, ECLIPSE_PRIEST, DANCER -> 40; case CHI_MASTER -> 50; case MAESTRO, SPELLBLADE, ANGEL -> 60;
            default -> 0;
        };
        return 100 + level(p) * 2 + bonus + statInt(p) * 3;
    }

    double mp(Player p) {
        return mp.computeIfAbsent(p.getUniqueId(), k -> maxMp(p));
    }

    boolean killedBoss(Player p, String id) {
        String s = p.getPersistentDataContainer().getOrDefault(BOSSES, PersistentDataType.STRING, "");
        return Arrays.asList(s.split(",")).contains(id);
    }

    private void markBoss(Player p, String id) {
        if (killedBoss(p, id)) return;
        String s = p.getPersistentDataContainer().getOrDefault(BOSSES, PersistentDataType.STRING, "");
        p.getPersistentDataContainer().set(BOSSES, PersistentDataType.STRING, s.isEmpty() ? id : s + "," + id);
    }

    void setLevel(Player p, int lv) {
        p.getPersistentDataContainer().set(LEVEL, PersistentDataType.INTEGER, Math.max(1, Math.min(MAX_LEVEL, lv)));
        p.getPersistentDataContainer().set(XP, PersistentDataType.INTEGER, 0);
        applyStats(p);
    }

    void setClass(Player p, RpgClass c) {
        p.getPersistentDataContainer().set(CLASS, PersistentDataType.STRING, c.name());
        applyStats(p);
    }

    /** 레벨·직업에 따른 체력/속도 보정 */
    void applyStats(Player p) {
        RpgClass c = rpgClass(p);
        double hpBonus = level(p) * 0.4 + switch (c) {
            case WARRIOR -> 4; case BERSERKER -> 6; case PALADIN, DRAGON_KNIGHT -> 8;
            case MONK, LANCER, ARTILLERY -> 2; case SWORD_MASTER, FIST_KING, VALKYRIE -> 4; case WARLORD, VAMPIRE -> 6;
            default -> 0;
        };
        AttributeInstance hp = p.getAttribute(Attribute.MAX_HEALTH);
        if (hp != null) {
            hp.removeModifier(HP_MOD);
            hp.addModifier(new AttributeModifier(HP_MOD, Math.round(hpBonus), AttributeModifier.Operation.ADD_NUMBER));
        }
        double spd = switch (c) {
            case ROGUE, ASSASSIN, RANGER, NINJA, DANCER -> 0.10; case JONIN -> 0.12; case SHADOW_DANCER, PHANTOM -> 0.18; default -> 0;
        };
        AttributeInstance sp = p.getAttribute(Attribute.MOVEMENT_SPEED);
        if (sp != null) {
            sp.removeModifier(SPD_MOD);
            if (spd > 0) sp.addModifier(new AttributeModifier(SPD_MOD, spd, AttributeModifier.Operation.ADD_SCALAR));
        }
    }

    // ================================================================== 경험치

    void addXp(Player p, int amount) {
        int lv = level(p);
        if (lv >= MAX_LEVEL || amount <= 0) return;
        int x = xp(p) + amount;
        boolean up = false;
        while (lv < MAX_LEVEL && x >= need(lv)) {
            x -= need(lv);
            lv++;
            up = true;
        }
        if (lv >= MAX_LEVEL) x = 0;
        p.getPersistentDataContainer().set(LEVEL, PersistentDataType.INTEGER, lv);
        p.getPersistentDataContainer().set(XP, PersistentDataType.INTEGER, x);
        if (up) levelUp(p, lv);
    }

    private void levelUp(Player p, int lv) {
        applyStats(p);
        mp.put(p.getUniqueId(), maxMp(p));
        p.setHealth(p.getAttribute(Attribute.MAX_HEALTH).getValue());
        p.sendTitle("§e§lLEVEL UP!", "§fLv." + lv + (lv == MAX_LEVEL ? " §6§l(만렙!)" : ""), 5, 40, 10);
        p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.8f, 1.2f);
        p.getWorld().spawnParticle(Particle.TOTEM_OF_UNDYING, p.getLocation().add(0, 1, 0), 40, 0.4, 0.8, 0.4, 0.3);
        RpgClass c = rpgClass(p);
        if (lv == 10 && c == RpgClass.NOVICE) p.sendMessage(P + "§a§l1차 전직이 가능해요! §e/전직");
        if (lv == 30 && c.tier == 1) p.sendMessage(P + "§a§l2차 전직이 가능해요! §e/전직");
        if (lv == 30 && c == RpgClass.NOVICE) p.sendMessage(P + "§d§l...아직도 초보자? §f어딘가에서 이상한 직업이 열렸다. §e/전직");
        for (Skill s : c.skills) if (unlockLevel(c, s) == lv) p.sendMessage(P + "§b새 스킬: §f" + s.korean + " §7(" + keyOf(c, s) + ")");
        if (lv == MAX_LEVEL) Bukkit.broadcastMessage(P + "§6§l" + p.getName() + "§f님이 §6§l만렙(50)§f을 달성했습니다!");
    }

    @EventHandler
    public void onKill(EntityDeathEvent e) {
        LivingEntity dead = e.getEntity();
        if (dead instanceof Player) return;
        Player killer = dead.getKiller();
        if (killer == null && dead.getLastDamageCause() instanceof EntityDamageByEntityEvent ed
                && ed.getDamager() instanceof Tameable t && t.getOwner() instanceof Player owner) {
            killer = owner;   // 펫이 잡은 것도 주인 경험치
        }
        if (killer == null) return;
        double max = dead.getAttribute(Attribute.MAX_HEALTH).getValue();
        int xp = (int) Math.min(6000, max * 2);
        String name = dead.getCustomName() == null ? "" : ChatColor.stripColor(dead.getCustomName());
        if (max >= 300) xp *= 3;
        if (dead instanceof Animals) xp = Math.max(2, xp / 4);
        addXp(killer, xp);
        killer.sendActionBar("§a+" + xp + " EXP");
        if (name.contains("적룡")) markBoss(killer, "ignis");
        if (name.contains("크루가")) markBoss(killer, "kruga");
        if (name.contains("메두사")) markBoss(killer, "medusa");
        if (name.contains("미노타우로스")) markBoss(killer, "minotaur");
        if (rpgClass(killer) == RpgClass.WARLOCK) skills.heal(killer, 2);
        long tod = killer.getWorld().getTime();
        if (dead instanceof org.bukkit.entity.Monster && tod >= 13000 && tod <= 23000) {
            int n = killer.getPersistentDataContainer().getOrDefault(NIGHT_KILLS, PersistentDataType.INTEGER, 0) + 1;
            killer.getPersistentDataContainer().set(NIGHT_KILLS, PersistentDataType.INTEGER, n);
        }
    }

    // ================================================================== MP / 액션바

    /** Skript 연동: 레벨·직업을 메타데이터로 넘긴다 (Skript: metadata value "rpg_level" of player) */
    void exportMeta(Player p) {
        RpgClass c = rpgClass(p);
        org.bukkit.plugin.Plugin pl = plugin;
        p.setMetadata("rpg_level", new org.bukkit.metadata.FixedMetadataValue(pl, level(p)));
        p.setMetadata("rpg_class", new org.bukkit.metadata.FixedMetadataValue(pl, c.korean));
        p.setMetadata("rpg_class_id", new org.bukkit.metadata.FixedMetadataValue(pl, c.name()));
        p.setMetadata("rpg_root", new org.bukkit.metadata.FixedMetadataValue(pl, c.root().name()));
        p.setMetadata("rpg_class_colored", new org.bukkit.metadata.FixedMetadataValue(pl, c.display()));
        String t = plugin.titleOf(p);
        p.setMetadata("rpg_title", new org.bukkit.metadata.FixedMetadataValue(pl, t == null ? "" : t));
        p.setMetadata("rpg_xp_percent", new org.bukkit.metadata.FixedMetadataValue(pl,
                level(p) >= MAX_LEVEL ? 100 : (int) (100.0 * xp(p) / need(level(p)))));
    }

    /** Skript 스탯(지능)을 읽는다 */
    static int statInt(Player p) {
        for (org.bukkit.metadata.MetadataValue v : p.getMetadata("stat_int")) {
            try { return v.asInt(); } catch (Exception ignored) { }
        }
        return 0;
    }

    private void secondTick() {
        for (Player p : Bukkit.getOnlinePlayers()) {
            exportMeta(p);
            double max = maxMp(p);
            RpgClass c = rpgClass(p);
            long tod = p.getWorld().getTime();
            boolean night = tod >= 13000 && tod <= 23000;
            double regen = 3 + level(p) * 0.05;
            if (night && (c == RpgClass.MOON_PRIEST || c == RpgClass.ECLIPSE_PRIEST)) regen *= 2;
            double cur = Math.min(max, mp(p) + regen);
            mp.put(p.getUniqueId(), cur);
            if (c == RpgClass.ANGEL && p.getHealth() > 0) skills.heal(p, 0.6);
            if (c == RpgClass.MAESTRO) for (Player a : skills.alliesAround(p, 8)) if (a != p && a.getHealth() > 0) skills.heal(a, 0.3);
            if (c == RpgClass.VAMPIRE && !night && p.getLocation().getBlock().getLightFromSky() >= 15 && p.getWorld().getEnvironment() == World.Environment.NORMAL) {
                p.addPotionEffect(new PotionEffect(PotionEffectType.WEAKNESS, 40, 0, true, false));
            }
            if ((c.root() == RpgClass.CLERIC || c == RpgClass.HIGH_PRIEST || c == RpgClass.JUDGE) && p.getHealth() > 0) {
                skills.heal(p, c == RpgClass.HIGH_PRIEST ? 0.6 : 0.3);
            }
            if (c == RpgClass.NEET_KING && ThreadLocalRandom.current().nextInt(30) == 0 && p.getHealth() > 0) {
                skills.heal(p, 6);
                p.sendActionBar("§d이유 없이 기분이 좋아졌다. (+6 체력)");
                continue;
            }
            if (c == RpgClass.DRAGON_KNIGHT) p.addPotionEffect(new PotionEffect(PotionEffectType.FIRE_RESISTANCE, 40, 0, true, false));
            int lv = level(p);
            String bar = lv >= MAX_LEVEL ? "§6MAX" : String.format("%.0f%%", 100.0 * xp(p) / need(lv));
            p.sendActionBar(String.format("§c❤ %.0f/%.0f  §9✦ %.0f/%.0f  §7Lv.%d %s §7(%s)",
                    p.getHealth(), p.getAttribute(Attribute.MAX_HEALTH).getValue(), cur, max, lv, c.display(), bar));
        }
    }

    // ================================================================== 스킬 사용

    int unlockLevel(RpgClass c, Skill s) {
        if (c == RpgClass.NOVICE) return 1;
        int idx = c.skills.indexOf(s);
        int base = c.tier == 1 ? 10 : 30;
        return switch (idx) {
            case 0 -> c.tier == 1 ? 10 : 10;
            case 1 -> c.tier == 1 ? 15 : 15;
            case 2 -> c.tier == 1 ? 20 : 20;
            default -> base;
        };
    }

    String keyOf(RpgClass c, Skill s) {
        return switch (c.skills.indexOf(s)) {
            case 0 -> "F";
            case 1 -> "Shift+좌클릭";
            case 2 -> "Shift+우클릭";
            default -> "Shift 두 번";
        };
    }

    private void use(Player p, int slot) {
        RpgClass c = rpgClass(p);
        if (slot >= c.skills.size()) {
            if (c == RpgClass.NOVICE && slot > 0) p.sendActionBar("§7초보자는 스킬이 하나뿐이에요. §e/전직");
            return;
        }
        Skill s = c.skills.get(slot);
        if (level(p) < unlockLevel(c, s)) {
            p.sendActionBar("§c" + s.korean + "§7은(는) Lv." + unlockLevel(c, s) + "부터 쓸 수 있어요.");
            return;
        }
        long now = System.currentTimeMillis();
        Map<Skill, Long> cd = cooldowns.computeIfAbsent(p.getUniqueId(), k -> new EnumMap<>(Skill.class));
        long left = cd.getOrDefault(s, 0L) - now;
        if (left > 0) {
            p.sendActionBar("§c" + s.korean + " §7쿨타임 " + String.format("%.1f", left / 1000.0) + "초");
            return;
        }
        if (mp(p) < s.mp) {
            p.sendActionBar("§9MP가 부족해요. §7(" + (int) mp(p) + "/" + s.mp + ")");
            p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.6f, 0.6f);
            return;
        }
        if (skills.cast(p, s)) {
            mp.put(p.getUniqueId(), mp(p) - s.mp);
            cd.put(s, now + s.cooldown * 1000L);
            p.sendActionBar("§b" + s.korean + "!");
        }
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onSwap(PlayerSwapHandItemsEvent e) {
        Player p = e.getPlayer();
        e.setCancelled(true);
        if (p.isSneaking()) { plugin.menu.open(p); return; }   // Shift+F = 메뉴
        use(p, 0);
    }

    private final Map<UUID, Long> lastSneak = new HashMap<>();

    @EventHandler(priority = EventPriority.HIGH)
    public void onDoubleSneak(PlayerToggleSneakEvent e) {   // Shift 두 번 = 궁극기
        if (!e.isSneaking()) return;
        Player p = e.getPlayer();
        if (p.isInsideVehicle() || p.isFlying()) return;
        long now = System.currentTimeMillis();
        Long prev = lastSneak.put(p.getUniqueId(), now);
        if (prev == null || now - prev > 350) return;
        lastSneak.remove(p.getUniqueId());
        if (rpgClass(p).skills.size() < 4) { p.sendActionBar("§7궁극기는 2차·히든 직업부터 쓸 수 있어요."); return; }
        use(p, 3);
    }

    /** Shift+좌클릭(허공) = 스킬2, Shift+우클릭 = 스킬3 */
    @EventHandler(priority = EventPriority.HIGH)
    public void onSneakClick(PlayerInteractEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        Player p = e.getPlayer();
        if (!p.isSneaking()) return;
        Action a = e.getAction();
        if (a == Action.LEFT_CLICK_AIR) { use(p, 1); return; }
        if (a != Action.RIGHT_CLICK_AIR && a != Action.RIGHT_CLICK_BLOCK) return;
        ItemStack hand = p.getInventory().getItemInMainHand();
        if ("바람의활".equals(mythicId(hand))) return;          // 바람의 활은 Shift+우클릭이 무기 스킬
        if (a == Action.RIGHT_CLICK_BLOCK && hand.getType().isBlock() && !hand.getType().isAir()) return;   // 웅크려 블록 설치는 그대로
        e.setCancelled(true);
        use(p, 2);
    }

    // ----- 무기 스킬: Mythic 무기 들고 우클릭 -----
    @EventHandler(priority = EventPriority.HIGH)
    public void onWeaponSkill(PlayerInteractEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        if (e.getAction() != Action.RIGHT_CLICK_AIR && e.getAction() != Action.RIGHT_CLICK_BLOCK) return;
        Player p = e.getPlayer();
        String id = mythicId(p.getInventory().getItemInMainHand());
        if (id == null || !Skills.WEAPON_SKILLS.containsKey(id)) return;
        if (id.equals("바람의활") && !p.isSneaking()) return;   // 활은 Shift+우클릭 (그냥 우클릭은 일반 사격)
        if (!id.equals("바람의활") && p.isSneaking()) return;   // 다른 무기는 Shift+우클릭이 직업 스킬3
        Object[] info = Skills.WEAPON_SKILLS.get(id);
        long now = System.currentTimeMillis();
        Map<String, Long> cd = weaponCd.computeIfAbsent(p.getUniqueId(), k -> new HashMap<>());
        long left = cd.getOrDefault(id, 0L) - now;
        if (left > 0) { p.sendActionBar("§c" + info[0] + " §7쿨타임 " + String.format("%.1f", left / 1000.0) + "초"); return; }
        if (skills.weaponSkill(p, id)) {
            e.setCancelled(true);
            cd.put(id, now + (int) info[1] * 1000L);
            p.sendActionBar("§6[무기 스킬] §e" + info[0] + "!");
        }
    }

    /** Mythic 아이템이면 그 ID (Mythic이 아이템 PDC에 남기는 mythicmobs:type) */
    static String mythicId(ItemStack it) {
        if (it == null || !it.hasItemMeta()) return null;
        PersistentDataContainer pdc = it.getItemMeta().getPersistentDataContainer();
        for (NamespacedKey k : pdc.getKeys()) {
            if (k.getNamespace().equals("mythicmobs") && k.getKey().equals("type")) {
                return pdc.get(k, PersistentDataType.STRING);
            }
        }
        return null;
    }

    // ================================================================== 패시브·효과

    @EventHandler(ignoreCancelled = true, priority = EventPriority.HIGH)
    public void onDamage(EntityDamageByEntityEvent e) {
        Player p = null;
        boolean arrow = false;
        if (e.getDamager() instanceof Player pl) p = pl;
        else if (e.getDamager() instanceof AbstractArrow a && a.getShooter() instanceof Player pl) { p = pl; arrow = true; }
        if (p == null || !(e.getEntity() instanceof LivingEntity target) || e.getEntity() instanceof Player) return;
        RpgClass c = rpgClass(p);
        if (arrow) {
            double mult = switch (c) { case ARCHER, RANGER -> 1.2; case SNIPER -> 1.35; case DIMENSION_SNIPER -> 1.3; default -> 1.0; };
            e.setDamage(e.getDamage() * mult);
        } else if (e.getCause() == EntityDamageEvent.DamageCause.ENTITY_ATTACK || e.getCause() == EntityDamageEvent.DamageCause.ENTITY_SWEEP_ATTACK) {
            boolean bare = p.getInventory().getItemInMainHand().getType() == Material.AIR;
            double mult = switch (c) {
                case SWORDSMAN -> 1.1; case NINJA, LANCER -> 1.05; case SWORD_MASTER -> 1.2; case BLADE_SAINT, SPELLBLADE -> 1.15;
                case JONIN, WARLORD -> 1.1;
                case MONK, CHI_MASTER -> bare ? 2.5 : 1.0; case FIST_KING -> bare ? 3.5 : 1.0;
                default -> 1.0;
            };
            e.setDamage(e.getDamage() * mult);
            if (c == RpgClass.BLADE_SAINT && ThreadLocalRandom.current().nextInt(5) == 0) {
                e.setDamage(e.getDamage() * 1.6);
                target.getWorld().spawnParticle(Particle.SWEEP_ATTACK, target.getLocation().add(0, 1, 0), 2, 0.3, 0.3, 0.3, 0);
            }
            if (c == RpgClass.CURSE_WEAVER && ThreadLocalRandom.current().nextInt(5) == 0) {
                target.addPotionEffect(new PotionEffect(PotionEffectType.WEAKNESS, 100, 0));
            }
            long nowMs = System.currentTimeMillis();
            if (skills.extra.godOfWarUntil.getOrDefault(p.getUniqueId(), 0L) > nowMs && !sweeping) {
                sweeping = true;
                try {
                    for (LivingEntity o : skills.enemiesAround(p, target.getLocation(), 3)) {
                        if (o != target) o.damage(e.getDamage() * 0.5, p);
                    }
                } finally { sweeping = false; }
                target.getWorld().spawnParticle(Particle.SWEEP_ATTACK, target.getLocation().add(0, 1, 0), 3, 1, 0.3, 1, 0);
            }
        }
        long nowV = System.currentTimeMillis();
        if (skills.extra.bloodMoonUntil.getOrDefault(p.getUniqueId(), 0L) > nowV) skills.heal(p, e.getDamage() * 0.4);
        else if (c == RpgClass.VAMPIRE) skills.heal(p, e.getDamage() * 0.1);
        if (c == RpgClass.ASSASSIN && !arrow && ThreadLocalRandom.current().nextInt(5) == 0) {
            e.setDamage(e.getDamage() * 1.8);
            target.getWorld().spawnParticle(Particle.CRIT, target.getLocation().add(0, 1, 0), 15, 0.3, 0.4, 0.3, 0.2);
        }
        long now = System.currentTimeMillis();
        if (skills.poisonUntil.getOrDefault(p.getUniqueId(), 0L) > now) {
            target.addPotionEffect(new PotionEffect(PotionEffectType.POISON, 80, 1));
        }
        if (skills.rageUntil.getOrDefault(p.getUniqueId(), 0L) > now) {
            skills.heal(p, e.getFinalDamage() * 0.25);
        }
    }

    private boolean sweeping = false;

    /** 패리: 자세 중 근접 공격을 튕겨내고 상대를 기절 */
    @EventHandler(ignoreCancelled = true, priority = EventPriority.HIGH)
    public void onParry(EntityDamageByEntityEvent e) {
        if (!(e.getEntity() instanceof Player p) || !(e.getDamager() instanceof LivingEntity atk)) return;
        if (skills.extra.parryUntil.getOrDefault(p.getUniqueId(), 0L) < System.currentTimeMillis()) return;
        e.setCancelled(true);
        skills.extra.parryUntil.remove(p.getUniqueId());
        skills.hit(p, atk, skills.scale(p, 8));
        atk.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 40, 9));
        atk.addPotionEffect(new PotionEffect(PotionEffectType.WEAKNESS, 40, 4));
        atk.setVelocity(atk.getLocation().toVector().subtract(p.getLocation().toVector()).setY(0).normalize().multiply(0.8).setY(0.3));
        p.getWorld().spawnParticle(Particle.FLASH, atk.getLocation().add(0, 1, 0), 1);
        p.getWorld().playSound(p.getLocation(), Sound.ITEM_SHIELD_BLOCK, 1f, 0.6f);
        p.getWorld().playSound(p.getLocation(), Sound.BLOCK_ANVIL_PLACE, 0.6f, 1.8f);
        p.sendActionBar("§b§l패리 성공! §7상대가 기절했어요");
    }

    @EventHandler(ignoreCancelled = true)
    public void onFall(EntityDamageEvent e) {
        if (e.getEntity() instanceof Player vp && e.getCause() == EntityDamageEvent.DamageCause.FALL
                && rpgClass(vp) == RpgClass.VALKYRIE) { e.setCancelled(true); return; }
        if (e.getEntity() instanceof Player p && e.getCause() == EntityDamageEvent.DamageCause.FALL
                && plugin.noFallUntil(p) > System.currentTimeMillis()) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onTarget(EntityTargetLivingEntityEvent e) {
        if (e.getTarget() instanceof Player p && vanishUntil.getOrDefault(p.getUniqueId(), 0L) > System.currentTimeMillis()) e.setCancelled(true);
    }

    void tagProjectile(Projectile proj, double dmg, double radius) {
        proj.getPersistentDataContainer().set(SKILL_PROJ, PersistentDataType.BYTE, (byte) 1);
        proj.getPersistentDataContainer().set(SKILL_DMG, PersistentDataType.DOUBLE, dmg);
        proj.getPersistentDataContainer().set(SKILL_RAD, PersistentDataType.DOUBLE, radius);
    }

    @EventHandler
    public void onSkillProjectile(ProjectileHitEvent e) {
        Projectile pr = e.getEntity();
        if (!pr.getPersistentDataContainer().has(SKILL_PROJ, PersistentDataType.BYTE)) return;
        if (!(pr.getShooter() instanceof Player p)) return;
        e.setCancelled(true);
        double dmg = pr.getPersistentDataContainer().getOrDefault(SKILL_DMG, PersistentDataType.DOUBLE, 5.0);
        double rad = pr.getPersistentDataContainer().getOrDefault(SKILL_RAD, PersistentDataType.DOUBLE, 2.0);
        Location at = pr.getLocation();
        pr.remove();
        at.getWorld().spawnParticle(Particle.EXPLOSION, at, 1);
        at.getWorld().spawnParticle(Particle.FLAME, at, 30, rad * 0.4, rad * 0.4, rad * 0.4, 0.05);
        at.getWorld().playSound(at, Sound.ENTITY_GENERIC_EXPLODE, 0.7f, 1.4f);
        for (LivingEntity t : skills.enemiesAround(p, at, rad)) {
            skills.hit(p, t, dmg);
            t.setFireTicks(60);
        }
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (!p.isOnline()) return;
            applyStats(p);
            if (!p.getPersistentDataContainer().has(LEVEL, PersistentDataType.INTEGER)) {
                p.getPersistentDataContainer().set(LEVEL, PersistentDataType.INTEGER, 1);
                p.sendMessage(P + "§e모험가님, 환영해요! §f지금은 §f초보자 Lv.1§f이에요.");
                p.sendMessage(P + "§7몹을 잡아 레벨을 올리고, Lv.10이 되면 §e/전직§7으로 직업을 고르세요. §8(F키: 스킬 · Shift+F: 메뉴)");
            }
        }, 30L);
    }

    @EventHandler
    public void onRespawn(PlayerRespawnEvent e) {
        Bukkit.getScheduler().runTaskLater(plugin, () -> applyStats(e.getPlayer()), 2L);
    }

    // ================================================================== 전직 창

    private static final class ClassHolder implements InventoryHolder {
        Inventory inv;
        final Map<Integer, RpgClass> slots = new HashMap<>();
        public Inventory getInventory() { return inv; }
    }

    private static ItemStack icon(Material m, String name, List<String> lore, boolean glow) {
        ItemStack it = new ItemStack(m);
        ItemMeta meta = it.getItemMeta();
        meta.setDisplayName(name);
        meta.setLore(lore);
        meta.addItemFlags(ItemFlag.values());
        if (glow) meta.setEnchantmentGlintOverride(true);
        it.setItemMeta(meta);
        return it;
    }

    private List<RpgClass> options(Player p) {
        RpgClass c = rpgClass(p);
        List<RpgClass> out = new ArrayList<>();
        if (c == RpgClass.NOVICE) {
            for (RpgClass r : RpgClass.values()) if (r.tier == 1) out.add(r);
            out.add(RpgClass.NEET_KING);
        } else if (c.tier == 1) {
            for (RpgClass r : RpgClass.values()) if (r.parent == c) out.add(r);
            for (RpgClass r : RpgClass.values()) if (r.tier == 3 && r != RpgClass.NEET_KING) out.add(r);
        }
        return out;
    }

    /** 전직 가능 여부와 안 되는 이유 */
    private String requirement(Player p, RpgClass to) {
        int lv = level(p);
        if (to.tier == 1) return lv >= 10 ? null : "Lv.10 필요 (현재 Lv." + lv + ")";
        if (to.tier == 2) return lv >= 30 ? null : "Lv.30 필요 (현재 Lv." + lv + ")";
        if (to == RpgClass.NEET_KING) return lv >= 30 ? null : "§k??????";
        if (to == RpgClass.DRAGON_KNIGHT) {
            if (lv < 30) return "Lv.30 필요";
            return killedBoss(p, "ignis") ? null : "§k??????????";
        }
        RpgClass root = rpgClass(p).root();
        if (to == RpgClass.SPELLBLADE) {   // 검사·마법사 계열 + 메두사 처치
            if (lv < 30) return "Lv.30 필요";
            return (root == RpgClass.SWORDSMAN || root == RpgClass.MAGE) && killedBoss(p, "medusa") ? null : "§k?????? ????";
        }
        if (to == RpgClass.VAMPIRE) {      // 밤에 몬스터 300마리 처치
            if (lv < 30) return "Lv.30 필요";
            int n = p.getPersistentDataContainer().getOrDefault(NIGHT_KILLS, PersistentDataType.INTEGER, 0);
            return n >= 300 ? null : "§k???? §8(" + Math.min(n, 300) * 100 / 300 + "%)";
        }
        if (to == RpgClass.ANGEL) {        // 성직자·달의 사제 계열 + 신전 사제 히든 퀘스트
            if (lv < 30) return "Lv.30 필요";
            return (root == RpgClass.CLERIC || root == RpgClass.MOON_PRIEST) && plugin.questDone(p, "h3") ? null : "§k??? ?? ???";
        }
        if (to == RpgClass.DIMENSION_SNIPER) {   // 궁수·건슬링거 계열 + 미노타우로스 처치
            if (lv < 30) return "Lv.30 필요";
            return (root == RpgClass.ARCHER || root == RpgClass.GUNSLINGER) && killedBoss(p, "minotaur") ? null : "§k????? ????";
        }
        return "전직 불가";
    }

    void openClassMenu(Player p) {
        ClassHolder h = new ClassHolder();
        Inventory inv = Bukkit.createInventory(h, 54, "§5§l전직");
        h.inv = inv;
        ItemStack pane = icon(Material.BLACK_STAINED_GLASS_PANE, " ", List.of(), false);
        for (int i = 0; i < 54; i++) inv.setItem(i, pane);
        RpgClass cur = rpgClass(p);
        inv.setItem(4, icon(cur.icon, "§f현재 직업: " + cur.display(),
                List.of("§7Lv." + level(p), "§7" + cur.description, "§7패시브: §f" + cur.passive), true));
        List<RpgClass> opts = options(p);
        if (opts.isEmpty()) {
            inv.setItem(22, icon(Material.BARRIER, "§7더 이상 전직할 수 없어요", List.of("§7이미 최종 직업이에요."), false));
        }
        int[] slots = opts.size() <= 3 ? new int[]{20, 22, 24}
                : opts.size() <= 7 ? new int[]{19, 21, 23, 25, 29, 31, 33}
                : new int[]{19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34};
        for (int i = 0; i < opts.size() && i < slots.length; i++) {
            RpgClass o = opts.get(i);
            String req = requirement(p, o);
            boolean hidden = o.tier == 3 && req != null;
            List<String> lore = new ArrayList<>();
            if (hidden) {
                lore.add("§8???");
                lore.add("§8조건: " + req);
                inv.setItem(slots[i], icon(Material.GRAY_DYE, "§8§k?????", lore, false));
            } else {
                lore.add("§7" + o.description);
                lore.add("§7패시브: §f" + o.passive);
                lore.add("");
                lore.add("§e스킬:");
                for (Skill s : o.skills) lore.add(" §f" + s.korean + " §8(" + keyOf(o, s) + ", Lv." + unlockLevel(o, s) + ")");
                lore.add("");
                lore.add(req == null ? "§a클릭해서 전직" : "§c" + req);
                inv.setItem(slots[i], icon(req == null ? o.icon : Material.GRAY_DYE, o.display(), lore, req == null));
            }
            h.slots.put(slots[i], o);
        }
        p.openInventory(inv);
    }

    @EventHandler
    public void onClassClick(InventoryClickEvent e) {
        if (!(e.getInventory().getHolder() instanceof ClassHolder h)) return;
        e.setCancelled(true);
        if (!(e.getWhoClicked() instanceof Player p)) return;
        RpgClass to = h.slots.get(e.getRawSlot());
        if (to == null) return;
        String req = requirement(p, to);
        if (req != null) { p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 1f, 1f); return; }
        long now = System.currentTimeMillis();
        if (confirmClass.get(p.getUniqueId()) != to || confirm.getOrDefault(p.getUniqueId(), 0L) < now) {
            confirmClass.put(p.getUniqueId(), to);
            confirm.put(p.getUniqueId(), now + 5000);
            p.sendMessage(P + to.display() + "§f(으)로 전직할까요? §e5초 안에 한 번 더 클릭§f하면 확정돼요. §7(되돌릴 수 없어요)");
            p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_PLING, 1f, 1.2f);
            return;
        }
        confirm.remove(p.getUniqueId());
        setClass(p, to);
        p.closeInventory();
        p.sendTitle(to.display(), "§f전직 완료!", 10, 60, 20);
        p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 1f, 1f);
        p.getWorld().spawnParticle(Particle.END_ROD, p.getLocation().add(0, 1, 0), 80, 0.5, 1, 0.5, 0.1);
        Bukkit.broadcastMessage(P + "§b" + p.getName() + "§f님이 " + to.display() + "§f(으)로 전직했습니다!"
                + (to.tier == 3 ? " §d§l[히든 직업]" : ""));
        p.sendMessage(P + "§7스킬 확인: §e/스킬");
        if (to == RpgClass.DRAGON_KNIGHT) {   // 용기사 전직 보상: 신화 탈것 흑룡
            plugin.giveItem(p, plugin.capsule(Species.DRAGON));
            Bukkit.broadcastMessage(P + "§5§l✦ " + p.getName() + "님이 신화 탈것 §d§l흑룡§5§l을 얻었습니다! ✦");
        }
    }

    @EventHandler
    public void onClassDrag(InventoryDragEvent e) {
        if (e.getInventory().getHolder() instanceof ClassHolder) e.setCancelled(true);
    }

    // ================================================================== 명령어 출력

    void showSkills(Player p) {
        RpgClass c = rpgClass(p);
        p.sendMessage("§d§m      §r " + c.display() + " §f스킬 §d§m      ");
        for (Skill s : c.skills) {
            boolean ok = level(p) >= unlockLevel(c, s);
            p.sendMessage((ok ? " §a" : " §8") + s.korean + " §7[" + keyOf(c, s) + "] §9MP " + s.mp + " §7쿨 " + s.cooldown + "초"
                    + (ok ? "" : " §c(Lv." + unlockLevel(c, s) + ")"));
            p.sendMessage("   §7" + s.description);
        }
        p.sendMessage("§8F: 스킬1 · Shift+좌클릭: 스킬2 · Shift+우클릭: 스킬3 · Shift 두 번: 궁극기 · Shift+F: 메뉴");
        p.sendMessage("§8무기 스킬: 별빛의검·용암도끼·대족장의도끼는 우클릭, 바람의활은 Shift+우클릭");
    }

    void showInfo(CommandSender s, Player p) {
        int lv = level(p);
        RpgClass c = rpgClass(p);
        s.sendMessage("§d§m      §r §f" + p.getName() + "의 정보 §d§m      ");
        s.sendMessage(" §7직업: " + c.display() + " §8(" + (c.tier == 0 ? "초보자" : c.tier == 3 ? "히든" : c.tier + "차") + ")");
        s.sendMessage(" §7레벨: §fLv." + lv + (lv >= MAX_LEVEL ? " §6(만렙)" : " §7(" + xp(p) + "/" + need(lv) + " EXP)"));
        s.sendMessage(String.format(" §7체력: §c%.0f/%.0f  §7MP: §9%.0f/%.0f", p.getHealth(),
                p.getAttribute(Attribute.MAX_HEALTH).getValue(), mp(p), maxMp(p)));
        s.sendMessage(" §7패시브: §f" + c.passive);
    }

    boolean admin(CommandSender s, String[] a) {
        if (a.length < 3) {
            s.sendMessage(P + "/레벨관리 레벨설정 <닉네임> <레벨> · /레벨관리 경험치 <닉네임> <양> · /레벨관리 직업설정 <닉네임> <직업이름>");
            s.sendMessage("§7(영어도 가능: /rpg setlevel · addxp · setclass)");
            s.sendMessage("§7직업: " + String.join(", ", Arrays.stream(RpgClass.values()).map(c -> c.korean).toList()));
            return true;
        }
        Player t = Bukkit.getPlayerExact(a[1]);
        if (t == null) { s.sendMessage(P + "§c플레이어를 찾을 수 없어요."); return true; }
        switch (a[0].toLowerCase(Locale.ROOT)) {
            case "setlevel", "레벨설정", "레벨" -> { setLevel(t, Integer.parseInt(a[2])); s.sendMessage(P + t.getName() + " → Lv." + level(t)); }
            case "addxp", "경험치", "경험치추가" -> { addXp(t, Integer.parseInt(a[2])); s.sendMessage(P + t.getName() + " +" + a[2] + " EXP"); }
            case "setclass", "직업설정", "직업" -> {
                RpgClass c = null;
                String want = String.join(" ", Arrays.copyOfRange(a, 2, a.length));
                for (RpgClass rc : RpgClass.values())
                    if (rc.name().equalsIgnoreCase(want) || rc.korean.equals(want) || rc.korean.replace(" ", "").equals(want.replace(" ", ""))) c = rc;
                if (c == null) { s.sendMessage(P + "§c알 수 없는 직업: " + want); return true; }
                setClass(t, c); s.sendMessage(P + t.getName() + " → " + rpgClass(t).display());
            }
            default -> s.sendMessage(P + "§c알 수 없는 명령");
        }
        return true;
    }

    /** PlaceholderAPI용 */
    static String bar(double ratio, String on, String off) {
        int n = (int) Math.round(Math.max(0, Math.min(1, ratio)) * 10);
        return on + "▰".repeat(n) + off + "▱".repeat(10 - n);
    }

    String placeholder(Player p, String key) {
        RpgClass c = rpgClass(p);
        return switch (key) {
            case "level" -> String.valueOf(level(p));
            case "class" -> c.korean;
            case "class_colored" -> c.display();
            case "tag" -> "§7[Lv." + level(p) + " " + c.display() + "§7]";
            case "xp_percent" -> level(p) >= MAX_LEVEL ? "MAX" : String.format("%.0f%%", 100.0 * xp(p) / need(level(p)));
            case "mp" -> String.valueOf((int) mp(p));
            case "mp_max" -> String.valueOf((int) maxMp(p));
            case "title" -> plugin.titleOf(p);
            case "xp_num" -> level(p) >= MAX_LEVEL ? "100" : String.valueOf((int) (100.0 * xp(p) / need(level(p))));
            case "xp_cur" -> String.format("%,d", (long) xp(p));
            case "xp_need" -> level(p) >= MAX_LEVEL ? "MAX" : String.format("%,d", (long) need(level(p)));
            case "xp_bar" -> bar(level(p) >= MAX_LEVEL ? 1 : (double) xp(p) / need(level(p)), "§a", "§8");
            case "mp_bar" -> bar(mp(p) / Math.max(1, maxMp(p)), "§9", "§8");
            case "hp_bar" -> bar(p.getHealth() / p.getAttribute(Attribute.MAX_HEALTH).getValue(), "§c", "§8");
            case "hp" -> String.valueOf((int) Math.ceil(p.getHealth()));
            case "hp_max" -> String.valueOf((int) p.getAttribute(Attribute.MAX_HEALTH).getValue());
            case "stat_points" -> { Object v = p.hasMetadata("stat_free") ? p.getMetadata("stat_free").get(0).value() : 0; yield String.valueOf(v); }
            default -> null;
        };
    }
}
