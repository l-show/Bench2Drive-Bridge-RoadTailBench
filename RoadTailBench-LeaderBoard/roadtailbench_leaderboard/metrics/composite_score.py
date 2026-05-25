from .base import BaseMetric, MetricResult


class CompositeScoreMetric(BaseMetric):
    name = "roadtailbench_driving_score"

    def compute(self, frames, config, context=None):
        context = context or {}

        def s(name, default=1.0):
            return float(context.get(name, {}).get("score", default))

        rc = s("route_completion", 0.0)
        col = s("collision_penalty", 0.0)
        eff = s("driving_efficiency")
        spd = s("speed_appropriateness")
        drv = s("drivable_area")
        inter = s("omnidirectional_interaction_risk")
        reha = s("road_engineering_hazard_adaptation")
        comfort = s("comfort")
        stable = s("control_stability")
        response = s("long_tail_hazard_response")
        score = (
            100.0
            * rc
            * col
            * drv
            * inter
            * reha
            * (0.5 + 0.5 * eff)
            * (0.6 + 0.4 * spd)
            * (0.8 + 0.2 * comfort)
            * (0.8 + 0.2 * stable)
            * (0.7 + 0.3 * response)
        )
        return MetricResult.make(
            self.name,
            score,
            {
                "route_completion": rc,
                "collision_penalty": col,
                "driving_efficiency": eff,
                "speed_appropriateness": spd,
                "drivable_area": drv,
                "interaction": inter,
                "road_engineering_hazard_adaptation": reha,
                "comfort": comfort,
                "control_stability": stable,
                "long_tail_hazard_response": response,
            },
        )
