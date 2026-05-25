import math

from .base import BaseMetric, MetricResult
from ..extractors import control, ego


class ControlStabilityMetric(BaseMetric):
    name = "control_stability"

    def compute(self, frames, config, context=None):
        if len(frames) < 2:
            return MetricResult.make(self.name, 1.0, {"reason": "insufficient_frames"})
        weights = config.get("control_jitter_weights", {"steer": 1.0, "throttle": 0.5, "brake": 0.8})
        jitters = []
        conflicts = 0
        prev = control(ego(frames[0]))
        for frame in frames[1:]:
            cur = control(ego(frame))
            jitter = (
                float(weights.get("steer", 1.0)) * abs(float(cur.get("steer", 0.0)) - float(prev.get("steer", 0.0)))
                + float(weights.get("throttle", 0.5)) * abs(float(cur.get("throttle", 0.0)) - float(prev.get("throttle", 0.0)))
                + float(weights.get("brake", 0.8)) * abs(float(cur.get("brake", 0.0)) - float(prev.get("brake", 0.0)))
            )
            if float(cur.get("throttle", 0.0)) > 0.1 and float(cur.get("brake", 0.0)) > 0.1:
                conflicts += 1
            jitters.append(jitter)
            prev = cur
        mean_jitter = sum(jitters) / len(jitters)
        score = math.exp(-mean_jitter)
        return MetricResult.make(
            self.name,
            score,
            {"mean_jitter": mean_jitter, "brake_throttle_conflict_rate": conflicts / len(jitters)},
        )
