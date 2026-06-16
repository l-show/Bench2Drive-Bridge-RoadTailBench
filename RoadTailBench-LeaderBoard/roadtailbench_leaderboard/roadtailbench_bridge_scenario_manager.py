import os

import carla
import py_trees

from leaderboard.scenarios.scenario_manager import ScenarioManager
from leaderboard.envs.sensor_interface import SensorReceivedNoData
from leaderboard.autoagents.agent_wrapper import AgentError, TickRuntimeError
from srunner.scenariomanager.carla_data_provider import CarlaDataProvider
from srunner.scenariomanager.timer import GameTime


class RoadTailBenchBridgeScenarioManager(ScenarioManager):
    """带 RoadTailBench 帧日志采集的 Bench2Drive ScenarioManager 派生版。"""

    def __init__(self, timeout, statistics_manager, debug_mode=0):
        super().__init__(timeout, statistics_manager, debug_mode)
        self.roadtailbench_logger = None
        self.roadtailbench_max_ticks = int(os.environ.get("ROADTAILBENCH_MAX_TICKS", "0") or "0")

    def set_roadtailbench_logger(self, logger):
        self.roadtailbench_logger = logger

    def _tick_scenario(self):
        if self._running and self.get_running_status():
            CarlaDataProvider.get_world().tick(self._timeout)

        timestamp = CarlaDataProvider.get_world().get_snapshot().timestamp

        if self._timestamp_last_run < timestamp.elapsed_seconds and self._running:
            self._timestamp_last_run = timestamp.elapsed_seconds

            self._watchdog.update()
            GameTime.on_carla_tick(timestamp)
            CarlaDataProvider.on_carla_tick()
            self.tick_count += 1
            self._watchdog.pause()

            if self.roadtailbench_max_ticks and self.tick_count > self.roadtailbench_max_ticks:
                raise TickRuntimeError(f"RoadTailBench tick_count > {self.roadtailbench_max_ticks}")
            if self.tick_count > 4000:
                raise TickRuntimeError("RuntimeError, tick_count > 4000")

            try:
                self._agent_watchdog.resume()
                self._agent_watchdog.update()
                ego_action = self._agent_wrapper()
                self._agent_watchdog.pause()
            except SensorReceivedNoData as e:
                raise RuntimeError(e)
            except Exception as e:
                raise AgentError(e)

            self._watchdog.resume()
            self.ego_vehicles[0].apply_control(ego_action)

            py_trees.blackboard.Blackboard().set("AV_control", ego_action, overwrite=True)
            self.scenario_tree.tick_once()

            # 在原 Bench2Drive criteria 更新后采集，确保本帧产生的事件可以同步写入。
            if self.roadtailbench_logger:
                self.roadtailbench_logger.log_tick(
                    CarlaDataProvider.get_world(),
                    self.ego_vehicles[0],
                    ego_action,
                )

            if self._debug_mode > 1:
                self.compute_duration_time()
                self._statistics_manager.compute_route_statistics(
                    self.route_index,
                    self.scenario_duration_system,
                    self.scenario_duration_game,
                    failure_message="",
                )
                self._statistics_manager.write_live_results(
                    self.route_index,
                    self.ego_vehicles[0].get_velocity().length(),
                    ego_action,
                    self.ego_vehicles[0].get_location(),
                )

            if self._debug_mode > 2:
                print("\n")
                py_trees.display.print_ascii_tree(self.scenario_tree, show_status=True)

            if self.scenario_tree.status != py_trees.common.Status.RUNNING:
                self._running = False

            ego_trans = self.ego_vehicles[0].get_transform()
            self._spectator.set_transform(carla.Transform(
                ego_trans.location + carla.Location(z=70),
                carla.Rotation(pitch=-90),
            ))

    def stop_scenario(self):
        try:
            super().stop_scenario()
        finally:
            self.roadtailbench_logger = None
