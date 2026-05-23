# ScenarioRunner 场景系统模块说明

本文档说明 `scenario_runner/` 目录。该目录提供 Bench2Drive 的场景类、行为树节点、触发条件、实时评价标准和 CARLA actor 管理。

## 1. 目录结构

```text
scenario_runner/
├── scenario_runner.py
├── metrics_manager.py
├── manual_control.py
├── Docs/
├── srunner/
│   ├── autoagents/
│   ├── data/
│   ├── examples/
│   ├── metrics/
│   ├── openscenario/
│   ├── scenarioconfigs/
│   ├── scenariomanager/
│   ├── scenarios/
│   ├── tests/
│   └── tools/
└── requirements.txt
```

Bench2Drive 闭环 leaderboard 主要使用：

```text
srunner/scenarios/
srunner/scenariomanager/
srunner/scenarioconfigs/
srunner/tools/
```

## 2. `srunner/scenarios/`

这里是具体交通场景类，每个文件通常定义一个或多个继承 `BasicScenario` 的 class。

常见类别：

### 2.1 障碍/事故/绕行

```text
route_obstacles.py
construction_crash_vehicle.py
vehicle_opens_door.py
parking_exit.py
parking_cut_in.py
```

代表场景：

- `Accident`
- `AccidentTwoWays`
- `ConstructionObstacle`
- `ConstructionObstacleTwoWays`
- `ParkedObstacle`
- `ParkedObstacleTwoWays`
- `VehicleOpensDoorTwoWays`
- `ParkingExit`
- `ParkingCutIn`

主要考察：

- 绕行能力。
- 对静态障碍和开门车辆的反应。
- 是否压线、碰撞、偏离路线。

### 2.2 并线/汇入/车流交互

```text
actor_flow.py
cut_in.py
cut_in_with_static_vehicle.py
change_lane.py
highway_cut_in.py
left_turn_enter_flow.py
sequentially_lane_change.py
```

代表场景：

- `EnterActorFlow`
- `HighwayExit`
- `HighwayCutIn`
- `MergerIntoSlowTraffic`
- `MergerIntoSlowTrafficV2`
- `InterurbanActorFlow`
- `InterurbanAdvancedActorFlow`
- `StaticCutIn`
- `SequentialLaneChange`
- `JunctionLeftTurnEnterFlow`

主要考察：

- 汇入车流。
- cut-in 处理。
- 交互式换道。
- 复杂车流下规划。

### 2.3 行人/骑行者/横穿

```text
object_crash_vehicle.py
object_crash_intersection.py
pedestrian_crossing.py
cross_bicycle_flow.py
```

代表场景：

- `DynamicObjectCrossing`
- `PedestrianCrossing`
- `ParkingCrossingPedestrian`
- `VehicleTurningRoutePedestrian`
- `CrossingBicycleFlow`

主要考察：

- 行人/骑行者避让。
- 紧急制动。
- 路口转弯时对弱交通参与者的处理。

### 2.4 路口与优先权

```text
no_signal_junction_crossing.py
opposite_vehicle_taking_priority.py
signalized_junction_left_turn.py
signalized_junction_right_turn.py
vanilla_turn.py
t_junction.py
green_traffic_light.py
blocked_intersection.py
invading_turn.py
```

代表场景：

- `NonSignalizedJunctionLeftTurn`
- `NonSignalizedJunctionRightTurn`
- `SignalizedJunctionLeftTurn`
- `SignalizedJunctionRightTurn`
- `OppositeVehicleTakingPriority`
- `OppositeVehicleRunningRedLight`
- `T_Junction`
- `BlockedIntersection`
- `InvadingTurn`

主要考察：

- 路口通行。
- 红绿灯/Stop/让行。
- 对对向来车和堵塞路口的处理。

### 2.5 纵向控制和安全驾驶

```text
follow_leading_vehicle.py
hard_break.py
control_loss.py
other_leading_vehicle.py
```

代表场景：

- `FollowLeadingVehicle`
- `HardBreakRoute`
- `ControlLoss`
- `OtherLeadingVehicle`

主要考察：

- 跟车。
- 前车急刹。
- 失控扰动。
- 纵向安全距离。

### 2.6 急救车让行

```text
yield_to_emergency_vehicle.py
```

代表场景：

- `YieldToEmergencyVehicle`

它会配合 `YieldToEmergencyVehicleTest` 生成对应 infraction。

## 3. `BasicScenario`

路径：

```text
scenario_runner/srunner/scenarios/basic_scenario.py
```

所有 scenario 的基类。

### 3.1 子类通常重写的方法

```python
_initialize_actors(self, config)
_create_behavior(self)
_create_test_criteria(self)
```

含义：

- `_initialize_actors()`：创建其他交通参与者，例如车辆、行人、障碍物。
- `_create_behavior()`：创建 py_trees 行为树，描述场景如何运行。
- `_create_test_criteria()`：创建场景自身的评价标准。

### 3.2 行为树结构

`BasicScenario` 创建：

```text
scenario_tree
  ├── lights behavior
  ├── weather behavior
  ├── behavior_tree
  ├── criteria_tree
  ├── timeout_node
  └── UpdateAllActorControls
```

在 route 模式下，scenario 由 blackboard trigger 控制，只有 ego 接近 trigger point 时才激活。

### 3.3 trigger 与 end

route 模式下：

- `_setup_scenario_trigger()` 返回 `WaitForBlackboardVariable(route_var_name, True)`。
- route scenario 的 `ScenarioTriggerer` 会在 ego 到达 trigger 附近时设置 blackboard。
- `_setup_scenario_end()` 会把 blackboard 变量重置为 False。

## 4. `srunner/scenariomanager/`

这里是场景运行的基础设施。

### 4.1 `carla_data_provider.py`

全局 CARLA 状态管理器。

负责：

- 保存 client/world/map。
- 创建/销毁 actors。
- 缓存 actor location/velocity/transform。
- 管理 Traffic Manager port。
- runtime init mode。

很多 criteria 和 scenario 都通过 `CarlaDataProvider` 取 CARLA 状态，而不是直接到处传 world。

### 4.2 `timer.py`

提供：

- `GameTime`
- `TimeOut`
- `RouteTimeoutBehavior`

leaderboard 每个 tick 会调用：

```python
GameTime.on_carla_tick(timestamp)
```

criteria 和 behavior 都依赖它获取仿真时间和 frame。

### 4.3 `traffic_events.py`

定义所有评测事件：

```text
COLLISION_STATIC
COLLISION_VEHICLE
COLLISION_PEDESTRIAN
ROUTE_DEVIATION
ROUTE_COMPLETION
ROUTE_COMPLETED
TRAFFIC_LIGHT_INFRACTION
WRONG_WAY_INFRACTION
ON_SIDEWALK_INFRACTION
STOP_INFRACTION
OUTSIDE_LANE_INFRACTION
OUTSIDE_ROUTE_LANES_INFRACTION
VEHICLE_BLOCKED
MIN_SPEED_INFRACTION
YIELD_TO_EMERGENCY_VEHICLE
SCENARIO_TIMEOUT
```

`TrafficEvent` 保存：

- type。
- frame。
- message。
- dictionary。

`StatisticsManager` 会读取 criteria 中的 events 并转换为 JSON infractions。

### 4.4 `watchdog.py`

防止 simulation 或 agent 卡死。

leaderboard 中有两个 watchdog：

- simulation watchdog。
- agent watchdog。

### 4.5 `weather_sim.py` 和 `lights_sim.py`

用于 route 中动态天气和灯光行为：

- `RouteWeatherBehavior`
- `RouteLightsBehavior`

## 5. `scenarioatomics/`

路径：

```text
scenario_runner/srunner/scenariomanager/scenarioatomics/
```

这是 ScenarioRunner 最核心的行为树原子节点。

### 5.1 `atomic_behaviors.py`

定义行为节点，例如：

- actor 移动。
- actor 销毁。
- 等待。
- 设置速度。
- 路径跟随。
- 触发 actor flow。
- 更新 actor controls。
- ScenarioTriggerer。

`RouteScenario` 中用到：

```python
ScenarioTriggerer
Idle
```

每个具体 scenario 的 `_create_behavior()` 大量使用这里的节点。

### 5.2 `atomic_trigger_conditions.py`

定义触发条件，例如：

- 到达某个位置。
- 与 ego 距离小于阈值。
- time-to-arrival。
- blackboard variable。
- actor 是否进入区域。

route 模式下最重要的是：

```text
WaitForBlackboardVariable
```

### 5.3 `atomic_criteria.py`

定义评价标准。Bench2Drive route 常驻 criteria 主要来自这里。

重要类：

- `CollisionTest`
- `ActorBlockedTest`
- `OutsideRouteLanesTest`
- `InRouteTest`
- `RouteCompletionTest`
- `RunningRedLightTest`
- `RunningStopTest`
- `MinimumSpeedRouteTest`
- `YieldToEmergencyVehicleTest`
- `ScenarioTimeoutTest`

这些类负责从 CARLA 实时状态产生 `TrafficEvent`。

## 6. 核心 criteria 简述

### 6.1 `CollisionTest`

使用 CARLA collision sensor。

按 other_actor 类型区分：

- static/traffic -> static collision。
- vehicle -> vehicle collision。
- walker -> pedestrian collision。

有去重逻辑，避免同一次碰撞重复计数。

### 6.2 `RouteCompletionTest`

根据 ego 是否通过 route waypoint 更新完成百分比。

route 完成条件：

- 完成率大于 99%。
- 到终点距离小于 10m。

### 6.3 `OutsideRouteLanesTest`

统计 ego 在路线车道外或错误方向车道的距离百分比。

该百分比会影响 infraction penalty。

### 6.4 `InRouteTest`

判断 ego 是否偏离 route 太远。

超过阈值会触发 `ROUTE_DEVIATION` 并终止 route。

### 6.5 `RunningRedLightTest`

检测 ego 是否在红灯状态下穿越 stop line。

使用：

- traffic light actor。
- map waypoint。
- ego bounding box。
- shapely 线段相交。

### 6.6 `RunningStopTest`

检测 Stop 标志影响区域内是否真正停车。

速度阈值：

```text
0.1 m/s
```

### 6.7 `MinimumSpeedRouteTest`

按 checkpoint 比较 ego 平均速度与背景车平均速度。

当前版本记录但不扣 Driving Score。

### 6.8 `ActorBlockedTest`

如果 ego 低速持续太久，判定 `VEHICLE_BLOCKED`。

leaderboard route 中阈值：

```text
min_speed = 0.1 m/s
max_time = 60.0 s
```

## 7. `srunner/tools/`

工具函数：

- `route_manipulation.py`：路线插值、GPS 转换。
- `route_parser.py`：ScenarioRunner 原生 route parser。
- `scenario_helper.py`：场景构建辅助函数，例如生成目标 waypoint、距离计算、车道判断。
- `scenario_parser.py`：解析 XML scenario。
- `openscenario_parser.py`：OpenSCENARIO 解析。
- `background_manager.py`：背景交通管理。

Bench2Drive leaderboard 自己也有一套 `leaderboard/utils/route_parser.py` 和 `route_manipulation.py`，闭环 leaderboard 优先用 leaderboard 目录下的版本。

## 8. `scenarioconfigs/`

配置数据结构：

- `scenario_configuration.py`
- `route_scenario_configuration.py`
- `openscenario_configuration.py`

route XML 解析后会转成这些 config 对象，再传给 `RouteScenario` 和各个具体 scenario。

## 9. `examples/` 与 `openscenario/`

`examples/`：

- ScenarioRunner 原始示例 XML/XOSC。
- 可作为新增场景的格式参考。

`openscenario/`：

- OpenSCENARIO XSD 和迁移文件。
- Bench2Drive 官方闭环主要用 route XML，不是重点。

## 10. 修改或新增场景的最小路径

假设要新增 RoadTailBench 场景 `RoadTailMerge`：

1. 在 `scenario_runner/srunner/scenarios/roadtail_merge.py` 中写 class：

```python
class RoadTailMerge(BasicScenario):
    def _initialize_actors(self, config):
        ...

    def _create_behavior(self):
        ...

    def _create_test_criteria(self):
        ...
```

2. 在 route XML 中写：

```xml
<scenario name="RoadTailMerge_001" type="RoadTailMerge">
  <trigger_point x="..." y="..." z="..." yaw="..." />
</scenario>
```

3. 确保 `SCENARIO_RUNNER_ROOT=scenario_runner`。

4. `RouteScenario.get_all_scenario_classes()` 会自动扫描 class 名并加载。

5. 如果场景要影响 Ability 统计，还要修改 `tools/ability_benchmark.py`。

## 11. 调试建议

- 场景没有触发：检查 trigger point 是否离 route 足够近。
- actor 没生成：检查 blueprint、spawn transform、地图 spawn collision。
- route 一开始就失败：检查 ego 起点是否在路面上、route 是否可插值。
- 红灯/Stop 指标异常：检查自定义地图 traffic light/stop trigger volume。
- 停车/阻塞误报：检查 route 是否太短、交通参与者是否卡死、20Hz tick 是否正常。
