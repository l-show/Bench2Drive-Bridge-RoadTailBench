import json
import os
from pathlib import Path

from srunner.scenariomanager.traffic_events import TrafficEventType

from .io import save_json
from .metrics import CORE_METRICS
from .metrics.ability_score import AbilityScoreMetric
from .metrics.composite_score import CompositeScoreMetric


COLLISION_EVENT_TYPES = {
    TrafficEventType.COLLISION_STATIC,
    TrafficEventType.COLLISION_VEHICLE,
    TrafficEventType.COLLISION_PEDESTRIAN,
}


def _vector3_to_list(v):
    return [float(v.x), float(v.y), float(v.z)]


def _rotation_to_list(r):
    return [float(r.roll), float(r.pitch), float(r.yaw)]


def _control_to_dict(c):
    return {
        "steer": float(c.steer),
        "throttle": float(c.throttle),
        "brake": float(c.brake),
        "hand_brake": bool(c.hand_brake),
        "reverse": bool(c.reverse),
    }


def _weather_to_dict(weather):
    if weather is None:
        return {}
    keys = [
        "cloudiness",
        "precipitation",
        "precipitation_deposits",
        "wind_intensity",
        "sun_azimuth_angle",
        "sun_altitude_angle",
        "fog_density",
        "fog_distance",
        "fog_falloff",
        "wetness",
    ]
    return {key: float(getattr(weather, key)) for key in keys if hasattr(weather, key)}


def _actor_to_record(actor, semantic_type=None, hazard_type=None):
    transform = actor.get_transform()
    record = {
        "id": int(actor.id),
        "type_id": actor.type_id,
        "role_name": actor.attributes.get("role_name", ""),
        "location": _vector3_to_list(transform.location),
        "rotation": _rotation_to_list(transform.rotation),
        "velocity": _vector3_to_list(actor.get_velocity()),
        "acceleration": _vector3_to_list(actor.get_acceleration()),
        "angular_velocity": _vector3_to_list(actor.get_angular_velocity()),
    }
    try:
        record["control"] = _control_to_dict(actor.get_control())
    except RuntimeError:
        pass
    if semantic_type:
        record["semantic_type"] = semantic_type
    if hazard_type:
        record["hazard_type"] = hazard_type
    return record


def _route_to_xy(route):
    points = []
    for transform, _road_option in route:
        loc = transform.location
        points.append([float(loc.x), float(loc.y), float(loc.z)])
    return points


def _load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_roadtailbench(frames, config):
    warmup_frames = max(0, int(config.get("metric_warmup_frames", 2)))
    evaluation_frames = frames[warmup_frames:] if len(frames) > warmup_frames else []
    results = {}
    for metric_cls in CORE_METRICS:
        metric = metric_cls()
        result = metric.compute(evaluation_frames, config, results)
        results[result["name"]] = result
    for metric in (CompositeScoreMetric(), AbilityScoreMetric()):
        result = metric.compute(evaluation_frames, config, results)
        results[result["name"]] = result
    return {
        "scenario_id": config.get("scenario_id", "unknown"),
        "route_id": config.get("route_id", "unknown"),
        "evaluation": {
            "raw_frame_count": len(frames),
            "warmup_frames_excluded": warmup_frames,
            "evaluated_frame_count": len(evaluation_frames),
        },
        "metrics": results,
    }


class RoadTailBenchBridgeLogger:
    """Bench2Drive 闭环运行时到 RoadTailBench 指标输入的桥接采集器。"""

    def __init__(self, output_root, route_scenario, route_index, repetition_index, route_record=None, metadata_root=None):
        self.output_root = Path(output_root)
        self.route_scenario = route_scenario
        self.route_index = route_index
        self.repetition_index = repetition_index
        self.route_record = route_record or {}
        self.metadata_root = Path(metadata_root) if metadata_root else None
        self._seen_event_keys = set()
        self._frames = []
        self._closed = False

        route_id = self.route_record.get("route_id") or f"{route_scenario.config.name}_rep{repetition_index}"
        save_name = self.route_record.get("save_name") or route_id
        self.route_dir = self.output_root / save_name
        self.route_dir.mkdir(parents=True, exist_ok=True)
        self.frames_path = self.route_dir / "roadtailbench_frame_log.jsonl"
        self.config_path = self.route_dir / "roadtailbench_scenario_config.json"
        self.metrics_path = self.route_dir / "roadtailbench_metrics.json"
        self._frame_file = self.frames_path.open("w", encoding="utf-8")

        self.config = self._build_config(route_id)
        save_json(self.config_path, self.config)

    def _metadata_candidates(self, route_id):
        if not self.metadata_root:
            return []
        scenario_name = self.route_record.get("scenario_name") or self.route_scenario.config.scenario_configs[0].name
        names = [
            f"{route_id}.json",
            f"{self.route_scenario.config.name}.json",
            f"{scenario_name}.json",
            "default.json",
        ]
        return [self.metadata_root / name for name in names]

    def _load_metadata(self, route_id):
        merged = {}
        for path in self._metadata_candidates(route_id):
            if path.exists():
                data = _load_json(path)
                merged.update(data)
        return merged

    def _build_config(self, route_id):
        metadata = self._load_metadata(route_id)
        scenario_config = self.route_scenario.config.scenario_configs[0]
        weather = self.route_scenario.config.weather[0][1] if self.route_scenario.config.weather else None
        config = {
            "schema_version": "roadtailbench.scenario.v1",
            "scenario_id": metadata.get("scenario_id", scenario_config.name),
            "route_id": route_id,
            "route_index": self.route_index,
            "repetition_index": self.repetition_index,
            "town": str(self.route_scenario.config.town),
            "bench2drive_scenario_name": scenario_config.name,
            "bench2drive_scenario_type": getattr(scenario_config, "type", ""),
            "weather": _weather_to_dict(weather),
            "reference_speed_kmh": 50.0,
            "allowed_lateral_error_m": 2.0,
            "metric_warmup_frames": 2,
            "route": _route_to_xy(self.route_scenario.route),
            "scenario_tags": [],
            "speed_zones": [],
            "hazards": [],
            "hazard_zones": [],
            "drivable_polygons": [],
        }
        config.update(metadata)
        if "route" not in metadata:
            config["route"] = _route_to_xy(self.route_scenario.route)
        return config

    def _collect_events(self, frame):
        events = []
        collisions = []
        for node in self.route_scenario.get_criteria():
            for event in getattr(node, "events", []):
                key = (event.get_type().name, event.get_frame(), event.get_message())
                if key in self._seen_event_keys:
                    continue
                self._seen_event_keys.add(key)
                event_record = {
                    "type": event.get_type().name,
                    "frame": int(event.get_frame()),
                    "message": event.get_message(),
                    "data": event.get_dict() or {},
                }
                events.append(event_record)
                if event.get_type() in COLLISION_EVENT_TYPES:
                    ctype = {
                        TrafficEventType.COLLISION_STATIC: "static",
                        TrafficEventType.COLLISION_VEHICLE: "vehicle",
                        TrafficEventType.COLLISION_PEDESTRIAN: "pedestrian",
                    }.get(event.get_type(), "unknown")
                    collisions.append({
                        "frame": int(event.get_frame()),
                        "type": ctype,
                        "other_actor_type": ctype,
                        "message": event.get_message(),
                    })
        return events, collisions

    def log_tick(self, world, ego_actor, ego_control):
        if self._closed:
            return
        snapshot = world.get_snapshot()
        ego_loc = ego_actor.get_location()
        actors = []
        radius = float(self.config.get("actor_log_radius_m", 100.0))
        for actor in world.get_actors():
            if actor.id == ego_actor.id:
                continue
            if not (actor.type_id.startswith("vehicle.") or actor.type_id.startswith("walker.") or actor.type_id.startswith("static.")):
                continue
            try:
                if actor.get_location().distance(ego_loc) <= radius:
                    actors.append(_actor_to_record(actor))
            except RuntimeError:
                continue

        ego_record = _actor_to_record(ego_actor)
        ego_record["control"] = _control_to_dict(ego_control)
        events, collisions = self._collect_events(int(snapshot.frame))
        frame = {
            "frame": int(snapshot.frame),
            "time": float(snapshot.timestamp.elapsed_seconds),
            "ego": ego_record,
            "actors": actors,
            "collisions": collisions,
            "bench2drive_events": events,
        }
        self._frames.append(frame)
        self._frame_file.write(json.dumps(frame, ensure_ascii=False) + "\n")
        self._frame_file.flush()

    def close_and_evaluate(self, route_record=None):
        if self._closed:
            return None
        self._closed = True
        self._frame_file.close()
        if route_record:
            self.config["bench2drive_result"] = route_record
            save_json(self.config_path, self.config)
        metrics = evaluate_roadtailbench(self._frames, self.config)
        save_json(self.metrics_path, metrics)
        return {
            "frames": str(self.frames_path),
            "config": str(self.config_path),
            "metrics": str(self.metrics_path),
            "summary": metrics.get("metrics", {}).get("roadtailbench_driving_score", {}),
        }


def roadtailbench_output_root(default="./roadtailbench_outputs"):
    return os.environ.get("ROADTAILBENCH_OUTPUT", os.environ.get("SAVE_PATH", default))


def roadtailbench_metadata_root():
    return os.environ.get("ROADTAILBENCH_METADATA_ROOT")
