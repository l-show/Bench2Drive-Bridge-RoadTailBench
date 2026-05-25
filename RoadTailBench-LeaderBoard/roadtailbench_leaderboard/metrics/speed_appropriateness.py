from .base import BaseMetric, MetricResult
from ..extractors import ego, location_xy, speed_mps
from ..geometry import clamp, distance2


def target_speed_for_frame(frame, config):
    pos = location_xy(ego(frame))
    base = float(config.get("reference_speed_kmh", 50.0)) / 3.6
    target = float(frame.get("target_speed_mps", base))
    for zone in config.get("speed_zones", []):
        center = tuple(zone.get("center", [0.0, 0.0])[:2])
        radius = float(zone.get("radius", 0.0))
        if radius > 0 and distance2(pos, center) <= radius:
            target = float(zone.get("target_speed_kmh", target * 3.6)) / 3.6
    return max(target, 0.1)


class SpeedAppropriatenessMetric(BaseMetric):
    name = "speed_appropriateness"

    def compute(self, frames, config, context=None):
        if not frames:
            return MetricResult.make(self.name, 0.0, {"reason": "missing_frames"})
        scores = []
        for frame in frames:
            target = target_speed_for_frame(frame, config)
            v = speed_mps(ego(frame))
            error = abs(v - target) / target
            scores.append(1.0 - clamp(error))
        return MetricResult.make(
            self.name,
            sum(scores) / len(scores),
            {"mean_frame_score": sum(scores) / len(scores)},
        )
