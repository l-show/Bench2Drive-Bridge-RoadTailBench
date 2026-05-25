from .base import BaseMetric, MetricResult
from ..extractors import ego, location_xy
from ..geometry import clamp, distance_point_to_polygon, point_in_polygon, project_point_to_polyline


class DrivableAreaMetric(BaseMetric):
    name = "drivable_area"

    def compute(self, frames, config, context=None):
        if not frames:
            return MetricResult.make(self.name, 0.0, {"reason": "missing_frames"})
        polygons = [[tuple(p[:2]) for p in poly] for poly in config.get("drivable_polygons", [])]
        route = [tuple(p[:2]) for p in config.get("route", [])]
        allowed_error = float(config.get("allowed_lateral_error_m", 2.0))
        scores = []
        max_violation = 0.0
        for frame in frames:
            pos = location_xy(ego(frame))
            if polygons:
                inside = any(point_in_polygon(pos, poly) for poly in polygons)
                if inside:
                    score = 1.0
                    violation = 0.0
                else:
                    d = min(distance_point_to_polygon(pos, poly) for poly in polygons)
                    violation = d
                    score = 1.0 - clamp(d / max(allowed_error, 0.1))
            elif len(route) >= 2:
                _, lateral_error, _ = project_point_to_polyline(pos, route)
                violation = max(0.0, lateral_error - allowed_error)
                score = 1.0 - clamp(violation / max(allowed_error, 0.1))
            else:
                score = 1.0
                violation = 0.0
            max_violation = max(max_violation, violation)
            scores.append(score)
        return MetricResult.make(
            self.name,
            sum(scores) / len(scores),
            {"max_violation_m": max_violation, "used_polygon": bool(polygons)},
        )
