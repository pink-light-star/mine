package kr.starserver.starrpg;

import org.bukkit.*;
import org.bukkit.entity.*;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.util.Vector;

import java.util.*;

/**
 * 스킬 트리의 데이터 스킬(kind) 실행기.
 * nova 주변 폭발 · cone 앞 부채꼴 · beam 일직선 · dash 돌진 · leap 도약 강타 · rain 낙하 연타
 * pull 끌어당겨 폭발 · orb 날아가는 구체 · mark 지속 피해 · buff 강화 · heal 회복
 * 추가 효과(마지막 값): "효과:세기:초" (힘·저항·재생·신속·흡수는 나에게, 나머지는 적에게) · fire · heal · cleanse · regen_self
 */
final class SpecCaster {
    private final StarRPG plugin;
    private final Skills k;

    SpecCaster(StarRPG plugin, Skills k) {
        this.plugin = plugin;
        this.k = k;
    }

    private static final Set<String> GOOD = Set.of("strength", "resistance", "regeneration", "speed", "absorption",
            "haste", "jump_boost", "night_vision", "invisibility", "fire_resistance");

    static PotionEffectType effect(String name) {
        return Registry.EFFECT.get(NamespacedKey.minecraft(name.toLowerCase(Locale.ROOT)));
    }

    private Particle particle(String n, Particle def) {
        try { return n == null ? def : Particle.valueOf(n); } catch (IllegalArgumentException e) { return def; }
    }

    private double num(List<String> v, int i, double def) {
        try { return i < v.size() ? Double.parseDouble(v.get(i)) : def; } catch (NumberFormatException e) { return def; }
    }

    private String extra(List<String> v, int from) {
        for (int i = from; i < v.size(); i++) {
            try { Double.parseDouble(v.get(i)); } catch (NumberFormatException e) { return v.get(i); }
        }
        return null;
    }

    /** 추가 효과를 맞은 적(또는 나)에게 */
    private void applyExtra(Player p, LivingEntity t, String ex) {
        if (ex == null) return;
        if (ex.equals("fire")) { t.setFireTicks(80); return; }
        if (ex.equals("heal") || ex.equals("cleanse") || ex.equals("regen_self")) return;
        String[] a = ex.split(":");
        PotionEffectType ty = effect(a[0]);
        if (ty == null || GOOD.contains(a[0])) return;
        int amp = a.length > 1 ? Integer.parseInt(a[1]) : 0, sec = a.length > 2 ? Integer.parseInt(a[2]) : 4;
        t.addPotionEffect(new PotionEffect(ty, sec * 20, amp));
    }

    /** 나에게 거는 좋은 추가 효과 */
    private void selfExtra(Player p, String ex, double dmg) {
        if (ex == null) return;
        if (ex.equals("regen_self")) { p.addPotionEffect(new PotionEffect(PotionEffectType.REGENERATION, 160, 1)); return; }
        if (ex.equals("heal")) { for (Player a : k.alliesAround(p, 8)) k.heal(a, Math.max(4, dmg * 0.3)); return; }
        String[] a = ex.split(":");
        if (!GOOD.contains(a[0])) return;
        PotionEffectType ty = effect(a[0]);
        if (ty == null) return;
        int amp = a.length > 1 ? Integer.parseInt(a[1]) : 0, sec = a.length > 2 ? Integer.parseInt(a[2]) : 6;
        p.addPotionEffect(new PotionEffect(ty, sec * 20, amp));
    }

    private void buffs(Player p, String list, int sec, double radius) {
        List<Player> who = radius > 0 ? k.alliesAround(p, radius) : List.of(p);
        for (String one : list.split(",")) {
            String[] a = one.trim().split(":");
            PotionEffectType ty = effect(a[0]);
            if (ty == null) continue;
            int amp = a.length > 1 ? Integer.parseInt(a[1]) : 0;
            for (Player t : who) t.addPotionEffect(new PotionEffect(ty, sec * 20, amp));
        }
    }

    /** @return true면 사용 성공 */
    boolean cast(Player p, SkillTree.TS t) {
        World w = p.getWorld();
        Location loc = p.getLocation();
        Vector dir = loc.getDirection().setY(0).normalize();
        List<String> v = t.val();
        Particle p1 = particle(t.p1(), Particle.CRIT), p2 = particle(t.p2(), Particle.END_ROD);
        String snd = t.snd() == null ? "entity.player.attack.strong" : t.snd();
        w.playSound(loc, snd, 1f, 1f);
        String ex = extra(v, 2);
        switch (t.kind()) {
            case "nova" -> {
                double r = num(v, 0, 4), d = k.scale(p, num(v, 1, 10));
                for (LivingEntity e : k.enemiesAround(p, loc, r)) {
                    k.hit(p, e, d);
                    e.setVelocity(e.getLocation().toVector().subtract(loc.toVector()).setY(0).normalize().multiply(0.6).setY(0.35));
                    applyExtra(p, e, ex);
                }
                for (double rr = 1; rr <= r; rr += 1) k.ring(loc.clone().add(0, 0.3, 0), p1, rr, (int) (rr * 10));
                w.spawnParticle(p2, loc.clone().add(0, 1, 0), 30, r / 3, 0.6, r / 3, 0.05);
                selfExtra(p, ex, d);
            }
            case "cone" -> {
                double len = num(v, 0, 5), d = k.scale(p, num(v, 1, 10));
                Vector look = loc.getDirection().normalize();
                for (LivingEntity e : k.enemiesAround(p, loc, len)) {
                    Vector to = e.getLocation().toVector().subtract(loc.toVector());
                    if (to.lengthSquared() < 0.01 || to.clone().normalize().dot(look) > 0.45) { k.hit(p, e, d); applyExtra(p, e, ex); }
                }
                for (double dd = 1; dd <= len; dd += 0.7) {
                    Location c = loc.clone().add(0, 1, 0).add(dir.clone().multiply(dd));
                    w.spawnParticle(p1, c, 3, dd * 0.25, 0.2, dd * 0.25, 0);
                }
                selfExtra(p, ex, d);
            }
            case "beam" -> {
                double len = num(v, 0, 20), d = k.scale(p, num(v, 1, 12));
                k.beam(p, p1, len, 1.0, d, true, null);
                for (LivingEntity e : k.enemiesAround(p, loc, len)) {
                    Vector to = e.getLocation().toVector().subtract(loc.toVector());
                    if (to.clone().normalize().dot(loc.getDirection()) > 0.97) applyExtra(p, e, ex);
                }
                selfExtra(p, ex, d);
            }
            case "dash" -> {
                double len = num(v, 0, 8), d = k.scale(p, num(v, 1, 10));
                p.setVelocity(dir.clone().multiply(Math.min(3.0, len / 3.2)).setY(0.15));
                Set<LivingEntity> hit = new HashSet<>();
                for (int i = 1; i <= 8; i++) {
                    k.later(i, () -> {
                        w.spawnParticle(p1, p.getLocation().add(0, 1, 0), 6, 0.3, 0.4, 0.3, 0.02);
                        if (d <= 0) return;
                        for (LivingEntity e : k.enemiesAround(p, p.getLocation(), 2.2)) {
                            if (hit.add(e)) { k.hit(p, e, d); applyExtra(p, e, ex); }
                        }
                    });
                }
                selfExtra(p, ex, d);
            }
            case "leap" -> {
                double r = num(v, 0, 5), d = k.scale(p, num(v, 1, 14));
                p.setVelocity(dir.clone().multiply(0.6).setY(1.1));
                k.later(18, () -> {
                    p.setVelocity(new Vector(0, -1.6, 0));
                    k.later(6, () -> {
                        Location at = p.getLocation();
                        for (LivingEntity e : k.enemiesAround(p, at, r)) {
                            k.hit(p, e, d);
                            e.setVelocity(new Vector(0, 0.7, 0));
                            applyExtra(p, e, ex);
                        }
                        w.spawnParticle(Particle.EXPLOSION, at, 3, r / 3, 0.2, r / 3, 0);
                        for (double rr = 1; rr <= r; rr += 1) k.ring(at.clone().add(0, 0.2, 0), p1, rr, (int) (rr * 10));
                        w.playSound(at, "entity.generic.explode", 0.9f, 1.2f);
                    });
                });
                plugin.noFall(p, 80);
                selfExtra(p, ex, d);
            }
            case "rain" -> {
                double r = num(v, 0, 5);
                int n = (int) num(v, 1, 8);
                double d = k.scale(p, num(v, 2, 8));
                Location c = k.lookBlock(p, 24);
                Random rnd = new Random();
                for (int i = 0; i < n; i++) {
                    k.later(i * 3L, () -> {
                        Location at = c.clone().add((rnd.nextDouble() * 2 - 1) * r, 0, (rnd.nextDouble() * 2 - 1) * r);
                        for (double y = 6; y >= 0; y -= 0.8) w.spawnParticle(p1, at.clone().add(0, y, 0), 1, 0, 0, 0, 0);
                        w.spawnParticle(p2, at, 8, 0.6, 0.2, 0.6, 0.05);
                        for (LivingEntity e : k.enemiesAround(p, at, 2.0)) { k.hit(p, e, d); applyExtra(p, e, ex); }
                    });
                }
                w.playSound(c, snd, 1f, 0.8f);
            }
            case "pull" -> {
                double r = num(v, 0, 6), d = k.scale(p, num(v, 1, 14));
                Location c = k.lookBlock(p, 18);
                for (int i = 0; i < 20; i += 2) {
                    k.later(i, () -> {
                        for (LivingEntity e : k.enemiesAround(p, c, r)) {
                            e.setVelocity(c.toVector().subtract(e.getLocation().toVector()).normalize().multiply(0.45));
                        }
                        k.ring(c.clone().add(0, 0.5, 0), p1, r * 0.6, 20);
                    });
                }
                k.later(22, () -> {
                    for (LivingEntity e : k.enemiesAround(p, c, r)) { k.hit(p, e, d); applyExtra(p, e, ex); }
                    w.spawnParticle(Particle.EXPLOSION, c, 2, 0.5, 0.5, 0.5, 0);
                    w.spawnParticle(p2, c, 40, r / 2, 0.8, r / 2, 0.1);
                    w.playSound(c, "entity.generic.explode", 1f, 0.9f);
                });
            }
            case "orb" -> {
                double r = num(v, 0, 3), d = k.scale(p, num(v, 1, 14));
                Location start = p.getEyeLocation();
                Vector step = start.getDirection().normalize().multiply(0.9);
                new org.bukkit.scheduler.BukkitRunnable() {
                    final Location at = start.clone();
                    int n = 0;
                    @Override public void run() {
                        at.add(step);
                        w.spawnParticle(p1, at, 4, 0.12, 0.12, 0.12, 0);
                        boolean boom = ++n > 30 || at.getBlock().getType().isSolid() || !k.enemiesAround(p, at, 1.3).isEmpty();
                        if (!boom) return;
                        cancel();
                        for (LivingEntity e : k.enemiesAround(p, at, r)) { k.hit(p, e, d); applyExtra(p, e, ex); }
                        w.spawnParticle(Particle.EXPLOSION, at, 1, 0, 0, 0, 0);
                        w.spawnParticle(p2, at, 30, r / 2, r / 2, r / 2, 0.08);
                        w.playSound(at, "entity.generic.explode", 0.8f, 1.3f);
                    }
                }.runTaskTimer(plugin, 1L, 1L);
            }
            case "mark" -> {
                double d = k.scale(p, num(v, 0, 6));
                int sec = (int) num(v, 1, 6);
                LivingEntity target = k.lookTarget(p, 24);
                if (target == null) { p.sendActionBar("§7바라보는 적이 없어요."); return false; }
                for (int i = 1; i <= sec; i++) {
                    k.later(i * 20L, () -> {
                        if (target.isDead()) return;
                        k.hit(p, target, d);
                        w.spawnParticle(p1, target.getLocation().add(0, 1.2, 0), 10, 0.3, 0.4, 0.3, 0.02);
                    });
                }
                target.addPotionEffect(new PotionEffect(PotionEffectType.GLOWING, sec * 20, 0));
            }
            case "buff" -> {
                String list = v.isEmpty() ? "strength:0" : v.get(0);
                int sec = (int) num(v, 1, 10);
                double radius = num(v, 2, 0);
                buffs(p, list, sec, radius);
                w.spawnParticle(p2, loc.clone().add(0, 1, 0), 30, Math.max(0.5, radius / 3), 0.8, Math.max(0.5, radius / 3), 0.05);
                k.ring(loc.clone().add(0, 0.2, 0), p1, Math.max(1.2, radius), 30);
            }
            case "heal" -> {
                double amount = num(v, 0, 12);
                double radius = num(v, 1, 0);
                boolean cleanse = "cleanse".equals(ex);
                List<Player> who = radius > 0 ? k.alliesAround(p, radius) : List.of(p);
                for (Player a : who) {
                    k.heal(a, amount * (1 + plugin.rpg().level(p) * 0.01));
                    if (cleanse) for (PotionEffect pe : a.getActivePotionEffects()) {
                        PotionEffectType ty = pe.getType();
                        if (ty == PotionEffectType.POISON || ty == PotionEffectType.WITHER || ty == PotionEffectType.SLOWNESS
                                || ty == PotionEffectType.WEAKNESS || ty == PotionEffectType.BLINDNESS || ty == PotionEffectType.NAUSEA
                                || ty == PotionEffectType.DARKNESS || ty == PotionEffectType.MINING_FATIGUE) a.removePotionEffect(ty);
                    }
                    w.spawnParticle(Particle.HEART, a.getLocation().add(0, 2, 0), 4, 0.4, 0.3, 0.4, 0);
                }
                w.spawnParticle(p2, loc.clone().add(0, 1, 0), 30, Math.max(0.5, radius / 3), 0.8, Math.max(0.5, radius / 3), 0.05);
                w.playSound(loc, "entity.player.levelup", 0.6f, 1.6f);
            }
            default -> { return false; }
        }
        return true;
    }
}
