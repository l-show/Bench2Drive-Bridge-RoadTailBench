from .base import BaseMetric, MetricResult
from .road_engineering_hazard_adaptation import A_SUBTYPES, B_SUBTYPES, C_SUBTYPES


class AbilityScoreMetric(BaseMetric):
    name = "ability_score"

    def compute(self, frames, config, context=None):
        context = context or {}
        success = bool(config.get("scenario_success", False))
        if not success:
            rc = context.get("route_completion", {}).get("score", 0.0)
            col = context.get("collision_penalty", {}).get("score", 0.0)
            drv = context.get("drivable_area", {}).get("score", 0.0)
            inter = context.get("omnidirectional_interaction_risk", {}).get("score", 0.0)
            success = rc >= 0.95 and col >= 0.999 and drv >= 0.80 and inter >= 0.70
        tags = config.get("scenario_tags", [])
        all_subtypes = {
            **{f"A.{k}": v for k, v in A_SUBTYPES.items()},
            **{f"B.{k}": v for k, v in B_SUBTYPES.items()},
            **{f"C.{k}": v for k, v in C_SUBTYPES.items()},
        }
        subtype_scores = {}
        for tag in tags:
            if tag in all_subtypes:
                subtype_scores[tag] = 1.0 if success else 0.0
        group_scores = {}
        for group in ("A", "B", "C"):
            vals = [v for k, v in subtype_scores.items() if k.startswith(group + ".")]
            group_scores[group] = sum(vals) / len(vals) if vals else None
        weights = {"A": 0.50, "B": 0.30, "C": 0.20}
        present_weight = sum(weights[g] for g, v in group_scores.items() if v is not None)
        if present_weight > 0:
            score = sum(weights[g] * v for g, v in group_scores.items() if v is not None) / present_weight
        else:
            score = 1.0 if success else 0.0
        return MetricResult.make(
            self.name,
            score,
            {"success": success, "scenario_tags": tags, "group_scores": group_scores, "subtype_scores": subtype_scores},
        )
