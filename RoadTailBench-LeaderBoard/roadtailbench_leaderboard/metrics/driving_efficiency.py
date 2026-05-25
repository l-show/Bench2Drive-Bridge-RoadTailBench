from .base import BaseMetric, MetricResult
from ..extractors import ego, speed_mps
from ..geometry import clamp


class DrivingEfficiencyMetric(BaseMetric):
    name = "driving_efficiency"

    def compute(self, frames, config, context=None):
        if not frames:
            return MetricResult.make(self.name, 0.0, {"reason": "missing_frames"})
        default_ref = float(config.get("reference_speed_kmh", 50.0)) / 3.6
        min_ratio = float(config.get("efficiency_min_ratio", 0.6))
        values = []
        low_speed = 0
        for frame in frames:
            ref = float(frame.get("reference_speed_mps", default_ref))
            if ref <= 0.1:
                continue
            v = speed_mps(ego(frame))
            values.append(min(v / ref, 1.0))
            if v < min_ratio * ref:
                low_speed += 1
        score = sum(values) / len(values) if values else 0.0
        return MetricResult.make(
            self.name,
            clamp(score),
            {
                "low_speed_frame_ratio": low_speed / len(values) if values else 0.0,
                "reference_speed_kmh": default_ref * 3.6,
            },
        )
