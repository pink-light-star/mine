package kr.starserver.starrpg;

import org.bukkit.*;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.entity.*;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityTargetEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.world.EntitiesLoadEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

import java.util.*;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 아군 펫: 주인을 따라다니며 적을 공격한다.
 * - 바탕은 길들인 늑대(모델로 가려짐). 주인이 때린 대상/주인을 때린 대상/근처 몬스터를 공격.
 * - 총 펫: 사거리 안이면 멈춰서 사격. 검 펫: 근접 베기.
 * - 전투에 들어가면 전투 모델·이름으로 바뀌고, 5초간 전투가 없으면 원래대로.
 */
@SuppressWarnings("deprecation")
final class Pets implements Listener {
    private static final String P = "§d[별빛] §f";
    private static final double GUN_RANGE = 18;
    private static final double GUN_STOP = 8;        // 이 거리 안이면 다가가지 않고 쏜다
    private static final double GUN_DAMAGE = 6;
    private static final int GUN_COOLDOWN = 24;      // 틱
    private static final double SWORD_DAMAGE = 9;
    private static final int COMBAT_LINGER = 100;    // 틱: 전투가 끝나고 원래 모습으로 돌아가기까지

    private final StarRPG plugin;
    private final NamespacedKey KIND, PET, PET_OWNER;
    private final Map<UUID, Long> lastShot = new HashMap<>();
    private final Map<UUID, Long> lastCombat = new HashMap<>();
    private final Set<UUID> inCombat = new HashSet<>();
    private boolean shooting;
    private int shieldSide = 1;   // 총 피해를 줄 때는 근접 취소 로직을 건너뛴다

    Pets(StarRPG plugin) {
        this.plugin = plugin;
        KIND = new NamespacedKey(plugin, "kind");
        PET = new NamespacedKey(plugin, "pet");
        PET_OWNER = new NamespacedKey(plugin, "pet_owner");
        Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 1L, 1L);
    }

    // ------------------------------------------------------------------ 아이템

    ItemStack card(PetType t) {
        ItemStack it = new ItemStack(Material.NAME_TAG);
        ItemMeta m = it.getItemMeta();
        m.setDisplayName("§e§l✦ 펫 카드 §7- " + t.color + "§l" + t.normalName
                + (t.transforms() ? " §7(전투: " + t.color + t.combatLabel() + "§7)" : ""));
        m.setLore(List.of(
                "§7무기: §f" + t.weapon.korean,
                t.transforms() ? "§7전투에 들어가면 §f" + t.combatLabel() + "§7(으)로 변신!" : "§7든든한 아군 펫",
                "",
                "§e블록에 우클릭: §f소환",
                "§eShift+우클릭(펫): §f카드로 되돌리기"));
        m.getPersistentDataContainer().set(KIND, PersistentDataType.STRING, "petcard");
        m.getPersistentDataContainer().set(PET, PersistentDataType.STRING, t.name());
        m.addItemFlags(ItemFlag.HIDE_ADDITIONAL_TOOLTIP);
        m.setEnchantmentGlintOverride(true);
        it.setItemMeta(m);
        return it;
    }

    // ------------------------------------------------------------------ 상태

    PetType typeOf(Entity e) {
        String s = e.getPersistentDataContainer().get(PET, PersistentDataType.STRING);
        if (s == null || !e.getPersistentDataContainer().has(PET_OWNER, PersistentDataType.STRING)) return null;
        try { return PetType.valueOf(s); } catch (IllegalArgumentException ex) { return null; }
    }

    boolean isPet(Entity e) {
        return e != null && typeOf(e) != null;
    }

    private UUID ownerOf(Entity e) {
        String s = e.getPersistentDataContainer().get(PET_OWNER, PersistentDataType.STRING);
        return s == null ? null : UUID.fromString(s);
    }

    private void name(Wolf w, PetType t, boolean combat) {
        UUID o = ownerOf(w);
        OfflinePlayer op = o == null ? null : Bukkit.getOfflinePlayer(o);
        String owner = op != null && op.getName() != null ? op.getName() + "의 " : "";
        w.setCustomName((combat ? "§c⚔ " : "") + t.color + "§l" + (combat ? t.combatName : t.normalName) + " §7(" + owner + "펫)");
        w.setCustomNameVisible(true);
    }

    Wolf spawn(PetType t, Location loc, Player owner) {
        Wolf w = loc.getWorld().spawn(loc, Wolf.class, wolf -> {
            wolf.getPersistentDataContainer().set(PET, PersistentDataType.STRING, t.name());
            wolf.getPersistentDataContainer().set(PET_OWNER, PersistentDataType.STRING, owner.getUniqueId().toString());
            wolf.setTamed(true);
            wolf.setOwner(owner);
            wolf.setAdult();
            wolf.setAgeLock(true);
            wolf.setSilent(true);
            wolf.setPersistent(true);
            wolf.setRemoveWhenFarAway(false);
            AttributeInstance hp = wolf.getAttribute(Attribute.MAX_HEALTH);
            if (hp != null) hp.setBaseValue(80);
            wolf.setHealth(80);
            AttributeInstance spd = wolf.getAttribute(Attribute.MOVEMENT_SPEED);
            if (spd != null) spd.setBaseValue(0.32);
            AttributeInstance dmg = wolf.getAttribute(Attribute.ATTACK_DAMAGE);
            if (dmg != null) dmg.setBaseValue(t.gun ? 0 : SWORD_DAMAGE);
        });
        name(w, t, false);
        plugin.applyModelId(w, t.normalModel);
        return w;
    }

    private void setCombat(Wolf w, PetType t, boolean combat) {
        boolean was = inCombat.contains(w.getUniqueId());
        if (was == combat) return;
        if (combat) inCombat.add(w.getUniqueId()); else inCombat.remove(w.getUniqueId());
        name(w, t, combat);
        if (t.transforms()) {
            plugin.swapModel(w, combat ? t.normalModel : t.combatModel, combat ? t.combatModel : t.normalModel);
            w.getWorld().spawnParticle(Particle.CLOUD, w.getLocation().add(0, 1, 0), 20, 0.3, 0.6, 0.3, 0.02);
            w.getWorld().spawnParticle(Particle.END_ROD, w.getLocation().add(0, 1, 0), 30, 0.4, 0.8, 0.4, 0.05);
            w.getWorld().playSound(w.getLocation(), Sound.ITEM_ARMOR_EQUIP_NETHERITE, 1f, 1.2f);
        }
    }

    // ------------------------------------------------------------------ 매 틱

    private void tick() {
        long now = Bukkit.getCurrentTick();
        for (World world : Bukkit.getWorlds()) {
            for (Wolf w : world.getEntitiesByClass(Wolf.class)) {
                PetType t = typeOf(w);
                if (t == null) continue;
                LivingEntity target = w.getTarget();
                if (target != null && (!target.isValid() || target.isDead() || !validEnemy(w, target))) {
                    w.setTarget(null);
                    target = null;
                }
                // 근처 몬스터 자동 공격 (1초마다)
                if (target == null && now % 20 == w.getEntityId() % 20) {
                    target = findMonster(w);
                    if (target != null) w.setTarget(target);
                }
                if (target != null) {
                    lastCombat.put(w.getUniqueId(), now);
                    setCombat(w, t, true);
                    if (t.gun) gunTick(w, t, target, now);
                } else if (inCombat.contains(w.getUniqueId())
                        && now - lastCombat.getOrDefault(w.getUniqueId(), 0L) > COMBAT_LINGER) {
                    setCombat(w, t, false);
                }
            }
        }
    }

    private LivingEntity findMonster(Wolf w) {
        LivingEntity best = null;
        double bestD = 14 * 14;
        for (Entity e : w.getNearbyEntities(14, 6, 14)) {
            if (!(e instanceof Monster m) || !validEnemy(w, m)) continue;
            double d = e.getLocation().distanceSquared(w.getLocation());
            if (d < bestD && w.hasLineOfSight(e)) { best = m; bestD = d; }
        }
        return best;
    }

    private boolean validEnemy(Wolf pet, Entity e) {
        if (!(e instanceof LivingEntity) || e instanceof Player || e instanceof ArmorStand) return false;
        if (isPet(e) || plugin.isMountEntity(e)) return false;
        if (e instanceof Tameable tm && tm.isTamed()) return false;
        return true;
    }

    private void gunTick(Wolf w, PetType t, LivingEntity target, long now) {
        PetType.Weapon wp = t.weapon;
        double dist = w.getLocation().distance(target.getLocation());
        if (dist <= wp.stop && w.hasLineOfSight(target)) {
            w.getPathfinder().stopPathfinding();     // 다가가지 않고 그 자리에서 사격
            w.lookAt(target);
        }
        if (dist > wp.range || now - lastShot.getOrDefault(w.getUniqueId(), -1000L) < wp.cooldown) return;
        if (!w.hasLineOfSight(target)) return;
        lastShot.put(w.getUniqueId(), now);
        plugin.animateModel(w, t.combatModel, "attack");
        if (wp.shots <= 1) { shoot(w, t, target); return; }
        // 연사: 일정 간격으로 여러 발
        for (int i = 0; i < wp.shots; i++) {
            Bukkit.getScheduler().runTaskLater(plugin, () -> {
                if (w.isValid() && target.isValid() && !target.isDead()) shoot(w, t, target);
            }, i * 2L);
        }
    }

    private void shoot(Wolf w, PetType t, LivingEntity target) {
        w.lookAt(target);
        PetType.Weapon wp = t.weapon;
        boolean shield = t == PetType.SILVER;   // 신데렐라: 양옆에 떠 있는 방패에서 번갈아 발사
        Location from = w.getLocation().add(0, shield ? 1.3 : 1.4, 0);
        if (shield) {
            double yaw = Math.toRadians(w.getLocation().getYaw());
            int side = (shieldSide = -shieldSide);
            from.add(Math.cos(yaw) * 0.8 * side, 0, Math.sin(yaw) * 0.8 * side);
        }
        Vector dir = target.getEyeLocation().subtract(0, 0.4, 0).toVector().subtract(from.toVector());
        double len = dir.length();
        dir.normalize();
        World world = w.getWorld();
        // 총알 궤적
        if (shield) {
            Particle.DustOptions blue = new Particle.DustOptions(Color.fromRGB(150, 220, 255), 1.0f);
            Particle.DustOptions pink = new Particle.DustOptions(Color.fromRGB(255, 160, 190), 0.8f);
            for (double d = 0.6; d < len; d += 0.35) {
                Location at = from.clone().add(dir.clone().multiply(d));
                world.spawnParticle(Particle.DUST, at, 1, 0.03, 0.03, 0.03, 0, (d * 3) % 2 < 1 ? blue : pink);
                if ((int) (d * 3) % 4 == 0) world.spawnParticle(Particle.END_ROD, at, 1, 0.05, 0.05, 0.05, 0.005);
            }
            world.spawnParticle(Particle.END_ROD, from.clone().add(dir.clone().multiply(0.6)), 8, 0.15, 0.15, 0.15, 0.03);
            world.playSound(from, Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 1f, 1.6f);
            world.playSound(from, Sound.ENTITY_FIREWORK_ROCKET_TWINKLE, 0.6f, 1.8f);
        } else if (wp == PetType.Weapon.SNIPER) {
            Particle.DustOptions trail = new Particle.DustOptions(Color.fromRGB(200, 230, 255), 1.2f);
            for (double d = 0.8; d < len; d += 0.25) world.spawnParticle(Particle.DUST, from.clone().add(dir.clone().multiply(d)), 1, 0, 0, 0, 0, trail);
            world.spawnParticle(Particle.END_ROD, from.clone().add(dir.clone().multiply(0.8)), 10, 0.1, 0.1, 0.1, 0.08);
            world.playSound(from, Sound.ENTITY_GENERIC_EXPLODE, 0.5f, 2.0f);
            world.playSound(from, Sound.ITEM_CROSSBOW_SHOOT, 1f, 0.5f);
            world.playSound(target.getLocation(), Sound.ENTITY_ARROW_HIT_PLAYER, 0.8f, 0.6f);
        } else if (wp == PetType.Weapon.GATLING) {
            Location jitter = target.getEyeLocation().add(ThreadLocalRandom.current().nextDouble(-0.4, 0.4), -0.4 + ThreadLocalRandom.current().nextDouble(-0.3, 0.3), ThreadLocalRandom.current().nextDouble(-0.4, 0.4));
            Vector jd = jitter.toVector().subtract(from.toVector()).normalize();
            Particle.DustOptions tracer = new Particle.DustOptions(Color.fromRGB(255, 180, 60), 0.6f);
            for (double d = 0.8; d < len; d += 0.6) world.spawnParticle(Particle.DUST, from.clone().add(jd.clone().multiply(d)), 1, 0, 0, 0, 0, tracer);
            world.spawnParticle(Particle.SMALL_FLAME, from.clone().add(dir.clone().multiply(0.8)), 2, 0.05, 0.05, 0.05, 0.01);
            world.playSound(from, Sound.BLOCK_NOTE_BLOCK_SNARE, 0.7f, 1.8f);
            world.playSound(from, Sound.ENTITY_FIREWORK_ROCKET_BLAST, 0.35f, 2.0f);
        } else {
            Particle.DustOptions dust = new Particle.DustOptions(Color.fromRGB(255, 220, 120), wp == PetType.Weapon.PISTOL ? 0.5f : 0.7f);
            for (double d = 0.8; d < len; d += 0.5) {
                world.spawnParticle(Particle.DUST, from.clone().add(dir.clone().multiply(d)), 1, 0, 0, 0, 0, dust);
            }
            world.spawnParticle(Particle.SMOKE, from.clone().add(dir.clone().multiply(0.8)), wp == PetType.Weapon.PISTOL ? 2 : 4, 0.05, 0.05, 0.05, 0.01);
            world.playSound(from, Sound.ENTITY_FIREWORK_ROCKET_BLAST, wp == PetType.Weapon.PISTOL ? 0.6f : 0.8f, wp == PetType.Weapon.PISTOL ? 2.0f : 1.6f);
            world.playSound(from, Sound.BLOCK_DISPENSER_LAUNCH, 0.5f, 1.8f);
        }
        // 벽에 막히면 맞지 않음
        RayTraceResult block = world.rayTraceBlocks(from, dir, len, FluidCollisionMode.NEVER, true);
        if (block != null && block.getHitBlock() != null) return;
        shooting = true;
        try { target.damage(wp.damage, w); } finally { shooting = false; }
        world.spawnParticle(Particle.CRIT, target.getEyeLocation(), 8, 0.2, 0.2, 0.2, 0.1);
    }

    // ------------------------------------------------------------------ 이벤트

    @EventHandler(priority = EventPriority.HIGH)
    public void onUseCard(PlayerInteractEvent e) {
        if (e.getHand() != EquipmentSlot.HAND || e.getAction() != Action.RIGHT_CLICK_BLOCK) return;
        ItemStack it = e.getItem();
        if (it == null || !it.hasItemMeta()) return;
        if (!"petcard".equals(it.getItemMeta().getPersistentDataContainer().get(KIND, PersistentDataType.STRING))) return;
        e.setCancelled(true);
        PetType t = PetType.byName(it.getItemMeta().getPersistentDataContainer().get(PET, PersistentDataType.STRING));
        if (t == null || e.getClickedBlock() == null) return;
        Block b = e.getClickedBlock().getRelative(e.getBlockFace() == null ? BlockFace.UP : e.getBlockFace());
        Location loc = b.getLocation().add(0.5, 0.1, 0.5);
        spawn(t, loc, e.getPlayer());
        it.setAmount(it.getAmount() - 1);
        loc.getWorld().spawnParticle(Particle.END_ROD, loc.clone().add(0, 1, 0), 40, 0.4, 0.8, 0.4, 0.05);
        e.getPlayer().playSound(loc, Sound.ENTITY_PLAYER_LEVELUP, 0.8f, 1.6f);
        e.getPlayer().sendMessage(P + t.color + t.normalName + "§f이(가) 함께합니다! §7(Shift+우클릭으로 카드로 되돌리기)");
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteractPet(PlayerInteractEntityEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        PetType t = typeOf(e.getRightClicked());
        if (t == null) return;
        e.setCancelled(true);   // 늑대 앉히기/먹이주기 방지
        Player p = e.getPlayer();
        if (!p.getUniqueId().equals(ownerOf(e.getRightClicked())) && !p.hasPermission("starrpg.admin")) {
            p.sendActionBar("§c다른 사람의 펫입니다.");
            return;
        }
        if (p.isSneaking()) {
            e.getRightClicked().remove();
            inCombat.remove(e.getRightClicked().getUniqueId());
            plugin.giveItem(p, card(t));
            p.sendMessage(P + t.color + t.normalName + "§7을(를) 카드로 되돌렸습니다.");
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onDamage(EntityDamageEvent e) {
        if (isPet(e.getEntity())) e.setCancelled(true);   // 펫은 다치지 않는다
    }

    @EventHandler(ignoreCancelled = true, priority = EventPriority.HIGH)
    public void onPetHit(EntityDamageByEntityEvent e) {
        PetType t = typeOf(e.getDamager());
        if (t == null) return;
        if (!validEnemy((Wolf) e.getDamager(), e.getEntity())) { e.setCancelled(true); return; }
        if (t.gun) {
            if (!shooting) e.setCancelled(true);   // 총 펫은 물지 않는다 (총으로만 공격)
            return;
        }
        e.setDamage(SWORD_DAMAGE);
        plugin.animateModel(e.getDamager(), t.combatModel, "attack");
        e.getEntity().getWorld().spawnParticle(Particle.SWEEP_ATTACK, e.getEntity().getLocation().add(0, 1, 0), 1);
        e.getEntity().getWorld().playSound(e.getEntity().getLocation(), Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1f, 1.1f);
    }

    @EventHandler(ignoreCancelled = true)
    public void onTarget(EntityTargetEvent e) {
        if (isPet(e.getEntity()) && e.getTarget() != null && !validEnemy((Wolf) e.getEntity(), e.getTarget())) e.setCancelled(true);
    }

    @EventHandler
    public void onLoad(EntitiesLoadEvent e) {
        for (Entity en : e.getEntities()) {
            PetType t = typeOf(en);
            if (t == null) continue;
            Bukkit.getScheduler().runTask(plugin, () -> {
                if (!en.isValid()) return;
                plugin.applyModelId(en, t.normalModel);
                if (en instanceof Wolf w) name(w, t, false);
            });
        }
    }

    void listTo(org.bukkit.command.CommandSender s) {
        s.sendMessage("§d§m        §r §e§l아군 펫 §d§m        ");
        for (PetType t : PetType.values()) {
            s.sendMessage(" " + t.color + "§l" + t.normalName + (t.transforms() ? " §7→ 전투 시 " + t.color + t.combatLabel() : "")
                    + " §8| §7" + t.weapon.korean + " §8| §7ID: " + t.name());
        }
        s.sendMessage("§7지급: §f/starrpg give <닉네임> pet:<ID>");
    }
}
