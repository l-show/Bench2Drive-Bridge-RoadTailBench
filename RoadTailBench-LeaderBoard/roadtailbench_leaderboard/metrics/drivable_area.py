from .base import BaseMetric, MetricResult
from ..extractors import ego, location_xy
from ..geometry import clamp, project_point_to_polyline


def _point_xy(point):
    if isinstance(point, dict):
        loc = point.get("location", point)
        if isinstance(loc, dict):
            return (float(loc.get("x", 0.0)), float(loc.get("y", 0.0)))
        return (float(loc[0]), float(loc[1]))
    return (float(point[0]), float(point[1]))


def _polyline(points):
    return [_point_xy(point) for point in points or []]


def _centerline_segments(config):
    segments = []
    raw_segments = config.get("centerline_segments") or []
    for idx, raw in enumerate(raw_segments):
        points = _polyline(raw.get("points", raw) if isinstance(raw, dict) else raw)
        if len(points) >= 2:
            segments.append({
                "id": raw.get("id", f"segment_{idx}") if isinstance(raw, dict) else f"segment_{idx}",
                "points": points,
            })
    if segments:
        return segments

    points = _polyline(
        config.get("centerline_route")
        or config.get("route")
        or config.get("route_waypoints")
        or []
    )
    if len(points) >= 2:
        return [{"id": "centerline_route", "points": points}]
    return []


class DrivableAreaMetric(BaseMetric):
    name = "drivable_area"

    def compute(self, frames, config, context=None):
        if not frames:
            return MetricResult.make(self.name, 0.0, {"reason": "missing_frames"})

        segments = _centerline_segments(config)
        allowed_error = float(config.get("allowed_lateral_error_m", 2.0))
        hard_error = float(config.get("hard_lateral_error_m", max(allowed_error * 2.0, allowed_error + 1.0)))
        if not segments:
            return MetricResult.make(
                self.name,
                1.0,
                {
                    "mode": "centerline_deviation",
                    "reason": "missing_centerline",
                    "used_polygon": False,
                    "allowed_lateral_error_m": allowed_error,
                },
            )

        scores = []
        deviations = []
        max_deviation = 0.0
        selected_segment_counts = {}
        for frame in frames:
            pos = location_xy(ego(frame))
            best_segment = None
            best_error = float("inf")
            best_s = 0.0
            best_idx = 0
            for segment in segments:
                s, lateral_error, idx = project_point_to_polyline(pos, segment["points"])
                if lateral_error < best_error:
                    best_segment = segment
                    best_error = lateral_error
                    best_s = s
                    best_idx = idx

            violation = max(0.0, best_error - allowed_error)
            penalty_band = max(hard_error - allowed_error, 0.1)
            score = 1.0 - clamp(violation / penalty_band)
            segment_id = best_segment["id"] if best_segment else "unknown"
            selected_segment_counts[segment_id] = selected_segment_counts.get(segment_id, 0) + 1
            deviations.append(best_error)
            max_deviation = max(max_deviation, best_error)
            scores.append(score)

        return MetricResult.make(
            self.name,
            sum(scores) / len(scores),
            {
                "mode": "centerline_deviation",
                "used_polygon": False,
                "max_centerline_deviation_m": max_deviation,
                "mean_centerline_deviation_m": sum(deviations) / len(deviations),
                "allowed_lateral_error_m": allowed_error,
                "hard_lateral_error_m": hard_error,
                "selected_segment_counts": selected_segment_counts,
                "note": (
                    "Each frame is evaluated against the nearest configured centerline segment; "
                    "after a lane change, the nearest new lane centerline is used."
                ),
                "last_projection_s_m": best_s,
                "last_projection_segment_index": best_idx,
            },
        )
