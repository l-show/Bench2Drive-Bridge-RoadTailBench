import math

from .base import BaseMetric, MetricResult
from ..extractors import control, ego, location_xy, speed_mps
from ..geometry import distance2


class LongTailHazardResponseMetric(BaseMetric):
    name = "long_tail_hazard_response"

    def compute(self, frames, config, context=None):
        hazards = config.get("hazards", [])
        if not hazards:
            return MetricResult.make(self.name, 1.0, {"reason": "no_hazard_events"})
        tau = float(config.get("response_tau_s", 2.0))
        scores = []
        details = []
        for hazard in hazards:
            center = tuple(hazard.get("center", [0.0, 0.0])[:2])
            perception_radius = float(hazard.get("perception_radius_m", hazard.get("radius_m", 10.0) + 15.0))
            danger_radius = float(hazard.get("danger_radius_m", hazard.get("radius_m", 5.0)))
            enter_time = None
            response_time = None
            collision_or_violation = False
            prev_speed = None
            for frame in frames:
                e = ego(frame)
                t = float(frame.get("time", frame.get("frame", 0) * 0.05))
                d = distance2(location_xy(e), center)
                if enter_time is None and d <= perception_radius:
                    enter_time = t
                if enter_time is not None and d <= danger_radius:
                    collision_or_violation = True
                for collision in frame.get("collisions", []):
                    text = " ".join(str(collision.get(k, "")) for k in ("type", "other_actor_type", "message")).lower()
                    hazard_id = str(hazard.get("id", "")).lower()
                    hazard_type = str(hazard.get("type", "")).lower()
                    if (hazard_id and hazard_id in text) or (hazard_type and hazard_type in text):
                        collision_or_violation = True
                for event in frame.get("bench2drive_events", []):
                    etype = str(event.get("type", "")).lower()
                    if "collision" in etype or "outside" in etype or "deviation" in etype:
                        collision_or_violation = True
                if enter_time is not None and response_time is None:
                    cur_control = control(e)
                    cur_speed = speed_mps(e)
                    braking = float(cur_control.get("brake", 0.0)) > float(config.get("response_brake_threshold", 0.15))
                    steering = abs(float(cur_control.get("steer", 0.0))) > float(config.get("response_steer_threshold", 0.20))
                    slowing = prev_speed is not None and (prev_speed - cur_speed) > float(config.get("response_speed_drop_mps", 0.5))
                    if braking or steering or slowing:
                        response_time = t
                prev_speed = speed_mps(e)
            if enter_time is None:
                score = 1.0
                rt = None
            elif response_time is None:
                score = 0.0
                rt = None
            else:
                rt = max(0.0, response_time - enter_time)
                score = math.exp(-rt / tau)
            if collision_or_violation and not hazard.get("allow_enter_danger_zone", False):
                score *= 0.2
            scores.append(score)
            details.append({"id": hazard.get("id"), "type": hazard.get("type"), "reaction_time_s": rt, "score": score})
        return MetricResult.make(self.name, sum(scores) / len(scores), {"hazard_responses": details})
