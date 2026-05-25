from .base import BaseMetric, MetricResult
from ..extractors import ego, location_xy
from ..geometry import clamp, project_point_to_polyline, polyline_lengths


class RouteCompletionMetric(BaseMetric):
    name = "route_completion"

    def compute(self, frames, config, context=None):
        route = [tuple(p[:2]) for p in config.get("route", [])]
        if not frames or len(route) < 2:
            return MetricResult.make(self.name, 0.0, {"reason": "missing_frames_or_route"})
        _, total = polyline_lengths(route)
        max_progress = 0.0
        max_lateral_error = 0.0
        for frame in frames:
            pos = location_xy(ego(frame))
            progress, lateral_error, _ = project_point_to_polyline(pos, route)
            max_progress = max(max_progress, progress)
            max_lateral_error = max(max_lateral_error, lateral_error)
        score = clamp(max_progress / total if total > 0 else 0.0)
        return MetricResult.make(
            self.name,
            score,
            {
                "completed_distance_m": max_progress,
                "route_length_m": total,
                "max_lateral_error_m": max_lateral_error,
            },
        )
