import json
from pathlib import Path


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


def actor_to_record(actor, semantic_type=None, hazard_type=None):
    tf = actor.get_transform()
    record = {
        "id": int(actor.id),
        "type_id": actor.type_id,
        "role_name": actor.attributes.get("role_name", ""),
        "location": _vector3_to_list(tf.location),
        "rotation": _rotation_to_list(tf.rotation),
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


class CarlaFrameLogger:
    """Append-only JSONL logger for RoadTailBench metric calculation."""

    def __init__(self, output_path):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.output_path.open("w", encoding="utf-8")
        self.collisions = []

    def attach_collision_sensor(self, world, ego_actor):
        bp = world.get_blueprint_library().find("sensor.other.collision")
        sensor = world.spawn_actor(bp, ego_actor.get_transform(), attach_to=ego_actor)

        def _on_collision(event):
            other = event.other_actor
            self.collisions.append({
                "frame": int(event.frame),
                "other_actor_id": int(other.id) if other else None,
                "other_actor_type": other.type_id if other else "unknown",
                "role_name": other.attributes.get("role_name", "") if other else "",
                "impulse": _vector3_to_list(event.normal_impulse),
            })

        sensor.listen(_on_collision)
        return sensor

    def log_frame(self, world, ego_actor, actors=None, hazards=None, extra=None):
        snapshot = world.get_snapshot()
        frame = int(snapshot.frame)
        collisions = [c for c in self.collisions if c.get("frame") == frame]
        data = {
            "frame": frame,
            "time": float(snapshot.timestamp.elapsed_seconds),
            "ego": actor_to_record(ego_actor),
            "actors": [actor_to_record(a) for a in (actors or []) if a and a.is_alive],
            "hazards": hazards or [],
            "collisions": collisions,
        }
        if extra:
            data.update(extra)
        self._file.write(json.dumps(data, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self):
        self._file.close()
