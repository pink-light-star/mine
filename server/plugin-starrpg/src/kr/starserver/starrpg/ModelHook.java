package kr.starserver.starrpg;

import kr.toxicity.model.api.BetterModel;
import kr.toxicity.model.api.bukkit.platform.BukkitAdapter;
import kr.toxicity.model.api.tracker.EntityTracker;
import org.bukkit.entity.Entity;

/** BetterModel 연동. BetterModel이 설치돼 있을 때만 이 클래스가 로드된다. */
final class ModelHook {
    private ModelHook() {}

    static boolean attach(Entity entity, String modelId) {
        return BetterModel.model(modelId)
                .map(r -> { r.getOrCreate(BukkitAdapter.adapt(entity)); return true; })
                .orElse(false);
    }

    /** 몹 크기(SCALE 속성)를 따라 커지는 모델 (탈것용) */
    static boolean attachScaled(Entity entity, String modelId, boolean keepVanilla) {
        return BetterModel.model(modelId)
                .map(r -> {
                    EntityTracker t = r.getOrCreate(BukkitAdapter.adapt(entity));
                    t.scaler(kr.toxicity.model.api.tracker.ModelScaler.entity());
                    if (keepVanilla) t.hideOption(kr.toxicity.model.api.tracker.EntityHideOption.FALSE);   // 바닐라 몸 + 장식만 얹기
                    return true;
                })
                .orElse(false);
    }

    /** 붙어 있는 모델을 from → to로 교체 */
    static boolean swap(Entity entity, String from, String to) {
        BetterModel.registry(BukkitAdapter.adapt(entity)).ifPresent(reg -> reg.remove(from));
        return attach(entity, to);
    }

    /** 모델의 애니메이션을 한 번 재생 (attack 등) */
    static boolean animate(Entity entity, String modelId, String animation) {
        return BetterModel.registry(BukkitAdapter.adapt(entity))
                .map(reg -> {
                    EntityTracker t = reg.tracker(modelId);
                    return t != null && t.animate(animation);
                })
                .orElse(false);
    }
}
