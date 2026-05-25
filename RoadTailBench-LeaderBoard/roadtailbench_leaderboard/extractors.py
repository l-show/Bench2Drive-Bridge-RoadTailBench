from .geometry import vec2, vec3, norm2


def ego(frame):
    return frame.get("ego", {})


def location_xy(entity):
    return vec2(entity.get("location", [0.0, 0.0, 0.0]))


def velocity_xy(entity):
    return vec2(entity.get("velocity", [0.0, 0.0, 0.0]))


def acceleration_xy(entity):
    return vec2(entity.get("acceleration", [0.0, 0.0, 0.0]))


def speed_mps(entity):
    if "speed_mps" in entity:
        return float(entity["speed_mps"])
    return norm2(velocity_xy(entity))


def yaw_deg(entity):
    rot = vec3(entity.get("rotation", [0.0, 0.0, 0.0]))
    return rot[2]


def control(entity):
    return entity.get("control", {})


def actor_type(actor):
    return (
        actor.get("hazard_type")
        or actor.get("semantic_type")
        or actor.get("role_name")
        or actor.get("type_id")
        or "unknown"
    )
