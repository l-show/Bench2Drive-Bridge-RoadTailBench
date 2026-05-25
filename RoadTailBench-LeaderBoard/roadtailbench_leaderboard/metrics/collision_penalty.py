from .base import BaseMetric, MetricResult


PENALTY_BY_TYPE = {
    "pedestrian": 0.25,
    "walker": 0.25,
    "animal": 0.30,
    "vehicle": 0.45,
    "rock": 0.55,
    "road_intrusion": 0.55,
    "obstacle": 0.60,
    "static": 0.70,
    "roadside": 0.70,
    "unknown": 0.65,
}


def classify_collision_type(collision):
    text = " ".join(
        str(collision.get(k, "")) for k in ("type", "other_actor_type", "role_name", "hazard_type")
    ).lower()
    for key in PENALTY_BY_TYPE:
        if key in text:
            return key
    if "walker" in text:
        return "pedestrian"
    return "unknown"


class CollisionPenaltyMetric(BaseMetric):
    name = "collision_penalty"

    def compute(self, frames, config, context=None):
        seen = set()
        collisions = []
        for frame in frames:
            for collision in frame.get("collisions", []):
                key = (
                    collision.get("frame", frame.get("frame")),
                    collision.get("other_actor_id"),
                    collision.get("other_actor_type"),
                )
                if key in seen:
                    continue
                seen.add(key)
                collisions.append(collision)
        penalty = 1.0
        counts = {}
        for collision in collisions:
            ctype = classify_collision_type(collision)
            counts[ctype] = counts.get(ctype, 0) + 1
            penalty *= PENALTY_BY_TYPE.get(ctype, PENALTY_BY_TYPE["unknown"])
        return MetricResult.make(
            self.name,
            penalty,
            {"collision_count": len(collisions), "counts_by_type": counts},
        )
