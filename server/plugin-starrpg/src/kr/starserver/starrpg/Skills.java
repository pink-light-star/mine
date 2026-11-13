package kr.starserver.starrpg;

import org.bukkit.*;
import org.bukkit.attribute.Attribute;
import org.bukkit.block.Block;
import org.bukkit.entity.*;
import org.bukkit.inventory.ItemStack;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

import java.util.*;
import java.util.concurrent.ThreadLocalRandom;

/** 직업 스킬·무기 스킬의 실제 효과 */
@SuppressWarnings("deprecation")
final class Skills {
    private final StarRPG plugin;
    private final Pets pets;
    /** 독칼/분노 등 지속 효과 만료 시각 (ms) */
    final Map<UUID, Long> poisonUntil = new HashMap<>();
    final Map<UUID, Long> rageUntil = new HashMap<>();

    final ExtraSkills extra;

    Skills(StarRPG plugin, Pets pets) {
        this.plugin = plugin;
        this.pets = pets;
        this.extra = new ExtraSkills(plugin, this);
    }

    // ------------------------------------------------------------------ 도우미

    /** 플레이어 기준 공격해도 되는 대상 */
    boolean enemy(Player p, Entity e) {
        if (!(e instanceof LivingEntity) || e == p || e instanceof Player || e instanceof ArmorStand) return false;
        if (pets.isPet(e) || plugin.isMountEntity(e)) return false;
        if (e instanceof Tameable t && t.isTamed()) return false;
        return !(e instanceof Villager) && !(e instanceof WanderingTrader);
    }

    List<LivingEntity> enemiesAround(Player p, Location c, double r) {
        List<LivingEntity> out = new ArrayList<>();
        for (Entity e : c.getWorld().getNearbyEntities(c, r, r, r)) {
            if (enemy(p, e) && e.getLocation().distanceSquared(c) <= r * r) out.add((LivingEntity) e);
        }
        return out;
    }

    List<Player> alliesAround(Player p, double r) {
        List<Player> out = new ArrayList<>();
        for (Player o : p.getWorld().getPlayers()) {
            if (o.getLocation().distanceSquared(p.getLocation()) <= r * r) out.add(o);
        }
        return out;
    }

    /** 레벨에 비례해 강해지는 피해 */
    double scale(Player p, double base) {
        double cls = switch (plugin.rpg().rpgClass(p)) {
            case GUNSLINGER -> 1.1; case DEADEYE -> 1.2; case ARTILLERY -> 1.15; case DIMENSION_SNIPER -> 1.3;
            default -> 1.0;
        };
        return base * (1 + plugin.rpg().level(p) * 0.03) * cls * (1 + Rpg.statInt(p) * 0.02);   // 지능 1당 스킬 피해 +2%
    }

    /** 스킬 피해. Skript 능력치가 근접(힘)·원거리(민첩) 보너스를 붙이지 않도록 표시해 둔다 (지능은 scale()에서 반영) */
    void hit(Player p, LivingEntity t, double dmg) {
        p.setMetadata("skill_hit", new org.bukkit.metadata.FixedMetadataValue(plugin, true));
        try { t.damage(dmg, p); }
        finally { p.removeMetadata("skill_hit", plugin); }
    }

    void heal(LivingEntity e, double amount) {
        double max = e.getAttribute(Attribute.MAX_HEALTH).getValue();
        e.setHealth(Math.min(max, e.getHealth() + amount));
    }

    LivingEntity lookTarget(Player p, double range) {
        RayTraceResult r = p.getWorld().rayTraceEntities(p.getEyeLocation(), p.getLocation().getDirection(), range, 0.6,
                e -> enemy(p, e));
        return r != null && r.getHitEntity() instanceof LivingEntity le ? le : null;
    }

    Location lookBlock(Player p, double range) {
        Block b = p.getTargetBlockExact((int) range);
        return b != null ? b.getLocation().add(0.5, 1, 0.5) : p.getEyeLocation().add(p.getLocation().getDirection().multiply(range));
    }

    void ring(Location c, Particle pt, double r, int n) {
        for (int i = 0; i < n; i++) {
            double a = 2 * Math.PI * i / n;
            c.getWorld().spawnParticle(pt, c.clone().add(Math.cos(a) * r, 0.2, Math.sin(a) * r), 1, 0, 0, 0, 0);
        }
    }

    void beam(Player p, Particle pt, double len, double radius, double dmg, boolean pierce, Particle.DustOptions dust) {
        Location from = p.getEyeLocation().subtract(0, 0.2, 0);
        Vector dir = from.getDirection().normalize();
        Set<LivingEntity> hitSet = new HashSet<>();
        for (double d = 0.5; d <= len; d += 0.4) {
            Location at = from.clone().add(dir.clone().multiply(d));
            if (at.getBlock().getType().isSolid()) break;
            if (dust != null) at.getWorld().spawnParticle(Particle.DUST, at, 2, 0.05, 0.05, 0.05, 0, dust);
            else at.getWorld().spawnParticle(pt, at, 1, 0.02, 0.02, 0.02, 0);
            for (LivingEntity e : enemiesAround(p, at, radius)) {
                if (hitSet.add(e)) {
                    hit(p, e, dmg);
                    if (!pierce) return;
                }
            }
        }
    }

    // ------------------------------------------------------------------ 직업 스킬

    /** @return true면 사용 성공 (MP/쿨타임 소모) */
    boolean cast(Player p, Skill s) {
        World w = p.getWorld();
        Location loc = p.getLocation();
        Vector dir = loc.getDirection().setY(0).normalize();
        switch (s) {
            case TACKLE -> {
                p.setVelocity(dir.clone().multiply(1.3).setY(0.2));
                later(5, () -> enemiesAround(p, p.getLocation(), 2).forEach(e -> {
                    hit(p, e, scale(p, 4));
                    e.setVelocity(dir.clone().multiply(0.8).setY(0.3));
                }));
                w.playSound(loc, Sound.ENTITY_PLAYER_ATTACK_KNOCKBACK, 1f, 0.8f);
            }
            case WHIRLWIND -> {
                for (LivingEntity e : enemiesAround(p, loc, 3.5)) hit(p, e, scale(p, 7));
                for (int i = 0; i < 3; i++) ring(loc.clone().add(0, 0.6 + i * 0.3, 0), Particle.SWEEP_ATTACK, 2.5, 8);
                w.playSound(loc, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1f, 0.7f);
            }
            case LEAP_SLAM -> {
                p.setVelocity(dir.clone().multiply(0.6).setY(1.1));
                plugin.noFall(p, 60);
                new BukkitRunnable() {
                    int t = 0;
                    public void run() {
                        if (!p.isOnline() || t++ > 60) { cancel(); return; }
                        if (t > 5 && p.isOnGround()) {
                            cancel();
                            Location l = p.getLocation();
                            w.spawnParticle(Particle.EXPLOSION, l, 3, 1, 0.2, 1);
                            ring(l, Particle.CLOUD, 3, 24);
                            w.playSound(l, Sound.ENTITY_GENERIC_EXPLODE, 0.8f, 1.2f);
                            for (LivingEntity e : enemiesAround(p, l, 4)) {
                                hit(p, e, scale(p, 9));
                                e.setVelocity(new Vector(0, 0.9, 0));
                            }
                        }
                    }
                }.runTaskTimer(plugin, 2, 1);
            }
            case IRON_WALL -> {
                p.addPotionEffect(new PotionEffect(PotionEffectType.RESISTANCE, 100, 2));
                ring(loc.clone().add(0, 1, 0), Particle.ENCHANTED_HIT, 1, 20);
                w.playSound(loc, Sound.ITEM_ARMOR_EQUIP_NETHERITE, 1f, 0.8f);
            }
            case MULTI_SHOT -> {
                for (int i = -2; i <= 2; i++) {
                    Vector v = p.getLocation().getDirection().rotateAroundY(Math.toRadians(i * 8)).multiply(2.4);
                    Arrow a = p.launchProjectile(Arrow.class, v);
                    a.setDamage(scale(p, 3));
                    a.setPickupStatus(AbstractArrow.PickupStatus.DISALLOWED);
                }
                w.playSound(loc, Sound.ENTITY_ARROW_SHOOT, 1f, 1.2f);
            }
            case ARROW_RAIN -> {
                Location c = lookBlock(p, 24);
                new BukkitRunnable() {
                    int t = 0;
                    public void run() {
                        if (t++ >= 16) { cancel(); return; }
                        for (int i = 0; i < 4; i++) {
                            Location sky = c.clone().add(ThreadLocalRandom.current().nextDouble(-3, 3), 10, ThreadLocalRandom.current().nextDouble(-3, 3));
                            Arrow a = w.spawnArrow(sky, new Vector(0, -1, 0), 1.6f, 2f);
                            a.setShooter(p);
                            a.setDamage(scale(p, 2.5));
                            a.setPickupStatus(AbstractArrow.PickupStatus.DISALLOWED);
                        }
                    }
                }.runTaskTimer(plugin, 0, 3);
                w.playSound(c, Sound.ENTITY_ARROW_SHOOT, 1f, 0.6f);
            }
            case BACKSTEP -> {
                p.setVelocity(dir.clone().multiply(-1.3).setY(0.45));
                p.addPotionEffect(new PotionEffect(PotionEffectType.SPEED, 60, 1));
                w.spawnParticle(Particle.CLOUD, loc, 15, 0.3, 0.1, 0.3, 0.02);
            }
            case FIREBALL -> {
                SmallFireball f = p.launchProjectile(SmallFireball.class, p.getLocation().getDirection().multiply(1.5));
                f.setIsIncendiary(false);
                plugin.tagSkillProjectile(f, scale(p, 7), 2.5);
                w.playSound(loc, Sound.ENTITY_BLAZE_SHOOT, 1f, 1f);
            }
            case ICE_SPEAR -> {
                beam(p, Particle.SNOWFLAKE, 16, 1.0, scale(p, 8), true, null);
                Location from = p.getEyeLocation();
                for (LivingEntity e : enemiesAround(p, from.clone().add(from.getDirection().multiply(8)), 8)) {
                    e.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 80, 2));
                }
                w.playSound(loc, Sound.BLOCK_GLASS_BREAK, 1f, 1.5f);
            }
            case BLINK -> {
                RayTraceResult r = w.rayTraceBlocks(p.getEyeLocation(), p.getLocation().getDirection(), 8, FluidCollisionMode.NEVER, true);
                Location to = r != null ? r.getHitPosition().toLocation(w).subtract(p.getLocation().getDirection().multiply(0.8))
                        : p.getEyeLocation().add(p.getLocation().getDirection().multiply(8));
                to.setYaw(loc.getYaw());
                to.setPitch(loc.getPitch());
                to.subtract(0, 1.5, 0);
                if (to.getBlock().getType().isSolid()) to.add(0, 1, 0);
                w.spawnParticle(Particle.PORTAL, p.getLocation().add(0, 1, 0), 40, 0.3, 0.6, 0.3, 0.5);
                p.teleport(to);
                p.setFallDistance(0);
                w.spawnParticle(Particle.REVERSE_PORTAL, to.clone().add(0, 1, 0), 40, 0.3, 0.6, 0.3, 0.05);
                w.playSound(to, Sound.ENTITY_ENDERMAN_TELEPORT, 1f, 1.3f);
            }
            case AMBUSH -> {
                Vector v = p.getLocation().getDirection().normalize().multiply(1.6);
                p.setVelocity(v.setY(0.15));
                new BukkitRunnable() {
                    int t = 0;
                    final Set<UUID> done = new HashSet<>();
                    public void run() {
                        if (t++ > 8 || !p.isOnline()) { cancel(); return; }
                        w.spawnParticle(Particle.SMOKE, p.getLocation().add(0, 1, 0), 4, 0.2, 0.3, 0.2, 0);
                        for (LivingEntity e : enemiesAround(p, p.getLocation(), 1.8)) {
                            if (done.add(e.getUniqueId())) {
                                hit(p, e, scale(p, 7));
                                w.spawnParticle(Particle.SWEEP_ATTACK, e.getLocation().add(0, 1, 0), 1);
                            }
                        }
                    }
                }.runTaskTimer(plugin, 0, 1);
                w.playSound(loc, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1f, 1.6f);
            }
            case POISON_BLADE -> {
                poisonUntil.put(p.getUniqueId(), System.currentTimeMillis() + 8000);
                w.spawnParticle(Particle.ITEM_SLIME, loc.add(0, 1, 0), 20, 0.3, 0.4, 0.3, 0);
                w.playSound(loc, Sound.ENTITY_SPIDER_AMBIENT, 1f, 1.4f);
            }
            case VANISH -> {
                p.addPotionEffect(new PotionEffect(PotionEffectType.INVISIBILITY, 100, 0, false, false));
                p.addPotionEffect(new PotionEffect(PotionEffectType.SPEED, 100, 1));
                for (Entity e : p.getNearbyEntities(16, 8, 16)) if (e instanceof Mob m && m.getTarget() == p) m.setTarget(null);
                plugin.rpg().vanishUntil.put(p.getUniqueId(), System.currentTimeMillis() + 5000);
                w.spawnParticle(Particle.LARGE_SMOKE, loc.add(0, 1, 0), 30, 0.4, 0.6, 0.4, 0.02);
                w.playSound(loc, Sound.ENTITY_ILLUSIONER_MIRROR_MOVE, 1f, 1f);
            }
            case HEAL_LIGHT -> {
                for (Player a : alliesAround(p, 8)) {
                    heal(a, 6 + plugin.rpg().level(p) * 0.2);
                    w.spawnParticle(Particle.HEART, a.getLocation().add(0, 2, 0), 4, 0.4, 0.2, 0.4, 0);
                }
                ring(loc, Particle.END_ROD, 3, 30);
                w.playSound(loc, Sound.BLOCK_AMETHYST_BLOCK_CHIME, 1f, 1.2f);
            }
            case HOLY_SMITE -> {
                LivingEntity t = lookTarget(p, 20);
                if (t == null) { p.sendActionBar("§c바라보는 적이 없어요."); return false; }
                w.strikeLightningEffect(t.getLocation());
                hit(p, t, scale(p, 10));
                if (t instanceof Zombie || t instanceof Skeleton || t instanceof WitherSkeleton || t instanceof Phantom) hit(p, t, scale(p, 5));
            }
            case BLESSING -> {
                for (Player a : alliesAround(p, 10)) {
                    a.addPotionEffect(new PotionEffect(PotionEffectType.REGENERATION, 200, 1));
                    a.addPotionEffect(new PotionEffect(PotionEffectType.STRENGTH, 200, 0));
                    w.spawnParticle(Particle.HAPPY_VILLAGER, a.getLocation().add(0, 1, 0), 15, 0.4, 0.6, 0.4, 0);
                }
                w.playSound(loc, Sound.BLOCK_BEACON_POWER_SELECT, 1f, 1.5f);
            }
            case RAGE -> {
                p.addPotionEffect(new PotionEffect(PotionEffectType.STRENGTH, 200, 2));
                p.addPotionEffect(new PotionEffect(PotionEffectType.SPEED, 200, 0));
                rageUntil.put(p.getUniqueId(), System.currentTimeMillis() + 10000);
                w.spawnParticle(Particle.ANGRY_VILLAGER, loc.add(0, 1, 0), 20, 0.5, 0.6, 0.5, 0);
                w.playSound(loc, Sound.ENTITY_RAVAGER_ROAR, 1f, 1.2f);
            }
            case HOLY_BARRIER -> {
                for (Player a : alliesAround(p, 10)) {
                    a.addPotionEffect(new PotionEffect(PotionEffectType.ABSORPTION, 300, 3));
                    ring(a.getLocation().add(0, 1, 0), Particle.END_ROD, 1, 16);
                }
                w.playSound(loc, Sound.BLOCK_BEACON_ACTIVATE, 1f, 1.2f);
            }
            case PIERCING_SHOT -> {
                beam(p, Particle.CRIT, 40, 1.0, scale(p, 22), true, new Particle.DustOptions(Color.fromRGB(120, 255, 140), 1.3f));
                w.playSound(loc, Sound.ITEM_CROSSBOW_SHOOT, 1f, 0.6f);
                w.playSound(loc, Sound.ENTITY_FIREWORK_ROCKET_BLAST, 1f, 0.6f);
            }
            case SNARE_TRAP -> {
                Location trap = loc.clone();
                w.playSound(trap, Sound.BLOCK_TRIPWIRE_ATTACH, 1f, 1f);
                new BukkitRunnable() {
                    int t = 0;
                    public void run() {
                        if (t++ > 300) { cancel(); return; }
                        if (t % 5 == 0) ring(trap, Particle.CRIT, 1.2, 10);
                        List<LivingEntity> in = enemiesAround(p, trap, 1.6);
                        if (!in.isEmpty()) {
                            for (LivingEntity e : enemiesAround(p, trap, 3)) {
                                e.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 100, 6));
                                hit(p, e, scale(p, 8));
                            }
                            w.spawnParticle(Particle.BLOCK, trap, 40, 1, 0.3, 1, Material.COBWEB.createBlockData());
                            w.playSound(trap, Sound.BLOCK_TRIPWIRE_CLICK_ON, 1f, 0.6f);
                            cancel();
                        }
                    }
                }.runTaskTimer(plugin, 10, 1);
            }
            case METEOR -> {
                Location c = lookBlock(p, 30);
                p.sendActionBar("§c§l메테오 소환!");
                new BukkitRunnable() {
                    int t = 0;
                    public void run() {
                        if (t++ < 30) {
                            ring(c, Particle.FLAME, 4, 30);
                            Location fall = c.clone().add(0, 20 - t * 0.66, 0);
                            w.spawnParticle(Particle.LAVA, fall, 6, 0.6, 0.6, 0.6, 0);
                            w.spawnParticle(Particle.LARGE_SMOKE, fall, 6, 0.6, 0.6, 0.6, 0.02);
                            return;
                        }
                        cancel();
                        w.spawnParticle(Particle.EXPLOSION_EMITTER, c, 2);
                        w.playSound(c, Sound.ENTITY_GENERIC_EXPLODE, 2f, 0.6f);
                        for (LivingEntity e : enemiesAround(p, c, 6)) {
                            hit(p, e, scale(p, 25));
                            e.setFireTicks(80);
                            e.setVelocity(e.getLocation().toVector().subtract(c.toVector()).normalize().setY(0.6));
                        }
                    }
                }.runTaskTimer(plugin, 0, 1);
            }
            case LIFE_DRAIN -> {
                double total = 0;
                for (LivingEntity e : enemiesAround(p, loc, 7)) {
                    hit(p, e, scale(p, 8));
                    total += 3;
                    Location from = e.getLocation().add(0, 1, 0);
                    Vector v = p.getLocation().add(0, 1, 0).toVector().subtract(from.toVector());
                    for (double d = 0; d < v.length(); d += 0.5) {
                        w.spawnParticle(Particle.DUST, from.clone().add(v.clone().normalize().multiply(d)), 1, 0, 0, 0, 0,
                                new Particle.DustOptions(Color.fromRGB(150, 0, 60), 1f));
                    }
                }
                heal(p, Math.min(20, total));
                w.playSound(loc, Sound.ENTITY_WITHER_SHOOT, 0.7f, 1.5f);
            }
            case SHADOW_EXECUTE -> {
                LivingEntity t = lookTarget(p, 15);
                if (t == null) { p.sendActionBar("§c바라보는 적이 없어요."); return false; }
                Location behind = t.getLocation().subtract(t.getLocation().getDirection().setY(0).normalize().multiply(1.2));
                behind.setDirection(t.getLocation().toVector().subtract(behind.toVector()));
                w.spawnParticle(Particle.LARGE_SMOKE, p.getLocation().add(0, 1, 0), 20, 0.3, 0.5, 0.3, 0.02);
                p.teleport(behind);
                double max = t.getAttribute(Attribute.MAX_HEALTH).getValue();
                hit(p, t, scale(p, t.getHealth() < max * 0.3 ? 30 : 15));
                w.spawnParticle(Particle.CRIT, t.getLocation().add(0, 1, 0), 30, 0.3, 0.5, 0.3, 0.3);
                w.playSound(behind, Sound.ENTITY_PLAYER_ATTACK_CRIT, 1f, 0.6f);
            }
            case BLADE_DANCE -> new BukkitRunnable() {
                int t = 0;
                public void run() {
                    if (t++ >= 6 || !p.isOnline()) { cancel(); return; }
                    Location l = p.getLocation();
                    for (LivingEntity e : enemiesAround(p, l, 3.5)) hit(p, e, scale(p, 4));
                    ring(l.clone().add(0, 1, 0), Particle.SWEEP_ATTACK, 2.2, 6);
                    w.playSound(l, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 0.8f, 1.2f + t * 0.1f);
                }
            }.runTaskTimer(plugin, 0, 4);
            case SANCTUARY -> {
                for (Player a : alliesAround(p, 10)) {
                    heal(a, 100);
                    for (PotionEffectType bad : List.of(PotionEffectType.POISON, PotionEffectType.WITHER, PotionEffectType.SLOWNESS,
                            PotionEffectType.WEAKNESS, PotionEffectType.BLINDNESS, PotionEffectType.NAUSEA, PotionEffectType.MINING_FATIGUE)) {
                        a.removePotionEffect(bad);
                    }
                    a.setFireTicks(0);
                    w.spawnParticle(Particle.TOTEM_OF_UNDYING, a.getLocation().add(0, 1, 0), 30, 0.4, 0.8, 0.4, 0.2);
                }
                w.playSound(loc, Sound.ITEM_TOTEM_USE, 0.6f, 1.4f);
            }
            case DIVINE_STORM -> new BukkitRunnable() {
                int t = 0;
                public void run() {
                    if (t++ >= 5 || !p.isOnline()) { cancel(); return; }
                    for (LivingEntity e : enemiesAround(p, p.getLocation(), 9)) {
                        if (ThreadLocalRandom.current().nextBoolean()) {
                            w.strikeLightningEffect(e.getLocation());
                            hit(p, e, scale(p, 8));
                        }
                    }
                }
            }.runTaskTimer(plugin, 0, 10);
            case DRAGON_BREATH -> {
                for (int i = 0; i < 10; i++) {
                    double d = 1 + i * 0.7;
                    Location at = p.getEyeLocation().add(p.getLocation().getDirection().multiply(d));
                    w.spawnParticle(Particle.FLAME, at, 8, 0.15 * i * 0.3, 0.15 * i * 0.3, 0.15 * i * 0.3, 0.02);
                    for (LivingEntity e : enemiesAround(p, at, 0.8 + i * 0.15)) {
                        hit(p, e, scale(p, 1.2));
                        e.setFireTicks(60);
                    }
                }
                w.playSound(loc, Sound.ENTITY_ENDER_DRAGON_SHOOT, 1f, 1f);
            }
            case DRAGON_DIVE -> {
                p.setVelocity(new Vector(0, 2.0, 0));
                plugin.noFall(p, 100);
                later(18, () -> {
                    if (!p.isOnline()) return;
                    p.setVelocity(p.getLocation().getDirection().multiply(1.5).setY(-2.5));
                    new BukkitRunnable() {
                        int t = 0;
                        public void run() {
                            if (!p.isOnline() || t++ > 60) { cancel(); return; }
                            w.spawnParticle(Particle.FLAME, p.getLocation(), 6, 0.3, 0.3, 0.3, 0.02);
                            if (p.isOnGround()) {
                                cancel();
                                Location l = p.getLocation();
                                w.spawnParticle(Particle.EXPLOSION_EMITTER, l, 1);
                                w.playSound(l, Sound.ENTITY_GENERIC_EXPLODE, 1.2f, 0.8f);
                                for (LivingEntity e : enemiesAround(p, l, 5)) {
                                    hit(p, e, scale(p, 16));
                                    e.setFireTicks(80);
                                }
                            }
                        }
                    }.runTaskTimer(plugin, 1, 1);
                });
            }
            case DRAGON_ROAR -> {
                for (LivingEntity e : enemiesAround(p, loc, 10)) {
                    e.addPotionEffect(new PotionEffect(PotionEffectType.WEAKNESS, 160, 1));
                    e.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 100, 2));
                    e.setVelocity(e.getLocation().toVector().subtract(loc.toVector()).normalize().multiply(0.8).setY(0.3));
                }
                p.addPotionEffect(new PotionEffect(PotionEffectType.STRENGTH, 200, 1));
                p.addPotionEffect(new PotionEffect(PotionEffectType.FIRE_RESISTANCE, 400, 0));
                w.playSound(loc, Sound.ENTITY_ENDER_DRAGON_GROWL, 1.5f, 1f);
                ring(loc, Particle.FLAME, 5, 40);
            }
            case LIE_DOWN -> {
                p.addPotionEffect(new PotionEffect(PotionEffectType.RESISTANCE, 60, 4));
                p.addPotionEffect(new PotionEffect(PotionEffectType.REGENERATION, 60, 3));
                p.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 60, 10));
                p.sendTitle("§d😴", "§7백수는 누워야 강해진다...", 5, 40, 10);
                w.spawnParticle(Particle.HEART, loc.add(0, 1, 0), 6, 0.4, 0.3, 0.4, 0);
                w.playSound(loc, Sound.ENTITY_CAT_PURR, 1f, 0.8f);
            }
            case MOM_CHANCE -> {
                String[][] gifts = {
                        {"BREAD", "16", "엄마: 밥은 먹고 다니니? (빵 16개)"},
                        {"COOKED_BEEF", "8", "엄마: 고기라도 먹어라 (스테이크 8개)"},
                        {"GOLDEN_APPLE", "2", "엄마: 이거 비싼 거다 (황금 사과 2개)"},
                        {"DIAMOND", "1", "엄마: 용돈이다 아껴 써라 (다이아 1개)"},
                        {"IRON_INGOT", "5", "엄마: 철이 들어라 (철 5개)"},
                        {"POTATO", "1", "엄마: 감자 하나 남았다... (감자 1개)"},
                        {"ENCHANTED_GOLDEN_APPLE", "1", "엄마: 아빠 몰래 챙겨왔다! (마법 황금 사과)"}};
                String[] g = gifts[ThreadLocalRandom.current().nextInt(gifts.length)];
                plugin.giveItem(p, new ItemStack(Material.valueOf(g[0]), Integer.parseInt(g[1])));
                p.sendMessage("§d[백수왕] §f" + g[2]);
                w.playSound(loc, Sound.ENTITY_VILLAGER_YES, 1f, 1.3f);
            }
            case NEET_RAGE -> {
                LivingEntity t = lookTarget(p, 6);
                if (t == null) { p.sendActionBar("§c때릴 대상이 없어요. 백수는 오늘도 쉰다."); return false; }
                int dmg = 1 + ThreadLocalRandom.current().nextInt(30);
                hit(p, t, dmg);
                String msg = dmg >= 25 ? "§c§l크리티컬! 백수의 한이 폭발했다!" : dmg <= 3 ? "§7...힘이 안 난다. 밥을 안 먹었다." : "§e백수의 주먹!";
                p.sendActionBar(msg + " §7(" + dmg + ")");
                w.spawnParticle(Particle.CRIT, t.getLocation().add(0, 1, 0), dmg, 0.3, 0.5, 0.3, 0.2);
                w.playSound(loc, Sound.ENTITY_PLAYER_ATTACK_STRONG, 1f, 0.7f);
            }
            case NEET_ULT -> {
                p.sendTitle("§6§l💰 월급날 💰", "§7...인 줄 알았는데 꿈이었다", 10, 50, 10);
                for (Player a : alliesAround(p, 10)) {
                    heal(a, 20);
                    PotionEffectType[] buffs = {PotionEffectType.SPEED, PotionEffectType.STRENGTH, PotionEffectType.RESISTANCE,
                            PotionEffectType.HASTE, PotionEffectType.JUMP_BOOST, PotionEffectType.REGENERATION};
                    a.addPotionEffect(new PotionEffect(buffs[ThreadLocalRandom.current().nextInt(buffs.length)], 400, 1));
                }
                w.spawnParticle(Particle.HAPPY_VILLAGER, loc.add(0, 2, 0), 80, 3, 1, 3, 0);
                w.playSound(loc, Sound.ENTITY_PLAYER_LEVELUP, 1f, 0.6f);
            }
            default -> { return extra.cast(p, s); }
        }
        return true;
    }

    // ------------------------------------------------------------------ 무기 스킬 (우클릭)

    /** Mythic 아이템 ID → 무기 스킬. 쿨타임 초 */
    static final Map<String, Object[]> WEAPON_SKILLS = Map.of(
            "별빛의검", new Object[]{"별빛 베기", 8},
            "용암도끼", new Object[]{"용암 분출", 12},
            "바람의활", new Object[]{"질풍 사격", 10},
            "대족장의도끼", new Object[]{"대지 분쇄", 14});

    boolean weaponSkill(Player p, String id) {
        World w = p.getWorld();
        Location loc = p.getLocation();
        switch (id) {
            case "별빛의검" -> {
                beam(p, Particle.END_ROD, 12, 1.2, scale(p, 12), true, new Particle.DustOptions(Color.fromRGB(150, 220, 255), 1.4f));
                w.playSound(loc, Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 1f, 1.6f);
                w.playSound(loc, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1f, 1.4f);
            }
            case "용암도끼" -> {
                Location c = loc.clone().add(loc.getDirection().setY(0).normalize().multiply(3));
                new BukkitRunnable() {
                    int t = 0;
                    public void run() {
                        if (t++ >= 4) { cancel(); return; }
                        w.spawnParticle(Particle.LAVA, c, 20, 1.5, 0.2, 1.5, 0);
                        w.spawnParticle(Particle.FLAME, c, 40, 1.5, 1, 1.5, 0.05);
                        for (LivingEntity e : enemiesAround(p, c, 3.5)) {
                            hit(p, e, scale(p, 5));
                            e.setFireTicks(80);
                            e.setVelocity(new Vector(0, 0.5, 0));
                        }
                    }
                }.runTaskTimer(plugin, 0, 6);
                w.playSound(c, Sound.ITEM_BUCKET_EMPTY_LAVA, 1f, 0.8f);
            }
            case "바람의활" -> {
                for (int i = -3; i <= 3; i++) {
                    Arrow a = p.launchProjectile(Arrow.class, p.getLocation().getDirection().rotateAroundY(Math.toRadians(i * 6)).multiply(3));
                    a.setDamage(scale(p, 3));
                    a.setCritical(true);
                    a.setPickupStatus(AbstractArrow.PickupStatus.DISALLOWED);
                }
                p.setVelocity(loc.getDirection().multiply(-0.6).setY(0.3));
                w.spawnParticle(Particle.CLOUD, loc, 20, 0.5, 0.2, 0.5, 0.05);
                w.playSound(loc, Sound.ENTITY_BREEZE_SHOOT, 1f, 1f);
            }
            case "대족장의도끼" -> {
                w.spawnParticle(Particle.EXPLOSION, loc, 4, 1.5, 0.2, 1.5);
                ring(loc, Particle.CLOUD, 4, 30);
                w.playSound(loc, Sound.ENTITY_IRON_GOLEM_ATTACK, 1.5f, 0.5f);
                for (LivingEntity e : enemiesAround(p, loc, 5)) {
                    hit(p, e, scale(p, 13));
                    e.setVelocity(new Vector(0, 1.1, 0));
                    e.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, 60, 2));
                }
            }
            default -> { return false; }
        }
        return true;
    }

    void later(long ticks, Runnable r) {
        Bukkit.getScheduler().runTaskLater(plugin, r, ticks);
    }
}
