package kr.starserver.starrpg;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Tag;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.*;
import org.bukkit.event.entity.EntityChangeBlockEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.persistence.PersistentDataType;

/**
 * 건축 맵 보호 (맵 제작자 요구사항):
 *  - 공중에 있는 잔디·꽃·모래·물 등이 사라지거나 떨어지지 않게
 *  - 불 번짐, 잔디·균사체 확산, 나뭇잎 사라짐, 얼음·눈 녹음 방지
 *  - 물·용암 흐름 방지
 * 그리고 맵을 바꾼 뒤 처음 접속한 플레이어는 새 맵 스폰으로 옮긴다.
 */
final class MapGuard implements Listener {
    static final String MAP_ID = "akenia-rpg";
    private final StarRPG plugin;
    private final NamespacedKey MAP_KEY;

    MapGuard(StarRPG plugin) {
        this.plugin = plugin;
        this.MAP_KEY = new NamespacedKey(plugin, "map_id");
    }

    private static boolean fragile(Material m) {
        return Tag.SAND.isTagged(m) || m == Material.GRAVEL || m.name().endsWith("CONCRETE_POWDER")
                || Tag.FLOWERS.isTagged(m) || Tag.SAPLINGS.isTagged(m) || m == Material.SHORT_GRASS || m == Material.TALL_GRASS
                || m == Material.FERN || m == Material.LARGE_FERN || m == Material.DEAD_BUSH || m == Material.SUGAR_CANE
                || m == Material.CACTUS || m == Material.VINE || m == Material.LILY_PAD || m == Material.SNOW
                || m == Material.WATER || m == Material.LAVA || Tag.CARPETS.isTagged(m) || m == Material.ANVIL
                || m == Material.TORCH || m == Material.WALL_TORCH || m == Material.LADDER || m == Material.SEAGRASS
                || m == Material.TALL_SEAGRASS || m == Material.KELP || m == Material.KELP_PLANT || m.name().contains("MUSHROOM");
    }

    @EventHandler(ignoreCancelled = true, priority = EventPriority.HIGH)
    public void onPhysics(BlockPhysicsEvent e) {
        if (fragile(e.getBlock().getType())) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onFall(EntityChangeBlockEvent e) {   // 모래·자갈이 떨어지는 블록으로 변하는 것
        if (e.getEntityType() == EntityType.FALLING_BLOCK && e.getTo() == Material.AIR) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onFlow(BlockFromToEvent e) { e.setCancelled(true); }        // 물·용암 흐름

    @EventHandler(ignoreCancelled = true)
    public void onSpread(BlockSpreadEvent e) { e.setCancelled(true); }      // 잔디·균사체·불·덩굴 확산

    @EventHandler(ignoreCancelled = true)
    public void onFade(BlockFadeEvent e) { e.setCancelled(true); }          // 잔디→흙, 얼음·눈 녹음, 산호 죽음

    @EventHandler(ignoreCancelled = true)
    public void onDecay(LeavesDecayEvent e) { e.setCancelled(true); }       // 나뭇잎 사라짐

    @EventHandler(ignoreCancelled = true)
    public void onBurn(BlockBurnEvent e) { e.setCancelled(true); }          // 불에 타서 사라짐

    @EventHandler(ignoreCancelled = true)
    public void onIgnite(BlockIgniteEvent e) {                               // 불 번짐 (플레이어가 직접 붙인 불은 허용)
        if (e.getCause() == BlockIgniteEvent.IgniteCause.SPREAD || e.getCause() == BlockIgniteEvent.IgniteCause.LAVA
                || e.getCause() == BlockIgniteEvent.IgniteCause.LIGHTNING) e.setCancelled(true);
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        if (MAP_ID.equals(p.getPersistentDataContainer().get(MAP_KEY, PersistentDataType.STRING))) return;
        p.getPersistentDataContainer().set(MAP_KEY, PersistentDataType.STRING, MAP_ID);
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (!p.isOnline()) return;
            p.teleport(p.getWorld().getSpawnLocation().add(0.5, 0, 0.5));
            p.sendTitle("§6§l새로운 대륙", "§f아케니아에 오신 걸 환영해요!", 10, 60, 20);
            p.sendMessage("§d[별빛] §f맵이 바뀌어서 새 스폰으로 이동했어요. 주변 NPC들에게 말을 걸어보세요!");
        }, 10L);
    }

    /** 폭발 방어: 침대·리스폰 정박기 등 블록 폭발이 블록을 부수지 않음 */
    @org.bukkit.event.EventHandler(priority = org.bukkit.event.EventPriority.HIGHEST)
    public void onBlockExplode(org.bukkit.event.block.BlockExplodeEvent e) {
        e.blockList().clear();
    }

    /** 폭발 방어: 액자·그림이 폭발로 떨어지지 않음 */
    @org.bukkit.event.EventHandler(ignoreCancelled = true)
    public void onHangingExplode(org.bukkit.event.hanging.HangingBreakEvent e) {
        if (e.getCause() == org.bukkit.event.hanging.HangingBreakEvent.RemoveCause.EXPLOSION) e.setCancelled(true);
    }
}
