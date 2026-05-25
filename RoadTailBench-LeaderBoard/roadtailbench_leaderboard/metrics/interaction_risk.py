import math

from .base import BaseMetric, MetricResult
from ..extractors import actor_type, ego, location_xy, speed_mps, velocity_xy, yaw_deg
from ..geometry import EPS, clamp, dot2, mul2, norm2, sub2, world_to_ego_frame


TYPE_WEIGHT = {
    "pedestrian": 1.20,
    "walker": 1.20,
    "animal": 1.15,
    "vehicle": 1.00,
    "bike": 1.05,
    "motorcycle": 1.05,
    "rock": 0.95,
    "obstacle": 0.90,
    "static": 0.75,
    "unknown": 0.85,
}


class OmnidirectionalInteractionRiskMetric(BaseMetric):
    name = "omnidirectional_interaction_risk"

    def _type_weight(self, actor):
        text = actor_type(actor).lower()
        for key, value in TYPE_WEIGHT.items():
            if key in text:
                return value
        return TYPE_WEIGHT["unknown"]

    def _actor_risk(self, ego_state, actor, params):
        p_ego = location_xy(ego_state)
        p_actor = location_xy(actor)
        v_ego = velocity_xy(ego_state)
        v_actor = velocity_xy(actor)
        r = sub2(p_actor, p_ego)
        v_rel = sub2(v_actor, v_ego)
        vv = max(dot2(v_rel, v_rel), EPS)
        horizon = params["horizon_s"]
        t_cpa = clamp(-dot2(r, v_rel) / vv, 0.0, horizon)
        d_cpa = norm2((r[0] + v_rel[0] * t_cpa, r[1] + v_rel[1] * t_cpa))
        r_cpa = math.exp(-d_cpa / params["cpa_distance_m"]) * math.exp(-t_cpa / params["cpa_time_s"])

        yaw = yaw_deg(ego_state)
        r_local = world_to_ego_frame(r, yaw)
        v_local = world_to_ego_frame(v_rel, yaw)
        d_long = abs(r_local[0])
        d_lat = abs(r_local[1])
        v_ego_long = abs(world_to_ego_frame(v_ego, yaw)[0])
        v_actor_long = abs(world_to_ego_frame(v_actor, yaw)[0])
        v_close_lat = max(0.0, -math.copysign(1.0, r_local[1] or 1.0) * v_local[1])

        rho = params["response_time_s"]
        a_max = params["max_accel_mps2"]
        b_min = params["ego_brake_mps2"]
        b_max = params["actor_brake_mps2"]
        d_safe_long = (
            params["long_min_m"]
            + v_ego_long * rho
            + 0.5 * a_max * rho * rho
            + ((v_ego_long + rho * a_max) ** 2) / (2.0 * b_min)
            - (v_actor_long ** 2) / (2.0 * b_max)
        )
        d_safe_long = max(params["long_min_m"], d_safe_long)
        d_safe_lat = params["lat_min_m"] + v_close_lat * rho + 0.5 * params["lat_accel_mps2"] * rho * rho

        long_overlap = clamp(1.0 - d_long / max(d_safe_long * 1.5, EPS))
        lat_overlap = clamp(1.0 - d_lat / max(d_safe_lat * 1.5, EPS))
        r_long = clamp((d_safe_long - d_long) / max(d_safe_long, EPS)) * lat_overlap
        r_lat = clamp((d_safe_lat - d_lat) / max(d_safe_lat, EPS)) * long_overlap
        r_rss = max(r_long, r_lat)
        return clamp(self._type_weight(actor) * max(r_cpa, r_rss), 0.0, 1.0)

    def compute(self, frames, config, context=None):
        params = {
            "horizon_s": float(config.get("interaction_horizon_s", 5.0)),
            "cpa_distance_m": float(config.get("cpa_distance_m", 8.0)),
            "cpa_time_s": float(config.get("cpa_time_s", 3.0)),
            "response_time_s": float(config.get("response_time_s", 0.8)),
            "max_accel_mps2": float(config.get("rss_max_accel_mps2", 2.0)),
            "ego_brake_mps2": float(config.get("rss_ego_brake_mps2", 4.0)),
            "actor_brake_mps2": float(config.get("rss_actor_brake_mps2", 4.0)),
            "lat_accel_mps2": float(config.get("rss_lat_accel_mps2", 1.5)),
            "long_min_m": float(config.get("rss_long_min_m", 2.0)),
            "lat_min_m": float(config.get("rss_lat_min_m", 1.0)),
        }
        if not frames:
            return MetricResult.make(self.name, 0.0, {"reason": "missing_frames"})
        risks = []
        worst = {"risk": 0.0}
        for frame in frames:
            ego_state = ego(frame)
            frame_risk = 0.0
            for actor in frame.get("actors", []):
                if actor.get("id") == ego_state.get("id"):
                    continue
                if norm2(sub2(location_xy(actor), location_xy(ego_state))) > float(config.get("interaction_radius_m", 80.0)):
                    continue
                risk = self._actor_risk(ego_state, actor, params)
                if risk > frame_risk:
                    frame_risk = risk
                if risk > worst["risk"]:
                    worst = {"risk": risk, "frame": frame.get("frame"), "time": frame.get("time"), "actor": actor.get("id")}
            risks.append(frame_risk)
        mean_risk = sum(risks) / len(risks)
        return MetricResult.make(self.name, 1.0 - clamp(mean_risk), {"mean_risk": mean_risk, "worst": worst})
