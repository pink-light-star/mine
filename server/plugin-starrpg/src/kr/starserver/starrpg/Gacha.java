package kr.starserver.starrpg;

import net.milkbowl.vault.economy.Economy;
import org.bukkit.*;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.scheduler.BukkitRunnable;

import java.util.*;
import java.util.concurrent.ThreadLocalRandom;
import java.util.function.Function;

/**
 * 펫 가챠: /가챠 로 창을 열고 1회/10회 뽑기.
 * 결과는 아래 POOL 표의 가중치대로 나온다 (펫 합계 4%, 나머지는 꽝).
 * 보상은 뽑는 순간 바로 지급되고, 창의 애니메이션은 연출만 담당한다.
 */
@SuppressWarnings("deprecation")
final class Gacha implements Listener {
    private static final String P = "§d[별빛] §f";
    static final int PRICE_1 = 30000;
    static final int PRICE_10 = 270000;
    /** 천장: 이 횟수째 뽑기까지 펫이 안 나오면 펫 확정 */
    static final int PITY = 40;

    /** 뽑기 결과 하나 */
    private record Reward(String id, String name, int weight, boolean pet, Material icon) {}

    // ===== 확률표: weight / 전체 합(15000) = 확률 =====
    //   펫 6마리 = 각 100 (0.67%) → 합계 600 (4%)
    //   꽝: 철 5개 10800 (72%), 다이아 1개 3600 (24%)
    private final List<Reward> POOL = List.of(
            new Reward("RICO", "§a§l세컨드 §7(전투: 리코)", 100, true, Material.NAME_TAG),
            new Reward("RAPI", "§c§l수영복 §7(전투: 라피)", 100, true, Material.NAME_TAG),
            new Reward("RED", "§4§l레드후드", 100, true, Material.NAME_TAG),
            new Reward("BLUE", "§9§l스노우화이트", 100, true, Material.NAME_TAG),
            new Reward("SILVER", "§7§l신데렐라", 100, true, Material.NAME_TAG),
            new Reward("PINK", "§d§l엘리스", 100, true, Material.NAME_TAG),
            new Reward("IRON", "§f꽝 §7- 철 주괴 5개", 10800, false, Material.IRON_INGOT),
            new Reward("DIAMOND", "§b꽝 §7- 다이아몬드 1개", 3600, false, Material.DIAMOND)
    );

    private final StarRPG plugin;
    private final Pets pets;
    private final Function<Void, Economy> eco;
    private final NamespacedKey KIND, PITY_KEY;
    private final Set<UUID> rolling = new HashSet<>();

    Gacha(StarRPG plugin, Pets pets, Function<Void, Economy> eco) {
        this.plugin = plugin;
        this.pets = pets;
        this.eco = eco;
        this.KIND = new NamespacedKey(plugin, "kind");
        this.PITY_KEY = new NamespacedKey(plugin, "gacha_pity");
    }

    private int totalWeight() {
        return POOL.stream().mapToInt(Reward::weight).sum();
    }

    private String pct(Reward r) {
        return String.format("%.2f%%", 100.0 * r.weight() / totalWeight());
    }

    /** 마지막으로 펫을 뽑은 뒤 지금까지 뽑은 횟수 (플레이어 데이터에 저장) */
    private int pityCount(Player p) {
        return p.getPersistentDataContainer().getOrDefault(PITY_KEY, PersistentDataType.INTEGER, 0);
    }

    private void setPity(Player p, int n) {
        p.getPersistentDataContainer().set(PITY_KEY, PersistentDataType.INTEGER, n);
    }

    private Reward randomPet() {
        List<Reward> petsOnly = POOL.stream().filter(Reward::pet).toList();
        int total = petsOnly.stream().mapToInt(Reward::weight).sum();
        int n = ThreadLocalRandom.current().nextInt(total);
        for (Reward r : petsOnly) {
            n -= r.weight();
            if (n < 0) return r;
        }
        return petsOnly.get(0);
    }

    private Reward roll() {
        int n = ThreadLocalRandom.current().nextInt(totalWeight());
        for (Reward r : POOL) {
            n -= r.weight();
            if (n < 0) return r;
        }
        return POOL.get(POOL.size() - 1);
    }

    // ------------------------------------------------------------------ 아이템

    ItemStack ticket(int amount) {
        ItemStack it = new ItemStack(Material.PAPER, amount);
        ItemMeta m = it.getItemMeta();
        m.setDisplayName("§e§l✦ 펫 뽑기권");
        m.setLore(List.of("§7/가챠 에서 돈 대신 사용됩니다.", "§71장 = 1회 뽑기"));
        m.getPersistentDataContainer().set(KIND, PersistentDataType.STRING, "gachaticket");
        m.setEnchantmentGlintOverride(true);
        it.setItemMeta(m);
        return it;
    }

    private int countTickets(Player p) {
        int n = 0;
        for (ItemStack it : p.getInventory().getContents()) {
            if (it != null && it.hasItemMeta()
                    && "gachaticket".equals(it.getItemMeta().getPersistentDataContainer().get(KIND, PersistentDataType.STRING))) {
                n += it.getAmount();
            }
        }
        return n;
    }

    private void takeTickets(Player p, int need) {
        for (ItemStack it : p.getInventory().getContents()) {
            if (need <= 0) return;
            if (it != null && it.hasItemMeta()
                    && "gachaticket".equals(it.getItemMeta().getPersistentDataContainer().get(KIND, PersistentDataType.STRING))) {
                int take = Math.min(need, it.getAmount());
                it.setAmount(it.getAmount() - take);
                need -= take;
            }
        }
    }

    private static ItemStack icon(Material mat, String name, String... lore) {
        ItemStack it = new ItemStack(mat);
        ItemMeta m = it.getItemMeta();
        m.setDisplayName(name);
        m.setLore(Arrays.asList(lore));
        m.addItemFlags(ItemFlag.values());
        it.setItemMeta(m);
        return it;
    }

    // ------------------------------------------------------------------ 메인 창

    private static final class MenuHolder implements InventoryHolder {
        Inventory inv;
        public Inventory getInventory() { return inv; }
    }

    private static final class RollHolder implements InventoryHolder {
        Inventory inv;
        public Inventory getInventory() { return inv; }
    }

    void open(Player p) {
        MenuHolder h = new MenuHolder();
        Inventory inv = Bukkit.createInventory(h, 54, "§5§l✦ 펫 뽑기 ✦");
        h.inv = inv;
        ItemStack pane = icon(Material.PURPLE_STAINED_GLASS_PANE, " ");
        for (int i = 0; i < 54; i++) inv.setItem(i, pane);
        // 결과 목록 (확률 표시)
        int[] slots = {10, 11, 12, 13, 14, 15, 16, 22};
        for (int i = 0; i < POOL.size() && i < slots.length; i++) {
            Reward r = POOL.get(i);
            inv.setItem(slots[i], icon(r.icon(), r.name(),
                    "§7확률: §e" + pct(r),
                    r.pet() ? "§7펫 카드가 지급됩니다." : "§8꽝"));
        }
        int tickets = countTickets(p);
        Economy e = eco.apply(null);
        String bal = e == null ? "?" : String.format("%,d", (long) e.getBalance(p));
        inv.setItem(39, icon(Material.GOLD_INGOT, "§e§l1회 뽑기",
                "§7가격: §6" + String.format("%,d", PRICE_1) + "원 §7또는 §e뽑기권 1장", "", "§a클릭해서 뽑기"));
        inv.setItem(41, icon(Material.GOLD_BLOCK, "§6§l10회 뽑기",
                "§7가격: §6" + String.format("%,d", PRICE_10) + "원 §7(10% 할인) 또는 §e뽑기권 10장", "", "§a클릭해서 뽑기"));
        int pity = pityCount(p);
        inv.setItem(40, icon(Material.BOOK, "§b§l내 정보",
                "§7보유 금액: §6" + bal + "원", "§7보유 뽑기권: §e" + tickets + "장", "",
                "§7천장: §d" + pity + " §7/ " + PITY + " §8(" + (PITY - pity) + "회 안에 펫 확정)", "",
                "§8뽑기권이 있으면 돈 대신 먼저 사용돼요."));
        p.openInventory(inv);
        p.playSound(p.getLocation(), Sound.BLOCK_ENDER_CHEST_OPEN, 0.7f, 1.2f);
    }

    @EventHandler
    public void onClick(InventoryClickEvent e) {
        InventoryHolder h = e.getInventory().getHolder();
        if (h instanceof RollHolder) { e.setCancelled(true); return; }
        if (!(h instanceof MenuHolder)) return;
        e.setCancelled(true);
        if (!(e.getWhoClicked() instanceof Player p)) return;
        if (e.getRawSlot() == 39) draw(p, 1);
        else if (e.getRawSlot() == 41) draw(p, 10);
    }

    @EventHandler
    public void onDrag(InventoryDragEvent e) {
        InventoryHolder h = e.getInventory().getHolder();
        if (h instanceof MenuHolder || h instanceof RollHolder) e.setCancelled(true);
    }

    // ------------------------------------------------------------------ 뽑기

    private void draw(Player p, int count) {
        if (rolling.contains(p.getUniqueId())) return;
        int price = count == 10 ? PRICE_10 : PRICE_1 * count;
        // 결제: 뽑기권 우선, 없으면 돈
        if (countTickets(p) >= count) {
            takeTickets(p, count);
        } else {
            Economy e = eco.apply(null);
            if (e == null) { p.sendMessage(P + "§c경제 플러그인이 연결되지 않았습니다."); return; }
            if (!e.has(p, price)) {
                p.sendMessage(P + "§c돈이 부족합니다. §7(필요: " + String.format("%,d", price) + "원, 보유: "
                        + String.format("%,d", (long) e.getBalance(p)) + "원)");
                p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 1f, 1f);
                return;
            }
            e.withdrawPlayer(p, price);
        }
        // 결과 결정 + 즉시 지급
        List<Reward> results = new ArrayList<>();
        int pity = pityCount(p);
        boolean pityHit = false;
        for (int i = 0; i < count; i++) {
            pity++;
            Reward r = pity >= PITY ? randomPet() : roll();
            if (r.pet()) {
                if (pity >= PITY) pityHit = true;
                pity = 0;
            }
            results.add(r);
        }
        setPity(p, pity);
        if (pityHit) p.sendMessage(P + "§6§l천장 도달! §f펫이 확정으로 나왔어요.");
        for (Reward r : results) give(p, r);
        animate(p, results);
    }

    private void give(Player p, Reward r) {
        switch (r.id()) {
            case "IRON" -> plugin.giveItem(p, new ItemStack(Material.IRON_INGOT, 5));
            case "DIAMOND" -> plugin.giveItem(p, new ItemStack(Material.DIAMOND, 1));
            default -> {
                PetType t = PetType.byName(r.id());
                if (t != null) plugin.giveItem(p, pets.card(t));
            }
        }
    }

    /** 슬롯이 돌다가 하나씩 멈추며 결과를 보여주는 연출 */
    private void animate(Player p, List<Reward> results) {
        rolling.add(p.getUniqueId());
        RollHolder h = new RollHolder();
        Inventory inv = Bukkit.createInventory(h, 27, "§5§l뽑는 중...");
        h.inv = inv;
        ItemStack frame = icon(Material.BLACK_STAINED_GLASS_PANE, " ");
        for (int i = 0; i < 27; i++) inv.setItem(i, frame);
        p.openInventory(inv);

        int n = results.size();
        int[] slots = n == 1 ? new int[]{13} : new int[]{2, 3, 4, 5, 6, 11, 12, 13, 14, 15};
        Material[] spin = {Material.RED_STAINED_GLASS_PANE, Material.ORANGE_STAINED_GLASS_PANE, Material.YELLOW_STAINED_GLASS_PANE,
                Material.LIME_STAINED_GLASS_PANE, Material.LIGHT_BLUE_STAINED_GLASS_PANE, Material.PURPLE_STAINED_GLASS_PANE,
                Material.MAGENTA_STAINED_GLASS_PANE};
        new BukkitRunnable() {
            int t = 0;
            int revealed = 0;
            final int spinTicks = 30;

            @Override
            public void run() {
                if (!p.isOnline()) { rolling.remove(p.getUniqueId()); cancel(); return; }
                // 돌아가는 슬롯
                for (int i = revealed; i < n; i++) {
                    inv.setItem(slots[i], icon(spin[(t + i) % spin.length], "§k???"));
                }
                if (t % 2 == 0 && revealed < n) p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_HAT, 0.6f, 1.6f);
                // 하나씩 멈춤
                if (t >= spinTicks && (t - spinTicks) % 6 == 0 && revealed < n) {
                    Reward r = results.get(revealed);
                    inv.setItem(slots[revealed], icon(r.icon(), r.name(), r.pet() ? "§a펫 카드 획득!" : "§8꽝..."));
                    if (r.pet()) {
                        p.playSound(p.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 1f, 1.4f);
                        p.getWorld().spawnParticle(Particle.TOTEM_OF_UNDYING, p.getLocation().add(0, 1, 0), 30, 0.5, 0.8, 0.5, 0.2);
                    } else {
                        p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 1f, 0.7f);
                    }
                    revealed++;
                }
                if (revealed >= n && t > spinTicks + n * 6 + 10) {
                    rolling.remove(p.getUniqueId());
                    cancel();
                    summary(p, results);
                    return;
                }
                t++;
            }
        }.runTaskTimer(plugin, 0L, 2L);
    }

    private void summary(Player p, List<Reward> results) {
        Map<String, Integer> counts = new LinkedHashMap<>();
        for (Reward r : results) counts.merge(r.name(), 1, Integer::sum);
        p.sendMessage(P + "§e뽑기 결과 §7(" + results.size() + "회) §8| §7천장까지 §d" + (PITY - pityCount(p)) + "회");
        counts.forEach((name, c) -> p.sendMessage("  " + name + (c > 1 ? " §fx" + c : "")));
        long petCount = results.stream().filter(Reward::pet).count();
        if (petCount > 0) {
            String names = String.join("§f, ", results.stream().filter(Reward::pet).map(Reward::name).distinct().toList());
            Bukkit.broadcastMessage(P + "§b" + p.getName() + "§f님이 펫 뽑기에서 " + names + "§f을(를) 뽑았습니다!");
        }
    }

    void info(CommandSender s) {
        s.sendMessage("§d§m        §r §5§l펫 뽑기 확률 §d§m        ");
        for (Reward r : POOL) s.sendMessage("  " + r.name() + " §8- §e" + pct(r));
        s.sendMessage("§71회 " + String.format("%,d", PRICE_1) + "원 · 10회 " + String.format("%,d", PRICE_10) + "원 (뽑기권 우선 사용)");
        s.sendMessage("§6천장: §f" + PITY + "회 안에 펫 확정 §7(펫이 나오면 다시 0부터)");
        if (s instanceof Player p) s.sendMessage("§7내 천장: §d" + pityCount(p) + " §7/ " + PITY);
    }
}
