package kr.starserver.starrpg;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Sound;
import org.bukkit.attribute.Attribute;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.inventory.ClickType;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;

import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 직업군 스킬 트리 (skills.yml).
 * 직업군마다 기본(F)·쉬좌(SL)·쉬우(SR)·패시브(P) 각 4단계 + 쉬쉬(SS) 5개.
 * 일반 유저는 자기 직업군 교관에게서만 배우고, 초보자는 아무 교관에게서 1단계만,
 * 초초보자·초초초보자는 모든 교관에게서 배울 수 있다. 배운 스킬은 /스킬 에서 키 4개에 장착한다.
 * 초초초보자는 배운 스킬을 파괴해 스킬 파편을 얻고, 파편 100개로 스킬을 진화(피해 +60%, MP·쿨타임 -30%)시킨다.
 */
final class SkillTree implements Listener {
    record TS(String id, String line, String slot, int rank, int level, String kind, String legacy,
              String name, String desc, int mp, int cd, List<String> val, String p1, String p2, String snd,
              String branch, boolean hidden, Map<String, Double> bonus) {}

    static final String[] SLOTS = {"F", "SL", "SR", "SS"};
    static final String[] SLOT_KO = {"F", "Shift+좌클릭", "Shift+우클릭", "Shift 두 번"};
    private static final String P = "§b[스킬] §f";

    private final StarRPG plugin;
    final Map<String, TS> byId = new LinkedHashMap<>();
    final Map<String, List<TS>> byLine = new LinkedHashMap<>();
    final Map<String, String[]> thirdClasses = new LinkedHashMap<>();   // id → {이름, 2차 부모, 설명, 직업군}
    private final NamespacedKey LEARNED, LOADOUT, FRAG, EVOLVED, DESTROYED, RECOG, BOOK, SCROLL;

    SkillTree(StarRPG plugin) {
        this.plugin = plugin;
        LEARNED = new NamespacedKey(plugin, "tree_learned");
        LOADOUT = new NamespacedKey(plugin, "tree_loadout");
        FRAG = new NamespacedKey(plugin, "tree_fragments");
        EVOLVED = new NamespacedKey(plugin, "tree_evolved");
        DESTROYED = new NamespacedKey(plugin, "tree_destroyed");
        RECOG = new NamespacedKey(plugin, "tree_recog_given");
        BOOK = new NamespacedKey(plugin, "hidden_skillbook");
        SCROLL = new NamespacedKey(plugin, "recog_scroll");
        load();
    }

    // ================================================================== 데이터

    private void load() {
        try (var in = plugin.getResource("skills.yml")) {
            if (in == null) { plugin.getLogger().warning("skills.yml 이 없어요"); return; }
            JsonObject root = JsonParser.parseReader(new InputStreamReader(in, StandardCharsets.UTF_8)).getAsJsonObject();
            for (JsonElement el : root.getAsJsonArray("skills")) {
                JsonObject o = el.getAsJsonObject();
                List<String> val = new ArrayList<>();
                if (o.has("val")) for (JsonElement x : o.getAsJsonArray("val")) val.add(x.getAsString());
                Map<String, Double> bonus = new HashMap<>();
                if (o.has("bonus")) for (String kv : o.get("bonus").getAsString().split(",")) {
                    String[] a = kv.split(":");
                    bonus.put(a[0], Double.parseDouble(a[1]));
                }
                TS t = new TS(s(o, "id"), s(o, "line"), s(o, "slot"), i(o, "rank"), i(o, "level"), s(o, "kind"), s(o, "legacy"),
                        s(o, "name"), s(o, "desc"), i(o, "mp"), i(o, "cd"), val, s(o, "p1"), s(o, "p2"), s(o, "snd"),
                        s(o, "branch"), o.has("hidden") && o.get("hidden").getAsBoolean(), bonus);
                byId.put(t.id(), t);
                byLine.computeIfAbsent(t.line(), k -> new ArrayList<>()).add(t);
            }
            JsonArray th = root.getAsJsonArray("third");
            for (JsonElement el : th) {
                JsonObject o = el.getAsJsonObject();
                thirdClasses.put(s(o, "id"), new String[]{s(o, "name"), s(o, "parent"), s(o, "desc"), s(o, "line")});
            }
            plugin.getLogger().info("스킬 트리: " + byId.size() + "개");
        } catch (Exception e) {
            plugin.getLogger().warning("skills.yml 을 읽지 못했어요: " + e);
        }
    }

    private static String s(JsonObject o, String k) { return o.has(k) && !o.get(k).isJsonNull() ? o.get(k).getAsString() : null; }
    private static int i(JsonObject o, String k) { return o.has(k) ? o.get(k).getAsInt() : 0; }

    Skill legacyOf(TS t) {
        try { return t.legacy() == null ? null : Skill.valueOf(t.legacy()); } catch (IllegalArgumentException e) { return null; }
    }
    String nameOf(TS t) { Skill s = legacyOf(t); return s != null ? s.korean : t.name(); }
    String descOf(TS t) { Skill s = legacyOf(t); return s != null ? s.description : t.desc(); }
    int mpOf(TS t) { Skill s = legacyOf(t); return s != null ? s.mp : t.mp(); }
    int cdOf(TS t) { Skill s = legacyOf(t); return s != null ? s.cooldown : t.cd(); }

    static String lineKo(String line) {
        if ("HIDDEN".equals(line)) return "히든";
        try { return RpgClass.valueOf(line).korean; } catch (IllegalArgumentException e) { return line; }
    }

    // ================================================================== 저장

    private Set<String> set(Player p, NamespacedKey key) {
        String raw = p.getPersistentDataContainer().get(key, PersistentDataType.STRING);
        Set<String> out = new LinkedHashSet<>();
        if (raw != null && !raw.isEmpty()) out.addAll(Arrays.asList(raw.split(",")));
        out.removeIf(id -> !byId.containsKey(id) && !id.contains("_RECOG"));
        return out;
    }
    private void saveSet(Player p, NamespacedKey key, Set<String> v) {
        p.getPersistentDataContainer().set(key, PersistentDataType.STRING, String.join(",", v));
    }
    Set<String> learned(Player p) { return set(p, LEARNED); }
    Set<String> evolved(Player p) { return set(p, EVOLVED); }
    boolean isEvolved(Player p, String id) { return evolved(p).contains(id); }
    int fragments(Player p) { return p.getPersistentDataContainer().getOrDefault(FRAG, PersistentDataType.INTEGER, 0); }
    private void setFragments(Player p, int n) { p.getPersistentDataContainer().set(FRAG, PersistentDataType.INTEGER, n); }

    void learn(Player p, String id) {
        Set<String> l = learned(p);
        if (l.add(id)) saveSet(p, LEARNED, l);
        plugin.rpg().applyStats(p);
    }

    int learnedCount(Player p) { return learned(p).size(); }
    int hiddenCount(Player p) { int n = 0; for (String id : learned(p)) if (byId.get(id).hidden()) n++; return n; }

    Map<String, String> loadout(Player p) {
        Map<String, String> m = new HashMap<>();
        String raw = p.getPersistentDataContainer().get(LOADOUT, PersistentDataType.STRING);
        if (raw != null) for (String kv : raw.split(";")) {
            String[] a = kv.split("=");
            if (a.length == 2) m.put(a[0], a[1]);
        }
        return m;
    }
    private void saveLoadout(Player p, Map<String, String> m) {
        StringBuilder sb = new StringBuilder();
        m.forEach((k, v) -> sb.append(k).append('=').append(v).append(';'));
        p.getPersistentDataContainer().set(LOADOUT, PersistentDataType.STRING, sb.toString());
    }

    // ================================================================== 규칙

    boolean ultra(Player p) {
        RpgClass c = plugin.rpg().rpgClass(p);
        return c == RpgClass.ULTRA_NOVICE || c == RpgClass.ULTRA_NOVICE2;
    }

    /** 지금 직업으로 이 스킬을 쓸 수 있나 */
    boolean usable(Player p, TS t) {
        if (ultra(p)) return true;
        RpgClass c = plugin.rpg().rpgClass(p);
        Skill leg = legacyOf(t);
        if (leg != null && c.skills.contains(leg)) return true;          // 직업 고유 스킬 (히든 직업 포함)
        if (t.hidden()) return false;
        if (c == RpgClass.NOVICE) return t.rank() == 1;
        if (!t.line().equals(c.root().name())) return false;
        if (t.branch() != null && !(c.name().equals(t.branch()) || (c.parent != null && c.parent.name().equals(t.branch())))) return false;
        return true;
    }

    static int cost(int rank) { return switch (rank) { case 1 -> 2000; case 2 -> 8000; case 3 -> 20000; default -> 50000; }; }

    /** 교관에게서 배울 수 있나 (안 되면 이유) */
    String canLearn(Player p, TS t) {
        if (learned(p).contains(t.id())) return "이미 배웠어요";
        if (set(p, DESTROYED).contains(t.id())) return "파괴한 스킬은 다시 배울 수 없어요";
        if (t.hidden()) return "히든 스킬서로만 얻을 수 있어요";
        RpgClass c = plugin.rpg().rpgClass(p);
        int lv = plugin.rpg().level(p);
        boolean ul = ultra(p);
        if (c == RpgClass.NOVICE) {
            if (t.rank() != 1) return "초보자는 1단계 스킬만 배울 수 있어요";
            return lv >= 5 ? null : "Lv.5 필요";
        }
        if (!ul && !t.line().equals(c.root().name())) return "다른 직업군의 스킬이에요";
        if (lv < t.level()) return "Lv." + t.level() + " 필요";
        if (!ul) {
            if (t.rank() >= 3 && c.tier < 2) return "2차 전직 필요";
            if (t.rank() == 4 && c.tier != 4) return "3차 전직 필요";
            if (t.branch() != null && !(c.name().equals(t.branch()) || (c.parent != null && c.parent.name().equals(t.branch()))))
                return lineKo(t.branch()).equals(t.branch()) ? branchName(t.branch()) + " 전용" : lineKo(t.branch()) + " 전용";
        }
        return null;
    }

    String branchName(String id) {
        String[] th = thirdClasses.get(id);
        if (th != null) return th[0];
        try { return RpgClass.valueOf(id).korean; } catch (IllegalArgumentException e) { return id; }
    }

    /** 키(F/SL/SR/SS)에 장착된, 지금 쓸 수 있는 스킬 */
    TS slotSkill(Player p, int slot) {
        String id = loadout(p).get(SLOTS[slot]);
        TS t = id == null ? null : byId.get(id);
        if (t == null || !learned(p).contains(id) || !usable(p, t)) return null;
        return t;
    }

    /** 직업이 바뀌었거나 접속했을 때: 직업 고유 스킬은 공짜로 배우고, 빈 키를 채운다 */
    void ensureClassSkills(Player p) {
        RpgClass c = plugin.rpg().rpgClass(p);
        Set<String> l = learned(p);
        boolean changed = false;
        for (TS t : byId.values()) {
            Skill leg = legacyOf(t);
            if (leg != null && c.skills.contains(leg) && usable(p, t) && l.add(t.id())) changed = true;
        }
        if (changed) saveSet(p, LEARNED, l);
        Map<String, String> m = loadout(p);
        boolean lc = false;
        for (int i = 0; i < 4; i++) {
            TS cur = slotSkill(p, i);
            if (cur != null) continue;
            // 직업 고유 스킬 순서대로 (F, SL, SR, 궁극기)
            TS pick = null;
            if (i < c.skills.size()) {
                Skill want = c.skills.get(i);
                for (String id : l) {
                    TS t = byId.get(id);
                    if (t.slot().equals(SLOTS[i]) && want.name().equals(t.legacy()) && usable(p, t)) { pick = t; break; }
                }
            }
            if (pick == null) for (String id : l) {
                TS t = byId.get(id);
                if (t.slot().equals(SLOTS[i]) && usable(p, t)) { pick = t; break; }
            }
            if (pick != null) { m.put(SLOTS[i], pick.id()); lc = true; }
            else if (m.remove(SLOTS[i]) != null) lc = true;
        }
        if (lc) saveLoadout(p, m);
    }

    // ================================================================== 패시브

    /** 배운 패시브 합계: hp mp spd mel rng skl reg mpr crit steal def */
    double bonus(Player p, String key) {
        double sum = 0;
        for (String id : learned(p)) {
            TS t = byId.get(id);
            if (t == null || !"passive".equals(t.kind()) || !usable(p, t)) continue;
            sum += t.bonus().getOrDefault(key, 0.0);
        }
        return sum;
    }

    // ================================================================== GUI

    private static final class Holder implements InventoryHolder {
        Inventory inv;
        String line;
        boolean trainer;
        String confirm;      // 파괴 확인용
        long confirmAt;
        final Map<Integer, String> slots = new HashMap<>();
        public Inventory getInventory() { return inv; }
    }

    private static final Material[] ROW_ICON = {Material.LIGHT_BLUE_STAINED_GLASS_PANE, Material.LIME_STAINED_GLASS_PANE,
            Material.ORANGE_STAINED_GLASS_PANE, Material.MAGENTA_STAINED_GLASS_PANE, Material.YELLOW_STAINED_GLASS_PANE};
    private static final String[] ROW_NAME = {"§b§l기본 스킬 §7(F)", "§a§l쉬좌 스킬 §7(Shift+좌클릭)", "§6§l쉬우 스킬 §7(Shift+우클릭)",
            "§d§l쉬쉬 스킬 §7(Shift 두 번)", "§e§l패시브 §7(배우면 항상 켜짐)"};
    private static final String[] ROW_SLOT = {"F", "SL", "SR", "SS", "P"};

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

    /** 내 직업군 (초초보자는 고를 수 있음) */
    String myLine(Player p) {
        RpgClass c = plugin.rpg().rpgClass(p);
        if (c == RpgClass.NOVICE || ultra(p)) return "WARRIOR";
        String r = c.root().name();
        return byLine.containsKey(r) ? r : "HIDDEN";
    }

    void openTree(Player p, String line, boolean trainer) {
        if (line == null || !byLine.containsKey(line)) line = myLine(p);
        Holder h = new Holder();
        h.line = line;
        h.trainer = trainer;
        String title = trainer ? "§0§l" + lineKo(line) + " 교관 §8- 스킬 배우기" : "§0§l스킬 §8- " + lineKo(line);
        h.inv = Bukkit.createInventory(h, 54, title);
        Set<String> l = learned(p);
        Set<String> ev = evolved(p);
        Map<String, String> lo = loadout(p);
        boolean ul2 = plugin.rpg().rpgClass(p) == RpgClass.ULTRA_NOVICE2;
        for (int r = 0; r < 5; r++) {
            h.inv.setItem(r * 9, icon(ROW_ICON[r], ROW_NAME[r], List.of(), false));
            List<TS> row = new ArrayList<>();
            for (TS t : byLine.get(line)) if (t.slot().equals(ROW_SLOT[r])) row.add(t);
            row.sort(Comparator.comparingInt(TS::rank).thenComparing(TS::id));
            for (int i = 0; i < row.size() && i < 8; i++) {
                TS t = row.get(i);
                boolean has = l.contains(t.id());
                boolean use = has && usable(p, t);
                boolean equipped = t.id().equals(lo.get(t.slot()));
                List<String> lore = new ArrayList<>();
                lore.add("§8" + t.rank() + "단계 · " + lineKo(t.line()) + (t.branch() != null ? " · " + branchName(t.branch()) + " 전용" : ""));
                lore.add("§7" + descOf(t));
                if (!"passive".equals(t.kind())) lore.add("§9MP " + mpOf(t) + " §7· 쿨타임 " + cdOf(t) + "초");
                if (ev.contains(t.id())) lore.add("§d✦ 진화함 §7(피해 +60%, MP·쿨타임 -30%)");
                lore.add("");
                Material m;
                if (has) {
                    m = equipped ? Material.ENCHANTED_BOOK : "passive".equals(t.kind()) ? Material.EXPERIENCE_BOTTLE : Material.BOOK;
                    if (!use) lore.add("§c지금 직업으로는 쓸 수 없어요");
                    else if (equipped) lore.add("§a장착 중 (" + keyKo(t.slot()) + ")");
                    else if (!"passive".equals(t.kind()) && !trainer) lore.add("§e▶ 클릭: " + keyKo(t.slot()) + "에 장착");
                    else lore.add("§a배움");
                    if (ul2 && !trainer) {
                        lore.add("§d우클릭: 진화 §7(파편 100개, 가진 것 " + fragments(p) + ")");
                        lore.add("§cShift+우클릭: 파괴 §7(파편 +" + (t.slot().equals("SS") ? 20 : 10) + ", 두 번 눌러 확인)");
                    }
                } else {
                    String why = canLearn(p, t);
                    m = why == null && trainer ? Material.LIME_DYE : Material.GRAY_DYE;
                    if (trainer) {
                        lore.add("§6비용: " + String.format("%,d", cost(t.rank())) + "원");
                        lore.add(why == null ? "§a▶ 클릭해서 배우기" : "§c" + why);
                    } else {
                        lore.add("§7" + lineKo(t.line()) + " 교관에게서 배울 수 있어요" + (t.hidden() ? " §8(히든 스킬서)" : ""));
                    }
                }
                String nm = (has ? "§f§l" : "§7") + nameOf(t) + (ev.contains(t.id()) ? " §d✦" : "");
                int slot = r * 9 + 1 + i;
                h.inv.setItem(slot, icon(m, nm, lore, equipped));
                h.slots.put(slot, t.id());
            }
        }
        // 아래 줄: 장착 현황 + 정보 + 직업군 넘기기
        ItemStack pane = icon(Material.BLACK_STAINED_GLASS_PANE, " ", List.of(), false);
        for (int i = 45; i < 54; i++) h.inv.setItem(i, pane);
        for (int i = 0; i < 4; i++) {
            TS cur = slotSkill(p, i);
            h.inv.setItem(46 + i, icon(cur == null ? Material.BARRIER : Material.ENCHANTED_BOOK,
                    "§e" + SLOT_KO[i] + ": §f" + (cur == null ? "없음" : nameOf(cur)), List.of("§7스킬을 눌러 바꿀 수 있어요"), cur != null));
        }
        List<String> info = new ArrayList<>(List.of("§7배운 스킬: §f" + l.size() + "개", "§7히든 스킬: §f" + hiddenCount(p) + "개"));
        if (ul2) info.add("§d스킬 파편: §f" + fragments(p) + "개");
        h.inv.setItem(51, icon(Material.NETHER_STAR, "§b§l내 스킬", info, false));
        if (ultra(p) || plugin.rpg().rpgClass(p) == RpgClass.NOVICE && trainer) {
            h.inv.setItem(45, icon(Material.ARROW, "§7◀ 다른 직업군", List.of(), false));
            h.inv.setItem(53, icon(Material.ARROW, "§7다른 직업군 ▶", List.of(), false));
        }
        if (trainer && plugin.rpg().rpgClass(p) == RpgClass.ULTRA_NOVICE && !"HIDDEN".equals(line)) {
            h.inv.setItem(52, icon(Material.PAPER, "§6§l인정의 주문서 받기",
                    List.of("§7이 직업군 스킬을 3개 이상 배우면", "§7교관이 인정의 주문서를 줘요.",
                            "§7(초초초보자 전직에 서로 다른 3장 필요)"), false));
        }
        p.openInventory(h.inv);
        p.playSound(p.getLocation(), Sound.ITEM_BOOK_PAGE_TURN, 0.8f, 1.1f);
    }

    static String keyKo(String slot) {
        for (int i = 0; i < 4; i++) if (SLOTS[i].equals(slot)) return SLOT_KO[i];
        return slot;
    }

    private String nextLine(String cur, int d, boolean withHidden) {
        List<String> keys = new ArrayList<>(byLine.keySet());
        if (!withHidden) keys.remove("HIDDEN");
        int i = Math.max(0, keys.indexOf(cur));
        return keys.get(Math.floorMod(i + d, keys.size()));
    }

    @EventHandler
    public void onClick(InventoryClickEvent e) {
        if (!(e.getInventory().getHolder() instanceof Holder h)) return;
        e.setCancelled(true);
        if (!(e.getWhoClicked() instanceof Player p) || e.getClickedInventory() != e.getInventory()) return;
        int raw = e.getRawSlot();
        if (raw == 45 || raw == 53) {
            if (e.getCurrentItem() == null || e.getCurrentItem().getType() != Material.ARROW) return;
            openTree(p, nextLine(h.line, raw == 45 ? -1 : 1, !h.trainer), h.trainer);
            return;
        }
        if (raw == 52 && h.trainer) { giveRecognition(p, h.line); return; }
        String id = h.slots.get(raw);
        if (id == null) return;
        TS t = byId.get(id);
        if (h.trainer) {
            String why = canLearn(p, t);
            if (why != null) { p.sendMessage(P + "§c" + why); p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.6f, 0.6f); return; }
            int c = cost(t.rank());
            if (plugin.balance(p) < c) { p.sendMessage(P + "§c돈이 모자라요. (" + String.format("%,d", c) + "원)"); return; }
            plugin.withdraw(p, c);
            learn(p, t.id());
            ensureClassSkills(p);
            p.sendMessage(P + "§a" + nameOf(t) + "§f을(를) 배웠어요! §7(/스킬 에서 장착)");
            p.playSound(p.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 0.8f, 1.4f);
            openTree(p, h.line, true);
            return;
        }
        if (!learned(p).contains(id)) return;
        boolean ul2 = plugin.rpg().rpgClass(p) == RpgClass.ULTRA_NOVICE2;
        if (ul2 && e.getClick() == ClickType.SHIFT_RIGHT) {
            long now = System.currentTimeMillis();
            if (!id.equals(h.confirm) || now - h.confirmAt > 3000) {
                h.confirm = id; h.confirmAt = now;
                p.sendMessage(P + "§c" + nameOf(t) + "§f을(를) 파괴할까요? 3초 안에 한 번 더 Shift+우클릭하세요.");
                return;
            }
            destroy(p, t);
            openTree(p, h.line, false);
            return;
        }
        if (ul2 && e.getClick() == ClickType.RIGHT) { evolve(p, t); openTree(p, h.line, false); return; }
        if ("passive".equals(t.kind())) return;
        if (!usable(p, t)) { p.sendMessage(P + "§c지금 직업으로는 쓸 수 없는 스킬이에요."); return; }
        Map<String, String> m = loadout(p);
        m.put(t.slot(), t.id());
        saveLoadout(p, m);
        p.sendMessage(P + "§e" + keyKo(t.slot()) + "§f에 §a" + nameOf(t) + "§f을(를) 장착했어요.");
        p.playSound(p.getLocation(), Sound.UI_BUTTON_CLICK, 0.6f, 1.3f);
        openTree(p, h.line, false);
    }

    @EventHandler
    public void onDrag(InventoryDragEvent e) {
        if (e.getInventory().getHolder() instanceof Holder) e.setCancelled(true);
    }

    // ================================================================== 초초초보자: 파괴·진화

    private void destroy(Player p, TS t) {
        Set<String> l = learned(p);
        if (!l.remove(t.id())) return;
        saveSet(p, LEARNED, l);
        Set<String> d = set(p, DESTROYED);
        d.add(t.id());
        saveSet(p, DESTROYED, d);
        Set<String> ev = evolved(p);
        if (ev.remove(t.id())) saveSet(p, EVOLVED, ev);
        int gain = t.slot().equals("SS") ? 20 : 10;
        setFragments(p, fragments(p) + gain);
        ensureClassSkills(p);
        plugin.rpg().applyStats(p);
        p.sendMessage(P + "§c" + nameOf(t) + "§f을(를) 파괴해 §d스킬 파편 " + gain + "개§f를 얻었어요. §7(" + fragments(p) + "개)");
        p.playSound(p.getLocation(), Sound.BLOCK_GLASS_BREAK, 1f, 0.7f);
    }

    private void evolve(Player p, TS t) {
        if (isEvolved(p, t.id())) { p.sendMessage(P + "이미 진화한 스킬이에요."); return; }
        if (fragments(p) < 100) { p.sendMessage(P + "§c스킬 파편이 모자라요. §7(" + fragments(p) + "/100)"); return; }
        setFragments(p, fragments(p) - 100);
        Set<String> ev = evolved(p);
        ev.add(t.id());
        saveSet(p, EVOLVED, ev);
        p.sendTitle("§d§l스킬 진화!", "§f" + nameOf(t) + " §d✦", 5, 50, 10);
        p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 1f, 1.2f);
        Bukkit.broadcastMessage(P + "§e" + p.getName() + "§f님이 §d" + nameOf(t) + "§f을(를) 진화시켰어요!");
    }

    // ================================================================== 인정의 주문서·히든 스킬서

    ItemStack scroll(String line) {
        ItemStack it = icon(Material.PAPER, "§6§l인정의 주문서 §7(" + lineKo(line) + ")",
                List.of("§7" + lineKo(line) + " 교관의 인정이 담긴 주문서.", "§7서로 다른 직업군 3장을 모으면", "§f초초초보자§7로 각성할 수 있어요."), true);
        ItemMeta meta = it.getItemMeta();
        meta.getPersistentDataContainer().set(SCROLL, PersistentDataType.STRING, line);
        it.setItemMeta(meta);
        return it;
    }

    private void giveRecognition(Player p, String line) {
        if (plugin.rpg().rpgClass(p) != RpgClass.ULTRA_NOVICE) { p.sendMessage(P + "§c초초보자만 받을 수 있어요."); return; }
        int n = 0;
        for (String id : learned(p)) if (byId.get(id).line().equals(line)) n++;
        if (n < 3) { p.sendMessage(P + "§c이 직업군 스킬을 3개 이상 배워야 해요. §7(" + n + "/3)"); return; }
        Set<String> given = set(p, RECOG);
        if (given.contains(line + "_RECOG")) { p.sendMessage(P + "§7이미 이 교관의 인정을 받았어요."); return; }
        given.add(line + "_RECOG");
        saveSet(p, RECOG, given);
        p.getInventory().addItem(scroll(line));
        p.sendMessage(P + "§6" + lineKo(line) + " 교관§f: 자네의 실력을 인정하지. 이 주문서를 가져가게.");
        p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_YES, 1f, 1f);
    }

    /** 가방 속 서로 다른 직업군 인정의 주문서 수 */
    int scrollKinds(Player p) {
        Set<String> kinds = new HashSet<>();
        for (ItemStack it : p.getInventory().getContents()) {
            if (it == null || !it.hasItemMeta()) continue;
            String l = it.getItemMeta().getPersistentDataContainer().get(SCROLL, PersistentDataType.STRING);
            if (l != null) kinds.add(l);
        }
        return kinds.size();
    }

    /** 서로 다른 직업군 주문서 3장을 가져간다 */
    void takeScrolls(Player p) {
        Set<String> taken = new HashSet<>();
        ItemStack[] c = p.getInventory().getContents();
        for (int i = 0; i < c.length && taken.size() < 3; i++) {
            ItemStack it = c[i];
            if (it == null || !it.hasItemMeta()) continue;
            String l = it.getItemMeta().getPersistentDataContainer().get(SCROLL, PersistentDataType.STRING);
            if (l == null || !taken.add(l)) continue;
            it.setAmount(it.getAmount() - 1);
            p.getInventory().setItem(i, it.getAmount() <= 0 ? null : it);
        }
    }

    ItemStack hiddenBook(TS t) {
        ItemStack it = icon(Material.ENCHANTED_BOOK, "§d§l히든 스킬서 §7- §f" + nameOf(t),
                List.of("§7" + descOf(t), "", "§e우클릭해서 배우기", "§8초초보자 계열만 쓸 수 있어요 (히든 직업 고유 스킬)"), true);
        ItemMeta meta = it.getItemMeta();
        meta.getPersistentDataContainer().set(BOOK, PersistentDataType.STRING, t.id());
        it.setItemMeta(meta);
        return it;
    }

    @EventHandler
    public void onUseBook(PlayerInteractEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        if (e.getAction() != Action.RIGHT_CLICK_AIR && e.getAction() != Action.RIGHT_CLICK_BLOCK) return;
        ItemStack it = e.getItem();
        if (it == null || !it.hasItemMeta()) return;
        String id = it.getItemMeta().getPersistentDataContainer().get(BOOK, PersistentDataType.STRING);
        if (id == null || !byId.containsKey(id)) return;
        e.setCancelled(true);
        Player p = e.getPlayer();
        TS t = byId.get(id);
        if (learned(p).contains(id)) { p.sendMessage(P + "이미 아는 히든 스킬이에요."); return; }
        it.setAmount(it.getAmount() - 1);
        learn(p, id);
        p.sendMessage(P + "§d히든 스킬 §f" + nameOf(t) + "§d을(를) 깨우쳤어요!");
        p.playSound(p.getLocation(), Sound.ENTITY_EVOKER_PREPARE_SUMMON, 1f, 1.2f);
    }

    /** 보스(체력 300 이상)를 잡으면 5% 확률로 히든 스킬서 */
    @EventHandler
    public void onBossDeath(EntityDeathEvent e) {
        LivingEntity dead = e.getEntity();
        if (dead instanceof Player || dead.getKiller() == null) return;
        var attr = dead.getAttribute(Attribute.MAX_HEALTH);
        if (attr == null || attr.getValue() < 300) return;
        if (ThreadLocalRandom.current().nextDouble() >= 0.05) return;
        List<TS> hidden = new ArrayList<>(byLine.getOrDefault("HIDDEN", List.of()));
        if (hidden.isEmpty()) return;
        TS t = hidden.get(ThreadLocalRandom.current().nextInt(hidden.size()));
        e.getDrops().add(hiddenBook(t));
        dead.getKiller().sendMessage(P + "§d히든 스킬서가 떨어졌어요! §f(" + nameOf(t) + ")");
    }

    /** 관리자 지급용 */
    TS find(String q) {
        TS t = byId.get(q);
        if (t != null) return t;
        for (TS x : byId.values()) if (q.equals(nameOf(x)) || q.equals("HIDDEN_" + x.legacy())) return x;
        return null;
    }
}
