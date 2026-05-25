from .base import BaseMetric, MetricResult
from ..extractors import ego, location_xy
from ..geometry import clamp, distance2


A_SUBTYPES = {
    "traffic_sign_marking": "Traffic Sign & Marking Robustness",
    "separation_protection": "Separation & Protection Robustness",
    "speed_control_facility": "Speed-Control Facility Robustness",
    "lighting_facility": "Lighting Facility Robustness",
    "pavement_condition": "Pavement Condition Robustness",
    "alignment_geometry": "Alignment Geometry Robustness",
    "sight_distance": "Sight-Distance Robustness",
    "clearance_intrusion": "Clearance Intrusion Robustness",
}

B_SUBTYPES = {
    "overtaking_bypass": "Overtaking & Obstacle Bypassing",
    "merging_flow": "Merging & Flow Negotiation",
    "emergency_avoidance": "Emergency Avoidance",
    "yielding_priority": "Yielding & Priority Negotiation",
}

C_SUBTYPES = {
    "low_light": "Low-Light Robustness",
    "glare": "Glare Robustness",
    "fog": "Fog Robustness",
    "rain_wet": "Rain & Wet-Road Robustness",
    "snow_low_friction": "Snow or Low-Friction Robustness",
    "wind_dust_visibility": "Wind/Dust Visibility Robustness",
}


class RoadEngineeringHazardAdaptationMetric(BaseMetric):
    name = "road_engineering_hazard_adaptation"

    def _zone_score(self, zone, frames, context):
        center = tuple(zone.get("center", [0.0, 0.0])[:2])
        radius = float(zone.get("radius_m", 10.0))
        local_frames = [f for f in frames if distance2(location_xy(ego(f)), center) <= radius]
        if not local_frames:
            return 1.0
        drivable = context.get("drivable_area", {}).get("score", 1.0) if context else 1.0
        speed = context.get("speed_appropriateness", {}).get("score", 1.0) if context else 1.0
        interaction = context.get("omnidirectional_interaction_risk", {}).get("score", 1.0) if context else 1.0
        collision = context.get("collision_penalty", {}).get("score", 1.0) if context else 1.0
        safe_pass = 1.0 if collision >= 0.999 else 0.0
        return clamp(0.35 * safe_pass + 0.25 * drivable + 0.20 * speed + 0.20 * interaction)

    def compute(self, frames, config, context=None):
        context = context or {}
        groups = {
            "A_infrastructure": A_SUBTYPES,
            "B_traffic_interaction": B_SUBTYPES,
            "C_environment": C_SUBTYPES,
        }
        configured = config.get("ability_tags", {})
        zone_scores = {}
        for group, subtypes in groups.items():
            zone_scores[group] = {}
            for subtype in subtypes:
                zones = [
                    z for z in config.get("hazard_zones", [])
                    if z.get("category") == group[0] or z.get("subtype") == subtype
                ]
                tag_value = configured.get(group, {}).get(subtype)
                if zones:
                    vals = [self._zone_score(z, frames, context) for z in zones]
                    score = sum(vals) / len(vals)
                elif tag_value is not None:
                    score = float(tag_value)
                else:
                    score = None
                zone_scores[group][subtype] = score
        group_means = {}
        for group, values in zone_scores.items():
            present = [v for v in values.values() if v is not None]
            group_means[group] = sum(present) / len(present) if present else 1.0
        weights = config.get("road_engineering_ability_weights", {
            "A_infrastructure": 0.50,
            "B_traffic_interaction": 0.30,
            "C_environment": 0.20,
        })
        score = sum(float(weights.get(k, 0.0)) * v for k, v in group_means.items())
        return MetricResult.make(
            self.name,
            clamp(score),
            {"group_scores": group_means, "subtype_scores": zone_scores},
        )
