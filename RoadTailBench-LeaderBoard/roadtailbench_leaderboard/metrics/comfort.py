import math

from .base import BaseMetric, MetricResult
from ..extractors import acceleration_xy, ego, velocity_xy, yaw_deg
from ..geometry import dot2, yaw_to_forward


class ComfortMetric(BaseMetric):
    name = "comfort"

    def compute(self, frames, config, context=None):
        if len(frames) < 2:
            return MetricResult.make(self.name, 0.0, {"reason": "insufficient_frames"})
        lat_acc_max = float(config.get("comfort_lat_acc_max", 4.0))
        lon_acc_min = float(config.get("comfort_lon_acc_min", -5.0))
        lon_acc_max = float(config.get("comfort_lon_acc_max", 3.0))
        jerk_max = float(config.get("comfort_jerk_max", 8.0))
        yaw_rate_max = float(config.get("comfort_yaw_rate_max", 1.0))
        yaw_acc_max = float(config.get("comfort_yaw_acc_max", 2.0))
        ok = 0
        total = 0
        prev_acc_mag = None
        prev_yaw_rate = None
        prev_time = None
        violations = {"lat_acc": 0, "lon_acc": 0, "jerk": 0, "yaw_rate": 0, "yaw_acc": 0}
        for frame in frames:
            e = ego(frame)
            t = float(frame.get("time", total * 0.05))
            yaw = yaw_deg(e)
            fwd = yaw_to_forward(yaw)
            right = (-fwd[1], fwd[0])
            acc = acceleration_xy(e)
            lon_acc = dot2(acc, fwd)
            lat_acc = dot2(acc, right)
            acc_mag = math.hypot(acc[0], acc[1])
            angular = e.get("angular_velocity", [0.0, 0.0, 0.0])
            yaw_rate = math.radians(float(angular[2])) if abs(float(angular[2])) > 3.5 else float(angular[2])
            dt = max(t - prev_time, 1e-3) if prev_time is not None else 0.05
            jerk = 0.0 if prev_acc_mag is None else (acc_mag - prev_acc_mag) / dt
            yaw_acc = 0.0 if prev_yaw_rate is None else (yaw_rate - prev_yaw_rate) / dt
            frame_ok = True
            if abs(lat_acc) > lat_acc_max:
                violations["lat_acc"] += 1
                frame_ok = False
            if lon_acc < lon_acc_min or lon_acc > lon_acc_max:
                violations["lon_acc"] += 1
                frame_ok = False
            if abs(jerk) > jerk_max:
                violations["jerk"] += 1
                frame_ok = False
            if abs(yaw_rate) > yaw_rate_max:
                violations["yaw_rate"] += 1
                frame_ok = False
            if abs(yaw_acc) > yaw_acc_max:
                violations["yaw_acc"] += 1
                frame_ok = False
            ok += int(frame_ok)
            total += 1
            prev_acc_mag = acc_mag
            prev_yaw_rate = yaw_rate
            prev_time = t
        return MetricResult.make(self.name, ok / total if total else 0.0, {"violations": violations})
