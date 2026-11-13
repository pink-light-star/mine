package kr.starserver.starrpg;

import io.papermc.paper.event.player.AsyncChatEvent;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import net.milkbowl.vault.economy.Economy;
import org.bukkit.*;
import org.bukkit.boss.BarColor;
import org.bukkit.boss.BarStyle;
import org.bukkit.boss.BossBar;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.*;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerFishEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;

import java.time.LocalDate;
import java.util.*;
import java.util.concurrent.ThreadLocalRandom;
import java.util.function.Function;

/**
 * 퀘스트: NPC 퀘스트(메인·수집·히든), 일일 퀘스트, 월드 퀘스트, 칭호.
 * 진행 상황은 플레이어 데이터(PDC)에 저장된다.
 */
@SuppressWarnings("deprecation")
final class Quests implements Listener {
    private static final String P = "§d[별빛] §f";

    enum Type { KILL, COLLECT, LEVEL, HIDDEN, FISH, MINE, FARM, BREAK, HEIGHT }

    /** match: KILL = 몹 이름에 포함될 글자들(|로 구분) 또는 엔티티 타입, COLLECT = 재료 이름 또는 '이름:표시이름' */
    record Quest(String id, String npc, String name, String desc, Type type, String match, int amount,
                 int money, int xp, int tickets, String title, String requires) {}

    record Daily(String id, String desc, String kind, String match, int amount) {}

    // ===== NPC: id → {이름, 짧은 이름, 직업(외형), 바이옴 타입, 역할} =====
    //   역할: quest = 퀘스트 창, daily = 일일 의뢰, cmd:<명령어> = 명령어 실행, class = 전직 창
    static final Map<String, String[]> NPCS = new LinkedHashMap<>();
    static {
        NPCS.put("guild", new String[]{"§6§l모험가 길드장 §f레온", "길드장", "WEAPONSMITH", "PLAINS", "quest"});
        NPCS.put("elder", new String[]{"§a§l촌장 할머니 §f마르타", "촌장", "FARMER", "PLAINS", "quest"});
        NPCS.put("guard", new String[]{"§c§l경비대장 §f가렛", "경비대장", "ARMORER", "TAIGA", "quest"});
        NPCS.put("hunter", new String[]{"§2§l사냥꾼 §f리나", "사냥꾼", "LEATHERWORKER", "SAVANNA", "quest"});
        NPCS.put("fisher", new String[]{"§b§l어부 할아버지 §f토마스", "어부", "FISHERMAN", "SWAMP", "quest"});
        NPCS.put("smith", new String[]{"§7§l대장장이 §f브론", "대장장이", "TOOLSMITH", "DESERT", "quest"});
        NPCS.put("scholar", new String[]{"§9§l신화학자 §f엘리아", "신화학자", "LIBRARIAN", "SNOW", "quest"});
        NPCS.put("priest", new String[]{"§e§l신전 사제 §f세라", "사제", "CLERIC", "DESERT", "quest"});
        NPCS.put("kid", new String[]{"§d§l길 잃은 아이 §f미오", "미오", "NONE", "JUNGLE", "quest"});
        NPCS.put("merchant", new String[]{"§5§l수상한 상인 §f카일", "상인", "CLERIC", "SWAMP", "daily"});
        NPCS.put("shop", new String[]{"§6§l잡화점 주인 §f한나", "잡화점", "BUTCHER", "PLAINS", "cmd:shop"});
        NPCS.put("gacha", new String[]{"§d§l뽑기 안내원 §f루루", "루루", "CARTOGRAPHER", "SNOW", "cmd:가챠"});
        NPCS.put("jobs", new String[]{"§a§l직업 소개소 §f벤", "직업 소개소", "MASON", "TAIGA", "cmd:jobs browse"});
        NPCS.put("class", new String[]{"§4§l전직관 §f아이언", "전직관", "WEAPONSMITH", "SAVANNA", "class"});
        NPCS.put("netshop", new String[]{"§3§l그물 장수 §f피트", "그물 장수", "FLETCHER", "SWAMP", "cmd:그물상점"});
        NPCS.put("dungeon", new String[]{"§4§l던전 안내인 §f카론", "던전 안내인", "NITWIT", "SNOW", "cmd:던전"});
        NPCS.put("potion", new String[]{"§d§l모험가 잡화점 §f니나", "잡화점 니나", "CLERIC", "JUNGLE", "cmd:잡화점"});
        NPCS.put("trainer", new String[]{"§a§l능력치 교관 §f고든", "교관", "ARMORER", "PLAINS", "cmd:능력치"});
        NPCS.put("forge", new String[]{"§6§l대장장이 길드장 §f하인츠", "하인츠", "WEAPONSMITH", "DESERT", "cmd:대장간"});
        NPCS.put("parkour", new String[]{"§8§l??? §7수상한 등반가", "등반가", "NITWIT", "TAIGA", "cmd:파쿠르"});
        NPCS.put("stylist", new String[]{"§b§l이름 장인 §f모모", "이름 장인", "SHEPHERD", "SAVANNA", "cmd:이름꾸미기"});
    }

    // ===== 메인·수집·히든 퀘스트 =====
    final List<Quest> QUESTS = List.of(
            // 길드장: 메인
            new Quest("m1", "guild", "첫 사냥", "좀비 10마리를 처치하자.", Type.KILL, "ZOMBIE", 10, 500, 300, 0, null, null),
            new Quest("m2", "guild", "오크의 습격", "밤에 나타나는 오크를 15마리 처치하자.", Type.KILL, "오크", 15, 1500, 1500, 1, null, "m1"),
            new Quest("m3", "guild", "진정한 모험가", "레벨 10을 달성하고 전직하자. (/전직)", Type.LEVEL, "", 10, 2000, 0, 1, "§7[견습 모험가]", "m2"),
            new Quest("m4", "guild", "신화 속 괴물", "사이렌·하피·케르베로스·키클롭스를 5마리 처치하자.", Type.KILL, "사이렌|하피|케르베로스|키클롭스", 5, 3000, 4000, 1, null, "m3"),
            new Quest("m5", "guild", "대족장 토벌", "오크 대족장 크루가를 쓰러뜨리자.", Type.KILL, "크루가", 1, 10000, 8000, 3, "§2[오크 사냥꾼]", "m4"),
            new Quest("m6", "guild", "용을 쓰러뜨린 자", "적룡 이그니스를 쓰러뜨리자.", Type.KILL, "적룡", 1, 20000, 20000, 5, "§c§l[용사냥꾼]", "m5"),
            new Quest("m7", "guild", "전설의 모험가", "레벨 50(만렙)을 달성하자.", Type.LEVEL, "", 50, 50000, 0, 10, "§6§l[전설의 모험가]", "m6"),
            // 촌장
            new Quest("c1", "elder", "빵 굽는 날", "빵 16개를 가져다 드리자.", Type.COLLECT, "BREAD", 16, 800, 200, 0, null, null),
            new Quest("c2", "elder", "광부의 부탁", "석탄 32개를 가져다 드리자.", Type.COLLECT, "COAL", 32, 600, 200, 0, null, null),
            new Quest("c3", "elder", "오크의 송곳니", "오크의 송곳니 10개를 모아오자.", Type.COLLECT, "이름:오크의 송곳니", 10, 2000, 800, 1, null, null),
            new Quest("c4", "elder", "약초 할머니", "달콤한 열매 20개를 가져다 드리자.", Type.COLLECT, "SWEET_BERRIES", 20, 700, 300, 0, null, null),
            new Quest("h1", "elder", "할머니의 미소", "§8(히든) 할머니 곁에서 칭찬을 해보자...", Type.HIDDEN, "(예쁘|이쁘|멋지|멋있|최고|감사|고마|사랑|짱)", 1, 1000, 500, 2, "§d[효도왕]", null),
            // 경비대장
            new Quest("g1", "guard", "야간 순찰", "오크 전사 20마리를 처치하자.", Type.KILL, "오크 전사", 20, 2500, 2000, 1, null, null),
            new Quest("g2", "guard", "궁수 소탕", "오크 궁수 15마리를 처치하자.", Type.KILL, "오크 궁수", 15, 2500, 2000, 1, null, "g1"),
            new Quest("g3", "guard", "주술 차단", "오크 주술사 8마리를 처치하자.", Type.KILL, "오크 주술사", 8, 3500, 3000, 2, "§c[마을 수비대]", "g2"),
            new Quest("h2", "guard", "경비대장의 비밀", "§8(히든) 경비대장 곁에서 '수고하십니다'라고 인사해보자...", Type.HIDDEN, "(수고|고생)", 1, 1500, 500, 1, "§7[예의 바른 모험가]", null),
            // 사냥꾼
            new Quest("t1", "hunter", "뼈다귀 수집가", "스켈레톤 20마리를 처치하자.", Type.KILL, "SKELETON", 20, 1500, 1200, 0, null, null),
            new Quest("t2", "hunter", "거미줄 청소", "거미 15마리를 처치하자.", Type.KILL, "SPIDER", 15, 1500, 1200, 0, null, "t1"),
            new Quest("t3", "hunter", "폭탄 해체반", "크리퍼 10마리를 처치하자.", Type.KILL, "CREEPER", 10, 2500, 1800, 1, null, "t2"),
            new Quest("t4", "hunter", "밤하늘의 공포", "팬텀 5마리를 처치하자.", Type.KILL, "PHANTOM", 5, 3000, 2000, 1, "§2[명사수]", "t3"),
            // 어부
            new Quest("f1", "fisher", "첫 입질", "물고기 10마리를 낚자.", Type.FISH, "", 10, 800, 500, 0, null, null),
            new Quest("f2", "fisher", "대어를 노려라", "물고기 30마리를 낚자.", Type.FISH, "", 30, 2500, 1500, 1, null, "f1"),
            new Quest("f3", "fisher", "연어 요리 재료", "연어 10마리를 가져다 드리자.", Type.COLLECT, "SALMON", 10, 1500, 600, 0, null, null),
            new Quest("f4", "fisher", "바다의 왕", "물고기 100마리를 낚자.", Type.FISH, "", 100, 8000, 5000, 3, "§b[바다의 왕]", "f2"),
            // 대장장이
            new Quest("s1", "smith", "쇠붙이 모으기", "철 주괴 32개를 가져오자.", Type.COLLECT, "IRON_INGOT", 32, 2000, 800, 0, null, null),
            new Quest("s2", "smith", "금빛 장식", "금 주괴 16개를 가져오자.", Type.COLLECT, "GOLD_INGOT", 16, 2500, 800, 0, null, "s1"),
            new Quest("s3", "smith", "명장의 재료", "다이아몬드 5개를 가져오자.", Type.COLLECT, "DIAMOND", 5, 6000, 2000, 2, "§7[명장의 제자]", "s2"),
            new Quest("s4", "smith", "용의 비늘 갑옷", "용의 비늘 3개를 가져오자.", Type.COLLECT, "이름:용의 비늘", 3, 15000, 5000, 3, null, "s3"),
            // 신화학자
            new Quest("x1", "scholar", "노래하는 비늘", "사이렌의 비늘 5개를 모아오자.", Type.COLLECT, "이름:사이렌의 비늘", 5, 3000, 2000, 1, null, null),
            new Quest("x2", "scholar", "하늘의 깃털", "하피의 깃털 5개를 모아오자.", Type.COLLECT, "이름:하피의 깃털", 5, 3000, 2000, 1, null, "x1"),
            new Quest("x3", "scholar", "거인의 눈", "거인의 눈 2개를 모아오자.", Type.COLLECT, "이름:거인의 눈", 2, 5000, 3000, 1, null, "x2"),
            new Quest("x4", "scholar", "석화의 비밀", "메두사를 쓰러뜨리자.", Type.KILL, "메두사", 1, 10000, 8000, 3, "§9[신화 연구가]", "x3"),
            new Quest("x5", "scholar", "미궁의 주인", "미노타우로스를 쓰러뜨리자.", Type.KILL, "미노타우로스", 1, 10000, 8000, 3, null, "x3"),
            // 사제
            new Quest("p1", "priest", "언데드 정화", "좀비·스켈레톤을 30마리 처치하자.", Type.KILL, "ZOMBIE|SKELETON", 30, 2000, 1500, 0, null, null),
            new Quest("p2", "priest", "신전의 등불", "횃불 64개를 가져오자.", Type.COLLECT, "TORCH", 64, 1000, 400, 0, null, null),
            new Quest("p3", "priest", "지옥의 문지기", "케르베로스 3마리를 처치하자.", Type.KILL, "케르베로스", 3, 5000, 4000, 2, "§e[성스러운 자]", "p1"),
            new Quest("h3", "priest", "진심 어린 기도", "§8(히든) 신전 사제 곁에서 기도를 올려보자...", Type.HIDDEN, "(기도|아멘|축복)", 1, 1500, 800, 1, "§e[독실한 신자]", null),
            // 미오 (개그 퀘스트)
            new Quest("k1", "kid", "배고픈 아이", "쿠키 3개를 가져다주자. 엄마 몰래...", Type.COLLECT, "COOKIE", 3, 300, 200, 0, null, null),
            new Quest("k2", "kid", "보물 상자", "케이크 1개를 가져다주자. 생일이래!", Type.COLLECT, "CAKE", 1, 1000, 500, 1, null, "k1"),
            new Quest("k3", "kid", "용사님 놀이", "슬라임 10마리를 처치해주자. (용 대신이래)", Type.KILL, "SLIME", 10, 1500, 800, 0, "§d[꼬마들의 영웅]", "k2"),

            // ===== 히든 퀘스트 (연계 없음 · 자동 진행 · 조건을 채우면 바로 완료 + 장비 보상) =====
            new Quest("hq1", "scholar", "금지된 지식", "§8(히든) 언데드 군주 리치를 10번 쓰러뜨렸다.", Type.KILL, "리치", 10, 20000, 15000, 2, "§4[금서의 주인]", null),
            new Quest("hq2", "priest", "하늘에 닿은 자", "§8(히든) 50층 탑 꼭대기에 올랐다.", Type.HEIGHT, "", 1, 15000, 12000, 2, "§d[하늘에 닿은 자]", null),
            new Quest("hq3", "hunter", "끝없는 반복", "§8(히든) 블록 20,000개를 부쉈다.", Type.BREAK, "", 20000, 18000, 14000, 2, "§5[노가다의 신]", null),
            new Quest("hq4", "smith", "용을 쓰러뜨린 자", "§8(히든) 적룡 이그니스를 쓰러뜨렸다.", Type.KILL, "적룡", 1, 30000, 25000, 3, "§c[용린의 기사]", null),
            new Quest("hq5", "guard", "거인의 곡괭이", "§8(히든) 광석 1,000개를 캤다.", Type.MINE, "", 1000, 20000, 15000, 2, "§6[광산의 거인]", null),
            new Quest("hq6", "fisher", "심해의 노래", "§8(히든) 물고기 300마리를 낚았다.", Type.FISH, "", 300, 15000, 12000, 2, "§b[심해의 기사]", null),
            new Quest("hq7", "elder", "태양을 기르는 자", "§8(히든) 다 자란 작물 2,000개를 수확했다.", Type.FARM, "", 2000, 20000, 15000, 2, "§6[태양의 농부]", null),
            new Quest("h4", "kid", "괜찮아", "§8(히든) 우는 아이를 달래보자...", Type.HIDDEN, "(괜찮아|울지마|걱정마|힘내)", 1, 1000, 500, 1, "§d[다정한 모험가]", null));

    // ===== 일일 퀘스트 풀 =====
    final List<Daily> DAILY_POOL = List.of(
            new Daily("d_kill", "몬스터 20마리 처치", "kill", "monster", 20),
            new Daily("d_orc", "오크 8마리 처치", "kill", "오크", 8),
            new Daily("d_fish", "물고기 5마리 낚기", "fish", "", 5),
            new Daily("d_ore", "광석 16개 캐기", "mine", "ORE", 16),
            new Daily("d_log", "원목 32개 캐기", "mine", "LOG", 32),
            new Daily("d_myth", "신화 몹 3마리 처치", "kill", "사이렌|하피|케르베로스|키클롭스", 3),
            new Daily("d_animal", "동물 10마리 사냥", "kill", "animal", 10));

    private final StarRPG plugin;
    private final Gacha gacha;
    private final Function<Void, Economy> eco;
    private final NamespacedKey NPC, QSTATE, DAILY, DAILY_DATE, TITLES, TITLE;

    // 월드 퀘스트
    private BossBar worldBar;
    private int worldGoal, worldProgress;
    private long worldEnd;
    private String worldName;
    private final Map<UUID, Integer> worldContrib = new HashMap<>();

    Quests(StarRPG plugin, Gacha gacha, Function<Void, Economy> eco) {
        this.plugin = plugin;
        this.gacha = gacha;
        this.eco = eco;
        NPC = new NamespacedKey(plugin, "quest_npc");
        QSTATE = new NamespacedKey(plugin, "quests");
        DAILY = new NamespacedKey(plugin, "daily");
        DAILY_DATE = new NamespacedKey(plugin, "daily_date");
        TITLES = new NamespacedKey(plugin, "titles");
        TITLE = new NamespacedKey(plugin, "title");
        // 90분마다 월드 퀘스트 (접속자 있을 때)
        Bukkit.getScheduler().runTaskTimer(plugin, () -> {
            if (worldBar == null && !Bukkit.getOnlinePlayers().isEmpty()) startWorldQuest();
        }, 20L * 60 * 10, 20L * 60 * 90);
        Bukkit.getScheduler().runTaskTimer(plugin, this::worldTick, 20L, 20L);
        Bukkit.getScheduler().runTaskTimer(plugin, this::markerTick, 40L, 20L);
    }

    // ================================================================== 머리 위 ! / ? 표시 (플레이어마다 다르게)

    /** 0 = 없음, 1 = 진행 중(회색 ?), 2 = 받을 수 있음(노란 !), 3 = 완료 보고(초록 ?) */
    int npcState(Player p, String npc, Map<String, String> st) {
        int best = 0;
        for (Quest q : QUESTS) {
            if (!q.npc().equals(npc) || q.type() == Type.HIDDEN || autoHidden(q)) continue;
            String s = st.get(q.id());
            if ("d".equals(s)) continue;
            if (s == null) {
                if (q.requires() == null || "d".equals(st.get(q.requires()))) best = Math.max(best, 2);
            } else {
                best = Math.max(best, progress(p, q, st) >= q.amount() ? 3 : 1);
            }
        }
        return best;
    }

    private final Map<UUID, Map<UUID, TextDisplay>> markers = new HashMap<>();

    private void markerTick() {
        Set<UUID> online = new HashSet<>();
        for (Player p : Bukkit.getOnlinePlayers()) {
            online.add(p.getUniqueId());
            Map<UUID, TextDisplay> mine = markers.computeIfAbsent(p.getUniqueId(), k -> new HashMap<>());
            Map<String, String> st = states(p);
            Set<UUID> seen = new HashSet<>();
            for (Villager v : p.getWorld().getNearbyEntitiesByType(Villager.class, p.getLocation(), 40)) {
                String id = v.getPersistentDataContainer().get(NPC, PersistentDataType.STRING);
                if (id == null) continue;
                String[] info = NPCS.get(id);
                if (info == null || !info[4].equals("quest")) continue;
                int state = npcState(p, id, st);
                TextDisplay td = mine.get(v.getUniqueId());
                if (state == 0) { if (td != null) { td.remove(); mine.remove(v.getUniqueId()); } continue; }
                seen.add(v.getUniqueId());
                String text = switch (state) { case 3 -> "§a§l?"; case 2 -> "§e§l!"; default -> "§7§l?"; };
                Location at = v.getLocation().add(0, 2.85, 0);
                if (td == null || !td.isValid()) {
                    td = v.getWorld().spawn(at, TextDisplay.class, t -> {
                        t.setPersistent(false);
                        t.setVisibleByDefault(false);
                        t.setBillboard(org.bukkit.entity.Display.Billboard.CENTER);
                        t.setBackgroundColor(org.bukkit.Color.fromARGB(0, 0, 0, 0));
                        t.setShadowed(true);
                        t.setTransformation(new org.bukkit.util.Transformation(new org.joml.Vector3f(),
                                new org.joml.AxisAngle4f(), new org.joml.Vector3f(2.2f, 2.2f, 2.2f), new org.joml.AxisAngle4f()));
                    });
                    p.showEntity(plugin, td);
                    mine.put(v.getUniqueId(), td);
                }
                td.setText(text);
                // 살짝 위아래로 둥실
                double bob = Math.sin(System.currentTimeMillis() / 400.0) * 0.08;
                td.teleport(at.add(0, bob, 0));
            }
            mine.entrySet().removeIf(en -> {
                if (seen.contains(en.getKey())) return false;
                en.getValue().remove();
                return true;
            });
        }
        markers.entrySet().removeIf(en -> {
            if (online.contains(en.getKey())) return false;
            en.getValue().values().forEach(Entity::remove);
            return true;
        });
    }

    /** NPC를 우클릭했을 때 바로 처리: 완료 보고 → 보상, 받을 퀘스트 → 바로 수락. 처리했으면 true */
    private boolean quickQuest(Player p, String npc) {
        Map<String, String> st = states(p);
        for (Quest q : QUESTS) {   // 1) 완료 보고
            String s = st.get(q.id());
            if (!q.npc().equals(npc) || q.type() == Type.HIDDEN || autoHidden(q) || s == null || "d".equals(s)) continue;
            if (progress(p, q, st) >= q.amount()) {
                if (q.type() == Type.COLLECT) take(p, q.match(), q.amount());
                complete(p, q, st);
                return true;
            }
        }
        for (Quest q : QUESTS) {   // 2) 진행 중이면 진행도만 보여주기
            String s = st.get(q.id());
            if (!q.npc().equals(npc) || q.type() == Type.HIDDEN || autoHidden(q) || s == null || "d".equals(s)) continue;
            p.sendMessage(P + "§7[" + q.name() + "] §f" + q.desc() + " §e(" + Math.min(progress(p, q, st), q.amount()) + "/" + q.amount() + ")");
            p.sendMessage("§8  (웅크리고 우클릭하면 퀘스트 목록을 열어요)");
            return true;
        }
        for (Quest q : QUESTS) {   // 3) 새 퀘스트 수락
            if (!q.npc().equals(npc) || q.type() == Type.HIDDEN || autoHidden(q) || st.get(q.id()) != null) continue;
            if (q.requires() != null && !"d".equals(st.get(q.requires()))) continue;
            st.put(q.id(), "a:0");
            save(p, st);
            p.sendTitle("§e§l! 새 퀘스트", "§f" + q.name(), 5, 40, 10);
            p.sendMessage(P + "§e퀘스트 수락: §f" + q.name());
            p.sendMessage("§7  " + q.desc());
            p.sendMessage("§7  보상: §6" + String.format("%,d", q.money()) + "원" + (q.xp() > 0 ? " §a+" + q.xp() + " EXP" : "")
                    + (q.tickets() > 0 ? " §e뽑기권 " + q.tickets() + "장" : "") + (q.title() != null ? " §7칭호 " + q.title() : ""));
            p.playSound(p.getLocation(), Sound.ITEM_BOOK_PAGE_TURN, 1f, 1f);
            p.playSound(p.getLocation(), Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 0.6f, 1.4f);
            return true;
        }
        return false;
    }

    // ================================================================== 저장

    /** 상태: 없음=시작 안 함, "a:n"=진행 중(진행도 n), "d"=완료 */
    private Map<String, String> states(Player p) {
        Map<String, String> m = new LinkedHashMap<>();
        String s = p.getPersistentDataContainer().getOrDefault(QSTATE, PersistentDataType.STRING, "");
        for (String part : s.split(";")) {
            int i = part.indexOf('=');
            if (i > 0) m.put(part.substring(0, i), part.substring(i + 1));
        }
        return m;
    }

    boolean done(Player p, String questId) { return "d".equals(states(p).get(questId)); }

    private void save(Player p, Map<String, String> m) {
        StringBuilder b = new StringBuilder();
        m.forEach((k, v) -> b.append(k).append('=').append(v).append(';'));
        p.getPersistentDataContainer().set(QSTATE, PersistentDataType.STRING, b.toString());
    }

    private Quest quest(String id) {
        return QUESTS.stream().filter(q -> q.id().equals(id)).findFirst().orElse(null);
    }

    private int progress(Player p, Quest q, Map<String, String> st) {
        String s = st.get(q.id());
        if (s == null || !s.startsWith("a:")) return 0;
        return switch (q.type()) {
            case LEVEL -> plugin.rpg().level(p);
            case COLLECT -> count(p, q.match());
            default -> Integer.parseInt(s.substring(2));
        };
    }

    // ================================================================== NPC

    void spawnNpc(Player admin, String id) {
        if (!NPCS.containsKey(id)) { admin.sendMessage(P + "§cNPC 종류: " + String.join(", ", NPCS.keySet())); return; }
        spawnNpcAt(admin.getLocation(), id);
        admin.sendMessage(P + NPCS.get(id)[0] + "§f을(를) 배치했어요. §7(지우기: /minecraft:kill @e[type=villager,distance=..2])");
    }

    Villager spawnNpcAt(Location loc, String id) {
        String[] info = NPCS.get(id);
        Villager v = loc.getWorld().spawn(loc, Villager.class, vl -> {
            vl.setAI(false);
            vl.setInvulnerable(true);
            vl.setSilent(true);
            vl.setPersistent(true);
            vl.setRemoveWhenFarAway(false);
            vl.setCollidable(false);
            vl.setCustomName(info[0]);
            vl.setCustomNameVisible(true);
            try { vl.setProfession(org.bukkit.Registry.VILLAGER_PROFESSION.get(NamespacedKey.minecraft(info[2].toLowerCase(Locale.ROOT)))); } catch (Exception ignored) { }
            try { vl.setVillagerType(org.bukkit.Registry.VILLAGER_TYPE.get(NamespacedKey.minecraft(info[3].toLowerCase(Locale.ROOT)))); } catch (Exception ignored) { }
            vl.setVillagerLevel(5);
            vl.setRecipes(new ArrayList<>());   // 거래 목록을 비워 둔다 (지도 거래 생성 시 청크 로딩 오류 방지)
            vl.getPersistentDataContainer().set(NPC, PersistentDataType.STRING, id);
        });
        plugin.applyModelId(v, "npc_" + id);   // NameMC 스킨 모델 입히기
        v.getWorld().spawnParticle(Particle.HAPPY_VILLAGER, v.getLocation().add(0, 2, 0), 20, 0.4, 0.4, 0.4, 0);
        return v;
    }

    /** 스폰 높이 근처에서 발 디딜 땅 찾기 (건물 지붕 위가 아니라 스폰과 같은 층) */
    private int groundY(World w, int x, int z, int near) {
        for (int dy = 0; dy <= 8; dy++) {
            for (int y : new int[]{near + dy, near - dy}) {
                if (w.getBlockAt(x, y - 1, z).getType().isSolid() && !w.getBlockAt(x, y, z).getType().isSolid()
                        && !w.getBlockAt(x, y + 1, z).getType().isSolid()) return y;
            }
        }
        return w.getHighestBlockYAt(x, z) + 1;
    }

    /** 서 있을 만한 바깥 땅인지 (물·용암·잎 위 X, 하늘이 보여야 함) */
    private boolean goodSpot(World w, int x, int y, int z) {
        org.bukkit.block.Block below = w.getBlockAt(x, y - 1, z);
        Material m = below.getType();
        if (!m.isSolid() || below.isLiquid() || m.name().contains("LEAVES") || m.name().contains("FENCE") || m.name().contains("WALL")) return false;
        if (w.getBlockAt(x, y, z).getType().isSolid() || w.getBlockAt(x, y + 1, z).getType().isSolid()) return false;
        if (w.getBlockAt(x, y, z).isLiquid()) return false;
        return w.getHighestBlockYAt(x, z) <= y;   // 지붕 밑이 아닌 바깥
    }

    /** 월드 스폰 근처 곳곳에 모든 NPC를 흩어서 배치 (이미 있는 NPC는 지우고 다시) */
    int spawnAllAtSpawn(World w) {
        for (Villager old : w.getEntitiesByClass(Villager.class)) {
            String oid = old.getPersistentDataContainer().get(NPC, PersistentDataType.STRING);
            if (oid != null && !oid.equals("parkour")) old.remove();
        }
        Location c = w.getSpawnLocation();
        List<String> ids = new ArrayList<>(NPCS.keySet());
        ids.remove("parkour");      // 숨겨진 NPC는 따로 배치
        java.util.Random rnd = new java.util.Random(20261112L);
        List<Location> used = new ArrayList<>();
        int n = 0;
        for (int i = 0; i < ids.size(); i++) {
            Location at = null;
            for (int tries = 0; tries < 200 && at == null; tries++) {
                double a = rnd.nextDouble() * Math.PI * 2;
                double r = 7 + rnd.nextDouble() * (18 + tries * 0.15);   // 7 ~ 약 55칸
                int x = (int) Math.round(c.getX() + Math.cos(a) * r), z = (int) Math.round(c.getZ() + Math.sin(a) * r);
                int y = groundY(w, x, z, c.getBlockY());
                if (Math.abs(y - c.getBlockY()) > 10 || !goodSpot(w, x, y, z)) continue;
                Location cand = new Location(w, x + 0.5, y, z + 0.5);
                boolean near = false;
                for (Location u : used) if (u.distanceSquared(cand) < 36) { near = true; break; }
                if (!near) at = cand;
            }
            if (at == null) continue;
            used.add(at);
            at.setDirection(c.toVector().subtract(at.toVector()).setY(0));
            spawnNpcAt(at, ids.get(i));
            n++;
        }
        return n;
    }

    /** 청크가 다시 불러와질 때 NPC에 스킨 모델을 다시 입힌다 */
    @EventHandler
    public void onNpcLoad(org.bukkit.event.world.EntitiesLoadEvent e) {
        for (org.bukkit.entity.Entity en : e.getEntities()) {
            String id = en.getPersistentDataContainer().get(NPC, PersistentDataType.STRING);
            if (id != null) plugin.applyModelId(en, "npc_" + id);
        }
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onNpc(PlayerInteractEntityEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        String id = e.getRightClicked().getPersistentDataContainer().get(NPC, PersistentDataType.STRING);
        if (id == null) return;
        e.setCancelled(true);
        Player p = e.getPlayer();
        String[] info = NPCS.get(id);
        String role = info == null ? "quest" : info[4];
        if (role.equals("daily")) openDaily(p);
        else if (role.equals("class")) plugin.rpg().openClassMenu(p);
        else if (role.startsWith("cmd:")) p.performCommand(role.substring(4));
        else if (p.isSneaking() || !quickQuest(p, id)) openNpc(p, id);
    }

    @EventHandler(ignoreCancelled = true)
    public void onNpcDamage(EntityDamageEvent e) {
        if (e.getEntity().getPersistentDataContainer().has(NPC, PersistentDataType.STRING)) e.setCancelled(true);
    }

    private static final class QHolder implements InventoryHolder {
        Inventory inv;
        String npc;
        final Map<Integer, String> slots = new HashMap<>();
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

    void openNpc(Player p, String npc) {
        QHolder h = new QHolder();
        h.npc = npc;
        Inventory inv = Bukkit.createInventory(h, 27, NPCS.get(npc)[0]);
        h.inv = inv;
        Map<String, String> st = states(p);
        int slot = 10;
        for (Quest q : QUESTS) {
            if (!q.npc().equals(npc)) continue;
            String s = st.get(q.id());
            if ((q.type() == Type.HIDDEN || autoHidden(q)) && !"d".equals(s)) continue;   // 히든은 깨기 전엔 안 보임
            if (q.requires() != null && !"d".equals(st.get(q.requires()))) {
                Quest req = quest(q.requires());
                if (req != null && req.type() == Type.HIDDEN) continue;   // 히든 연계는 발견 전엔 안 보임
            }
            boolean locked = q.requires() != null && !"d".equals(st.get(q.requires()));
            List<String> lore = new ArrayList<>();
            lore.add("§7" + q.desc());
            lore.add("");
            lore.add("§e보상: §6" + String.format("%,d", q.money()) + "원" + (q.xp() > 0 ? " §a+" + q.xp() + " EXP" : "")
                    + (q.tickets() > 0 ? " §e뽑기권 " + q.tickets() + "장" : ""));
            if (q.title() != null) lore.add("§e칭호: " + q.title());
            Material m;
            if ("d".equals(s)) { m = Material.LIME_DYE; lore.add("§a완료!"); }
            else if (locked) { m = Material.GRAY_DYE; lore.add("§8이전 퀘스트를 먼저 끝내세요"); }
            else if (s == null) { m = Material.PAPER; lore.add("§a클릭해서 수락"); }
            else {
                int pr = progress(p, q, st);
                boolean ready = pr >= q.amount();
                m = ready ? Material.WRITABLE_BOOK : Material.BOOK;
                lore.add("§7진행: §f" + Math.min(pr, q.amount()) + "/" + q.amount());
                lore.add(ready ? "§a§l클릭해서 보상 받기!" : "§7진행 중...");
            }
            inv.setItem(slot, icon(m, (locked ? "§8" : "§f") + q.name(), lore, s != null && !"d".equals(s)));
            h.slots.put(slot, q.id());
            slot++;
            if (slot == 17) slot = 19;
        }
        p.openInventory(inv);
        p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_AMBIENT, 1f, 1f);
    }

    @EventHandler
    public void onClick(InventoryClickEvent e) {
        if (e.getInventory().getHolder() instanceof DHolder) { e.setCancelled(true); return; }
        if (!(e.getInventory().getHolder() instanceof QHolder h)) return;
        e.setCancelled(true);
        if (!(e.getWhoClicked() instanceof Player p)) return;
        String id = h.slots.get(e.getRawSlot());
        Quest q = id == null ? null : quest(id);
        if (q == null) return;
        Map<String, String> st = states(p);
        String s = st.get(q.id());
        if ("d".equals(s)) return;
        if (q.requires() != null && !"d".equals(st.get(q.requires()))) return;
        if (s == null) {
            st.put(q.id(), "a:0");
            save(p, st);
            p.sendMessage(P + "§e퀘스트 수락: §f" + q.name() + " §7- " + q.desc());
            p.playSound(p.getLocation(), Sound.ITEM_BOOK_PAGE_TURN, 1f, 1f);
        } else {
            int pr = progress(p, q, st);
            if (pr < q.amount()) { p.sendMessage(P + "§7아직이에요. (" + pr + "/" + q.amount() + ")"); return; }
            if (q.type() == Type.COLLECT) take(p, q.match(), q.amount());
            complete(p, q, st);
        }
        openNpc(p, h.npc);
    }

    /** 자동 진행 히든 퀘스트: 수락 없이 처음부터 기록, 다 채우면 바로 완료 */
    static final Set<String> AUTO_HIDDEN = Set.of("hq1", "hq2", "hq3", "hq4", "hq5", "hq6", "hq7");
    static boolean autoHidden(Quest q) { return AUTO_HIDDEN.contains(q.id()); }

    /** 히든 퀘스트 장비 보상 (Skript 대장간 아이템) */
    static final Map<String, List<String>> ITEM_REWARD = Map.of(
            "hq1", List.of("tome_void"), "hq2", List.of("moon_staff"), "hq3", List.of("void_dagger"),
            "hq4", List.of("dragon_helmet", "dragon_chest", "dragon_legs", "dragon_boots"),
            "hq5", List.of("giant_crusher"), "hq6", List.of("siren_blade"), "hq7", List.of("sun_staff"));

    private void complete(Player p, Quest q, Map<String, String> st) {
        st.put(q.id(), "d");
        save(p, st);
        Economy e = eco.apply(null);
        if (e != null && q.money() > 0) e.depositPlayer(p, q.money());
        if (q.xp() > 0) plugin.rpg().addXp(p, q.xp());
        if (q.tickets() > 0) plugin.giveItem(p, gacha.ticket(q.tickets()));
        if (q.title() != null) addTitle(p, q.title());
        List<String> items = ITEM_REWARD.get(q.id());
        if (items != null) {
            for (String it : items) Bukkit.dispatchCommand(Bukkit.getConsoleSender(), "대장간관리 지급 " + p.getName() + " " + it);
            p.sendMessage(P + "§5숨겨진 장비를 손에 넣었어요!");
            Bukkit.broadcastMessage(P + "§b" + p.getName() + "§f님이 히든 퀘스트 §d" + q.name() + "§f을(를) 완료하고 전설의 장비를 얻었습니다!");
        }
        p.sendTitle("§e§l퀘스트 완료!", "§f" + q.name(), 5, 40, 10);
        p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 1f, 1.2f);
        p.sendMessage(P + "§a퀘스트 완료: §f" + q.name() + " §7(보상 " + String.format("%,d", q.money()) + "원"
                + (q.xp() > 0 ? ", " + q.xp() + " EXP" : "") + (q.tickets() > 0 ? ", 뽑기권 " + q.tickets() + "장" : "") + ")");
        if (q.title() != null) p.sendMessage(P + "§d새 칭호: " + q.title() + " §7(/칭호)");
        for (Quest next : QUESTS) {
            if (q.id().equals(next.requires()) && next.type() != Type.HIDDEN) {
                String who = NPCS.get(next.npc())[1];
                p.sendMessage(P + "§6▶ 연계 퀘스트 열림: §f" + next.name() + " §7(" + who + "에게 말을 걸어 보세요 §e!§7)");
            }
        }
        if (q.id().equals("m6") || q.type() == Type.HIDDEN) Bukkit.broadcastMessage(P + "§b" + p.getName() + "§f님이 §e" + q.name() + "§f 퀘스트를 완료했습니다!");
    }

    // ================================================================== 진행 추적

    private boolean nameMatches(Entity e, String match) {
        if (match.equals("monster")) return e instanceof Monster;
        if (match.equals("animal")) return e instanceof Animals;
        String name = e.getCustomName() == null ? "" : ChatColor.stripColor(e.getCustomName());
        for (String m : match.split("\\|")) {
            if (!m.isEmpty() && (name.contains(m) || (name.isEmpty() && e.getType().name().equals(m)))) return true;
        }
        return false;
    }

    @EventHandler
    public void onKill(EntityDeathEvent e) {
        Player p = e.getEntity().getKiller();
        if (p == null) return;
        Map<String, String> st = states(p);
        boolean changed = false;
        List<Quest> autoDone = new ArrayList<>();
        for (Quest q : QUESTS) {
            String s = st.get(q.id());
            if (s == null && autoHidden(q)) s = "a:0";
            if (q.type() != Type.KILL || s == null || !s.startsWith("a:")) continue;
            if (!nameMatches(e.getEntity(), q.match())) continue;
            int n = Integer.parseInt(s.substring(2)) + 1;
            st.put(q.id(), "a:" + n);
            changed = true;
            if (autoHidden(q)) {
                if (n >= q.amount()) autoDone.add(q);
                else if (n == q.amount() / 2 && q.amount() > 2) p.sendMessage("§8...어디선가 누군가 당신을 지켜보는 것 같다.");
                continue;
            }
            if (n == q.amount()) p.sendMessage(P + "§a[" + q.name() + "] 목표 달성! §f" + NPCS.get(q.npc())[1] + "에게 돌아가세요.");
            else if (n < q.amount()) p.sendActionBar("§e[" + q.name() + "] §f" + n + "/" + q.amount());
        }
        if (changed) save(p, st);
        for (Quest q : autoDone) {
            p.sendTitle("§5§l✦ 히든 퀘스트 ✦", "§f" + q.name(), 5, 50, 10);
            complete(p, q, st);
        }
        dailyProgress(p, "kill", e.getEntity(), null);
        if (worldBar != null && e.getEntity() instanceof Monster) {
            worldProgress++;
            worldContrib.merge(p.getUniqueId(), 1, Integer::sum);
        }
    }

    /** 자동 히든 퀘스트 진행 (낚시·광질·농사·노가다·높이) */
    void autoStep(Player p, Type t, int inc) {
        Map<String, String> st = states(p);
        boolean changed = false;
        List<Quest> done = new ArrayList<>();
        for (Quest q : QUESTS) {
            if (!autoHidden(q) || q.type() != t) continue;
            String s = st.get(q.id());
            if ("d".equals(s)) continue;
            int n = (s == null ? 0 : Integer.parseInt(s.substring(2))) + inc;
            st.put(q.id(), "a:" + Math.min(n, q.amount()));
            changed = true;
            if (n >= q.amount()) done.add(q);
            else if (q.amount() > 2 && n - inc < q.amount() / 2 && n >= q.amount() / 2) p.sendMessage("§8...어디선가 누군가 당신을 지켜보는 것 같다.");
        }
        if (changed) save(p, st);
        for (Quest q : done) {
            p.sendTitle("§5§l✦ 히든 퀘스트 ✦", "§f" + q.name(), 5, 50, 10);
            complete(p, q, st);
        }
    }

    /** 관리자/스크립트용: 히든 퀘스트 강제 완료 (이미 완료면 무시) */
    void forceComplete(Player p, String id) {
        Quest q = quest(id);
        if (q == null) return;
        Map<String, String> st = states(p);
        if ("d".equals(st.get(id))) return;
        p.sendTitle("§5§l✦ 히든 퀘스트 ✦", "§f" + q.name(), 5, 50, 10);
        complete(p, q, st);
    }

    private static boolean isOre(Material m) {
        String n = m.name();
        return n.endsWith("_ORE") || m == Material.ANCIENT_DEBRIS;
    }

    @EventHandler(ignoreCancelled = true)
    public void onMine(BlockBreakEvent e) {
        dailyProgress(e.getPlayer(), "mine", null, e.getBlock().getType());
        Player p = e.getPlayer();
        if (p.getGameMode() == GameMode.CREATIVE) return;
        org.bukkit.block.Block b = e.getBlock();
        autoStep(p, Type.BREAK, 1);
        if (isOre(b.getType())) autoStep(p, Type.MINE, 1);
        if (b.getBlockData() instanceof org.bukkit.block.data.Ageable ag && ag.getAge() == ag.getMaximumAge()) {
            switch (b.getType()) {
                case WHEAT, CARROTS, POTATOES, BEETROOTS, NETHER_WART, COCOA -> autoStep(p, Type.FARM, 1);
                default -> { }
            }
        }
    }


    @EventHandler(ignoreCancelled = true)
    public void onFish(PlayerFishEvent e) {
        if (e.getState() != PlayerFishEvent.State.CAUGHT_FISH) return;
        Player p = e.getPlayer();
        dailyProgress(p, "fish", null, null);
        autoStep(p, Type.FISH, 1);
        Map<String, String> st = states(p);
        boolean changed = false;
        for (Quest q : QUESTS) {
            String s = st.get(q.id());
            if (q.type() != Type.FISH || s == null || !s.startsWith("a:") || autoHidden(q)) continue;
            int n = Integer.parseInt(s.substring(2)) + 1;
            st.put(q.id(), "a:" + n);
            changed = true;
            if (n == q.amount()) p.sendMessage(P + "§a[" + q.name() + "] 목표 달성! §f" + NPCS.get(q.npc())[1] + "에게 돌아가세요.");
            else if (n < q.amount()) p.sendActionBar("§e[" + q.name() + "] §f" + n + "/" + q.amount());
        }
        if (changed) save(p, st);
    }

    // ----- 히든: NPC 곁에서 특정 말을 하면 발견 -----
    private static final Map<String, String> HIDDEN_REPLY = Map.ofEntries(
            Map.entry("h1", "§a[촌장 할머니] §f어머나, 이 할미한테 그런 말을... 오래 살고 볼 일이네! 이거 받으렴."),
            Map.entry("h2", "§c[경비대장] §f...10년 동안 그 말 처음 들어보네. 고맙다, 모험가. 이건 비밀 보급품이다."),
            Map.entry("h3", "§e[신전 사제] §f당신의 기도가 닿았어요. 여신께서 작은 선물을 내리셨답니다."),
            Map.entry("h4", "§d[미오] §f...훌쩍. 진짜? 고마워 형/누나! 이거 내 보물이야!"),
            Map.entry("hx1", "§9[신화학자] §f...쉿. 그 이름을 어디서 들었죠? 금서는 리치가 지키고 있어요. 정말 원한다면..."),
            Map.entry("hx2", "§e[신전 사제] §f달... 오늘 밤 꿈에서 달의 여신을 봤어요. 그분이 사냥꾼을 찾고 계세요."),
            Map.entry("hx3", "§2[사냥꾼] §f그림자를 걷는 법이 궁금하다고? 원혼들을 사냥해 봐. 그럼 알려주지."),
            Map.entry("hx4", "§7[대장장이] §f용...? 평생 한 번은 용린 갑옷을 만들어 보고 싶었지. 비늘만 가져와 봐."),
            Map.entry("hx5", "§c[경비대장] §f맹세라... 좋다. 크루가의 목을 가져오면 거인의 검을 내주지."),
            Map.entry("hx6", "§b[어부 할아버지] §f허허, 바다 얘기라... 사이렌의 노래를 이기면 물결이 너를 따를 게다."),
            Map.entry("hx7", "§d[미오] §f별? 나 별 좋아해! 별의 조각 잔뜩 모아 오면 내 비밀 지팡이 줄게!"));

    @EventHandler
    public void onChat(AsyncChatEvent e) {
        String msg = PlainTextComponentSerializer.plainText().serialize(e.message());
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTask(plugin, () -> {
            Set<String> near = new HashSet<>();
            for (Entity en : p.getNearbyEntities(5, 3, 5)) {
                String id = en.getPersistentDataContainer().get(NPC, PersistentDataType.STRING);
                if (id != null) near.add(id);
            }
            if (near.isEmpty()) return;
            Map<String, String> st = states(p);
            for (Quest q : QUESTS) {
                if (q.type() != Type.HIDDEN || !near.contains(q.npc()) || "d".equals(st.get(q.id()))) continue;
                if (!msg.matches(".*" + q.match() + ".*")) continue;
                p.sendMessage(HIDDEN_REPLY.getOrDefault(q.id(), "§f...!"));
                p.sendMessage(P + "§d§l히든 퀘스트 발견!");
                complete(p, q, st);
                st = states(p);
            }
        });
    }

    // ================================================================== 수집 아이템

    private boolean matchesItem(ItemStack it, String match) {
        if (it == null) return false;
        if (match.startsWith("이름:")) {
            return it.hasItemMeta() && it.getItemMeta().hasDisplayName()
                    && ChatColor.stripColor(it.getItemMeta().getDisplayName()).contains(match.substring(3));
        }
        return it.getType().name().equals(match) && !(it.hasItemMeta() && it.getItemMeta().hasDisplayName());
    }

    private int count(Player p, String match) {
        int n = 0;
        for (ItemStack it : p.getInventory().getStorageContents()) if (matchesItem(it, match)) n += it.getAmount();
        return n;
    }

    private void take(Player p, String match, int amount) {
        for (ItemStack it : p.getInventory().getStorageContents()) {
            if (amount <= 0) return;
            if (matchesItem(it, match)) {
                int t = Math.min(amount, it.getAmount());
                it.setAmount(it.getAmount() - t);
                amount -= t;
            }
        }
    }

    // ================================================================== 일일 퀘스트

    private static final class DHolder implements InventoryHolder {
        Inventory inv;
        public Inventory getInventory() { return inv; }
    }

    /** 오늘의 일일 퀘스트 3개: "id:진행도:받음여부" */
    private List<String[]> daily(Player p) {
        String today = LocalDate.now().toString();
        if (!today.equals(p.getPersistentDataContainer().get(DAILY_DATE, PersistentDataType.STRING))) {
            List<Daily> pool = new ArrayList<>(DAILY_POOL);
            Collections.shuffle(pool);
            StringBuilder b = new StringBuilder();
            for (int i = 0; i < 3; i++) b.append(pool.get(i).id()).append(":0:0;");
            p.getPersistentDataContainer().set(DAILY, PersistentDataType.STRING, b.toString());
            p.getPersistentDataContainer().set(DAILY_DATE, PersistentDataType.STRING, today);
        }
        List<String[]> out = new ArrayList<>();
        for (String part : p.getPersistentDataContainer().getOrDefault(DAILY, PersistentDataType.STRING, "").split(";")) {
            if (!part.isEmpty()) out.add(part.split(":"));
        }
        return out;
    }

    private void saveDaily(Player p, List<String[]> d) {
        StringBuilder b = new StringBuilder();
        for (String[] x : d) b.append(String.join(":", x)).append(';');
        p.getPersistentDataContainer().set(DAILY, PersistentDataType.STRING, b.toString());
    }

    private Daily dailyDef(String id) {
        return DAILY_POOL.stream().filter(d -> d.id().equals(id)).findFirst().orElse(null);
    }

    private void dailyProgress(Player p, String kind, Entity killed, Material mined) {
        List<String[]> d = daily(p);
        boolean changed = false;
        for (String[] x : d) {
            Daily def = dailyDef(x[0]);
            if (def == null || !def.kind().equals(kind) || x[2].equals("1")) continue;
            int n = Integer.parseInt(x[1]);
            if (n >= def.amount()) continue;
            boolean ok = switch (kind) {
                case "kill" -> nameMatches(killed, def.match());
                case "mine" -> mined != null && mined.name().contains(def.match());
                default -> true;
            };
            if (!ok) continue;
            x[1] = String.valueOf(n + 1);
            changed = true;
            if (n + 1 == def.amount()) p.sendMessage(P + "§a[일일] " + def.desc() + " 완료! §f수상한 상인에게 보상을 받으세요.");
        }
        if (changed) saveDaily(p, d);
    }

    void openDaily(Player p) {
        DHolder h = new DHolder();
        Inventory inv = Bukkit.createInventory(h, 27, NPCS.get("merchant")[0] + " §8- 일일 의뢰");
        h.inv = inv;
        List<String[]> d = daily(p);
        boolean claimed = false;
        for (int i = 0; i < d.size(); i++) {
            String[] x = d.get(i);
            Daily def = dailyDef(x[0]);
            if (def == null) continue;
            int n = Integer.parseInt(x[1]);
            boolean done = n >= def.amount();
            if (done && x[2].equals("0")) {   // 창을 여는 순간 완료된 의뢰 보상 지급
                x[2] = "1";
                claimed = true;
                Economy e = eco.apply(null);
                if (e != null) e.depositPlayer(p, 1000);
                plugin.rpg().addXp(p, 500);
                boolean ticket = ThreadLocalRandom.current().nextDouble() < 0.15;
                if (ticket) plugin.giveItem(p, gacha.ticket(1));
                p.sendMessage(P + "§a[일일] " + def.desc() + " §f보상: §61,000원 §a+500 EXP" + (ticket ? " §e+뽑기권 1장!" : ""));
                p.playSound(p.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 1f, 1.4f);
            }
            inv.setItem(11 + i * 2, icon(x[2].equals("1") ? Material.LIME_DYE : Material.MAP, "§f" + def.desc(),
                    List.of("§7진행: §f" + Math.min(n, def.amount()) + "/" + def.amount(),
                            x[2].equals("1") ? "§a보상 받음" : done ? "§a완료!" : "§7진행 중",
                            "", "§e보상: §61,000원 §a+500 EXP §7(15% 뽑기권)"), x[2].equals("1")));
        }
        if (claimed) saveDaily(p, d);
        inv.setItem(22, icon(Material.CLOCK, "§7매일 자정에 새 의뢰로 바뀌어요", List.of("§7의뢰를 끝내고 이 창을 열면 보상을 받아요."), false));
        p.openInventory(inv);
    }

    @EventHandler
    public void onDrag(InventoryDragEvent e) {
        if (e.getInventory().getHolder() instanceof QHolder || e.getInventory().getHolder() instanceof DHolder) e.setCancelled(true);
    }

    // ================================================================== 월드 퀘스트

    void startWorldQuest() {
        if (worldBar != null) return;
        int online = Math.max(1, Bukkit.getOnlinePlayers().size());
        String[][] kinds = {{"몬스터 대토벌", "100"}, {"밤의 습격 막기", "80"}, {"별빛 수호 작전", "120"}};
        String[] k = kinds[ThreadLocalRandom.current().nextInt(kinds.length)];
        worldName = k[0];
        worldGoal = Integer.parseInt(k[1]) * online;
        worldProgress = 0;
        worldContrib.clear();
        worldEnd = System.currentTimeMillis() + 20 * 60 * 1000L;
        worldBar = Bukkit.createBossBar("", BarColor.PURPLE, BarStyle.SEGMENTED_10);
        Bukkit.getOnlinePlayers().forEach(worldBar::addPlayer);
        Bukkit.broadcastMessage("");
        Bukkit.broadcastMessage(P + "§5§l[월드 퀘스트] §e" + worldName + "§f 시작!");
        Bukkit.broadcastMessage(P + "§f20분 안에 서버 전체가 몬스터 §e" + worldGoal + "마리§f를 처치하세요. 참여한 모두가 보상을 받아요!");
        Bukkit.broadcastMessage("");
        for (Player p : Bukkit.getOnlinePlayers()) p.playSound(p.getLocation(), Sound.EVENT_RAID_HORN, 1f, 1f);
    }

    private void worldTick() {
        if (worldBar == null) return;
        for (Player p : Bukkit.getOnlinePlayers()) if (!worldBar.getPlayers().contains(p)) worldBar.addPlayer(p);
        long left = (worldEnd - System.currentTimeMillis()) / 1000;
        worldBar.setTitle("§5§l[월드 퀘스트] §e" + worldName + " §f" + worldProgress + "/" + worldGoal + " §7(" + left / 60 + ":" + String.format("%02d", left % 60) + ")");
        worldBar.setProgress(Math.min(1.0, worldProgress / (double) worldGoal));
        if (worldProgress >= worldGoal) endWorldQuest(true);
        else if (left <= 0) endWorldQuest(false);
    }

    private void endWorldQuest(boolean success) {
        worldBar.removeAll();
        worldBar = null;
        if (!success) {
            Bukkit.broadcastMessage(P + "§5[월드 퀘스트] §c" + worldName + " 실패... §7(" + worldProgress + "/" + worldGoal + ")");
            return;
        }
        Bukkit.broadcastMessage(P + "§5§l[월드 퀘스트] §a§l" + worldName + " 성공! §f참여자 전원에게 보상이 지급됐어요.");
        UUID mvp = worldContrib.entrySet().stream().max(Map.Entry.comparingByValue()).map(Map.Entry::getKey).orElse(null);
        Economy e = eco.apply(null);
        for (Map.Entry<UUID, Integer> en : worldContrib.entrySet()) {
            Player p = Bukkit.getPlayer(en.getKey());
            if (p == null) continue;
            int money = 2000 + en.getValue() * 50;
            if (e != null) e.depositPlayer(p, money);
            plugin.rpg().addXp(p, 1500 + en.getValue() * 20);
            plugin.giveItem(p, gacha.ticket(en.getKey().equals(mvp) ? 3 : 1));
            p.sendMessage(P + "§a월드 퀘스트 보상: §6" + String.format("%,d", money) + "원 §a+EXP §e뽑기권 " + (en.getKey().equals(mvp) ? "3장 §6(MVP!)" : "1장"));
            p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 1f, 1f);
        }
        if (mvp != null && Bukkit.getPlayer(mvp) != null) {
            Bukkit.broadcastMessage(P + "§6MVP: §e" + Bukkit.getPlayer(mvp).getName() + " §7(" + worldContrib.get(mvp) + "마리)");
            addTitle(Bukkit.getPlayer(mvp), "§5[월드 영웅]");
        }
    }

    // ================================================================== 칭호

    private List<String> titles(Player p) {
        String s = p.getPersistentDataContainer().getOrDefault(TITLES, PersistentDataType.STRING, "");
        List<String> out = new ArrayList<>();
        for (String t : s.split("\\|")) if (!t.isEmpty()) out.add(t);
        return out;
    }

    void addTitle(Player p, String t) {
        List<String> ts = titles(p);
        if (ts.contains(t)) return;
        ts.add(t);
        p.getPersistentDataContainer().set(TITLES, PersistentDataType.STRING, String.join("|", ts));
        if (!p.getPersistentDataContainer().has(TITLE, PersistentDataType.STRING)) p.getPersistentDataContainer().set(TITLE, PersistentDataType.STRING, t);
    }

    String title(Player p) {
        String t = p.getPersistentDataContainer().get(TITLE, PersistentDataType.STRING);
        return t == null ? "" : t + " ";
    }

    void titleCommand(Player p, String[] a) {
        List<String> ts = titles(p);
        if (a.length == 0) {
            p.sendMessage("§d§m      §r §e내 칭호 §d§m      ");
            if (ts.isEmpty()) p.sendMessage(" §7아직 칭호가 없어요. 퀘스트를 깨보세요!");
            for (int i = 0; i < ts.size(); i++) p.sendMessage(" §f" + (i + 1) + ". " + ts.get(i));
            p.sendMessage("§7사용: §e/칭호 <번호> §7· 끄기: §e/칭호 끄기");
            return;
        }
        if (a[0].equals("끄기")) { p.getPersistentDataContainer().remove(TITLE); p.sendMessage(P + "칭호를 껐어요."); return; }
        try {
            String t = ts.get(Integer.parseInt(a[0]) - 1);
            p.getPersistentDataContainer().set(TITLE, PersistentDataType.STRING, t);
            p.sendMessage(P + "칭호를 " + t + "§f(으)로 바꿨어요.");
        } catch (Exception ex) { p.sendMessage(P + "§c번호를 확인하세요. §7(/칭호)"); }
    }

    // ================================================================== 퀘스트 목록

    void log(Player p) {
        Map<String, String> st = states(p);
        p.sendMessage("§d§m      §r §e퀘스트 §d§m      ");
        boolean any = false;
        for (Quest q : QUESTS) {
            String s = st.get(q.id());
            if (s == null || "d".equals(s) || autoHidden(q)) continue;
            any = true;
            int pr = progress(p, q, st);
            p.sendMessage(" §f" + q.name() + " §7(" + Math.min(pr, q.amount()) + "/" + q.amount() + ") §8- " + NPCS.get(q.npc())[1]
                    + (pr >= q.amount() ? " §a보상 받으러 가기!" : ""));
        }
        if (!any) p.sendMessage(" §7진행 중인 퀘스트가 없어요. NPC에게 말을 걸어보세요.");
        p.sendMessage("§e[일일 의뢰]");
        for (String[] x : daily(p)) {
            Daily def = dailyDef(x[0]);
            if (def != null) p.sendMessage(" §f" + def.desc() + " §7(" + Math.min(Integer.parseInt(x[1]), def.amount()) + "/" + def.amount() + ")"
                    + (x[2].equals("1") ? " §a받음" : ""));
        }
        long done = st.values().stream().filter("d"::equals).count();
        p.sendMessage("§7완료한 퀘스트: §f" + done + "개");
    }

    boolean worldCommand(CommandSender s, String[] a) {
        if (a.length > 0 && a[0].equals("시작") && s.hasPermission("starrpg.admin")) {
            if (worldBar != null) s.sendMessage(P + "§c이미 진행 중이에요.");
            else startWorldQuest();
            return true;
        }
        if (worldBar == null) s.sendMessage(P + "§7지금은 월드 퀘스트가 없어요. §8(90분마다 시작)");
        else s.sendMessage(P + "§5" + worldName + " §f" + worldProgress + "/" + worldGoal);
        return true;
    }
}
