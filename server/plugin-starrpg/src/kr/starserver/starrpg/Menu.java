package kr.starserver.starrpg;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.Sound;
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
import org.bukkit.inventory.meta.SkullMeta;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Shift+F (또는 /메뉴) 로 여는 메인 메뉴. 버튼을 누르면 해당 명령어를 실행한다. */
final class Menu implements Listener {
    private final StarRPG plugin;

    Menu(StarRPG plugin) { this.plugin = plugin; }

    private static final class Holder implements InventoryHolder {
        Inventory inv;
        final Map<Integer, String> actions = new HashMap<>();
        public Inventory getInventory() { return inv; }
    }

    private static ItemStack icon(Material m, String name, String... lore) {
        ItemStack it = new ItemStack(m);
        ItemMeta im = it.getItemMeta();
        im.setDisplayName(name);
        List<String> l = new ArrayList<>();
        for (String s : lore) l.add(s);
        im.setLore(l);
        im.addItemFlags(ItemFlag.values());
        it.setItemMeta(im);
        return it;
    }

    private void button(Holder h, int slot, Material m, String name, String cmd, String... lore) {
        String[] l = new String[lore.length + 2];
        System.arraycopy(lore, 0, l, 0, lore.length);
        l[lore.length] = "";
        l[lore.length + 1] = "§a▶ 클릭 §8(/" + cmd.split(" ")[0] + ")";
        h.inv.setItem(slot, icon(m, name, l));
        h.actions.put(slot, cmd);
    }

    private static void glow(Inventory inv, int slot) {
        ItemStack it = inv.getItem(slot);
        if (it == null) return;
        ItemMeta m = it.getItemMeta();
        m.setEnchantmentGlintOverride(true);
        it.setItemMeta(m);
    }

    void open(Player p) {
        Holder h = new Holder();
        Inventory inv = Bukkit.createInventory(h, 54, "§f\uF801\uE100\uF802§6§l✦ 별빛 메뉴");   // 리소스팩 배경(gui_6)
        h.inv = inv;
        ItemStack dark = icon(Material.BLACK_STAINED_GLASS_PANE, " ");
        ItemStack purple = icon(Material.PURPLE_STAINED_GLASS_PANE, " ");
        ItemStack magenta = icon(Material.MAGENTA_STAINED_GLASS_PANE, " ");
        // 바탕은 리소스팩 배경 그림이 그린다 (유리판 없음)
        // 왼쪽 분류 표시
        inv.setItem(9, icon(Material.RED_STAINED_GLASS_PANE, "§c§l⚔ 전투 · 성장"));
        inv.setItem(18, icon(Material.ORANGE_STAINED_GLASS_PANE, "§6§l✦ 모험 · 수집"));
        inv.setItem(27, icon(Material.LIME_STAINED_GLASS_PANE, "§a§l⛃ 경제 · 생활"));
        inv.setItem(36, icon(Material.LIGHT_BLUE_STAINED_GLASS_PANE, "§b§l➜ 이동"));
        inv.setItem(17, icon(Material.RED_STAINED_GLASS_PANE, "§c§l⚔ 전투 · 성장"));
        inv.setItem(26, icon(Material.ORANGE_STAINED_GLASS_PANE, "§6§l✦ 모험 · 수집"));
        inv.setItem(35, icon(Material.LIME_STAINED_GLASS_PANE, "§a§l⛃ 경제 · 생활"));
        inv.setItem(44, icon(Material.LIGHT_BLUE_STAINED_GLASS_PANE, "§b§l➜ 이동"));

        // 내 정보 (머리)
        Rpg rpg = plugin.rpg();
        RpgClass c = rpg.rpgClass(p);
        ItemStack head = new ItemStack(Material.PLAYER_HEAD);
        SkullMeta sm = (SkullMeta) head.getItemMeta();
        sm.setOwningPlayer(p);
        sm.setDisplayName("§e§l" + p.getName());
        String title = plugin.titleOf(p);
        sm.setLore(List.of(
                "§7레벨: §fLv." + rpg.level(p),
                "§7직업: " + c.display(),
                "§7MP: §9" + (int) rpg.mp(p) + "§7/§9" + (int) rpg.maxMp(p),
                "§7돈: §6" + String.format("%,d", (long) plugin.balance(p)) + "원",
                "§7칭호: " + (title == null || title.isEmpty() ? "§8없음" : title),
                "", "§a▶ 클릭: 자세한 정보"));
        head.setItemMeta(sm);
        inv.setItem(4, head);
        h.actions.put(4, "rpginfo");

        // 전투 · 성장
        button(h, 10, Material.NETHER_STAR, "§d§l전직", "rpgclass", "§7전투 직업 고르기·전직");
        button(h, 11, Material.BLAZE_POWDER, "§b§l내 스킬", "rpgskill", "§7스킬·사용 키·MP·쿨타임");
        button(h, 12, Material.EXPERIENCE_BOTTLE, "§a§l능력치", "능력치", "§7힘·민첩·지능·체력 올리기", "§7직업마다 성장 능력치가 달라요");
        button(h, 13, Material.WRITABLE_BOOK, "§e§l퀘스트", "questlog", "§7진행 중·완료한 퀘스트");
        button(h, 14, Material.BEACON, "§5§l월드 퀘스트", "worldquest", "§7서버 전체가 함께하는 퀘스트");
        button(h, 15, Material.NAME_TAG, "§f§l칭호", "title", "§7칭호 보기·바꾸기");
        button(h, 16, Material.GOLDEN_HELMET, "§6§l이름 꾸미기", "이름꾸미기", "§7이름 색·머리 위 장식 고르기");

        // 모험 · 수집
        button(h, 19, Material.WITHER_SKELETON_SKULL, "§4§l⚠ 던전 입장", "던전", "§7용암 협곡 던전 (파티 가능)", "§7몹 웨이브 → 보스 → 보상");
        button(h, 20, Material.AMETHYST_SHARD, "§d§l펫 뽑기", "gacha", "§71회 30,000원 · 10회 270,000원");
        button(h, 21, Material.BONE, "§f§l펫 목록", "petlist", "§7내 펫·펫 도감");
        button(h, 22, Material.KNOWLEDGE_BOOK, "§6§l도감", "dex", "§7탈것·펫·보스·장비 도감", "§7누르면 3D 모델이 앞에 나타나요");
        button(h, 23, Material.COBWEB, "§7§l그물 상점", "netshop", "§7그물총·그물·빗자루");
        button(h, 24, Material.DIAMOND_SWORD, "§6§l장비 등급", "gear", "§7일반 ~ 신화 등급 안내");
        button(h, 25, Material.ENCHANTED_BOOK, "§3§l생활 스킬", "skills", "§7채굴·농사·전투 등 스킬");

        // 경제 · 생활
        button(h, 28, Material.EMERALD, "§a§l상점", "shop", "§7블록·광물·음식·인첸트");
        button(h, 29, Material.POTION, "§d§l모험가 잡화점", "잡화점", "§7물약·귀환 주문서·능력치 초기화");
        button(h, 30, Material.HOPPER, "§e§l판매창", "sellgui", "§7넣은 물건을 한 번에 판매");
        button(h, 31, Material.IRON_PICKAXE, "§b§l생활 직업", "jobs browse", "§7직업 가입 (탈퇴 불가!)");
        button(h, 32, Material.FISHING_ROD, "§9§l낚시", "emf", "§7낚시 메뉴·물고기 판매");
        button(h, 33, Material.GOLD_INGOT, "§6§l돈 순위", "baltop", "§7부자 순위");
        button(h, 34, Material.CLOCK, "§e§l일일 의뢰", "일일의뢰", "§7매일 바뀌는 의뢰 3개");

        // 이동
        button(h, 37, Material.COMPASS, "§a§l스폰", "spawn", "§7마을로 이동");
        button(h, 38, Material.RED_BED, "§c§l집", "home", "§7저장한 집으로 이동");
        button(h, 39, Material.ENDER_PEARL, "§5§l돌아가기", "back", "§7직전 위치(죽은 곳)로");
        button(h, 41, Material.ANVIL, "§6§l대장간", "대장간", "§7몹·보스 재료로 능력 무기·방어구 제작", "§7요구 레벨·요구 능력치 있음");
        button(h, 43, Material.BOOK, "§f§l명령어 도움말", "명령어", "§7한국어 명령어 모음");
        glow(inv, 19);

        inv.setItem(49, icon(Material.BARRIER, "§c닫기"));
        h.actions.put(49, "");
        p.openInventory(inv);
        p.playSound(p.getLocation(), Sound.BLOCK_AMETHYST_BLOCK_CHIME, 0.8f, 1.4f);
    }

    @EventHandler
    public void onClick(InventoryClickEvent e) {
        if (!(e.getInventory().getHolder() instanceof Holder h)) return;
        e.setCancelled(true);
        if (!(e.getWhoClicked() instanceof Player p) || e.getClickedInventory() != e.getInventory()) return;
        String cmd = h.actions.get(e.getRawSlot());
        if (cmd == null) return;
        p.closeInventory();
        p.playSound(p.getLocation(), Sound.UI_BUTTON_CLICK, 0.6f, 1.2f);
        if (!cmd.isEmpty()) Bukkit.getScheduler().runTask(plugin, () -> p.performCommand(cmd));
    }

    @EventHandler
    public void onDrag(InventoryDragEvent e) {
        if (e.getInventory().getHolder() instanceof Holder) e.setCancelled(true);
    }
}
