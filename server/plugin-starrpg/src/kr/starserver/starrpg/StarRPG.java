package kr.starserver.starrpg;

import net.milkbowl.vault.economy.Economy;
import org.bukkit.*;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.*;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.*;
import org.bukkit.event.player.AsyncPlayerPreLoginEvent;
import org.bukkit.event.player.PlayerAnimationEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.world.EntitiesLoadEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.ShapedRecipe;
import org.bukkit.inventory.ShapelessRecipe;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.RegisteredServiceProvider;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.util.Vector;

import java.io.File;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;

@SuppressWarnings("deprecation")
public class StarRPG extends JavaPlugin implements Listener {

    static final String P = "§d[별빛] §f";
    private static final int NET_GUN_PRICE = 4500;
    private static final int NET_PACK_PRICE = 600;
    private static final int NET_PACK_SIZE = 8;
    private static final int BROOM_PRICE = 10_000_000;

    private NamespacedKey KIND, SPECIES, OWNER, NETSHOT, DRAGONFIRE;
    private final Map<UUID, Long> gunCooldown = new HashMap<>();
    private final Map<UUID, Long> fireCooldown = new HashMap<>();
    private Economy economy;
    private boolean models;
    Dex dex;
    boolean hasModels() { return models; }
    private PackServer pack;
    private Pets pets;
    private Gacha gacha;
    private Rpg rpg;
    private Quests quests;
    private Gear gear;
    Menu menu;
    private final Map<UUID, Long> noFall = new HashMap<>();
    private final Map<UUID, String> joinHost = new ConcurrentHashMap<>();

    @Override
    public void onEnable() {
        KIND = new NamespacedKey(this, "kind");
        SPECIES = new NamespacedKey(this, "species");
        OWNER = new NamespacedKey(this, "owner");
        NETSHOT = new NamespacedKey(this, "netshot");
        DRAGONFIRE = new NamespacedKey(this, "dragonfire");

        getServer().getPluginManager().registerEvents(this, this);
        pets = new Pets(this);
        getServer().getPluginManager().registerEvents(pets, this);
        gacha = new Gacha(this, pets, v -> economy);
        getServer().getPluginManager().registerEvents(gacha, this);
        rpg = new Rpg(this, pets);
        getServer().getPluginManager().registerEvents(rpg, this);
        quests = new Quests(this, gacha, v -> economy);
        getServer().getPluginManager().registerEvents(quests, this);
        getServer().getPluginManager().registerEvents(new MapGuard(this), this);
        gear = new Gear(this);
        getServer().getPluginManager().registerEvents(gear, this);
        dex = new Dex(this);
        getServer().getPluginManager().registerEvents(dex, this);
        Dex.cleanup();
        menu = new Menu(this);
        getServer().getPluginManager().registerEvents(menu, this);
        if (getServer().getPluginManager().getPlugin("PlaceholderAPI") != null) {
            try { new RpgPapi(rpg).register(); getLogger().info("PlaceholderAPI 연동: %starrpg_...%"); }
            catch (Throwable t) { getLogger().warning("PlaceholderAPI 연동 실패: " + t); }
        }
        registerRecipes();
        loadDungeonWorld();
        if (getServer().getPluginManager().getPlugin("Vault") != null) {
            RegisteredServiceProvider<Economy> rsp = getServer().getServicesManager().getRegistration(Economy.class);
            if (rsp != null) economy = rsp.getProvider();
        }
        Bukkit.getScheduler().runTaskTimer(this, this::tickRiders, 1L, 1L);
        getConfig().addDefault("resource-pack.enabled", true);
        getConfig().addDefault("resource-pack.port", 8163);
        getConfig().addDefault("resource-pack.file", "plugins/BetterModel/build.zip");
        getConfig().addDefault("resource-pack.public-host", "");
        getConfig().addDefault("resource-pack.public-url", "");
        getConfig().addDefault("resource-pack.required", false);
        getConfig().options().copyDefaults(true);
        saveConfig();
        models = getServer().getPluginManager().getPlugin("BetterModel") != null;
        if (getConfig().getBoolean("resource-pack.enabled")) {
            pack = new PackServer(new File(getConfig().getString("resource-pack.file")), new File(getDataFolder(), "pack-extra"),
                    new File(getDataFolder(), "pack-merged.zip"), getConfig().getInt("resource-pack.port"), getLogger());
            try { pack.start(); } catch (Exception ex) { getLogger().warning("리소스팩 서버 시작 실패: " + ex.getMessage()); pack = null; }
        }
        getLogger().info("탈것/그물총 플러그인 활성화 (경제: " + (economy != null ? economy.getName() : "없음") + ")");
    }

    @Override
    public void onDisable() {
        if (pack != null) pack.stop();
        if (dex != null) dex.stopAll();
        Dex.cleanup();
    }

    // =====================================================================
    // 리소스팩 / 모델
    // =====================================================================

    @EventHandler
    public void onPreLogin(AsyncPlayerPreLoginEvent e) {
        String host = e.getHostname();
        if (host == null) return;
        host = host.split("\u0000")[0];
        if (host.startsWith("[")) host = host.substring(1, host.indexOf(']') > 0 ? host.indexOf(']') : host.length());
        else if (host.contains(":")) host = host.substring(0, host.lastIndexOf(':'));
        joinHost.put(e.getUniqueId(), host);
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        if (pack == null) return;
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(this, () -> sendPack(p), 20L);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        joinHost.remove(e.getPlayer().getUniqueId());
    }

    private void sendPack(Player p) {
        if (!p.isOnline() || pack == null) return;
        reloadConfig();   // upload-pack.sh가 바꾼 주소를 바로 반영
        byte[] sha1 = pack.sha1();
        if (sha1 == null) { getLogger().warning("리소스팩 파일이 없습니다: " + getConfig().getString("resource-pack.file")); return; }
        String joined = joinHost.getOrDefault(p.getUniqueId(), "localhost");
        String base;
        String publicUrl = getConfig().getString("resource-pack.public-url", "");
        boolean local = joined.equals("localhost") || joined.startsWith("127.") || joined.startsWith("192.168.")
                || joined.startsWith("10.") || joined.startsWith("172.");
        if (!local && publicUrl != null && !publicUrl.isBlank()) {
            base = publicUrl.endsWith("/") ? publicUrl.substring(0, publicUrl.length() - 1) : publicUrl;  // 외부 접속자: 터널 주소
        } else {
            String host = getConfig().getString("resource-pack.public-host", "");
            if (host == null || host.isBlank() || local) host = joined;
            base = "http://" + host + ":" + pack.port();
        }
        // public-url이 .zip 파일 주소면(외부 호스팅) 그대로 쓴다. 해시는 로컬 파일과 같아야 한다.
        String url = (!local && publicUrl != null && publicUrl.toLowerCase().endsWith(".zip"))
                ? publicUrl
                : base + "/pack.zip?v=" + HexFormat.of().formatHex(sha1, 0, 4);
        p.setResourcePack(url, sha1, "§d별빛 서버 §f전용 몹/탈것 모델입니다. §e수락해야 커스텀 모델이 보여요!",
                getConfig().getBoolean("resource-pack.required"));
    }

    void applyModel(Entity e, Species sp) {
        if (!models || sp == null || sp.model == null) return;
        try {
            boolean keep = sp == Species.HORSE || sp == Species.WOLF || sp == Species.FOX;   // 장식만 있는 모델
            if (!ModelHook.attachScaled(e, sp.model, keep)) getLogger().warning("모델을 찾을 수 없음: " + sp.model);
        } catch (Throwable t) {
            getLogger().warning("모델 적용 실패 (" + sp.model + "): " + t);
        }
    }

    // ----- Pets에서 쓰는 도우미 -----
    void applyModelId(Entity e, String modelId) {
        if (!models || modelId == null) return;
        try {
            if (!ModelHook.attach(e, modelId)) getLogger().warning("모델을 찾을 수 없음: " + modelId);
        } catch (Throwable t) { getLogger().warning("모델 적용 실패 (" + modelId + "): " + t); }
    }

    void swapModel(Entity e, String from, String to) {
        if (!models) return;
        try { ModelHook.swap(e, from, to); } catch (Throwable t) { getLogger().warning("모델 교체 실패: " + t); }
    }

    void animateModel(Entity e, String modelId, String anim) {
        if (!models) return;
        try { ModelHook.animate(e, modelId, anim); } catch (Throwable ignored) { }
    }

    boolean isMountEntity(Entity e) { return isMount(e); }

    Rpg rpg() { return rpg; }

    boolean questDone(Player p, String id) { return quests != null && quests.done(p, id); }

    double balance(Player p) { return economy == null ? 0 : economy.getBalance(p); }

    String titleOf(Player p) { return quests == null ? "" : quests.title(p); }

    void noFall(Player p, int ticks) { noFall.put(p.getUniqueId(), System.currentTimeMillis() + ticks * 50L); }

    long noFallUntil(Player p) { return noFall.getOrDefault(p.getUniqueId(), 0L); }

    void tagSkillProjectile(Projectile proj, double dmg, double radius) { rpg.tagProjectile(proj, dmg, radius); }

    void giveItem(Player p, ItemStack it) { give(p, it); }

    @EventHandler
    public void onEntitiesLoad(EntitiesLoadEvent e) {
        if (!models) return;
        for (Entity en : e.getEntities()) {
            if (isMount(en) && speciesOf(en) == null) {   // 삭제된 탈것(드래곤·페가수스·그리핀·워그)은 정리
                Bukkit.getScheduler().runTask(this, en::remove);
                continue;
            }
            if (isMount(en)) {
                Species sp = speciesOf(en);
                Bukkit.getScheduler().runTask(this, () -> { if (en.isValid()) applyModel(en, sp); });
            }
        }
    }

    // =====================================================================
    // 아이템
    // =====================================================================

    private ItemStack tagged(Material mat, String kind, String name, List<String> lore) {
        ItemStack it = new ItemStack(mat);
        ItemMeta m = it.getItemMeta();
        m.setDisplayName(name);
        m.setLore(lore);
        m.getPersistentDataContainer().set(KIND, PersistentDataType.STRING, kind);
        m.addItemFlags(ItemFlag.HIDE_ATTRIBUTES, ItemFlag.HIDE_UNBREAKABLE, ItemFlag.HIDE_ADDITIONAL_TOOLTIP);
        it.setItemMeta(m);
        return it;
    }

    public ItemStack netGun() {
        ItemStack it = tagged(Material.CROSSBOW, "netgun", "§6§l⌖ 그물총", List.of(
                "§7우클릭으로 그물을 발사해 생물을 포획한다.",
                "§7대상의 §c체력을 깎을수록 §7포획 확률이 올라간다.",
                "",
                "§8탄약: 그물 (인벤토리에 있어야 함)"));
        ItemMeta m = it.getItemMeta();
        m.setUnbreakable(true);
        it.setItemMeta(m);
        return it;
    }

    public ItemStack nets(int amount) {
        ItemStack it = tagged(Material.COBWEB, "net", "§f그물", List.of("§7그물총의 탄약."));
        it.setAmount(amount);
        return it;
    }

    public ItemStack capsule(Species sp) {
        Material mat = sp == Species.WHALE ? Material.SQUID_SPAWN_EGG : sp == Species.BROOM ? Material.ALLAY_SPAWN_EGG
                : sp == Species.DRAGON ? Material.ENDER_DRAGON_SPAWN_EGG
                : Optional.ofNullable(Material.matchMaterial(sp.type.name() + "_SPAWN_EGG")).orElse(Material.EGG);
        String grade = sp.grade.display();
        ItemStack it = tagged(mat, "capsule", (sp.legendary() ? sp.grade.color + "§l✦ " : sp.grade.color) + "포획 캡슐 §7- §f" + sp.korean, List.of(
                "§7등급: " + grade,
                "§7속도: §f" + String.format("%.0f", sp.speed * 20) + " 블록/초",
                "§7이동: §f" + (sp.fly ? "비행" : "육지"),
                "",
                "§e블록에 우클릭: §f꺼내기",
                "§e탈것 우클릭: §f타기",
                "§eShift+우클릭: §f캡슐로 되돌리기"));
        ItemMeta m = it.getItemMeta();
        m.getPersistentDataContainer().set(SPECIES, PersistentDataType.STRING, sp.name());
        it.setItemMeta(m);
        return it;
    }

    private String kind(ItemStack it) {
        if (it == null || !it.hasItemMeta()) return null;
        return it.getItemMeta().getPersistentDataContainer().get(KIND, PersistentDataType.STRING);
    }


    private void give(Player p, ItemStack it) {
        p.getInventory().addItem(it).values().forEach(left -> p.getWorld().dropItemNaturally(p.getLocation(), left));
    }

    private void registerRecipes() {
        ShapedRecipe gun = new ShapedRecipe(new NamespacedKey(this, "netgun"), netGun());
        gun.shape(" I ", "SCS", " I ");
        gun.setIngredient('I', Material.IRON_INGOT);
        gun.setIngredient('S', Material.STRING);
        gun.setIngredient('C', Material.CROSSBOW);
        Bukkit.addRecipe(gun);

        ShapelessRecipe net = new ShapelessRecipe(new NamespacedKey(this, "nets"), nets(4));
        net.addIngredient(3, Material.STRING);
        net.addIngredient(Material.SLIME_BALL);
        Bukkit.addRecipe(net);
    }

    // =====================================================================
    // 탈것 상태
    // =====================================================================

    private Species speciesOf(Entity e) {
        String s = e.getPersistentDataContainer().get(SPECIES, PersistentDataType.STRING);
        if (s == null) return null;
        try { return Species.valueOf(s); } catch (IllegalArgumentException ex) { return null; }
    }

    private UUID ownerOf(Entity e) {
        String s = e.getPersistentDataContainer().get(OWNER, PersistentDataType.STRING);
        return s == null ? null : UUID.fromString(s);
    }

    private boolean isMount(Entity e) {
        return e != null && e.getPersistentDataContainer().has(OWNER, PersistentDataType.STRING);
    }

    private LivingEntity spawnMount(Species sp, Location loc, Player owner) {
        Entity raw = loc.getWorld().spawnEntity(loc, sp.type);
        if (!(raw instanceof LivingEntity le)) { raw.remove(); return null; }
        PersistentDataContainer pdc = le.getPersistentDataContainer();
        pdc.set(OWNER, PersistentDataType.STRING, owner.getUniqueId().toString());
        pdc.set(SPECIES, PersistentDataType.STRING, sp.name());

        le.setCustomName(sp.grade.color + "[" + sp.grade.korean + "] §f" + owner.getName() + "의 " + sp.grade.color + sp.korean);
        le.setCustomNameVisible(true);
        le.setPersistent(true);
        le.setRemoveWhenFarAway(false);
        AttributeInstance scale = le.getAttribute(Attribute.SCALE);
        if (scale != null) scale.setBaseValue(sp.scale);

        if (le instanceof Mob mob) { mob.setTarget(null); mob.setAware(false); }
        if (le instanceof Ageable ag) ag.setAdult();
        if (le instanceof Breedable br) br.setAgeLock(true);
        if (le instanceof Tameable t) { t.setTamed(true); t.setOwner(owner); }
        if (sp == Species.HORSE && le instanceof org.bukkit.entity.Horse h) h.getInventory().setSaddle(new ItemStack(Material.SADDLE));
        if (le instanceof Phantom ph) {
            ph.setShouldBurnInDay(false);
            ph.setSize(2);
        }
        le.setGravity(!(le instanceof Phantom) && !(le instanceof Bee));
        applyModel(le, sp);
        return le;
    }

    // =====================================================================
    // 그물총
    // =====================================================================

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteract(PlayerInteractEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        Player p = e.getPlayer();
        ItemStack hand = e.getItem();
        String kind = kind(hand);
        if (kind == null) return;
        boolean right = e.getAction() == Action.RIGHT_CLICK_AIR || e.getAction() == Action.RIGHT_CLICK_BLOCK;
        if (!right) return;

        switch (kind) {
            case "netgun" -> { e.setCancelled(true); fireNet(p); }
            case "capsule" -> {
                e.setCancelled(true);
                if (e.getAction() != Action.RIGHT_CLICK_BLOCK || e.getClickedBlock() == null) {
                    p.sendActionBar("§e블록을 우클릭하면 탈것을 꺼냅니다.");
                    return;
                }
                Species sp = Species.byName(hand.getItemMeta().getPersistentDataContainer().get(SPECIES, PersistentDataType.STRING));
                if (sp == null) return;
                Block b = e.getClickedBlock().getRelative(e.getBlockFace() == null ? BlockFace.UP : e.getBlockFace());
                Location loc = b.getLocation().add(0.5, 0.1, 0.5);
                loc.setYaw(p.getYaw());
                if (spawnMount(sp, loc, p) != null) {
                    hand.setAmount(hand.getAmount() - 1);
                    p.getWorld().spawnParticle(Particle.CLOUD, loc, 30, 0.5, 0.5, 0.5, 0.05);
                    p.playSound(loc, Sound.ENTITY_ITEM_PICKUP, 1f, 0.6f);
                    p.sendMessage(P + "§f" + sp.korean + "§7을(를) 꺼냈습니다. §e우클릭§7으로 타고, §eShift+우클릭§7으로 회수하세요.");
                }
            }
            case "net" -> { /* 설치 방지는 BlockPlaceEvent에서 */ }
        }
    }

    private void fireNet(Player p) {
        long now = System.currentTimeMillis();
        if (gunCooldown.getOrDefault(p.getUniqueId(), 0L) > now) return;
        gunCooldown.put(p.getUniqueId(), now + 1000);

        if (p.getGameMode() != GameMode.CREATIVE) {
            ItemStack ammo = null;
            for (ItemStack it : p.getInventory().getContents()) {
                if ("net".equals(kind(it))) { ammo = it; break; }
            }
            if (ammo == null) {
                p.sendActionBar("§c그물이 없습니다! §7(실 3 + 슬라임볼 → 그물 4개, 또는 /그물상점)");
                p.playSound(p.getLocation(), Sound.BLOCK_DISPENSER_FAIL, 1f, 1.2f);
                return;
            }
            ammo.setAmount(ammo.getAmount() - 1);
        }
        Snowball shot = p.launchProjectile(Snowball.class, p.getLocation().getDirection().multiply(2.2));
        shot.setItem(new ItemStack(Material.COBWEB));
        shot.getPersistentDataContainer().set(NETSHOT, PersistentDataType.BYTE, (byte) 1);
        p.playSound(p.getLocation(), Sound.ITEM_CROSSBOW_SHOOT, 1f, 1.3f);
    }

    @EventHandler
    public void onNetHit(ProjectileHitEvent e) {
        Projectile proj = e.getEntity();
        if (!proj.getPersistentDataContainer().has(NETSHOT, PersistentDataType.BYTE)) return;
        if (!(proj.getShooter() instanceof Player p)) return;
        Entity hit = e.getHitEntity();
        proj.remove();
        e.setCancelled(true);
        if (!(hit instanceof LivingEntity target) || hit instanceof Player || hit instanceof ArmorStand) return;

        Location loc = target.getLocation();
        if (isMount(target)) { p.sendActionBar("§c이미 주인이 있는 탈것입니다."); return; }
        Species sp = Species.wild(target.getType());
        if (sp == null) { p.sendActionBar("§c이 생물은 포획할 수 없습니다. §7(/탈것도감)"); return; }
        double max = target.getAttribute(Attribute.MAX_HEALTH).getValue();
        if (max > 150) { p.sendActionBar("§c너무 강력해서 그물이 통하지 않는다!"); return; }

        double ratio = Math.max(0, Math.min(1, target.getHealth() / max));
        double chance = Math.min(0.95, sp.capture * (0.5 + (1 - ratio)));
        String pct = String.format("%.0f%%", chance * 100);
        loc.getWorld().spawnParticle(Particle.BLOCK, loc.clone().add(0, 0.8, 0), 40, 0.5, 0.5, 0.5, Material.COBWEB.createBlockData());

        if (ThreadLocalRandom.current().nextDouble() < chance) {
            target.remove();
            give(p, capsule(sp));
            loc.getWorld().spawnParticle(Particle.HAPPY_VILLAGER, loc.clone().add(0, 0.8, 0), 25, 0.5, 0.5, 0.5);
            p.playSound(loc, Sound.ENTITY_PLAYER_LEVELUP, 1f, 1.5f);
            p.sendMessage(P + "§a포획 성공! " + sp.grade.display() + " §f" + sp.korean + " §7(확률 " + pct + ")");
            if (sp.grade.ordinal() >= Species.Grade.HERO.ordinal())
                Bukkit.broadcastMessage(P + "§c§l✦ " + p.getName() + "님이 " + sp.grade.display() + " §f탈것 §c§l" + sp.korean + "§f을(를) 포획했습니다! ✦");
        } else {
            p.playSound(loc, Sound.ENTITY_ITEM_BREAK, 1f, 0.8f);
            p.sendMessage(P + "§c그물이 찢어졌다... §7(" + sp.grade.display() + " §7" + sp.korean + ", 확률 " + pct + ") §8체력을 깎을수록 확률이 올라갑니다.");
        }
    }

    // =====================================================================
    // 타기 / 회수
    // =====================================================================

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteractEntity(PlayerInteractEntityEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        Player p = e.getPlayer();
        Entity t = e.getRightClicked();
        if ("capsule".equals(kind(p.getInventory().getItemInMainHand()))) e.setCancelled(true);
        if (!isMount(t)) return;
        e.setCancelled(true);
        Species sp = speciesOf(t);
        if (sp == null) return;
        if (!p.getUniqueId().equals(ownerOf(t)) && !p.hasPermission("starrpg.admin")) {
            p.sendActionBar("§c다른 사람의 탈것입니다.");
            return;
        }
        if (p.isSneaking()) {
            t.eject();
            t.remove();
            give(p, capsule(sp));
            p.playSound(p.getLocation(), Sound.ENTITY_ITEM_PICKUP, 1f, 1.4f);
            p.sendMessage(P + "§f" + sp.korean + "§7을(를) 캡슐로 회수했습니다.");
            return;
        }
        if (t.getPassengers().isEmpty()) {
            t.addPassenger(p);
            p.sendActionBar(sp.fly
                    ? "§eWASD §7이동 · §e바라보는 방향§7으로 비행 · §e스페이스 §7상승 · §eShift §7내리기"
                    : "§eWASD §7이동 · §e스페이스 §7점프 · §e달리기 §7가속 · §eShift §7내리기");
        }
    }

    private void tickRiders() {
        for (Player p : Bukkit.getOnlinePlayers()) {
            Entity v = p.getVehicle();
            if (!(v instanceof LivingEntity mount) || !isMount(v)) continue;
            Species sp = speciesOf(v);
            if (sp == null) continue;
            control(p, mount, sp);
        }
    }

    private void control(Player p, LivingEntity mount, Species sp) {
        Input in = p.getCurrentInput();
        float yaw = p.getYaw();
        mount.setRotation(yaw, sp.fly ? p.getPitch() * 0.5f : 0f);
        mount.setBodyYaw(yaw);

        double rad = Math.toRadians(yaw);
        Vector fwd = new Vector(-Math.sin(rad), 0, Math.cos(rad));
        Vector left = new Vector(Math.cos(rad), 0, Math.sin(rad));
        Vector move = new Vector();
        if (in.isForward()) move.add(fwd);
        if (in.isBackward()) move.subtract(fwd.clone().multiply(0.5));
        if (in.isLeft()) move.add(left.clone().multiply(0.6));
        if (in.isRight()) move.subtract(left.clone().multiply(0.6));
        double speed = sp.speed * (in.isSprint() ? 1.25 : 1.0);

        if (sp.fly) {
            mount.setGravity(false);
            Vector vel;
            if (in.isForward()) vel = p.getLocation().getDirection().multiply(speed);
            else vel = move.lengthSquared() > 0 ? move.normalize().multiply(speed * 0.5) : new Vector();
            if (in.isJump()) vel.setY(vel.getY() + 0.45);
            Vector cur = mount.getVelocity();
            mount.setVelocity(cur.multiply(0.25).add(vel.multiply(0.75)));
            if (sp == Species.WHALE && mount.getTicksLived() % 3 == 0) {
                mount.getWorld().spawnParticle(Particle.END_ROD, mount.getLocation().subtract(fwd.clone().multiply(2.5)).add(0, 0.6, 0), 2, 0.5, 0.3, 0.5, 0.01);
            }
            if (sp == Species.DRAGON && mount.getTicksLived() % 2 == 0) {
                mount.getWorld().spawnParticle(Particle.FLAME, mount.getLocation().subtract(fwd.clone().multiply(2.0)).add(0, 1.2, 0), 2, 0.4, 0.2, 0.4, 0.01);
            }
            if (sp == Species.BROOM && mount.getTicksLived() % 2 == 0) {
                mount.getWorld().spawnParticle(Particle.WITCH, mount.getLocation().subtract(fwd.clone().multiply(1.2)).add(0, 1.0, 0), 2, 0.1, 0.1, 0.1, 0.01);
            }
        } else {
            Vector cur = mount.getVelocity();
            Vector h = move.lengthSquared() > 0 ? move.normalize().multiply(speed) : new Vector();
            double y = cur.getY();
            boolean ground = mount.isOnGround();
            if (ground && in.isJump()) y = sp.jump;
            else if (ground && h.lengthSquared() > 0 && blockedAhead(mount, h)) y = 0.45;
            mount.setVelocity(new Vector(h.getX(), y, h.getZ()));
        }
    }

    private boolean blockedAhead(LivingEntity e, Vector dir) {
        Location front = e.getLocation().add(dir.clone().normalize().multiply(e.getWidth() / 2 + 0.4));
        Block b = front.getBlock();
        return b.getType().isSolid() && !b.getRelative(BlockFace.UP).getType().isSolid();
    }

    @EventHandler
    public void onDismount(EntityDismountEvent e) {
        Entity mount = e.getDismounted();
        if (!isMount(mount)) return;
        mount.setVelocity(new Vector());
        if (!(mount instanceof Phantom) && !(mount instanceof Bee)) mount.setGravity(true);
    }

    // 별빛 고래: 타고 있을 때 좌클릭 → 고래 울음 (주변 적 밀쳐내기)
    @EventHandler
    public void onSwing(PlayerAnimationEvent e) {
        Player p = e.getPlayer();
        Entity v = p.getVehicle();
        if (v == null || !isMount(v)) return;
        if (speciesOf(v) == Species.DRAGON) { dragonBreath(p, v); return; }
        if (speciesOf(v) != Species.WHALE) return;
        long now = System.currentTimeMillis();
        if (fireCooldown.getOrDefault(p.getUniqueId(), 0L) > now) return;
        fireCooldown.put(p.getUniqueId(), now + 4000);
        Location c = v.getLocation();
        c.getWorld().playSound(c, Sound.ENTITY_WARDEN_SONIC_BOOM, 0.6f, 1.6f);
        c.getWorld().spawnParticle(Particle.SONIC_BOOM, c.clone().add(0, 1, 0), 1);
        for (Entity en : v.getNearbyEntities(6, 4, 6)) {
            if (en instanceof Monster m) {
                m.damage(4, p);
                m.setVelocity(m.getLocation().toVector().subtract(c.toVector()).normalize().multiply(1.2).setY(0.5));
            }
        }
    }

    /** 흑룡: 타고 좌클릭 → 화염 숨결 (블록은 안 태움) */
    private void dragonBreath(Player p, Entity dragon) {
        long now = System.currentTimeMillis();
        if (fireCooldown.getOrDefault(p.getUniqueId(), 0L) > now) return;
        fireCooldown.put(p.getUniqueId(), now + 2500);
        Location eye = p.getEyeLocation();
        Vector dir = eye.getDirection();
        dragon.getWorld().playSound(dragon.getLocation(), Sound.ENTITY_ENDER_DRAGON_GROWL, 0.7f, 1.4f);
        for (int i = 1; i <= 10; i++) {
            Location at = eye.clone().add(dir.clone().multiply(i * 0.9));
            at.getWorld().spawnParticle(Particle.FLAME, at, 6, 0.25 + i * 0.05, 0.25 + i * 0.05, 0.25 + i * 0.05, 0.02);
            if (i % 3 == 0) at.getWorld().spawnParticle(Particle.LARGE_SMOKE, at, 2, 0.3, 0.3, 0.3, 0.01);
        }
        for (Entity en : dragon.getNearbyEntities(10, 6, 10)) {
            if (!(en instanceof Monster m)) continue;
            Vector to = m.getLocation().add(0, 1, 0).toVector().subtract(eye.toVector());
            if (to.length() > 10 || to.normalize().dot(dir) < 0.8) continue;
            m.damage(8, p);
            m.setFireTicks(80);
        }
    }

    @EventHandler
    public void onIgnite(BlockIgniteEvent e) {
        Entity src = e.getIgnitingEntity();
        if (src != null && src.getPersistentDataContainer().has(DRAGONFIRE, PersistentDataType.BYTE)) e.setCancelled(true);
    }

    // =====================================================================
    // 탈것 보호
    // =====================================================================

    @EventHandler(ignoreCancelled = true)
    public void onDamage(EntityDamageEvent e) {
        if (isMount(e.getEntity())) { e.setCancelled(true); return; }
        if (e.getEntity() instanceof Player p && e.getCause() == EntityDamageEvent.DamageCause.FALL && isMount(p.getVehicle())) {
            e.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onCombust(EntityCombustEvent e) {
        if (isMount(e.getEntity())) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onTarget(EntityTargetEvent e) {
        if (isMount(e.getEntity())) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent e) {
        if (kind(e.getItemInHand()) != null) e.setCancelled(true);
    }

    // =====================================================================
    // 보스 처치 시 전설 탈것 드롭
    // =====================================================================

    @EventHandler
    public void onDeath(EntityDeathEvent e) {
        LivingEntity dead = e.getEntity();
        String name = dead.getCustomName() == null ? "" : ChatColor.stripColor(dead.getCustomName());
        if (name.isEmpty() || isMount(dead)) return;
        // 보스 처치 시 펫 뽑기권 (40% 확률로 1~3장)
        if (name.matches(".*(적룡|미노타우로스|메두사|크루가|별의 기사|화염 군주|데몬 나이트|대마법사).*") && ThreadLocalRandom.current().nextDouble() < 0.4) {
            int k = 1 + ThreadLocalRandom.current().nextInt(3);
            dead.getWorld().dropItemNaturally(dead.getLocation(), gacha.ticket(k));
            Player kp = dead.getKiller();
            if (kp != null) kp.sendMessage(P + "§e펫 뽑기권 " + k + "장§f이 떨어졌습니다!");
        }
        Species drop = null;
        double chance = 0;
        if (name.contains("적룡") && ThreadLocalRandom.current().nextDouble() < 0.10) { drop = Species.DRAGON; chance = 1; }
        else if (name.contains("적룡")) { drop = Species.WHALE; chance = 0.30; }
        else if (name.contains("미노타우로스") || name.contains("메두사") || name.contains("크루가")) { drop = Species.WHALE; chance = 0.10; }
        if (drop == null || ThreadLocalRandom.current().nextDouble() >= chance) return;
        dead.getWorld().dropItemNaturally(dead.getLocation(), capsule(drop));
        Player killer = dead.getKiller();
        Bukkit.broadcastMessage(P + "§e§l✦ " + (killer != null ? killer.getName() + "님이 " : "") + drop.grade.display() + " §e§l탈것 " + drop.grade.color + "§l" + drop.korean + "§e§l 캡슐을 획득했습니다! ✦");
    }

    // =====================================================================
    // 명령어
    // =====================================================================

    @Override
    public boolean onCommand(CommandSender s, Command cmd, String label, String[] a) {
        switch (cmd.getName().toLowerCase(Locale.ROOT)) {
            case "starrpg" -> { return adminCommand(s, a); }
            case "netshop" -> { return shopCommand(s, a); }
            case "mountlist" -> { mountList(s); return true; }
            case "dex" -> { if (s instanceof Player pl) dex.open(pl, a.length > 0 ? a[0] : "mount"); return true; }
            case "petlist" -> { pets.listTo(s); return true; }
            case "packupload" -> { packUpload(s); return true; }
            case "rpgclass" -> { if (s instanceof Player pl) rpg.openClassMenu(pl); return true; }
            case "rpgskill" -> { if (s instanceof Player pl) rpg.showSkills(pl); return true; }
            case "rpginfo" -> {
                Player target = a.length > 0 ? Bukkit.getPlayerExact(a[0]) : (s instanceof Player pl ? pl : null);
                if (target == null) { s.sendMessage(P + "§c플레이어를 찾을 수 없어요."); return true; }
                rpg.showInfo(s, target);
                return true;
            }
            case "rpg" -> { return rpg.admin(s, a); }
            case "questlog" -> { if (s instanceof Player pl) quests.log(pl); return true; }
            case "questnpc" -> {
                if (a.length >= 6 && a[0].equals("배치") && s.hasPermission("starrpg.admin")) {   // /퀘스트npc 배치 <id> <world> <x> <y> <z>
                    World w = Bukkit.getWorld(a[2]);
                    if (w == null) { s.sendMessage(P + "§c월드 없음"); return true; }
                    Location at = new Location(w, Double.parseDouble(a[3]) + 0.5, Double.parseDouble(a[4]), Double.parseDouble(a[5]) + 0.5);
                    quests.spawnNpcAt(at, a[1]);
                    s.sendMessage(P + a[1] + " NPC 배치: " + a[2] + " " + a[3] + " " + a[4] + " " + a[5]);
                    return true;
                }
                if (a.length >= 3 && a[0].equals("완료") && s.hasPermission("starrpg.admin")) {   // /퀘스트npc 완료 <플레이어> <퀘스트id>
                    Player t = Bukkit.getPlayerExact(a[1]);
                    if (t != null) quests.forceComplete(t, a[2]);
                    return true;
                }
                if (a.length > 0 && (a[0].equals("스폰") || a[0].equalsIgnoreCase("spawn"))) {
                    World w = s instanceof Player pl ? pl.getWorld() : Bukkit.getWorlds().get(0);
                    s.sendMessage(P + "스폰 둘레에 NPC " + quests.spawnAllAtSpawn(w) + "명을 배치했어요.");
                } else if (s instanceof Player pl) {
                    if (a.length == 0) s.sendMessage(P + "/퀘스트npc <종류> §7또는 §f/퀘스트npc 스폰 §7(스폰에 전부 배치) · 종류: " + String.join(", ", Quests.NPCS.keySet()));
                    else quests.spawnNpc(pl, a[0].toLowerCase(Locale.ROOT));
                }
                return true;
            }
            case "worldquest" -> { return quests.worldCommand(s, a); }
            case "title" -> { if (s instanceof Player pl) quests.titleCommand(pl, a); return true; }
            case "gear" -> { gear.info(s); return true; }
            case "spawn" -> {
                if (!(s instanceof Player pl)) return true;
                pl.teleport(Bukkit.getWorlds().get(0).getSpawnLocation().add(0.5, 0, 0.5));
                pl.sendMessage(P + "스폰으로 이동했어요.");
                return true;
            }
            case "명령어" -> { helpKo(s); return true; }
            case "menu" -> { if (s instanceof Player pl) menu.open(pl); return true; }
            case "daily" -> { if (s instanceof Player pl) quests.openDaily(pl); return true; }
            case "gacha" -> {
                if (a.length > 0 && (a[0].equals("확률") || a[0].equalsIgnoreCase("info"))) { gacha.info(s); return true; }
                if (s instanceof Player pl) gacha.open(pl); else gacha.info(s);
                return true;
            }
        }
        return false;
    }

    private void helpKo(CommandSender s) {
        s.sendMessage("§d§l━━ 별빛서버 명령어 ━━ §7(Shift+F 또는 /메뉴 로 메뉴 열기)");
        s.sendMessage("§e기본 §f/메뉴 /명령어 /내정보 /도감");
        s.sendMessage("§e이동 §f/스폰 /집 /집설정 /집삭제 /돌아가기 /워프 /텔포 /텔포부르기 /수락 /거절");
        s.sendMessage("§e성장 §f/전직 /스킬 /능력치 /칭호 /이름꾸미기");
        s.sendMessage("§e퀘스트 §f/퀘스트 /월드퀘스트 /일일의뢰");
        s.sendMessage("§e전투·장비 §f/던전 §7(나가기: /던전 나가기) §f/대장간 /장비 /잡화점");
        s.sendMessage("§e도감 §f/도감 §7(탈것·펫·보스, 누르면 3D 모델) §f/장비도감 /물고기도감");
        s.sendMessage("§e펫·탈것 §f/뽑기 /뽑기 확률 /펫목록 /탈것도감 /그물상점");
        s.sendMessage("§e돈 §f/돈 /송금 /돈순위 /상점 /판매 /판매창 /키트");
        s.sendMessage("§e생활 §f/생활직업 /직업가입 /직업스탯 /생활스킬 /스탯 /마나");
        s.sendMessage("§e낚시 §f/낚시 /물고기판매 /낚시순위");
        s.sendMessage("§e대화 §f/귓 /답장 /메일 /접속자 /잠수 /음성채팅");
        if (s.hasPermission("starrpg.admin")) {
            s.sendMessage("§c관리 §f/관리 지급 /레벨관리 /능력치관리 /대장간관리 지급 /던전관리 /보물상자관리 /퀘스트npc");
            s.sendMessage("§c관리 §f/몹소환 /모델리로드 /팩업로드 /크리 /서바 /낮 /밤");
        }
    }

    private boolean adminCommand(CommandSender s, String[] a) {
        if (a.length >= 3) a[2] = switch (a[2]) {
            case "그물총" -> "netgun"; case "그물" -> "net"; case "뽑기권", "티켓" -> "ticket";
            default -> a[2].startsWith("펫:") ? "pet:" + a[2].substring(2) : a[2].startsWith("장비") ? "gear" + a[2].substring(2) : a[2];
        };
        if (a.length < 3 || !(a[0].equalsIgnoreCase("give") || a[0].equals("지급") || a[0].equals("주기"))) {
            s.sendMessage(P + "/관리 지급 <플레이어> <그물총|그물|뽑기권|탈것종류|펫:펫ID|장비:등급[:종류]> [개수]");
            s.sendMessage("§7(영어도 가능: /starrpg give <플레이어> <netgun|net|ticket|종류|pet:ID|gear:등급> [개수])");
            s.sendMessage("§7종류: " + String.join(", ", Arrays.stream(Species.values()).map(Enum::name).toList()));
            return true;
        }
        Player t = Bukkit.getPlayerExact(a[1]);
        if (t == null) { s.sendMessage(P + "§c플레이어를 찾을 수 없습니다."); return true; }
        int n = a.length >= 4 ? Math.max(1, Integer.parseInt(a[3])) : 1;
        ItemStack it;
        if (a[2].equalsIgnoreCase("ticket")) {
            it = gacha.ticket(Math.min(n, 64));
        } else if (a[2].toLowerCase(Locale.ROOT).startsWith("pet:")) {
            PetType pt = PetType.byName(a[2].substring(4));
            if (pt == null) { s.sendMessage(P + "§c알 수 없는 펫: " + a[2].substring(4) + " §7(/펫목록)"); return true; }
            it = pets.card(pt);
        } else if (a[2].toLowerCase(Locale.ROOT).startsWith("gear")) {
            it = gear.parse(a[2]);
            if (it == null) { s.sendMessage(P + "§cgear:<등급>[:종류] §7등급: COMMON RARE UNIQUE ANCIENT LEGEND HERO TRANSCEND MYTH (또는 일반~신화) · 종류: 검 도끼 활 석궁 삼지창 투구 갑옷 바지 신발"); return true; }
        } else if (a[2].equalsIgnoreCase("netgun")) it = netGun();
        else if (a[2].equalsIgnoreCase("net")) it = nets(n);
        else {
            Species sp = Species.byName(a[2]);
            if (sp == null) { s.sendMessage(P + "§c알 수 없는 종류: " + a[2]); return true; }
            it = capsule(sp);
        }
        if (!a[2].equalsIgnoreCase("net") && !a[2].equalsIgnoreCase("ticket")) it.setAmount(Math.min(n, it.getMaxStackSize()));
        give(t, it);
        s.sendMessage(P + t.getName() + "에게 지급했습니다.");
        return true;
    }

    /** /팩업로드: upload-pack.sh 실행 → 공개 주소 갱신 (비동기) */
    private void packUpload(CommandSender s) {
        File script = new File("upload-pack.sh").getAbsoluteFile();
        if (!script.isFile()) { s.sendMessage(P + "§c스크립트가 없습니다: " + script); return; }
        s.sendMessage(P + "§e리소스팩을 올리는 중... §7(잠시만요)");
        Bukkit.getScheduler().runTaskAsynchronously(this, () -> {
            if (pack != null) pack.bytes();   // 추가 모델을 합친 pack-merged.zip을 최신으로
            String out;
            int code;
            try {
                Process pr = new ProcessBuilder("/bin/zsh", script.getPath())
                        .directory(script.getParentFile()).redirectErrorStream(true).start();
                out = new String(pr.getInputStream().readAllBytes(), java.nio.charset.StandardCharsets.UTF_8).trim();
                code = pr.waitFor();
            } catch (Exception ex) {
                out = ex.toString();
                code = -1;
            }
            final String msg = out;
            final boolean ok = code == 0;
            Bukkit.getScheduler().runTask(this, () -> {
                reloadConfig();
                s.sendMessage(P + (ok ? "§a" : "§c") + msg);
                if (ok) s.sendMessage(P + "§7다음에 밖에서 접속하는 친구부터 새 팩을 받아요.");
                getLogger().info("팩업로드 (" + s.getName() + "): " + msg);
            });
        });
    }

    private boolean shopCommand(CommandSender s, String[] a) {
        if (!(s instanceof Player p)) return true;
        if (a.length == 0) {
            p.sendMessage("§d§m          §r §6§l그물 상점 §d§m          ");
            p.sendMessage("§e/그물상점 그물총 §7- §f그물총 §6" + NET_GUN_PRICE + "원");
            p.sendMessage("§e/그물상점 그물 §7- §f그물 " + NET_PACK_SIZE + "개 §6" + NET_PACK_PRICE + "원");
            p.sendMessage("§e/그물상점 빗자루 §7- §d마법 빗자루 §7(나는 탈것) §6" + String.format("%,d", BROOM_PRICE) + "원");
            p.sendMessage("§7제작: 실 3 + 슬라임볼 → 그물 4개 / 철 2 + 실 2 + 쇠뇌 → 그물총");
            return true;
        }
        if (economy == null) { p.sendMessage(P + "§c경제 플러그인이 연결되지 않았습니다."); return true; }
        int price;
        ItemStack item;
        if (a[0].equals("그물총") || a[0].equalsIgnoreCase("netgun")) { price = NET_GUN_PRICE; item = netGun(); }
        else if (a[0].equals("그물") || a[0].equalsIgnoreCase("net")) { price = NET_PACK_PRICE; item = nets(NET_PACK_SIZE); }
        else if (a[0].equals("빗자루") || a[0].equalsIgnoreCase("broom")) { price = BROOM_PRICE; item = capsule(Species.BROOM); }
        else { p.sendMessage(P + "§c/그물상점 그물총 · /그물상점 그물 · /그물상점 빗자루"); return true; }
        if (!economy.has(p, price)) {
            p.sendMessage(P + "§c돈이 부족합니다. §7(필요: " + price + "원, 보유: " + (long) economy.getBalance(p) + "원)");
            return true;
        }
        economy.withdrawPlayer(p, price);
        give(p, item);
        p.sendMessage(P + "§a구매 완료! §7(-" + price + "원)");
        return true;
    }

    private void mountList(CommandSender s) {
        s.sendMessage("§d§m        §r §b§l탈것 도감 §d§m        ");
        s.sendMessage("§7그물총으로 야생 동물을 맞히면 §f등급별 확률§7로 포획해요. §c체력이 낮을수록 확률↑ §8(기본의 50%~150%)");
        for (Species.Grade g : Species.Grade.values()) {
            StringBuilder sb = new StringBuilder();
            for (Species sp : Species.values()) {
                if (sp.grade != g) continue;
                sb.append("§f").append(sp.korean).append(sp.fly ? "§b(비행)" : "").append(sp.model != null ? "§e★" : "").append("§7, ");
            }
            if (sb.length() == 0) continue;
            sb.setLength(sb.length() - 4);
            String rate = g.capture > 0 ? "§7포획 " + Math.round(g.capture * 50) + "~" + Math.round(Math.min(0.95, g.capture * 1.5) * 100) + "%" : "§8포획 불가";
            s.sendMessage(g.display() + " §8| " + rate + " §8| " + sb);
        }
        s.sendMessage("§6전설: §f별빛 고래 §7(적룡 30%, 메두사·미노타우로스·크루가 10%) §8| §f마법 빗자루 §7(/그물상점 빗자루 " + String.format("%,d", BROOM_PRICE) + "원)");
        s.sendMessage("§5신화: §f흑룡 §7(용기사 전직 보상, 적룡 처치 10%) · 타고 좌클릭: 화염 숨결");
        s.sendMessage("§e★ §7= 전용 장식 모델 (왕관·갑옷 등)");
    }


    /** 던전 맵 월드를 모두 불러온다: 서버 폴더의 dungeon, dungeon_1 ~ dungeon_N */
    void loadDungeonWorld() {
        java.io.File[] dirs = getServer().getWorldContainer().listFiles(f -> f.isDirectory()
                && f.getName().matches("dungeon(_\\d+)?|parkour") && new java.io.File(f, "level.dat").exists());
        if (dirs == null) return;
        int n = 0;
        for (java.io.File d : dirs) {
            World w = Bukkit.getWorld(d.getName());
            if (w == null) w = new WorldCreator(d.getName()).createWorld();
            if (w == null) continue;
            w.setDifficulty(Bukkit.getWorlds().get(0).getDifficulty() == Difficulty.PEACEFUL ? Difficulty.NORMAL : Bukkit.getWorlds().get(0).getDifficulty());
            w.setGameRule(GameRule.DO_MOB_SPAWNING, false);
            w.setGameRule(GameRule.DO_DAYLIGHT_CYCLE, false);
            w.setGameRule(GameRule.DO_WEATHER_CYCLE, false);
            w.setGameRule(GameRule.KEEP_INVENTORY, true);
            w.setGameRule(GameRule.MOB_GRIEFING, false);
            w.setGameRule(GameRule.DO_FIRE_TICK, false);
            w.setKeepSpawnInMemory(false);
            if (d.getName().equals("parkour")) {     // 50층 탑 파쿠르: 낙하 피해 없음, 평화로움
                w.setDifficulty(Difficulty.PEACEFUL);
                w.setGameRule(GameRule.FALL_DAMAGE, false);
                w.setTime(6000);
            } else {
                w.getWorldBorder().setCenter(14, 23);
                w.getWorldBorder().setSize(260);
            }
            n++;
        }
        getLogger().info("던전 월드 " + n + "개를 불러왔어요.");
    }
}
