package kr.starserver.starrpg;

import org.bukkit.*;
import org.bukkit.entity.*;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.util.Vector;

import java.util.*;

/** 추가 직업(검사·닌자·무투가·달의 사제·건슬링거·창술사·음유시인·히든)의 스킬 효과 */
@SuppressWarnings("deprecation")
final class ExtraSkills {
    private final StarRPG plugin;
    private final Skills k;
    /** 지속 효과 만료 시각 (ms) */
    final Map<UUID, Long> parryUntil = new HashMap<>();
    final Map<UUID, Long> godOfWarUntil = new HashMap<>();
    final Map<UUID, Long> bloodMoonUntil = new HashMap<>();
    final Map<UUID, Long> coverUntil = new HashMap<>();

    ExtraSkills(StarRPG plugin, Skills k) {
        this.plugin = plugin;
        this.k = k;
    }

    private static Particle.DustOptions dust(int r, int g, int b, float size) {
        return new Particle.DustOptions(Color.fromRGB(r, g, b), size);
    }

    /** 원뿔(앞쪽) 안의 적 */
    private List<LivingEntity> cone(Player p, double range, double cosLimit) {
        Location eye = p.getLocation();
        Vector dir = eye.getDirection().setY(0).normalize();
        List<LivingEntity> out = new ArrayList<>();
        for (LivingEntity e : k.enemiesAround(p, eye, range)) {
            Vector to = e.getLocation().toVector().subtract(eye.toVector()).setY(0);
            if (to.lengthSquared() < 0.01 || to.normalize().dot(dir) >= cosLimit) out.add(e);
        }
        return out;
    }

    /** 앞으로 돌진하며 지나간 적에게 피해 */
    private void dash(Player p, double power, double dmg, Particle trail, Runnable onHitFx) {
        Vector dir = p.getLocation().getDirection().setY(0).normalize();
        p.setVelocity(dir.clone().multiply(power).setY(0.15));
        plugin.noFall(p, 40);
        Set<LivingEntity> done = new HashSet<>();
        new BukkitRunnable() {
            int t = 0;
            public void run() {
                if (!p.isOnline() || t++ > 8) { cancel(); return; }
                p.getWorld().spawnParticle(trail, p.getLocation().add(0, 1, 0), 6, 0.3, 0.4, 0.3, 0.02);
                for (LivingEntity e : k.enemiesAround(p, p.getLocation(), 2.2)) {
                    if (done.add(e)) {
                        k.hit(p, e, dmg);
                        if (onHitFx != null) onHitFx.run();
                    }
                }
            }
        }.runTaskTimer(plugin, 0, 1);
    }

    private void buffAllies(Player p, double r, PotionEffectType type, int ticks, int amp) {
        for (Player a : k.alliesAround(p, r)) a.addPotionEffect(new PotionEffect(type, ticks, amp));
    }

    private void lifesteal(Player p, double amount) {
        k.heal(p, amount);
        p.getWorld().spawnParticle(Particle.DUST, p.getLocation().add(0, 1, 0), 8, 0.3, 0.5, 0.3, 0, dust(170, 0, 0, 1.2f));
    }

    boolean cast(Player p, Skill s) {
        World w = p.getWorld();
        Location loc = p.getLocation();
        Vector dir = loc.getDirection().setY(0).normalize();
        switch (s) {
            // ================================================== 검사
            case CROSS_SLASH -> {
                for (LivingEntity e : cone(p, 4.5, 0.5)) k.hit(p, e, k.scale(p, 8));
                Location c = loc.clone().add(dir.clone().multiply(2)).add(0, 1, 0);
                Vector side = dir.clone().crossProduct(new Vector(0, 1, 0)).normalize();
                for (double d = -1.6; d <= 1.6; d += 0.2) {
                    w.spawnParticle(Particle.DUST, c.clone().add(side.clone().multiply(d)).add(0, d, 0), 1, 0, 0, 0, 0, dust(170, 230, 255, 1.3f));
                    w.spawnParticle(Particle.DUST, c.clone().add(side.clone().multiply(d)).add(0, -d, 0), 1, 0, 0, 0, 0, dust(170, 230, 255, 1.3f));
                }
                w.spawnParticle(Particle.SWEEP_ATTACK, c, 3, 0.6, 0.4, 0.6, 0);
                w.playSound(loc, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1f, 1.3f);
            }
            case DRAW_SLASH -> {
                dash(p, 1.8, k.scale(p, 10), Particle.SWEEP_ATTACK, null);
                w.playSound(loc, Sound.ITEM_TRIDENT_RIPTIDE_1, 1f, 1.6f);
            }
            case PARRY -> {
                parryUntil.put(p.getUniqueId(), System.currentTimeMillis() + 1500);
                p.addPotionEffect(new PotionEffect(PotionEffectType.RESISTANCE, 30, 3, true, false));
                w.spawnParticle(Particle.ENCHANTED_HIT, loc.add(0, 1, 0), 20, 0.5, 0.6, 0.5, 0.1);
                w.playSound(loc, Sound.ITEM_SHIELD_BLOCK, 1f, 1.4f);
                p.sendActionBar("§b패리 자세! §7(1.5초)");
            }
            case IMPERIAL_FALL -> {
                p.setVelocity(new Vector(0, 0.6, 0));
                k.later(10, () -> {
                    Location l = p.getLocation();
                    for (int r = 1; r <= 6; r++) {
                        final int rr = r;
                        k.later(r * 2L, () -> {
                            for (int i = 0; i < rr * 10; i++) {
                                double a = 2 * Math.PI * i / (rr * 10);
                                w.spawnParticle(Particle.DUST, l.clone().add(Math.cos(a) * rr, 0.2, Math.sin(a) * rr), 1, 0, 0, 0, 0, dust(80, 170, 255, 1.6f));
                            }
                        });
                    }
                    for (LivingEntity e : k.enemiesAround(p, l, 6)) {
                        k.hit(p, e, k.scale(p, 22));
                        e.setVelocity(e.getLocation().toVector().subtract(l.toVector()).setY(0).normalize().multiply(0.8).setY(0.5));
                    }
                    w.playSound(l, Sound.ITEM_MACE_SMASH_GROUND_HEAVY, 1.5f, 0.8f);
                    w.playSound(l, Sound.BLOCK_BEACON_POWER_SELECT, 1f, 1.5f);
                });
            }
            case ABYSS_SLASH -> {
                w.spawnParticle(Particle.SOUL_FIRE_FLAME, loc.clone().add(0, 1, 0), 40, 0.4, 0.6, 0.4, 0.05);
                w.playSound(loc, Sound.BLOCK_BEACON_ACTIVATE, 1f, 1.8f);
                k.later(15, () -> {
                    Location from = p.getEyeLocation().subtract(0, 0.3, 0);
                    Vector d = from.getDirection().normalize();
                    Set<LivingEntity> hitSet = new HashSet<>();
                    Vector side = d.clone().crossProduct(new Vector(0, 1, 0)).normalize();
                    for (double t = 0.5; t <= 16; t += 0.4) {
                        Location at = from.clone().add(d.clone().multiply(t));
                        for (double sd = -1.2; sd <= 1.2; sd += 0.6)
                            w.spawnParticle(Particle.DUST, at.clone().add(side.clone().multiply(sd)), 1, 0, 0, 0, 0, dust(40, 120, 255, 1.4f));
                        for (LivingEntity e : k.enemiesAround(p, at, 1.6)) {
                            if (!hitSet.add(e)) continue;
                            double max = e.getAttribute(org.bukkit.attribute.Attribute.MAX_HEALTH).getValue();
                            double dmg = k.scale(p, 24) * (e.getHealth() < max * 0.3 ? 2 : 1);
                            k.hit(p, e, dmg);
                        }
                    }
                    w.playSound(from, Sound.ENTITY_WARDEN_SONIC_BOOM, 0.8f, 1.6f);
                });
            }

            // ================================================== 닌자
            case DEEP_PIERCE -> {
                LivingEntity t = k.lookTarget(p, 4);
                if (t == null) { p.sendActionBar("§c찌를 대상이 없어요."); return false; }
                k.hit(p, t, k.scale(p, 9));
                t.addPotionEffect(new PotionEffect(PotionEffectType.WITHER, 100, 1));
                w.spawnParticle(Particle.DUST, t.getLocation().add(0, 1, 0), 25, 0.3, 0.4, 0.3, 0, dust(160, 0, 0, 1.2f));
                w.playSound(loc, Sound.ENTITY_PLAYER_ATTACK_CRIT, 1f, 1.4f);
            }
            case SHURIKEN -> {
                for (int i = -1; i <= 1; i++) {
                    Snowball sb = p.launchProjectile(Snowball.class, p.getLocation().getDirection().rotateAroundY(Math.toRadians(i * 10)).multiply(2.2));
                    sb.setItem(new org.bukkit.inventory.ItemStack(Material.IRON_NUGGET));
                    plugin.tagSkillProjectile(sb, k.scale(p, 6), 0.8);
                }
                w.playSound(loc, Sound.ENTITY_WITCH_THROW, 1f, 1.6f);
            }
            case BLADE_DASH -> {
                dash(p, 1.6, k.scale(p, 8), Particle.CRIT, null);
                w.playSound(loc, Sound.ENTITY_BREEZE_JUMP, 1f, 1.4f);
            }
            case SHADOW_CLONE -> {
                p.addPotionEffect(new PotionEffect(PotionEffectType.SPEED, 80, 1));
                new BukkitRunnable() {
                    int t = 0;
                    public void run() {
                        if (!p.isOnline() || t++ >= 6) { cancel(); return; }
                        Location l = p.getLocation();
                        for (int i = 0; i < 3; i++) {
                            double a = Math.toRadians(t * 40 + i * 120);
                            Location cl = l.clone().add(Math.cos(a) * 2, 0, Math.sin(a) * 2);
                            w.spawnParticle(Particle.LARGE_SMOKE, cl.clone().add(0, 1, 0), 12, 0.2, 0.5, 0.2, 0.01);
                            w.spawnParticle(Particle.SWEEP_ATTACK, cl.clone().add(0, 1, 0), 1, 0, 0, 0, 0);
                        }
                        for (LivingEntity e : k.enemiesAround(p, l, 4.5)) k.hit(p, e, k.scale(p, 5));
                        w.playSound(l, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 0.8f, 1.5f);
                    }
                }.runTaskTimer(plugin, 0, 6);
            }
            case PHANTOM_PIERCE -> {
                LivingEntity t = k.lookTarget(p, 12);
                if (t == null) { p.sendActionBar("§c대상이 없어요."); return false; }
                Location behind = t.getLocation().add(t.getLocation().getDirection().setY(0).normalize().multiply(-1.2));
                behind.setDirection(t.getLocation().toVector().subtract(behind.toVector()));
                p.teleport(behind);
                new BukkitRunnable() {
                    int n = 0;
                    public void run() {
                        if (!p.isOnline() || t.isDead() || n++ >= 8) { cancel(); return; }
                        t.setNoDamageTicks(0);
                        k.hit(p, t, k.scale(p, 4));
                        Location at = t.getLocation().add(Math.random() - 0.5, 1 + Math.random() * 0.6, Math.random() - 0.5);
                        w.spawnParticle(Particle.DUST, at, 6, 0.1, 0.1, 0.1, 0, dust(180, 120, 255, 1.1f));
                        w.spawnParticle(Particle.CRIT, at, 4, 0.1, 0.1, 0.1, 0.2);
                        w.playSound(at, Sound.ENTITY_PLAYER_ATTACK_CRIT, 0.7f, 1.8f);
                    }
                }.runTaskTimer(plugin, 0, 2);
            }

            // ================================================== 무투가
            case IRON_FIST -> {
                LivingEntity t = k.lookTarget(p, 4);
                if (t == null) { p.sendActionBar("§c때릴 대상이 없어요."); return false; }
                k.hit(p, t, k.scale(p, 10));
                t.setVelocity(dir.clone().multiply(1.6).setY(0.4));
                w.spawnParticle(Particle.EXPLOSION, t.getLocation().add(0, 1, 0), 1);
                w.playSound(loc, Sound.ENTITY_PLAYER_ATTACK_KNOCKBACK, 1f, 0.6f);
            }
            case COMBO_RUSH -> new BukkitRunnable() {
                int n = 0;
                public void run() {
                    if (!p.isOnline() || n++ >= 6) { cancel(); return; }
                    for (LivingEntity e : cone(p, 3.5, 0.3)) { e.setNoDamageTicks(0); k.hit(p, e, k.scale(p, 3)); }
                    w.spawnParticle(Particle.CRIT, p.getLocation().add(dir.clone().multiply(1.5)).add(0, 1.2, 0), 8, 0.4, 0.3, 0.4, 0.2);
                    w.playSound(p.getLocation(), Sound.ENTITY_PLAYER_ATTACK_WEAK, 1f, 1.2f + n * 0.1f);
                }
            }.runTaskTimer(plugin, 0, 4);
            case QI_GUARD -> {
                p.addPotionEffect(new PotionEffect(PotionEffectType.RESISTANCE, 120, 1));
                p.addPotionEffect(new PotionEffect(PotionEffectType.ABSORPTION, 120, 1));
                k.ring(loc.clone().add(0, 1, 0), Particle.END_ROD, 1.2, 20);
                w.playSound(loc, Sound.BLOCK_BEACON_POWER_SELECT, 1f, 1.6f);
            }
            case HUNDRED_FISTS -> new BukkitRunnable() {
                int n = 0;
                public void run() {
                    if (!p.isOnline() || n++ >= 10) { cancel(); return; }
                    Vector d = p.getLocation().getDirection().setY(0).normalize();
                    Location at = p.getLocation().add(d.clone().multiply(2 + Math.random() * 2)).add((Math.random() - 0.5) * 2, 1, (Math.random() - 0.5) * 2);
                    w.spawnParticle(Particle.EXPLOSION, at, 1);
                    for (LivingEntity e : k.enemiesAround(p, at, 2.2)) { e.setNoDamageTicks(0); k.hit(p, e, k.scale(p, 5)); }
                    w.playSound(at, Sound.ENTITY_GENERIC_EXPLODE, 0.5f, 1.6f);
                }
            }.runTaskTimer(plugin, 0, 4);
            case QI_BLAST -> {
                w.playSound(loc, Sound.BLOCK_BEACON_ACTIVATE, 1f, 2f);
                k.later(10, () -> {
                    k.beam(p, Particle.END_ROD, 20, 1.6, k.scale(p, 20), true, dust(255, 230, 120, 2.0f));
                    w.playSound(p.getLocation(), Sound.ENTITY_WARDEN_SONIC_BOOM, 1f, 1.2f);
                });
            }

            // ================================================== 달의 사제
            case MOON_CURSE -> {
                LivingEntity t = k.lookTarget(p, 16);
                if (t == null) { p.sendActionBar("§c저주할 대상이 없어요."); return false; }
                t.addPotionEffect(new PotionEffect(PotionEffectType.WEAKNESS, 200, 1));
                t.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 200, 1));
                t.addPotionEffect(new PotionEffect(PotionEffectType.GLOWING, 200, 0));
                k.hit(p, t, k.scale(p, 4));
                w.spawnParticle(Particle.DUST, t.getLocation().add(0, 2.2, 0), 30, 0.4, 0.2, 0.4, 0, dust(120, 140, 255, 1.4f));
                w.playSound(loc, Sound.ENTITY_ILLUSIONER_CAST_SPELL, 1f, 1.2f);
            }
            case MOON_WEIGHT -> {
                Location c = k.lookBlock(p, 14);
                for (LivingEntity e : k.enemiesAround(p, c, 4.5)) {
                    k.hit(p, e, k.scale(p, 8));
                    e.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 100, 4));
                    e.setVelocity(new Vector(0, -1, 0));
                }
                k.ring(c, Particle.REVERSE_PORTAL, 4, 40);
                w.spawnParticle(Particle.DUST, c.clone().add(0, 3, 0), 60, 1.5, 0.3, 1.5, 0, dust(200, 210, 255, 2.0f));
                w.playSound(c, Sound.BLOCK_ANVIL_LAND, 0.8f, 0.5f);
            }
            case MOONLIGHT -> {
                for (Player a : k.alliesAround(p, 8)) {
                    k.heal(a, 8);
                    a.addPotionEffect(new PotionEffect(PotionEffectType.NIGHT_VISION, 600, 0));
                }
                w.spawnParticle(Particle.END_ROD, loc.clone().add(0, 2.5, 0), 40, 2, 0.5, 2, 0.02);
                w.playSound(loc, Sound.BLOCK_AMETHYST_BLOCK_CHIME, 1f, 0.8f);
            }
            case ECLIPSE -> {
                for (LivingEntity e : k.enemiesAround(p, loc, 9)) {
                    e.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS, 160, 0));
                    e.addPotionEffect(new PotionEffect(PotionEffectType.WITHER, 160, 1));
                    e.addPotionEffect(new PotionEffect(PotionEffectType.WEAKNESS, 160, 2));
                    k.hit(p, e, k.scale(p, 10));
                }
                buffAllies(p, 9, PotionEffectType.STRENGTH, 200, 1);
                k.ring(loc.clone().add(0, 0.2, 0), Particle.SQUID_INK, 9, 60);
                w.spawnParticle(Particle.DUST, loc.clone().add(0, 4, 0), 80, 2, 0.5, 2, 0, dust(20, 20, 40, 2.5f));
                w.playSound(loc, Sound.ENTITY_WITHER_SPAWN, 0.6f, 1.6f);
            }
            case LETHARGY -> {
                for (LivingEntity e : k.enemiesAround(p, loc, 8)) {
                    e.addPotionEffect(new PotionEffect(PotionEffectType.MINING_FATIGUE, 160, 2));
                    e.addPotionEffect(new PotionEffect(PotionEffectType.WEAKNESS, 160, 2));
                    e.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 160, 2));
                    e.addPotionEffect(new PotionEffect(PotionEffectType.NAUSEA, 160, 0));
                    k.hit(p, e, k.scale(p, 8));
                    w.spawnParticle(Particle.FALLING_WATER, e.getLocation().add(0, 2.2, 0), 15, 0.3, 0.1, 0.3, 0);
                }
                w.playSound(loc, Sound.ENTITY_GHAST_SCREAM, 0.6f, 0.6f);
                p.sendActionBar("§5무기무기 무기력증... §7현타·우울·불안이 퍼진다");
            }

            // ================================================== 건슬링거
            case QUICK_SHOT -> {
                k.beam(p, Particle.CRIT, 24, 0.5, k.scale(p, 6), false, null);
                w.playSound(loc, Sound.ENTITY_FIREWORK_ROCKET_BLAST, 1f, 1.8f);
            }
            case SCATTER_SHOT -> {
                Location from = p.getEyeLocation().subtract(0, 0.2, 0);
                for (int i = -2; i <= 2; i++) {
                    Vector d = from.getDirection().rotateAroundY(Math.toRadians(i * 9)).normalize();
                    for (double t = 0.5; t <= 9; t += 0.5) {
                        Location at = from.clone().add(d.clone().multiply(t));
                        if (at.getBlock().getType().isSolid()) break;
                        w.spawnParticle(Particle.SMOKE, at, 1, 0, 0, 0, 0);
                        List<LivingEntity> hits = k.enemiesAround(p, at, 0.8);
                        if (!hits.isEmpty()) { hits.get(0).setNoDamageTicks(0); k.hit(p, hits.get(0), k.scale(p, 4)); break; }
                    }
                }
                p.setVelocity(from.getDirection().multiply(-0.4).setY(0.1));
                w.playSound(loc, Sound.ENTITY_GENERIC_EXPLODE, 0.6f, 1.8f);
            }
            case ROLL -> {
                Vector side = dir.clone().crossProduct(new Vector(0, 1, 0)).normalize();
                if (p.isSneaking()) side.multiply(-1);
                p.setVelocity(side.multiply(1.2).setY(0.25));
                p.addPotionEffect(new PotionEffect(PotionEffectType.SPEED, 40, 2));
                w.spawnParticle(Particle.CLOUD, loc, 10, 0.4, 0.1, 0.4, 0.02);
                w.playSound(loc, Sound.ENTITY_BREEZE_SLIDE, 1f, 1.4f);
            }
            case DEAD_EYE -> {
                List<LivingEntity> targets = k.enemiesAround(p, loc, 14);
                targets.sort(Comparator.comparingDouble(e -> e.getLocation().distanceSquared(loc)));
                if (targets.isEmpty()) { p.sendActionBar("§c조준할 적이 없어요."); return false; }
                List<LivingEntity> six = targets.subList(0, Math.min(6, targets.size()));
                for (LivingEntity e : six) e.addPotionEffect(new PotionEffect(PotionEffectType.GLOWING, 30, 0));
                p.sendActionBar("§c§l데드아이 §7- 조준 완료: " + six.size() + "명");
                for (int i = 0; i < six.size(); i++) {
                    LivingEntity e = six.get(i);
                    k.later(15 + i * 3L, () -> {
                        if (e.isDead() || !p.isOnline()) return;
                        Location from = p.getEyeLocation();
                        Vector d = e.getLocation().add(0, 1, 0).toVector().subtract(from.toVector());
                        double len = d.length();
                        d.normalize();
                        for (double t = 0.5; t < len; t += 0.5) w.spawnParticle(Particle.CRIT, from.clone().add(d.clone().multiply(t)), 1, 0, 0, 0, 0);
                        e.setNoDamageTicks(0);
                        k.hit(p, e, k.scale(p, 14));
                        w.playSound(from, Sound.ENTITY_FIREWORK_ROCKET_BLAST, 1f, 1.5f);
                    });
                }
            }
            case CANNON -> {
                Location c = k.lookBlock(p, 30);
                w.playSound(loc, Sound.ENTITY_GENERIC_EXPLODE, 0.8f, 0.6f);
                for (int i = 0; i < 12; i++) {
                    final int ii = i;
                    k.later(i, () -> w.spawnParticle(Particle.SMOKE, c.clone().add(0, 12 - ii, 0), 6, 0.2, 0.2, 0.2, 0.01));
                }
                k.later(14, () -> {
                    w.spawnParticle(Particle.EXPLOSION_EMITTER, c, 1);
                    w.playSound(c, Sound.ENTITY_GENERIC_EXPLODE, 2f, 0.7f);
                    for (LivingEntity e : k.enemiesAround(p, c, 5)) {
                        k.hit(p, e, k.scale(p, 24));
                        e.setVelocity(e.getLocation().toVector().subtract(c.toVector()).normalize().multiply(0.8).setY(0.6));
                    }
                });
            }

            // ================================================== 창술사
            case SPEAR_THRUST -> {
                k.beam(p, Particle.SWEEP_ATTACK, 6, 1.0, k.scale(p, 9), true, dust(230, 230, 230, 1.0f));
                p.setVelocity(dir.clone().multiply(0.4));
                w.playSound(loc, Sound.ITEM_TRIDENT_THROW, 1f, 1.2f);
            }
            case SPEAR_SWEEP -> {
                for (LivingEntity e : cone(p, 5, 0.0)) {
                    k.hit(p, e, k.scale(p, 8));
                    e.setVelocity(e.getLocation().toVector().subtract(loc.toVector()).setY(0).normalize().multiply(0.9).setY(0.3));
                }
                for (int i = -6; i <= 6; i++) {
                    Vector d = dir.clone().rotateAroundY(Math.toRadians(i * 15));
                    w.spawnParticle(Particle.SWEEP_ATTACK, loc.clone().add(d.multiply(3)).add(0, 1, 0), 1, 0, 0, 0, 0);
                }
                w.playSound(loc, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1f, 0.6f);
            }
            case CHARGE -> {
                dash(p, 2.0, k.scale(p, 9), Particle.CLOUD, null);
                k.later(6, () -> { for (LivingEntity e : k.enemiesAround(p, p.getLocation(), 2.5)) e.setVelocity(new Vector(0, 0.9, 0)); });
                w.playSound(loc, Sound.ENTITY_RAVAGER_ROAR, 0.8f, 1.3f);
            }
            case GOD_OF_WAR -> {
                godOfWarUntil.put(p.getUniqueId(), System.currentTimeMillis() + 10000);
                p.addPotionEffect(new PotionEffect(PotionEffectType.STRENGTH, 200, 1));
                p.addPotionEffect(new PotionEffect(PotionEffectType.SPEED, 200, 1));
                p.sendTitle("§4§l천하무쌍", "§710초 동안 모든 공격이 주변을 휩쓴다", 5, 40, 10);
                w.spawnParticle(Particle.FLAME, loc.clone().add(0, 1, 0), 60, 0.6, 1, 0.6, 0.05);
                w.playSound(loc, Sound.ENTITY_ENDER_DRAGON_GROWL, 0.8f, 1.4f);
            }
            case SPEAR_RAIN -> {
                Location c = k.lookBlock(p, 24);
                for (int i = 0; i < 14; i++) {
                    k.later(i * 2L, () -> {
                        Location at = c.clone().add((Math.random() - 0.5) * 8, 0, (Math.random() - 0.5) * 8);
                        for (double y = 8; y >= 0; y -= 0.5) w.spawnParticle(Particle.END_ROD, at.clone().add(0, y, 0), 1, 0, 0, 0, 0);
                        w.spawnParticle(Particle.FLASH, at, 1);
                        for (LivingEntity e : k.enemiesAround(p, at, 2)) { e.setNoDamageTicks(0); k.hit(p, e, k.scale(p, 7)); }
                        w.playSound(at, Sound.ITEM_TRIDENT_HIT_GROUND, 1f, 1.2f);
                    });
                }
            }

            // ================================================== 음유시인
            case SONG_COURAGE -> {
                buffAllies(p, 10, PotionEffectType.STRENGTH, 200, 0);
                w.spawnParticle(Particle.NOTE, loc.clone().add(0, 2.2, 0), 20, 2, 0.5, 2, 1);
                w.playSound(loc, Sound.BLOCK_NOTE_BLOCK_BELL, 1f, 1.0f);
            }
            case SONG_SWIFT -> {
                buffAllies(p, 10, PotionEffectType.SPEED, 200, 1);
                buffAllies(p, 10, PotionEffectType.HASTE, 200, 1);
                w.spawnParticle(Particle.NOTE, loc.clone().add(0, 2.2, 0), 20, 2, 0.5, 2, 1);
                w.playSound(loc, Sound.BLOCK_NOTE_BLOCK_FLUTE, 1f, 1.4f);
            }
            case DISSONANCE -> {
                for (LivingEntity e : k.enemiesAround(p, loc, 6)) {
                    k.hit(p, e, k.scale(p, 7));
                    e.addPotionEffect(new PotionEffect(PotionEffectType.NAUSEA, 120, 0));
                    e.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 60, 0));
                }
                k.ring(loc.clone().add(0, 1, 0), Particle.NOTE, 4, 24);
                w.playSound(loc, Sound.BLOCK_NOTE_BLOCK_DIDGERIDOO, 1.5f, 0.5f);
                w.playSound(loc, Sound.BLOCK_NOTE_BLOCK_BASS, 1.5f, 0.6f);
            }
            case SYMPHONY -> {
                for (Player a : k.alliesAround(p, 12)) {
                    k.heal(a, 16);
                    a.addPotionEffect(new PotionEffect(PotionEffectType.REGENERATION, 300, 1));
                    a.addPotionEffect(new PotionEffect(PotionEffectType.RESISTANCE, 300, 0));
                    a.addPotionEffect(new PotionEffect(PotionEffectType.STRENGTH, 300, 0));
                }
                w.spawnParticle(Particle.NOTE, loc.clone().add(0, 2.5, 0), 60, 4, 1, 4, 1);
                for (float pitch : new float[]{0.8f, 1.0f, 1.2f, 1.6f}) w.playSound(loc, Sound.BLOCK_NOTE_BLOCK_HARP, 1f, pitch);
            }
            case SWORD_DANCE -> {
                buffAllies(p, 8, PotionEffectType.SPEED, 160, 1);
                new BukkitRunnable() {
                    int n = 0;
                    public void run() {
                        if (!p.isOnline() || n++ >= 4) { cancel(); return; }
                        Location l = p.getLocation();
                        l.setYaw(l.getYaw() + 90);
                        p.teleport(l);
                        for (LivingEntity e : k.enemiesAround(p, l, 3.5)) { e.setNoDamageTicks(0); k.hit(p, e, k.scale(p, 6)); }
                        k.ring(l.clone().add(0, 1, 0), Particle.CHERRY_LEAVES, 2.5, 16);
                        w.spawnParticle(Particle.SWEEP_ATTACK, l.clone().add(0, 1, 0), 4, 1.2, 0.2, 1.2, 0);
                        w.playSound(l, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1f, 1.2f + n * 0.15f);
                    }
                }.runTaskTimer(plugin, 0, 5);
            }

            // ================================================== 마검사
            case INFERNO_OVERLAY -> {
                k.beam(p, Particle.FLAME, 16, 1.0, k.scale(p, 11), true, null);
                Location from = p.getEyeLocation();
                for (double t = 1; t <= 16; t += 1.5) w.spawnParticle(Particle.FLAME, from.clone().add(from.getDirection().multiply(t)), 6, 0.3, 0.3, 0.3, 0.02);
                for (LivingEntity e : cone(p, 16, 0.95)) e.setFireTicks(100);
                w.playSound(loc, Sound.ENTITY_BLAZE_SHOOT, 1f, 0.7f);
            }
            case OVERVOLT_DRIVE -> {
                dash(p, 2.2, k.scale(p, 12), Particle.ELECTRIC_SPARK, null);
                w.playSound(loc, Sound.ENTITY_LIGHTNING_BOLT_THUNDER, 0.6f, 1.8f);
            }
            case GLACIAL_DOMINION -> {
                for (LivingEntity e : k.enemiesAround(p, loc, 7)) {
                    k.hit(p, e, k.scale(p, 9));
                    e.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 60, 9));
                    e.setFreezeTicks(140);
                    w.spawnParticle(Particle.SNOWFLAKE, e.getLocation().add(0, 1, 0), 30, 0.4, 0.6, 0.4, 0.02);
                }
                k.ring(loc.clone().add(0, 0.2, 0), Particle.SNOWFLAKE, 7, 50);
                w.playSound(loc, Sound.BLOCK_GLASS_BREAK, 1f, 0.6f);
                w.playSound(loc, Sound.ENTITY_PLAYER_HURT_FREEZE, 1f, 0.8f);
            }
            case TEMPEST_CALL -> {
                w.spawnParticle(Particle.LARGE_SMOKE, loc.clone().add(0, 8, 0), 120, 5, 0.5, 5, 0.01);
                List<LivingEntity> ts = k.enemiesAround(p, loc, 12);
                if (ts.isEmpty()) { p.sendActionBar("§7먹구름이 몰려왔지만 칠 대상이 없어요."); }
                for (int i = 0; i < ts.size() && i < 10; i++) {
                    LivingEntity e = ts.get(i);
                    k.later(10 + i * 4L, () -> {
                        if (e.isDead()) return;
                        w.strikeLightningEffect(e.getLocation());
                        e.setNoDamageTicks(0);
                        k.hit(p, e, k.scale(p, 18));
                    });
                }
            }

            // ================================================== 뱀파이어
            case BITE -> {
                LivingEntity t = k.lookTarget(p, 3.5);
                if (t == null) { p.sendActionBar("§c깨물 대상이 없어요."); return false; }
                double dmg = k.scale(p, 8);
                k.hit(p, t, dmg);
                lifesteal(p, dmg * 0.6);
                w.playSound(loc, Sound.ENTITY_FOX_BITE, 1f, 0.6f);
            }
            case BLOOD_RAIN -> {
                double total = 0;
                for (LivingEntity e : k.enemiesAround(p, loc, 7)) {
                    double dmg = k.scale(p, 8);
                    k.hit(p, e, dmg);
                    total += dmg;
                }
                lifesteal(p, Math.min(20, total * 0.3));
                w.spawnParticle(Particle.DUST, loc.clone().add(0, 5, 0), 150, 4, 0.3, 4, 0, dust(150, 0, 0, 1.5f));
                w.spawnParticle(Particle.DRIPPING_LAVA, loc.clone().add(0, 4, 0), 60, 4, 0.2, 4, 0);
                w.playSound(loc, Sound.WEATHER_RAIN, 1.5f, 0.6f);
            }
            case BAT_FORM -> {
                p.addPotionEffect(new PotionEffect(PotionEffectType.INVISIBILITY, 100, 0));
                p.addPotionEffect(new PotionEffect(PotionEffectType.SPEED, 100, 2));
                p.addPotionEffect(new PotionEffect(PotionEffectType.SLOW_FALLING, 100, 0));
                p.setVelocity(new Vector(0, 0.8, 0));
                plugin.noFall(p, 120);
                for (int i = 0; i < 6; i++) {
                    Bat b = w.spawn(loc.clone().add(0, 1, 0), Bat.class, bt -> { bt.setInvulnerable(true); bt.setSilent(true); });
                    k.later(60, b::remove);
                }
                w.playSound(loc, Sound.ENTITY_BAT_TAKEOFF, 1f, 1f);
            }
            case BLOOD_MOON -> {
                bloodMoonUntil.put(p.getUniqueId(), System.currentTimeMillis() + 10000);
                p.addPotionEffect(new PotionEffect(PotionEffectType.STRENGTH, 200, 1));
                p.sendTitle("§4§l핏빛 달", "§7모든 공격이 피를 빨아들인다", 5, 40, 10);
                w.spawnParticle(Particle.DUST, loc.clone().add(0, 2, 0), 80, 1, 1, 1, 0, dust(200, 0, 0, 2f));
                w.playSound(loc, Sound.ENTITY_WITHER_AMBIENT, 1f, 0.6f);
            }

            // ================================================== 천사
            case JUDGMENT_SPEAR -> {
                k.beam(p, Particle.END_ROD, 22, 1.0, k.scale(p, 14), true, dust(255, 245, 190, 1.6f));
                w.playSound(loc, Sound.BLOCK_BEACON_DEACTIVATE, 1f, 2f);
                w.playSound(loc, Sound.ITEM_TRIDENT_THROW, 1f, 0.8f);
            }
            case DIVINE_WING -> {
                p.setVelocity(loc.getDirection().multiply(0.6).setY(1.3));
                p.addPotionEffect(new PotionEffect(PotionEffectType.SLOW_FALLING, 120, 0));
                plugin.noFall(p, 160);
                w.spawnParticle(Particle.END_ROD, loc.clone().add(0, 1, 0), 40, 0.8, 0.4, 0.8, 0.05);
                w.spawnParticle(Particle.CLOUD, loc, 20, 0.6, 0.1, 0.6, 0.05);
                w.playSound(loc, Sound.ITEM_ELYTRA_FLYING, 0.6f, 1.6f);
            }
            case GRACE -> {
                for (Player a : k.alliesAround(p, 12)) {
                    k.heal(a, 999);
                    for (PotionEffect pe : a.getActivePotionEffects()) {
                        PotionEffectType t = pe.getType();
                        if (t == PotionEffectType.POISON || t == PotionEffectType.WITHER || t == PotionEffectType.SLOWNESS
                                || t == PotionEffectType.WEAKNESS || t == PotionEffectType.BLINDNESS || t == PotionEffectType.NAUSEA
                                || t == PotionEffectType.MINING_FATIGUE || t == PotionEffectType.HUNGER) a.removePotionEffect(t);
                    }
                    a.setFireTicks(0);
                    a.addPotionEffect(new PotionEffect(PotionEffectType.ABSORPTION, 400, 3));
                }
                w.spawnParticle(Particle.END_ROD, loc.clone().add(0, 3, 0), 150, 5, 2, 5, 0.03);
                w.playSound(loc, Sound.UI_TOAST_CHALLENGE_COMPLETE, 1f, 1.4f);
            }

            // ================================================== 차원의 저격수
            case PRECISION_SHOT -> {
                k.beam(p, Particle.CRIT, 40, 0.5, k.scale(p, 18), false, dust(120, 255, 255, 0.9f));
                w.playSound(loc, Sound.ENTITY_FIREWORK_ROCKET_LARGE_BLAST, 1f, 1.6f);
            }
            case COVER -> {
                coverUntil.put(p.getUniqueId(), System.currentTimeMillis() + 3000);
                p.addPotionEffect(new PotionEffect(PotionEffectType.INVISIBILITY, 60, 0));
                p.addPotionEffect(new PotionEffect(PotionEffectType.RESISTANCE, 60, 2));
                w.spawnParticle(Particle.SMOKE, loc.clone().add(0, 1, 0), 30, 0.5, 0.6, 0.5, 0.02);
                w.playSound(loc, Sound.BLOCK_WOOL_PLACE, 1f, 0.6f);
            }
            case DIMENSION_SHOT -> {
                w.spawnParticle(Particle.PORTAL, p.getEyeLocation(), 80, 0.3, 0.3, 0.3, 1);
                w.playSound(loc, Sound.BLOCK_PORTAL_TRIGGER, 0.6f, 2f);
                k.later(16, () -> {
                    Location from = p.getEyeLocation();
                    Vector d = from.getDirection().normalize();
                    Set<LivingEntity> hitSet = new HashSet<>();
                    Location end = from.clone();
                    for (double t = 0.5; t <= 60; t += 0.5) {
                        end = from.clone().add(d.clone().multiply(t));
                        w.spawnParticle(Particle.DUST, end, 1, 0, 0, 0, 0, dust(150, 80, 255, 1.2f));
                        for (LivingEntity e : k.enemiesAround(p, end, 1.2)) if (hitSet.add(e)) k.hit(p, e, k.scale(p, 30));
                        if (end.getBlock().getType().isSolid()) break;
                    }
                    w.spawnParticle(Particle.EXPLOSION_EMITTER, end, 1);
                    for (LivingEntity e : k.enemiesAround(p, end, 4)) if (hitSet.add(e)) k.hit(p, e, k.scale(p, 15));
                    w.playSound(from, Sound.ENTITY_WARDEN_SONIC_BOOM, 1f, 0.8f);
                    w.playSound(end, Sound.ENTITY_GENERIC_EXPLODE, 1.5f, 0.8f);
                });
            }
            default -> { return false; }
        }
        return true;
    }
}
