import importlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from roadtailbench_leaderboard.carla_frame_logger import _control_to_dict, actor_to_record
from roadtailbench_leaderboard.io import save_json
from roadtailbench_leaderboard.metrics import CORE_METRICS
from roadtailbench_leaderboard.metrics.ability_score import AbilityScoreMetric
from roadtailbench_leaderboard.metrics.composite_score import CompositeScoreMetric


RTB_ID_RE = re.compile(r"^RTB(?P<num>\d{3,})(?:[^\d].*)?\.py$", re.IGNORECASE)
carla = None


EGO_MODE_ALIASES = {
    "scene_ego": "scene_ego",
    "script_ego": "scene_ego",
    "agent_ego": "agent_ego",
    "external_ego": "agent_ego",
}


def normalize_ego_mode(value):
    try:
        return EGO_MODE_ALIASES[value]
    except KeyError:
        raise ValueError(f"Unsupported ego mode: {value}")


def _require_carla():
    """运行时加载 CARLA；这样 --help 和场景发现不被 CARLA DLL 环境阻塞。"""
    global carla
    if carla is None:
        import carla as carla_module
        carla = carla_module
    return carla


@dataclass
class RoadTailBenchScene:
    """RoadTailBench 代码场景索引项。"""

    scene_id: str
    number: int
    script_path: Path
    metadata_path: Path = None
    metadata: dict = None


def _vector3_to_list(v):
    return [float(v.x), float(v.y), float(v.z)]


def _rotation_to_list(r):
    return [float(r.roll), float(r.pitch), float(r.yaw)]


def _transform_to_dict(transform):
    return {
        "location": _vector3_to_list(transform.location),
        "rotation": _rotation_to_list(transform.rotation),
    }


def _dict_to_transform(data):
    carla_module = _require_carla()
    loc = data.get("location", data) if isinstance(data, dict) else data
    rot = data.get("rotation", {}) if isinstance(data, dict) else {}
    return carla_module.Transform(
        carla_module.Location(
            x=float(loc.get("x", loc[0] if isinstance(loc, list) else 0.0) if isinstance(loc, dict) else loc[0]),
            y=float(loc.get("y", loc[1] if isinstance(loc, list) else 0.0) if isinstance(loc, dict) else loc[1]),
            z=float(
                loc.get("z", loc[2] if isinstance(loc, list) and len(loc) > 2 else 0.5)
                if isinstance(loc, dict)
                else (loc[2] if len(loc) > 2 else 0.5)
            ),
        ),
        carla_module.Rotation(
            pitch=float(rot.get("pitch", rot[0] if isinstance(rot, list) and len(rot) > 0 else 0.0)),
            yaw=float(rot.get("yaw", rot[2] if isinstance(rot, list) and len(rot) > 2 else 0.0)),
            roll=float(rot.get("roll", rot[1] if isinstance(rot, list) and len(rot) > 1 else 0.0)),
        ),
    )


def _metadata_location(data):
    if not data:
        return None
    loc = data.get("location", data) if isinstance(data, dict) else data
    try:
        if isinstance(loc, dict):
            return (
                float(loc.get("x", 0.0)),
                float(loc.get("y", 0.0)),
                float(loc.get("z", 0.5)),
            )
        return (
            float(loc[0]),
            float(loc[1]),
            float(loc[2] if len(loc) > 2 else 0.5),
        )
    except (TypeError, ValueError, IndexError):
        return None


def _load_json_if_exists(path):
    path = Path(path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_roadtailbench(frames, config):
    """复用 RoadTailBench 10 个核心指标，不依赖 Bench2Drive 原生 ScenarioRunner。"""
    results = {}
    for metric_cls in CORE_METRICS:
        metric = metric_cls()
        result = metric.compute(frames, config, results)
        results[result["name"]] = result
    for metric in (CompositeScoreMetric(), AbilityScoreMetric()):
        result = metric.compute(frames, config, results)
        results[result["name"]] = result
    return {
        "scenario_id": config.get("scenario_id", "unknown"),
        "route_id": config.get("route_id", "unknown"),
        "metrics": results,
    }


def _parse_scene_range(value):
    """解析 RTB001-RTB010、1-10、RTB101 这种选择表达式。"""
    if not value:
        return None
    selected = set()
    for raw_part in value.split(","):
        part = raw_part.strip().upper().replace("RTB", "")
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            start = int(left)
            end = int(right.replace("RTB", ""))
            if end < start:
                start, end = end, start
            selected.update(range(start, end + 1))
        else:
            selected.add(int(part))
    return selected


def discover_scenes(scene_root, metadata_root=None, scene_range=None):
    """从动态地图代码目录发现 RTBXXX.py，自动跳过不存在或不匹配的文件。"""
    scene_root = _resolve_scene_root(scene_root)
    metadata_root = Path(metadata_root) if metadata_root else None
    selected_numbers = _parse_scene_range(scene_range)
    scenes = {}
    for path in scene_root.glob("RTB*.py"):
        match = RTB_ID_RE.match(path.name)
        if not match:
            continue
        number = int(match.group("num"))
        if selected_numbers is not None and number not in selected_numbers:
            continue

        # 同一编号可能有备份或草稿，优先 RTB001.py 这种规范文件。
        scene_id = f"RTB{number:03d}"
        old = scenes.get(number)
        if old and old.script_path.name.upper() == f"{scene_id}.PY":
            continue

        metadata_path = None
        metadata = {}
        if metadata_root:
            for candidate in (metadata_root / f"{scene_id}.json", metadata_root / f"{path.stem}.json"):
                if candidate.exists():
                    metadata_path = candidate
                    metadata = _load_json_if_exists(candidate)
                    break

        scenes[number] = RoadTailBenchScene(
            scene_id=scene_id,
            number=number,
            script_path=path,
            metadata_path=metadata_path,
            metadata=metadata,
        )
    return [scenes[k] for k in sorted(scenes)]


def _resolve_scene_root(scene_root):
    """解析场景目录；中文路径编码异常时自动在 G:\\RoadTailCode 下兜底搜索。"""
    root = Path(scene_root)
    if root.exists():
        return root
    fallback_parent = Path(r"G:\RoadTailCode")
    if fallback_parent.exists():
        for child in fallback_parent.iterdir():
            if child.is_dir() and any(child.glob("RTB*.py")):
                return child
    return root


class RoadTailBenchRuntimeLogger:
    """直接从 CARLA 世界采集 RoadTailBench 指标所需逐帧数据。"""

    def __init__(self, output_dir, scene, config):
        self.output_dir = Path(output_dir)
        self.scene = scene
        self.config = config
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.frames_path = self.output_dir / "roadtailbench_frame_log.jsonl"
        self.config_path = self.output_dir / "roadtailbench_scenario_config.json"
        self.metrics_path = self.output_dir / "roadtailbench_metrics.json"
        self.summary_path = self.output_dir / "roadtailbench_run_summary.json"
        self._file = self.frames_path.open("w", encoding="utf-8")
        self._frames = []
        self._collision_sensor = None
        self._collisions = []
        save_json(self.config_path, self.config)

    def attach_collision_sensor(self, world, ego_actor):
        carla_module = _require_carla()
        bp = world.get_blueprint_library().find("sensor.other.collision")
        self._collision_sensor = world.spawn_actor(bp, carla_module.Transform(), attach_to=ego_actor)

        def _on_collision(event):
            other = event.other_actor
            self._collisions.append({
                "frame": int(event.frame),
                "type": "collision",
                "other_actor_id": int(other.id) if other else None,
                "other_actor_type": other.type_id if other else "unknown",
                "role_name": other.attributes.get("role_name", "") if other else "",
                "impulse": _vector3_to_list(event.normal_impulse),
            })

        self._collision_sensor.listen(_on_collision)

    def log_tick(self, world, ego_actor, ego_control=None, actor_radius_m=120.0, extra=None):
        snapshot = world.get_snapshot()
        frame_id = int(snapshot.frame)
        ego_loc = ego_actor.get_location()
        actors = []
        for actor in world.get_actors():
            if actor.id == ego_actor.id or actor.type_id.startswith("sensor."):
                continue
            if not (
                actor.type_id.startswith("vehicle.")
                or actor.type_id.startswith("walker.")
                or actor.type_id.startswith("static.")
                or actor.type_id.startswith("traffic.")
            ):
                continue
            try:
                if actor.get_location().distance(ego_loc) <= actor_radius_m:
                    actors.append(actor_to_record(actor))
            except RuntimeError:
                continue

        ego_record = actor_to_record(ego_actor)
        if ego_control is not None:
            ego_record["control"] = _control_to_dict(ego_control)
        collisions = [c for c in self._collisions if c.get("frame") == frame_id]
        record = {
            "frame": frame_id,
            "time": float(snapshot.timestamp.elapsed_seconds),
            "ego": ego_record,
            "actors": actors,
            "collisions": collisions,
        }
        if extra:
            record.update(extra)
        self._frames.append(record)
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self, run_summary=None):
        try:
            if self._collision_sensor:
                self._collision_sensor.stop()
                self._collision_sensor.destroy()
        finally:
            self._file.close()
        metrics = evaluate_roadtailbench(self._frames, self.config)
        save_json(self.metrics_path, metrics)
        if run_summary:
            save_json(self.summary_path, run_summary)
        return {
            "frames": str(self.frames_path),
            "config": str(self.config_path),
            "metrics": str(self.metrics_path),
            "summary": str(self.summary_path),
        }


class RoadTailBenchScriptRunner:
    """RoadTailBench 纯代码动态场景批量执行器。"""

    def __init__(self, args):
        self.args = args
        self.args.ego_mode = normalize_ego_mode(getattr(args, "ego_mode", getattr(args, "ego_policy", "scene_ego")))
        carla_module = _require_carla()
        self.client = carla_module.Client(args.host, args.port)
        self.client.set_timeout(args.timeout)
        self.world = None
        self.agent_instance = None
        self.agent_wrapper = None
        self._agent_module = None

    def _connect_world(self, scene):
        metadata = scene.metadata or {}
        town = metadata.get("town") or self.args.town
        if town:
            self.world = self.client.load_world(town)
        else:
            self.world = self.client.get_world()
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = float(self.args.fixed_delta_seconds)
        self.world.apply_settings(settings)
        return self.world

    def _restore_async_world(self):
        if not self.world:
            return
        settings = self.world.get_settings()
        settings.synchronous_mode = False
        settings.fixed_delta_seconds = None
        self.world.apply_settings(settings)

    def _find_scene_ego(self, scene):
        metadata = scene.metadata or {}
        role_values = []
        for key in ("ego_role_names", "ego_role_name"):
            value = metadata.get(key)
            if isinstance(value, list):
                role_values.extend(value)
            elif isinstance(value, str):
                role_values.extend(value.split(","))
        role_values.extend(self.args.ego_role_name.split(","))
        role_names = []
        for value in role_values:
            value = str(value).strip()
            if value and value not in role_names:
                role_names.append(value)

        actors = list(self.world.get_actors().filter("vehicle.*"))
        for role_name in role_names:
            for actor in actors:
                if actor.attributes.get("role_name") == role_name:
                    return actor

        ego_type_id = (
            metadata.get("ego_type_id")
            or metadata.get("ego_blueprint")
            or getattr(self.args, "ego_type_id", "")
        )
        ego_start = _metadata_location(metadata.get("ego_start") or metadata.get("ego_spawn"))
        if ego_type_id:
            matches = [actor for actor in actors if actor.type_id == ego_type_id]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1 and ego_start:
                carla_module = _require_carla()
                start_loc = carla_module.Location(x=ego_start[0], y=ego_start[1], z=ego_start[2])
                ranked = []
                for actor in matches:
                    try:
                        ranked.append((actor.get_location().distance(start_loc), actor))
                    except RuntimeError:
                        continue
                ranked.sort(key=lambda item: item[0])
                if ranked and (len(ranked) == 1 or ranked[0][0] + 1.0 < ranked[1][0]):
                    return ranked[0][1]
                if ranked and ranked[0][0] <= float(metadata.get("ego_start_match_radius_m", 8.0)):
                    close = [
                        item for item in ranked
                        if item[0] <= float(metadata.get("ego_start_match_radius_m", 8.0))
                    ]
                    if len(close) == 1:
                        return close[0][1]
            if len(matches) > 1:
                raise RuntimeError(
                    f"{scene.scene_id}: found {len(matches)} vehicles with type_id={ego_type_id}; "
                    "set ego role_name or provide ego_start metadata that uniquely identifies the ego."
                )
        if ego_start:
            carla_module = _require_carla()
            start_loc = carla_module.Location(x=ego_start[0], y=ego_start[1], z=ego_start[2])
            ranked = []
            for actor in actors:
                try:
                    ranked.append((actor.get_location().distance(start_loc), actor))
                except RuntimeError:
                    continue
            ranked.sort(key=lambda item: item[0])
            radius = float(metadata.get("ego_start_match_radius_m", 6.0))
            close = [item for item in ranked if item[0] <= radius]
            if len(close) == 1:
                return close[0][1]
        if len(actors) == 1:
            return actors[0]
        return None

    def _spawn_agent_ego(self, scene):
        metadata = scene.metadata or {}
        ego_meta = metadata.get("ego_start") or metadata.get("ego_spawn")
        if not ego_meta:
            raise RuntimeError(f"{scene.scene_id} missing ego_start metadata; agent_ego cannot spawn ego")
        transform = _dict_to_transform(ego_meta)
        bp_id = metadata.get("ego_blueprint", self.args.ego_blueprint)
        bp = self.world.get_blueprint_library().find(bp_id)
        bp.set_attribute("role_name", "hero")
        if bp.has_attribute("color"):
            bp.set_attribute("color", metadata.get("ego_color", "0,0,255"))
        ego = self.world.try_spawn_actor(bp, transform)
        if not ego:
            raise RuntimeError(f"{scene.scene_id} failed to spawn agent_ego: {bp_id} @ {ego_meta}")
        return ego

    def _build_route_from_metadata(self, scene):
        metadata = scene.metadata or {}
        raw_points = (
            metadata.get("route")
            or metadata.get("route_waypoints")
            or metadata.get("centerline_route")
            or []
        )
        route = []
        for point in raw_points:
            transform = _dict_to_transform(point)
            route.append((transform, None))
        if not route and metadata.get("ego_start") and metadata.get("ego_end"):
            route = [(_dict_to_transform(metadata["ego_start"]), None), (_dict_to_transform(metadata["ego_end"]), None)]
        gps_route = [({"lat": 0.0, "lon": 0.0, "z": t.location.z}, road_option) for t, road_option in route]
        return gps_route, route

    def _setup_agent(self, scene, ego):
        if not self.args.agent:
            if self.args.ego_mode == "agent_ego":
                raise RuntimeError("agent_ego mode requires -a/--agent so the model can control ego")
            return None, None

        sys.path.insert(0, str(Path(self.args.agent).resolve().parent))
        module_name = Path(self.args.agent).stem
        self._agent_module = importlib.import_module(module_name)
        class_name = self._agent_module.get_entry_point()
        agent_cls = getattr(self._agent_module, class_name)
        agent = agent_cls(self.args.host, self.args.port, self.args.debug)

        gps_route, route = self._build_route_from_metadata(scene)
        agent.set_global_plan(gps_route, route)
        agent_config = self.args.agent_config
        if self.args.agent_config_append_scene:
            agent_config = f"{agent_config}+{scene.scene_id}"
        agent.setup(agent_config)

        from leaderboard.autoagents.agent_wrapper import AgentWrapperFactory, validate_sensor_configuration
        from srunner.scenariomanager.carla_data_provider import CarlaDataProvider

        CarlaDataProvider.set_client(self.client)
        CarlaDataProvider.set_world(self.world)
        validate_sensor_configuration(agent.sensors(), agent.track, self.args.track)
        wrapper = AgentWrapperFactory.get_wrapper(agent)
        wrapper.setup_sensors(ego)
        return agent, wrapper

    def _start_scene_process(self, scene, output_dir):
        if self.args.dry_run:
            return None
        env = os.environ.copy()
        env["ROADTAILBENCH_SCENE_ID"] = scene.scene_id
        env["ROADTAILBENCH_OUTPUT_DIR"] = str(output_dir)
        env["ROADTAILBENCH_EGO_MODE"] = self.args.ego_mode
        env["ROADTAILBENCH_EGO_POLICY"] = self.args.ego_mode
        env["ROADTAILBENCH_CARLA_HOST"] = self.args.host
        env["ROADTAILBENCH_CARLA_PORT"] = str(self.args.port)
        if self.args.scenario_args:
            env["ROADTAILBENCH_SCENARIO_ARGS"] = self.args.scenario_args
        cmd = [sys.executable, str(scene.script_path)]
        return subprocess.Popen(
            cmd,
            cwd=str(scene.script_path.parent),
            env=env,
            stdout=subprocess.PIPE if self.args.capture_scenario_stdout else None,
            stderr=subprocess.STDOUT if self.args.capture_scenario_stdout else None,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def _terminate_process(self, proc):
        if not proc or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    def _build_config(self, scene):
        metadata = dict(scene.metadata or {})
        config = {
            "schema_version": "roadtailbench.code_scene.v1",
            "scenario_id": scene.scene_id,
            "route_id": scene.scene_id,
            "script_path": str(scene.script_path),
            "metadata_path": str(scene.metadata_path) if scene.metadata_path else None,
            "town": metadata.get("town") or self.args.town or self.world.get_map().name.split("/")[-1],
            "ego_mode": self.args.ego_mode,
            "reference_speed_kmh": 50.0,
            "allowed_lateral_error_m": 2.0,
            "route": [],
            "scenario_tags": [],
            "speed_zones": [],
            "hazards": [],
            "hazard_zones": [],
            "drivable_polygons": [],
        }
        config.update(metadata)
        if not config.get("route"):
            _gps, route = self._build_route_from_metadata(scene)
            config["route"] = [[t.location.x, t.location.y, t.location.z] for t, _ in route]
        return config

    def run_scene(self, scene):
        started_at = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(self.args.output_root) / f"{scene.scene_id}_{started_at}"
        output_dir.mkdir(parents=True, exist_ok=True)
        proc = None
        logger = None
        ego = None
        status = "started"
        error = ""
        ticks = 0
        script_exit_tick = None

        try:
            world = self._connect_world(scene)
            if self.args.ego_mode == "agent_ego":
                ego = self._spawn_agent_ego(scene)

            proc = self._start_scene_process(scene, output_dir)

            wait_deadline = time.time() + float(self.args.ego_wait_timeout)
            while time.time() < wait_deadline:
                world.tick()
                ego = ego or self._find_scene_ego(scene)
                if ego:
                    break
                if proc and proc.poll() is not None:
                    break

            if not ego:
                raise RuntimeError(f"{scene.scene_id} 未发现 ego/hero 车辆，无法采集闭环评测数据")

            config = self._build_config(scene)
            config["ego_initial_transform"] = _transform_to_dict(ego.get_transform())
            logger = RoadTailBenchRuntimeLogger(output_dir, scene, config)
            logger.attach_collision_sensor(world, ego)

            agent, wrapper = self._setup_agent(scene, ego) if self.args.ego_mode == "agent_ego" else (None, None)
            self.agent_instance = agent
            self.agent_wrapper = wrapper

            max_ticks = int(self.args.max_ticks)
            while ticks < max_ticks:
                world.tick()
                ticks += 1
                ego_control = None
                if wrapper:
                    ego_control = wrapper()
                    ego.apply_control(ego_control)
                else:
                    try:
                        ego_control = ego.get_control()
                    except RuntimeError:
                        ego_control = None
                logger.log_tick(world, ego, ego_control, actor_radius_m=self.args.actor_log_radius_m)
                if proc and proc.poll() is not None:
                    if script_exit_tick is None:
                        script_exit_tick = ticks
                    if ticks - script_exit_tick >= int(self.args.min_ticks_after_script_exit):
                        break

            status = "completed"
        except Exception as exc:
            status = "failed"
            error = f"{exc}\n{traceback.format_exc()}"
        finally:
            if self.agent_wrapper:
                try:
                    self.agent_wrapper.cleanup()
                except Exception:
                    pass
                self.agent_wrapper = None
            if self.agent_instance:
                try:
                    self.agent_instance.destroy()
                except Exception:
                    pass
                self.agent_instance = None
            self._terminate_process(proc)
            summary = {
                "scene_id": scene.scene_id,
                "status": status,
                "error": error,
                "ticks": ticks,
                "script_path": str(scene.script_path),
                "output_dir": str(output_dir),
            }
            if logger:
                outputs = logger.close(summary)
                summary["outputs"] = outputs
            else:
                save_json(output_dir / "roadtailbench_run_summary.json", summary)
            if self.args.cleanup_ego and ego and ego.is_alive and self.args.ego_mode == "agent_ego":
                try:
                    ego.destroy()
                except Exception:
                    pass
            try:
                self._restore_async_world()
            except Exception:
                pass
        return summary

    def run(self, scenes):
        summaries = []
        for idx, scene in enumerate(scenes):
            if self.args.limit and len(summaries) >= self.args.limit:
                break
            print(f"[RoadTailBench] ({idx + 1}/{len(scenes)}) running {scene.scene_id}: {scene.script_path}", flush=True)
            summary = self.run_scene(scene)
            summaries.append(summary)
            save_json(Path(self.args.output_root) / "roadtailbench_batch_summary.json", summaries)
            print(f"[RoadTailBench] {scene.scene_id} {summary['status']} ticks={summary['ticks']}", flush=True)
        return summaries
