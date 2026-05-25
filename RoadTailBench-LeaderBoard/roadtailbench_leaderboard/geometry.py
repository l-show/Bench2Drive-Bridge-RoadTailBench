import math


EPS = 1e-6


def clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, value))


def vec2(value, default=(0.0, 0.0)):
    if value is None:
        return default
    return (float(value[0]), float(value[1]))


def vec3(value, default=(0.0, 0.0, 0.0)):
    if value is None:
        return default
    return (float(value[0]), float(value[1]), float(value[2]))


def norm2(v):
    return math.hypot(v[0], v[1])


def sub2(a, b):
    return (a[0] - b[0], a[1] - b[1])


def add2(a, b):
    return (a[0] + b[0], a[1] + b[1])


def mul2(a, s):
    return (a[0] * s, a[1] * s)


def dot2(a, b):
    return a[0] * b[0] + a[1] * b[1]


def distance2(a, b):
    return norm2(sub2(a, b))


def yaw_to_forward(yaw_deg):
    yaw = math.radians(yaw_deg)
    return (math.cos(yaw), math.sin(yaw))


def world_to_ego_frame(delta_xy, ego_yaw_deg):
    yaw = math.radians(ego_yaw_deg)
    c = math.cos(yaw)
    s = math.sin(yaw)
    x, y = delta_xy
    return (c * x + s * y, -s * x + c * y)


def polyline_lengths(points):
    if not points or len(points) < 2:
        return [0.0], 0.0
    accum = [0.0]
    total = 0.0
    for i in range(1, len(points)):
        total += distance2(points[i - 1], points[i])
        accum.append(total)
    return accum, total


def project_point_to_polyline(point, polyline):
    if not polyline:
        return 0.0, float("inf"), 0
    if len(polyline) == 1:
        return 0.0, distance2(point, polyline[0]), 0
    accum, _ = polyline_lengths(polyline)
    best_s = 0.0
    best_d = float("inf")
    best_i = 0
    px, py = point
    for i in range(len(polyline) - 1):
        ax, ay = polyline[i]
        bx, by = polyline[i + 1]
        ab = (bx - ax, by - ay)
        ap = (px - ax, py - ay)
        denom = dot2(ab, ab)
        t = 0.0 if denom < EPS else clamp(dot2(ap, ab) / denom)
        proj = (ax + ab[0] * t, ay + ab[1] * t)
        d = distance2(point, proj)
        if d < best_d:
            best_d = d
            best_s = accum[i] + distance2(polyline[i], proj)
            best_i = i
    return best_s, best_d, best_i


def point_in_polygon(point, polygon):
    if not polygon or len(polygon) < 3:
        return False
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or EPS) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def distance_point_to_polygon(point, polygon):
    if not polygon:
        return float("inf")
    if point_in_polygon(point, polygon):
        return 0.0
    best = float("inf")
    for i in range(len(polygon)):
        a = polygon[i]
        b = polygon[(i + 1) % len(polygon)]
        s, d, _ = project_point_to_polyline(point, [a, b])
        best = min(best, d)
    return best
