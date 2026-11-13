package kr.starserver.starrpg;

import me.clip.placeholderapi.expansion.PlaceholderExpansion;
import org.bukkit.OfflinePlayer;
import org.bukkit.entity.Player;

/** %starrpg_level%, %starrpg_class%, %starrpg_class_colored%, %starrpg_tag%, %starrpg_xp_percent%, %starrpg_mp% */
final class RpgPapi extends PlaceholderExpansion {
    private final Rpg rpg;

    RpgPapi(Rpg rpg) { this.rpg = rpg; }

    @Override public String getIdentifier() { return "starrpg"; }
    @Override public String getAuthor() { return "starserver"; }
    @Override public String getVersion() { return "1.0"; }
    @Override public boolean persist() { return true; }

    @Override
    public String onRequest(OfflinePlayer op, String params) {
        if (op == null || !op.isOnline()) return "";
        Player p = op.getPlayer();
        String v = rpg.placeholder(p, params);
        return v == null ? "" : v;
    }
}
