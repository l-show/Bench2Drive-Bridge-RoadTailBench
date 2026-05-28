#!/usr/bin/env python
import argparse
import os
import sys
import traceback
from argparse import RawTextHelpFormatter
from pathlib import Path
from datetime import datetime

import carla

THIS_DIR = Path(__file__).resolve().parent
BENCH2DRIVE_ROOT = THIS_DIR.parent
for module_dir in (BENCH2DRIVE_ROOT / "leaderboard", BENCH2DRIVE_ROOT / "scenario_runner", THIS_DIR):
    module_dir = str(module_dir)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)

from leaderboard.leaderboard_evaluator import (
    FAILURE_MESSAGES,
    LeaderboardEvaluator,
    find_free_port,
    get_weather_id,
    sensors_to_icons,
)
from leaderboard.autoagents.agent_wrapper import AgentError, TickRuntimeError, validate_sensor_configuration
from leaderboard.envs.sensor_interface import SensorConfigurationInvalid
from leaderboard.scenarios.route_scenario import RouteScenario
from leaderboard.utils.route_indexer import RouteIndexer
from leaderboard.utils.statistics_manager import StatisticsManager
from srunner.scenariomanager.carla_data_provider import CarlaDataProvider
from srunner.scenariomanager.timer import GameTime
from srunner.scenariomanager.watchdog import Watchdog

from roadtailbench_leaderboard.bench2drive_bridge import (
    RoadTailBenchBridgeLogger,
    roadtailbench_metadata_root,
    roadtailbench_output_root,
)
from roadtailbench_leaderboard.roadtailbench_bridge_scenario_manager import RoadTailBenchBridgeScenarioManager


class RoadTailBenchBridgeEvaluator(LeaderboardEvaluator):
    """Bench2Drive 原 evaluator 的 RoadTailBench 指标派生入口。"""

    def __init__(self, args, statistics_manager):
        super().__init__(args, statistics_manager)
        self.manager = RoadTailBenchBridgeScenarioManager(args.timeout, self.statistics_manager, args.debug)

    def _register_roadtailbench_logger(self, args, config, route_name, scenario_name, weather_id, save_name, town_name):
        route_record = {
            "route_id": route_name,
            "scenario_name": scenario_name,
            "weather_id": weather_id,
            "save_name": save_name,
            "town_name": town_name,
        }
        logger = RoadTailBenchBridgeLogger(
            output_root=args.roadtailbench_output,
            route_scenario=self.route_scenario,
            route_index=config.index,
            repetition_index=config.repetition_index,
            route_record=route_record,
            metadata_root=args.roadtailbench_metadata_root,
        )
        self.manager.set_roadtailbench_logger(logger)
        return logger

    def _load_and_run_scenario(self, args, config):
        crash_message = ""
        entry_status = "Started"
        roadtailbench_logger = None

        print("\n\033[1m========= Preparing {} (repetition {}) =========\033[0m".format(
            config.name, config.repetition_index), flush=True)

        route_name = f"{config.name}_rep{config.repetition_index}"
        scenario_name = config.scenario_configs[0].name
        town_name = str(config.town)
        weather_id = get_weather_id(config.weather[0][1])
        current_time = datetime.now().strftime("%m_%d_%H_%M_%S")
        save_name = f"{route_name}_{town_name}_{scenario_name}_{weather_id}_{current_time}"
        self.statistics_manager.create_route_data(route_name, scenario_name, weather_id, save_name, town_name, config.index)

        print("\033[1m> Loading the world\033[0m", flush=True)
        try:
            self._load_and_wait_for_world(args, config.town)
            self.route_scenario = RouteScenario(world=self.world, config=config, debug_mode=args.debug)
            self.statistics_manager.set_scenario(self.route_scenario)
            roadtailbench_logger = self._register_roadtailbench_logger(
                args, config, route_name, scenario_name, weather_id, save_name, town_name)
        except Exception:
            print("\n\033[91mThe scenario could not be loaded:", flush=True)
            print(f"\n{traceback.format_exc()}\033[0m", flush=True)
            entry_status, crash_message = FAILURE_MESSAGES["Simulation"]
            self._register_statistics(config.index, entry_status, crash_message)
            self._cleanup()
            return True

        print("\033[1m> Setting up the agent\033[0m", flush=True)
        try:
            self._agent_watchdog = Watchdog(args.timeout)
            self._agent_watchdog.start()
            agent_class_name = getattr(self.module_agent, "get_entry_point")()
            agent_class_obj = getattr(self.module_agent, agent_class_name)

            if getattr(agent_class_obj, "get_ros_version")() == 1 and self._ros1_server is None:
                from leaderboard.autoagents.ros1_agent import ROS1Server
                self._ros1_server = ROS1Server()
                self._ros1_server.start()

            self.agent_instance = agent_class_obj(args.host, args.port, args.debug)
            self.agent_instance.set_global_plan(self.route_scenario.gps_route, self.route_scenario.route)
            route_agent_config = args.agent_config + "+" + save_name
            self.agent_instance.setup(route_agent_config)

            if not self.sensors:
                self.sensors = self.agent_instance.sensors()
                track = self.agent_instance.track
                validate_sensor_configuration(self.sensors, track, args.track)
                self.sensor_icons = [sensors_to_icons[sensor["type"]] for sensor in self.sensors]
                self.statistics_manager.save_sensors(self.sensor_icons)
                self.statistics_manager.write_statistics()
                self.sensors_initialized = True

            self._agent_watchdog.stop()
            self._agent_watchdog = None
        except SensorConfigurationInvalid as e:
            print("\n\033[91mThe sensor's configuration used is invalid:", flush=True)
            print(f"{e}\033[0m\n", flush=True)
            entry_status, crash_message = FAILURE_MESSAGES["Sensors"]
            self._register_statistics(config.index, entry_status, crash_message)
            self._cleanup()
            return True
        except Exception as e:
            print("\n\033[91mCould not set up the required agent:", flush=True)
            print(f"\n{traceback.format_exc()}\033[0m", flush=True)
            print(f"{e}\033[0m\n", flush=True)
            entry_status, crash_message = FAILURE_MESSAGES["Agent_init"]
            self._register_statistics(config.index, entry_status, crash_message)
            self._cleanup()
            return True

        print("\033[1m> Running the route with RoadTailBench bridge logging\033[0m", flush=True)
        try:
            if args.record:
                self.client.start_recorder("{}/{}_rep{}.log".format(args.record, config.name, config.repetition_index))
            self.manager.load_scenario(self.route_scenario, self.agent_instance, config.index, config.repetition_index)
            self.manager.tick_count = 0
            self.manager.run_scenario()
        except AgentError:
            print("\n\033[91mStopping the route, the agent has crashed:", flush=True)
            print(f"\n{traceback.format_exc()}\033[0m")
            entry_status, crash_message = FAILURE_MESSAGES["Agent_runtime"]
        except KeyboardInterrupt:
            return True
        except TickRuntimeError:
            entry_status, crash_message = "Started", "TickRuntime"
        except Exception:
            print("\n\033[91mError during the simulation:", flush=True)
            print(f"\n{traceback.format_exc()}\033[0m", flush=True)
            entry_status, crash_message = FAILURE_MESSAGES["Simulation"]

        try:
            print("\033[1m> Stopping the route\033[0m", flush=True)
            self.manager.stop_scenario()
            self._register_statistics(config.index, entry_status, crash_message)

            if roadtailbench_logger:
                route_record = self.statistics_manager._results.checkpoint.records[config.index].to_json()
                output = roadtailbench_logger.close_and_evaluate(route_record)
                print(f"\033[1m> RoadTailBench metrics saved: {output['metrics']}\033[0m", flush=True)

            if args.record:
                self.client.stop_recorder()

            self._cleanup()
        except Exception:
            print("\n\033[91mFailed to stop the scenario, the statistics might be empty:", flush=True)
            print(f"\n{traceback.format_exc()}\033[0m", flush=True)
            _, crash_message = FAILURE_MESSAGES["Simulation"]
            if roadtailbench_logger:
                roadtailbench_logger.close_and_evaluate()

        return crash_message == "Simulation crashed"


def build_argparser():
    description = "Bench2Drive evaluation with RoadTailBench metric bridge\n"
    parser = argparse.ArgumentParser(description=description, formatter_class=RawTextHelpFormatter)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=2000, type=int)
    parser.add_argument("--traffic-manager-port", default=8000, type=int)
    parser.add_argument("--traffic-manager-seed", default=0, type=int)
    parser.add_argument("--debug", type=int, default=0)
    parser.add_argument("--record", type=str, default="")
    parser.add_argument("--timeout", default=600.0, type=float)
    parser.add_argument("--routes", required=True)
    parser.add_argument("--routes-subset", default="", type=str)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("-a", "--agent", type=str, required=True)
    parser.add_argument("--agent-config", type=str, default="")
    parser.add_argument("--track", type=str, default="SENSORS")
    parser.add_argument("--resume", type=bool, default=False)
    parser.add_argument("--checkpoint", type=str, default="./simulation_results.json")
    parser.add_argument("--debug-checkpoint", type=str, default="./live_results.txt")
    parser.add_argument("--gpu-rank", type=int, default=0)
    parser.add_argument("--roadtailbench-output", default=roadtailbench_output_root())
    parser.add_argument("--roadtailbench-metadata-root", default=roadtailbench_metadata_root())
    return parser


def main():
    args = build_argparser().parse_args()
    statistics_manager = StatisticsManager(args.checkpoint, args.debug_checkpoint)
    evaluator = RoadTailBenchBridgeEvaluator(args, statistics_manager)
    crashed = evaluator.run(args)
    del evaluator
    sys.exit(-1 if crashed else 0)


if __name__ == "__main__":
    main()
