# Leaderboard 闭环评测模块说明

本文档说明 `leaderboard/` 目录。该目录是 Bench2Drive 闭环评测的主入口。

## 1. 目录结构

```text
leaderboard/
├── data/
├── docs/
├── leaderboard/
│   ├── autoagents/
│   ├── envs/
│   ├── scenarios/
│   ├── utils/
│   └── leaderboard_evaluator.py
├── scripts/
├── requirements.txt
└── run_leaderboard.sh
```

## 2. `leaderboard_evaluator.py`

路径：

```text
leaderboard/leaderboard/leaderboard_evaluator.py
```

这是闭环评测总入口，负责把 CARLA、route、scenario、agent、statistics 串起来。

### 2.1 初始化流程

`LeaderboardEvaluator.__init__()` 中做了几件事：

1. 调用 `_setup_simulation(args)` 启动 CARLA。
2. 检查 CARLA Python API 版本。
3. 根据 `--agent` 动态 import agent 文件。
4. 创建 `ScenarioManager`。
5. 初始化 watchdog，防止 agent setup 或 run_step 卡死。

### 2.2 CARLA 启动方式

`_setup_simulation()` 中自动启动 CARLA：

```bash
${CARLA_ROOT}/CarlaUE4.sh \
  -RenderOffScreen \
  -nosound \
  -carla-rpc-port=${port} \
  -graphicsadapter=${gpu_rank}
```

关键点：

- 使用 `CARLA_ROOT` 环境变量定位 CARLA。
- 自动查找空闲 port。
- `-RenderOffScreen` 适合服务器无显示环境。
- `-graphicsadapter` 控制 CARLA 用哪张显卡，不受 `CUDA_VISIBLE_DEVICES` 控制。
- 启动后默认 `sleep 30`，机器慢时可能需要加长。

### 2.3 仿真设置

初始化 CARLA client 后设置：

```python
carla.WorldSettings(
    synchronous_mode=True,
    fixed_delta_seconds=1.0 / 20.0,
    deterministic_ragdolls=True,
    spectator_as_ego=False
)
```

含义：

- 同步模式。
- 20Hz 固定步长。
- route evaluation 每帧由评测器显式 tick。
- Traffic Manager 也设置为同步模式和 hybrid physics。

### 2.4 route 加载和 world 切换

`_load_and_wait_for_world(args, town)`：

- `client.load_world(town, reset_settings=False)` 加载 town。
- 设置 large map streaming 距离。
- `world.reset_all_traffic_lights()`。
- 把 client/world/traffic manager port 注册到 `CarlaDataProvider`。
- 检查实际 map 名称是否等于 route XML 中的 town。

如果你的自定义地图 RoadTailBench 无法加载，通常会在这里报错。

### 2.5 agent 加载

`_load_and_run_scenario()` 中：

```python
agent_class_name = getattr(self.module_agent, 'get_entry_point')()
agent_class_obj = getattr(self.module_agent, agent_class_name)
self.agent_instance = agent_class_obj(args.host, args.port, args.debug)
self.agent_instance.set_global_plan(self.route_scenario.gps_route, self.route_scenario.route)
args.agent_config = args.agent_config + '+' + save_name
self.agent_instance.setup(args.agent_config)
```

要求 agent 文件必须提供：

```python
def get_entry_point():
    return "YourAgentClassName"
```

agent 类必须继承 leaderboard 的 `AutonomousAgent` 或兼容同样接口。

### 2.6 sensor 检查

首次 route 会读取：

```python
self.sensors = self.agent_instance.sensors()
track = self.agent_instance.track
validate_sensor_configuration(self.sensors, track, args.track)
```

合法后保存 sensor icons 到结果 JSON。

### 2.7 route 运行和异常处理

主要异常：

- `SensorConfigurationInvalid`：传感器非法，entry status 为 Rejected。
- agent setup 异常：`Agent_init`。
- `AgentError`：agent runtime 崩溃。
- `TickRuntimeError`：tick 数超过限制。
- 其他异常：simulation crash。

每条 route 结束后都会调用：

```python
self.manager.stop_scenario()
self._register_statistics(config.index, entry_status, crash_message)
self._cleanup()
```

### 2.8 resume

`run()` 中：

```python
route_indexer = RouteIndexer(args.routes, args.repetitions, args.routes_subset)
resume = route_indexer.validate_and_resume(args.checkpoint)
```

如果 checkpoint 可用，会跳过已完成 route，从上次中断点继续。

## 3. `scenarios/scenario_manager.py`

路径：

```text
leaderboard/leaderboard/scenarios/scenario_manager.py
```

这是每帧闭环主循环。

### 3.1 `load_scenario()`

做以下事：

- 重置 `GameTime`。
- 用 `AgentWrapperFactory` 包装 agent。
- 保存 route index、scenario tree、ego vehicle。
- 调用 `AgentWrapper.setup_sensors()` 创建传感器。

### 3.2 `_tick_scenario()`

每帧执行：

```text
1. world.tick(timeout)
2. 读取 snapshot timestamp
3. GameTime.on_carla_tick(timestamp)
4. CarlaDataProvider.on_carla_tick()
5. ego_action = agent_wrapper()
6. ego_vehicle.apply_control(ego_action)
7. scenario_tree.tick_once()
8. 如果 scenario_tree 不再 RUNNING，结束 route
```

这是真正闭环的核心：agent 输出控制后，车辆状态会影响下一帧传感器输入。

### 3.3 TickRuntime 限制

当前代码：

```python
if self.tick_count > 4000:
    raise TickRuntimeError("RuntimeError, tick_count > 4000")
```

20Hz 下 4000 tick 约等于 200 秒仿真时间。

### 3.4 build scenarios 线程

`run_scenario()` 会启动线程：

```python
self._scenario_thread = threading.Thread(target=self.build_scenarios_loop, ...)
```

这个线程周期性调用：

- `self.scenario.build_scenarios()`
- `self.scenario.spawn_parked_vehicles()`

因此部分 scenario/parked vehicles 是 ego 接近后才运行时初始化的。

## 4. `scenarios/route_scenario.py`

路径：

```text
leaderboard/leaderboard/scenarios/route_scenario.py
```

它把一条 route 变成可运行的 CARLA scenario。

### 4.1 主要职责

- 插值 route。
- 生成 ego vehicle。
- 过滤距离路线太远的 scenario trigger。
- 动态加载 `scenario_runner/srunner/scenarios/*.py` 中的 scenario 类。
- 运行时按距离初始化 scenario。
- 添加背景交通 `BackgroundBehavior`。
- 添加 route 常驻 criteria。
- 添加 weather/lights/timeout behavior。

### 4.2 route 插值

```python
self.gps_route, self.route = interpolate_trajectory(config.keypoints)
```

`gps_route` 会传给 agent，`route` 用于 CARLA 世界坐标下的行为树和指标。

### 4.3 ego vehicle

默认 ego blueprint：

```text
vehicle.lincoln.mkz_2020
```

role name：

```text
hero
```

Bench2DriveZoo agent 中的 `get_hero()` 就是按 `role_name == 'hero'` 找 ego。

### 4.4 scenario 动态加载

`get_all_scenario_classes()` 会扫描：

```text
${SCENARIO_RUNNER_ROOT}/srunner/scenarios/*.py
```

把所有 class 放入字典：

```python
all_scenario_classes[class_name] = class_obj
```

route XML 中：

```xml
<scenario type="PedestrianCrossing" ...>
```

会映射到同名 Python class `PedestrianCrossing`。

### 4.5 常驻 criteria

每条 route 默认添加：

```text
RouteCompletionTest
OutsideRouteLanesTest
CollisionTest
RunningRedLightTest
RunningStopTest
MinimumSpeedRouteTest(checkpoints=20)
InRouteTest(offroad_max=30, terminate_on_failure=True)
ActorBlockedTest(min_speed=0.1, max_time=60.0, terminate_on_failure=True)
```

这些 criteria 是 Driving Score 和 Success Rate 的基础。

## 5. `autoagents/`

路径：

```text
leaderboard/leaderboard/autoagents/
```

### 5.1 `autonomous_agent.py`

所有 agent 的基类。

关键接口：

```python
setup(path_to_conf_file)
sensors()
run_step(input_data, timestamp)
destroy()
set_global_plan(global_plan_gps, global_plan_world_coord)
```

`__call__()` 中执行：

```python
input_data = self.sensor_interface.get_data(GameTime.get_frame())
timestamp = GameTime.get_time()
control = self.run_step(input_data, timestamp)
```

### 5.2 `agent_wrapper.py`

负责：

- sensor 配置合法性检查。
- 根据 agent.sensors() 创建真实 CARLA sensor。
- 创建 speedometer/opendrive pseudo sensor。
- 注册 sensor callback。
- 清理 sensor。

传感器限制：

```text
camera rgb: 8
lidar: 2
radar: 4
gnss: 1
imu: 1
opendrive_map: 1
speedometer: 1
```

如果设置了 `SAVE_PATH`，Bench2Drive 允许更大的 sensor 安装半径，方便顶视 BEV 相机保存。

### 5.3 ROS/Human/NPC/Dummy agent

这些是通用参考 agent：

- `dummy_agent.py`
- `human_agent.py`
- `npc_agent.py`
- `ros1_agent.py`
- `ros2_agent.py`
- `ros_base_agent.py`

复现 UniAD/VAD 时重点不在这里，主要看 Zoo 的 `team_code`。

## 6. `envs/sensor_interface.py`

路径：

```text
leaderboard/leaderboard/envs/sensor_interface.py
```

负责传感器数据队列。

### 6.1 数据解析

`CallBack` 会把 CARLA 数据转成：

- Image：numpy uint8 array。
- Lidar：`(N, 4)`。
- Radar：`(N, 4)`。
- GNSS：`[lat, lon, alt]`。
- IMU：`[acc, gyro, compass]`。
- Speedometer：`{'speed': ...}`。

### 6.2 同帧同步

`SensorInterface.get_data(frame)` 会等待当前 frame 的所有 sensor 数据：

```python
while len(data_dict.keys()) < len(self._sensors_objects.keys()):
    sensor_data = self._data_buffers.get(True, self._queue_timeout)
    if sensor_data[1] != frame:
        continue
    data_dict[sensor_data[0]] = (frame, data)
```

如果传感器长时间无数据，会抛出 `SensorReceivedNoData`。

## 7. `utils/`

### 7.1 `route_parser.py`

解析 route XML：

- route id/town。
- weather。
- waypoints。
- scenarios。
- trigger point。
- other actors。

还提供 `is_scenario_at_route()`，用于过滤离 route 太远的 scenario trigger。

### 7.2 `route_indexer.py`

管理 route 执行顺序和 resume。

支持：

- repetitions。
- routes subset。
- checkpoint resume。

### 7.3 `statistics_manager.py`

闭环 route 分数计算核心。

输出：

- route record。
- global record。
- score_route。
- score_penalty。
- score_composed。
- infractions。
- durations。
- entry_status。

### 7.4 `checkpoint_tools.py`

读写 checkpoint JSON。

支持本地文件和 HTTP endpoint。

### 7.5 `result_writer.py`

打印 scenario criteria 的终端表格结果。

## 8. `scripts/`

### 8.1 `run_evaluation.sh`

底层统一入口，接收端口、route、agent、config、checkpoint、save path、gpu rank 等参数，然后调用：

```bash
python leaderboard/leaderboard/leaderboard_evaluator.py
```

### 8.2 `run_evaluation_debug.sh`

单进程 debug 模板。

需要你改：

- `CARLA_ROOT`
- `TEAM_AGENT`
- `TEAM_CONFIG`
- `GPU_RANK`
- `ROUTES`
- `SAVE_PATH`

### 8.3 `run_evaluation_multi_*.sh`

多进程并行评测模板。

流程：

1. 用 `tools/split_xml.py` 把 `bench2drive220.xml` 切分成多个 XML。
2. 每个 GPU/任务启动一个 `run_evaluation.sh`。
3. 输出多个 checkpoint JSON。
4. 后续用 `tools/merge_route_json.py` 合并。

## 9. `data/`

`leaderboard/data/` 是闭环评测路线和天气配置。

详见：

- `docs/BENCH2DRIVE_ROUTES_AND_DATA_ZH.md`

## 10. 常见修改点

接入新模型：

- 添加 `leaderboard/team_code/your_agent.py`，或软链接到 Zoo 的 `team_code`。
- 修改 `TEAM_AGENT` 和 `TEAM_CONFIG`。

换路线：

- 修改 `ROUTES=leaderboard/data/xxx.xml`。

只跑一部分 route：

- 使用 `--routes-subset`，或用 `tools/split_xml.py` 切分。

换地图：

- route XML 中 `town` 必须和 CARLA map 名称一致。
- waypoints 必须落在可导航道路上。
- scenario trigger 必须距离 route 足够近。

改指标：

- route 级实时事件：`atomic_criteria.py`。
- 分数聚合：`statistics_manager.py`。
- benchmark 后处理：`tools/*.py`。
