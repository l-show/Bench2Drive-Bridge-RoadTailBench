#!/usr/bin/env python
import argparse
import sys
from argparse import RawTextHelpFormatter
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
ROADTAILBENCH_ROOT = THIS_DIR.parent
BENCH2DRIVE_ROOT = ROADTAILBENCH_ROOT.parent
ZOO_ROOT = BENCH2DRIVE_ROOT.parent.parent

for module_dir in (
    ROADTAILBENCH_ROOT,
    THIS_DIR,
    BENCH2DRIVE_ROOT / "leaderboard",
    BENCH2DRIVE_ROOT / "scenario_runner",
    ZOO_ROOT,
):
    module_dir = str(module_dir)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)

from batch_scenario_runner.roadtailbench_script_runner import (  # noqa: E402
    RoadTailBenchScriptRunner,
    discover_scenes,
    normalize_ego_mode,
)


def build_argparser():
    parser = argparse.ArgumentParser(
        description="RoadTailBench code-scenario runner. Runs RTBXXX.py directly without Bench2Drive XML/XOSC.",
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=2000, type=int)
    parser.add_argument("--timeout", default=60.0, type=float)
    parser.add_argument("--town", default="", help="Optional CARLA map to load before each scene.")
    parser.add_argument("--fixed-delta-seconds", default=0.05, type=float)
    parser.add_argument("--debug", default=0, type=int)

    parser.add_argument("--scene-root", default=r"G:\RoadTailCode\dynamic_map_code")
    parser.add_argument("--metadata-root", default="", help="Optional directory containing RTB001.json style metadata.")
    parser.add_argument("--scenes", default="", help="Scene selection, e.g. RTB001-RTB020,RTB101. Empty means all discovered scenes.")
    parser.add_argument("--limit", default=0, type=int, help="Maximum number of scenes to run. 0 means unlimited.")
    parser.add_argument("--output-root", default=str(ROADTAILBENCH_ROOT / "outputs" / "code_scenarios"))

    parser.add_argument(
        "--ego-mode",
        "--ego-policy",
        dest="ego_mode",
        choices=["scene_ego", "agent_ego", "script_ego", "external_ego"],
        default="scene_ego",
        help=(
            "scene_ego: RTB script creates/controls ego; runner only finds that vehicle and evaluates metrics.\n"
            "agent_ego: runner creates hero ego and calls a Bench2DriveZoo agent; RTB script must not create/control ego.\n"
            "Legacy aliases are accepted: script_ego=scene_ego, external_ego=agent_ego."
        ),
    )
    parser.add_argument("--ego-role-name", default="hero,ego", help="scene_ego lookup role_name list, comma separated.")
    parser.add_argument("--ego-type-id", default="", help="scene_ego fallback vehicle type_id, e.g. vehicle.tesla.model3.")
    parser.add_argument("--ego-wait-timeout", default=20.0, type=float)
    parser.add_argument("--ego-blueprint", default="vehicle.tesla.model3", help="agent_ego ego blueprint.")
    parser.add_argument("--cleanup-ego", action="store_true")

    parser.add_argument("-a", "--agent", default="", help="Bench2DriveZoo agent py file for agent_ego mode.")
    parser.add_argument("--agent-config", default="", help="Agent config string used by Bench2DriveZoo agents.")
    parser.add_argument("--agent-config-append-scene", action="store_true")
    parser.add_argument("--track", default="SENSORS")

    parser.add_argument("--max-ticks", default=4000, type=int)
    parser.add_argument("--min-ticks-after-script-exit", default=20, type=int)
    parser.add_argument("--actor-log-radius-m", default=120.0, type=float)
    parser.add_argument("--scenario-args", default="", help="Passed to RTB scripts as ROADTAILBENCH_SCENARIO_ARGS.")
    parser.add_argument("--capture-scenario-stdout", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Discover scenes and metadata only; do not import CARLA or start RTB scripts.")
    return parser


def main():
    args = build_argparser().parse_args()
    args.ego_mode = normalize_ego_mode(args.ego_mode)
    scenes = discover_scenes(args.scene_root, args.metadata_root or None, args.scenes)
    if args.limit:
        scenes = scenes[:args.limit]
    print(f"[RoadTailBench] ego_mode={args.ego_mode}", flush=True)
    print(f"[RoadTailBench] discovered {len(scenes)} scene(s)", flush=True)
    for scene in scenes:
        metadata = f" metadata={scene.metadata_path}" if scene.metadata_path else " metadata=<missing>"
        print(f"  - {scene.scene_id}: {scene.script_path}{metadata}", flush=True)
    if not scenes:
        return 0
    if args.dry_run:
        missing = [scene.scene_id for scene in scenes if not scene.metadata_path]
        if missing:
            print(f"[RoadTailBench] dry-run warning: missing metadata for {', '.join(missing)}", flush=True)
        return 0
    runner = RoadTailBenchScriptRunner(args)
    summaries = runner.run(scenes)
    failed = [s for s in summaries if s.get("status") != "completed"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
