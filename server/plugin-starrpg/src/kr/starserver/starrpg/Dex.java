package kr.starserver.starrpg;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.entity.ArmorStand;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerInteractAtEntityEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * /도감 — 탈것 · 펫 · 보스/몬스터 · 장비 도감 GUI.
 * 항목을 누르면 플레이어 앞에 그 3D 모델이 15초 동안 나타나 빙글 돈다 (장비 탭은 Skript /장비도감).
 */
final class Dex implements Listener {
    static final String TAG = "starrpg_dex_preview";
    private static final int[] SLOTS = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 37, 38, 39, 40, 41, 42, 43};
    private static final long PREVIEW_TICKS = 15 * 20L;

    private final StarRPG plugin;
    private final Map<UUID, Preview> previews = new HashMap<>();
    private final Map<UUID, Long> cooldown = new HashMap<>();

    Dex(StarRPG plugin) { this.plugin = plugin; }

    // ------------------------------------------------------------------ 보스·몬스터 목록

    record Mob(String name, String model, int hp, int dmg, String kind, Material icon, String note) {}

    static final Mob[] MOBS = {
            new Mob("§c§l🐉 적룡 이그니스", "dragon", 1500, 18, "§4최종 보스", Material.DRAGON_HEAD,
                    "처치 시 랜덤박스 · 별빛 고래 30% · 흑룡 10%"),
            new Mob("§4§l⚔ 오크 대족장 크루가", "orc_chief", 900, 16, "§c보스", Material.NETHERITE_AXE, "별빛 고래 10%"),
            new Mob("§4§l⚔ 데몬 나이트", "demon_knight", 900, 14, "§c보스", Material.NETHERITE_SWORD, "마왕군의 선봉"),
            new Mob("§c§l🐂 미노타우로스", "minotaur", 800, 15, "§c보스", Material.IRON_AXE, "별빛 고래 10%"),
            new Mob("§9§l✦ 푸른 대마법사", "blue_wizard", 700, 8, "§c보스", Material.BLAZE_ROD, "마왕군의 대마법사"),
            new Mob("§2§l🐍 메두사", "medusa", 650, 10, "§c보스", Material.BOW, "별빛 고래 10%"),
            new Mob("§6§l키클롭스", "cyclops", 220, 15, "§6정예", Material.STONE, "외눈 거인"),
            new Mob("§4§l케르베로스", "cerberus", 120, 11, "§6정예", Material.BONE, "머리 셋 지옥견"),
            new Mob("§b사이렌", "siren", 45, 6, "§7몬스터", Material.PRISMARINE_SHARD, "바다의 노래하는 마물"),
            new Mob("§2오크 전사", "orc_warrior", 40, 7, "§7몬스터", Material.IRON_AXE, "오크 부족"),
            new Mob("§a오크 주술사", "orc_shaman", 35, 0, "§7몬스터", Material.STICK, "오크 부족 · 아군 치유"),
            new Mob("§2오크 궁수", "orc_archer", 30, 6, "§7몬스터", Material.BOW, "오크 부족"),
            new Mob("§e하피", "harpy", 25, 5, "§7몬스터", Material.FEATHER, "하늘의 마물"),
    };

    // ------------------------------------------------------------------ GUI

    private static final class Holder implements InventoryHolder {
        Inventory inv;
        String tab;
        boolean lastShift;
        final Map<Integer, Runnable> actions = new HashMap<>();
        public Inventory getInventory() { return inv; }
    }

    private static ItemStack icon(Material m, String name, List<String> lore) {
        ItemStack it = new ItemStack(m == null ? Material.PAPER : m);
        ItemMeta im = it.getItemMeta();
        im.setDisplayName(name);
        im.setLore(lore);
        im.addItemFlags(ItemFlag.values());
        it.setItemMeta(im);
        return it;
    }

    private static ItemStack icon(Material m, String name, String... lore) { return icon(m, name, List.of(lore)); }

    void open(Player p, String tab) {
        Holder h = new Holder();
        h.tab = tab;
        String title = switch (tab) {
            case "pet" -> "§d§l✦ 도감 §8- §f펫";
            case "mob" -> "§4§l✦ 도감 §8- §f보스·몬스터";
            default -> "§6§l✦ 도감 §8- §f탈것";
        };
        h.inv = Bukkit.createInventory(h, 54, title);
        ItemStack pane = icon(Material.BLACK_STAINED_GLASS_PANE, " ");
        for (int i = 0; i < 9; i++) h.inv.setItem(i, pane);
        for (int i = 45; i < 54; i++) h.inv.setItem(i, pane);

        tabButton(p, h, 1, "mount", Material.SADDLE, "§6§l탈것", "§7그물총으로 잡는 탈것 · 전설·신화 탈것");
        tabButton(p, h, 3, "pet", Material.AMETHYST_SHARD, "§d§l펫", "§7펫 뽑기로 얻는 아군 펫");
        tabButton(p, h, 5, "mob", Material.WITHER_SKELETON_SKULL, "§4§l보스·몬스터", "§7전용 모델이 있는 몹과 보스");
        h.inv.setItem(7, icon(Material.NETHERITE_SWORD, "§b§l장비", "§7대장간 무기·방어구 (입체 모델)", "", "§a▶ 클릭"));
        h.actions.put(7, () -> { p.closeInventory(); Bukkit.getScheduler().runTask(plugin, () -> p.performCommand("장비도감")); });

        switch (tab) {
            case "pet" -> fillPets(p, h);
            case "mob" -> fillMobs(p, h);
            default -> fillMounts(p, h);
        }

        h.inv.setItem(45, icon(Material.ARROW, "§7← 메뉴"));
        h.actions.put(45, () -> { p.closeInventory(); Bukkit.getScheduler().runTask(plugin, () -> p.performCommand("메뉴")); });
        h.inv.setItem(49, icon(Material.BARRIER, "§c닫기"));
        h.actions.put(49, p::closeInventory);
        h.inv.setItem(53, icon(Material.ENDER_EYE, "§e3D 미리보기 안내",
                "§7항목을 누르면 내 앞에 모델이 나타나요.", "§715초 뒤에 사라지고, 다시 누르면 바뀌어요.", "§8(쿨타임 3초)"));
        p.openInventory(h.inv);
        p.playSound(p.getLocation(), Sound.ITEM_BOOK_PAGE_TURN, 0.8f, 1.1f);
    }

    private void tabButton(Player p, Holder h, int slot, String tab, Material m, String name, String desc) {
        boolean on = tab.equals(h.tab);
        ItemStack it = icon(m, name + (on ? " §a(보는 중)" : ""), desc, "", on ? "§8선택됨" : "§a▶ 클릭");
        if (on) { ItemMeta im = it.getItemMeta(); im.setEnchantmentGlintOverride(true); it.setItemMeta(im); }
        h.inv.setItem(slot, it);
        if (!on) h.actions.put(slot, () -> open(p, tab));
    }

    private static Material mountIcon(Species sp) {
        return switch (sp) {
            case WHALE -> Material.HEART_OF_THE_SEA;
            case BROOM -> Material.BRUSH;
            case DRAGON -> Material.DRAGON_HEAD;
            default -> {
                Material egg = Material.matchMaterial(sp.type.name() + "_SPAWN_EGG");
                yield egg != null ? egg : Material.SADDLE;
            }
        };
    }

    private static String mountHow(Species sp) {
        return switch (sp) {
            case WHALE -> "§7적룡 30% · 메두사·미노타우로스·크루가 10%";
            case BROOM -> "§7/그물상점 에서 구매";
            case DRAGON -> "§7용기사 전직 보상 · 적룡 처치 10%";
            default -> sp.grade.capture > 0
                    ? "§7그물총 포획 §f" + Math.round(sp.grade.capture * 50) + "~" + Math.round(Math.min(0.95, sp.grade.capture * 1.5) * 100) + "%"
                    : "§8야생 포획 불가";
        };
    }

    private void fillMounts(Player p, Holder h) {
        Species[] all = Species.values();
        // 높은 등급부터
        List<Species> list = new ArrayList<>(List.of(all));
        list.sort((a, b) -> b.grade.ordinal() - a.grade.ordinal());
        int i = 0;
        for (Species sp : list) {
            if (i >= SLOTS.length) break;
            List<String> lore = new ArrayList<>();
            lore.add("§8━━━━━━━━━━━━━━");
            lore.add("§7등급: " + sp.grade.display());
            lore.add("§7속도: §f" + String.format("%.1f", sp.speed * 20) + " 블록/초" + (sp.fly ? " §b(비행)" : ""));
            if (!sp.fly && sp.jump > 0) lore.add("§7점프: §f" + sp.jump);
            lore.add("§7얻는 법: " + mountHow(sp));
            if (sp.model != null) lore.add("§e★ 전용 모델");
            if (sp == Species.DRAGON) lore.add("§c타고 좌클릭: 화염 숨결");
            lore.add("");
            lore.add("§a▶ 클릭: 3D 모델 보기");
            h.inv.setItem(SLOTS[i], icon(mountIcon(sp), sp.grade.color + "§l" + sp.korean, lore));
            h.actions.put(SLOTS[i], () -> previewMount(p, sp));
            i++;
        }
    }

    private static Material petIcon(PetType t) {
        return switch (t.weapon) {
            case SWORD -> Material.IRON_SWORD;
            case GATLING -> Material.CROSSBOW;
            case SNIPER -> Material.SPYGLASS;
            case PISTOL -> Material.TRIPWIRE_HOOK;
            case SHIELD -> Material.SHIELD;
            default -> Material.CROSSBOW;
        };
    }

    private void fillPets(Player p, Holder h) {
        int i = 0;
        for (PetType t : PetType.values()) {
            List<String> lore = new ArrayList<>();
            lore.add("§8━━━━━━━━━━━━━━");
            lore.add("§7무기: §f" + t.weapon.korean);
            lore.add("§7한 발 피해: §c" + t.weapon.damage + (t.weapon.shots > 1 ? " §7x " + t.weapon.shots + "발" : ""));
            if (t.weapon.range > 0) lore.add("§7사거리: §f" + (int) t.weapon.range + " 블록");
            if (t.transforms()) lore.add("§7전투 시 변신: " + t.color + t.combatName);
            lore.add("§7얻는 법: §f/뽑기 §7(펫 뽑기)");
            lore.add("");
            lore.add("§a▶ 클릭: 3D 모델 보기");
            if (t.transforms()) lore.add("§a▶ 쉬프트+클릭: 전투 모습 보기");
            h.inv.setItem(SLOTS[i], icon(petIcon(t), t.color + "§l" + t.normalName, lore));
            final int slot = SLOTS[i];
            h.actions.put(slot, () -> previewModel(p, h.lastShift ? t.combatModel : t.normalModel, t.color + t.normalName, EntityType.ARMOR_STAND));
            i++;
        }
    }

    private void fillMobs(Player p, Holder h) {
        int i = 0;
        for (Mob m : MOBS) {
            List<String> lore = new ArrayList<>();
            lore.add("§8━━━━━━━━━━━━━━");
            lore.add("§7분류: " + m.kind);
            lore.add("§7체력: §c" + String.format("%,d", m.hp));
            lore.add(m.dmg > 0 ? "§7공격력: §6" + m.dmg : "§7공격력: §8없음 (지원형)");
            lore.add("§7" + m.note);
            lore.add("");
            lore.add("§a▶ 클릭: 3D 모델 보기");
            h.inv.setItem(SLOTS[i], icon(m.icon, m.name, lore));
            h.actions.put(SLOTS[i], () -> previewModel(p, m.model, m.name, EntityType.ARMOR_STAND));
            i++;
        }
    }

    // ------------------------------------------------------------------ 3D 미리보기

    private record Preview(Entity entity, BukkitTask spin, BukkitTask end) {}

    private boolean ready(Player p) {
        if (!plugin.hasModels()) { p.sendMessage(StarRPG.P + "§c모델 플러그인이 없어서 미리보기를 쓸 수 없어요."); return false; }
        long now = System.currentTimeMillis();
        Long last = cooldown.get(p.getUniqueId());
        if (last != null && now - last < 3000) { p.sendActionBar("§c잠시 뒤에 다시 눌러 주세요."); return false; }
        cooldown.put(p.getUniqueId(), now);
        return true;
    }

    private Location spot(Player p) {
        Vector dir = p.getLocation().getDirection().setY(0);
        if (dir.lengthSquared() < 1e-4) dir = new Vector(0, 0, 1);
        dir.normalize();
        Location at = p.getLocation().add(dir.multiply(5));
        World w = at.getWorld();
        // 발밑 땅 찾기 (3칸 위 ~ 6칸 아래)
        int x = at.getBlockX(), z = at.getBlockZ(), y = at.getBlockY() + 3;
        for (int k = 0; k < 9 && y > w.getMinHeight(); k++, y--) {
            if (w.getBlockAt(x, y - 1, z).getType().isSolid() && !w.getBlockAt(x, y, z).getType().isSolid()) break;
        }
        Location loc = new Location(w, x + 0.5, y, z + 0.5);
        loc.setYaw(p.getLocation().getYaw() + 180);   // 플레이어를 바라본다
        return loc;
    }

    private Entity spawnBase(Location at, EntityType type) {
        Entity e = at.getWorld().spawnEntity(at, type);
        e.addScoreboardTag(TAG);
        e.setPersistent(false);
        e.setInvulnerable(true);
        e.setSilent(true);
        if (e instanceof ArmorStand as) {
            as.setInvisible(true);
            as.setGravity(false);
            as.setBasePlate(false);
        }
        if (e instanceof LivingEntity le) {
            le.setAI(false);
            le.setCollidable(false);
            le.setRemoveWhenFarAway(true);
        }
        return e;
    }

    private void start(Player p, Entity e, String name) {
        stop(p.getUniqueId());
        final float[] yaw = {e.getLocation().getYaw()};
        BukkitTask spin = Bukkit.getScheduler().runTaskTimer(plugin, () -> {
            if (!e.isValid()) return;
            yaw[0] += 3f;
            e.setRotation(yaw[0], 0);
        }, 40L, 1L);
        BukkitTask end = Bukkit.getScheduler().runTaskLater(plugin, () -> stop(p.getUniqueId()), PREVIEW_TICKS);
        previews.put(p.getUniqueId(), new Preview(e, spin, end));
        p.closeInventory();
        p.playSound(p.getLocation(), Sound.BLOCK_ENCHANTMENT_TABLE_USE, 0.8f, 1.3f);
        p.sendMessage(StarRPG.P + name + " §7모델이 앞에 나타났어요. §8(15초)");
        e.getWorld().spawnParticle(org.bukkit.Particle.END_ROD, e.getLocation().add(0, 1, 0), 40, 1, 1, 1, 0.05);
    }

    private void previewModel(Player p, String model, String name, EntityType base) {
        if (!ready(p)) return;
        Entity e = spawnBase(spot(p), base);
        plugin.applyModelId(e, model);
        start(p, e, name);
    }

    private void previewMount(Player p, Species sp) {
        if (!ready(p)) return;
        Entity e = spawnBase(spot(p), sp.type);
        if (sp.model != null) plugin.applyModel(e, sp);
        start(p, e, sp.grade.color + sp.korean);
    }

    void stop(UUID id) {
        Preview pv = previews.remove(id);
        if (pv == null) return;
        pv.spin.cancel();
        pv.end.cancel();
        if (pv.entity.isValid()) {
            pv.entity.getWorld().spawnParticle(org.bukkit.Particle.CLOUD, pv.entity.getLocation().add(0, 1, 0), 20, 0.8, 0.8, 0.8, 0.02);
            pv.entity.remove();
        }
    }

    void stopAll() {
        for (UUID id : new ArrayList<>(previews.keySet())) stop(id);
    }

    /** 서버가 꺼질 때 남은 미리보기 몹 정리 */
    static void cleanup() {
        for (World w : Bukkit.getWorlds())
            for (Entity e : w.getEntities())
                if (e.getScoreboardTags().contains(TAG)) e.remove();
    }

    // ------------------------------------------------------------------ 이벤트

    @EventHandler
    public void onClick(InventoryClickEvent e) {
        if (!(e.getInventory().getHolder() instanceof Holder h)) return;
        e.setCancelled(true);
        if (!(e.getWhoClicked() instanceof Player) || e.getClickedInventory() != e.getInventory()) return;
        Runnable r = h.actions.get(e.getRawSlot());
        if (r == null) return;
        h.lastShift = e.isShiftClick();
        r.run();
    }

    @EventHandler
    public void onDrag(InventoryDragEvent e) {
        if (e.getInventory().getHolder() instanceof Holder) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInteract(PlayerInteractEntityEvent e) {
        if (e.getRightClicked().getScoreboardTags().contains(TAG)) e.setCancelled(true);   // 타거나 그물로 잡지 못하게
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInteractAt(PlayerInteractAtEntityEvent e) {
        if (e.getRightClicked().getScoreboardTags().contains(TAG)) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent e) {
        if (e.getEntity().getScoreboardTags().contains(TAG)) e.setCancelled(true);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        stop(e.getPlayer().getUniqueId());
        cooldown.remove(e.getPlayer().getUniqueId());
    }
}
