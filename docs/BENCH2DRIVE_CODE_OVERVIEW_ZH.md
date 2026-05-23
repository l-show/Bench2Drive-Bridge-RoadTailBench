# Bench2Drive 工程代码总览

本文档说明 `Bench2Drive` 仓库本身的模块结构。注意：这里不是模型仓库，模型代码主要在 `Bench2DriveZoo`；本仓库是闭环测试基准、CARLA 评测器、场景系统、路线文件和指标后处理工具。

## 1. 仓库定位

`Bench2Drive` 负责：

- 提供闭环 benchmark 的 routes、scenario、weather 配置。
- 启动 CARLA 0.9.15。
- 加载用户/模型 agent。
- 在 CARLA 中创建 ego vehicle、传感器、背景车、场景参与者。
- 每个 tick 调用 agent，让 agent 输出 `carla.VehicleControl`。
- 实时检测驾驶事件，例如碰撞、红灯、Stop、偏离路线、阻塞、最低速度。
- 生成 route 级 JSON 结果。
- 合并 JSON，计算 Driving Score、Success Rate、Ability、Efficiency、Smoothness。

`Bench2DriveZoo` 负责：

- 放模型代码，例如 UniAD、VAD、BEVFormer、TCP、ADMLP。
- 提供 `team_code/*_agent.py`，使模型能被本仓库的 leaderboard 加载。
- 模型推理并输出控制量或轨迹。

两者关系：

```text
Bench2Drive
  -> 启动 CARLA 和 leaderboard
  -> 加载 Bench2DriveZoo/team_code/xxx_agent.py
  -> agent 用 Zoo 中模型 checkpoint 推理
  -> Bench2Drive 接收 VehicleControl 并评测闭环表现
```

## 2. 顶层目录

```text
Bench2Drive/
├── README.md
├── assets/
├── docs/
├── leaderboard/
├── scenario_runner/
└── tools/
```

### 2.1 `assets/`

项目图片和视频资源，例如 overview、benchmark 图，不参与运行逻辑。

### 2.2 `docs/`

原始仓库中主要包括：

- `anno.md`：Bench2Drive 离线数据集标注结构说明。
- `bench2drive_mini_10.json`：Mini 数据集文件清单。
- `bench2drive_base_1000.json`：Base 数据集文件清单。
- `bench2drive_full+sup_13638.json`：Full/Sup 数据集文件清单。

本次新增的中文代码文档也放在这里。

### 2.3 `leaderboard/`

闭环评测主框架。它是你复现 CARLA 闭环测试时最重要的目录。

核心功能：

- 启动 CARLA server。
- 设置同步仿真、固定步长、Traffic Manager。
- 读取 route XML。
- 动态加载 agent。
- 创建传感器并收集数据。
- 执行 route scenario。
- 调用统计器写入 JSON 结果。

重点文件：

```text
leaderboard/leaderboard/leaderboard_evaluator.py
leaderboard/leaderboard/scenarios/scenario_manager.py
leaderboard/leaderboard/scenarios/route_scenario.py
leaderboard/leaderboard/autoagents/agent_wrapper.py
leaderboard/leaderboard/autoagents/autonomous_agent.py
leaderboard/leaderboard/envs/sensor_interface.py
leaderboard/leaderboard/utils/statistics_manager.py
leaderboard/scripts/run_evaluation*.sh
leaderboard/data/*.xml
```

详见：

- `docs/BENCH2DRIVE_LEADERBOARD_ZH.md`
- `docs/BENCH2DRIVE_RUN_AND_DEBUG_ZH.md`

### 2.4 `scenario_runner/`

CARLA ScenarioRunner 体系，Bench2Drive 在其基础上扩展了大量场景、行为树节点、触发条件和评价标准。

核心功能：

- 定义各种 scenario 类。
- 定义 py_trees 行为节点。
- 定义 criteria，也就是闭环实时评测项。
- 管理 CARLA actor、时间、天气、灯光、背景交通。

重点文件：

```text
scenario_runner/srunner/scenarios/*.py
scenario_runner/srunner/scenarios/basic_scenario.py
scenario_runner/srunner/scenariomanager/carla_data_provider.py
scenario_runner/srunner/scenariomanager/timer.py
scenario_runner/srunner/scenariomanager/traffic_events.py
scenario_runner/srunner/scenariomanager/scenarioatomics/atomic_behaviors.py
scenario_runner/srunner/scenariomanager/scenarioatomics/atomic_trigger_conditions.py
scenario_runner/srunner/scenariomanager/scenarioatomics/atomic_criteria.py
scenario_runner/srunner/tools/*.py
```

详见：

- `docs/BENCH2DRIVE_SCENARIO_RUNNER_ZH.md`

### 2.5 `tools/`

Bench2Drive 工具脚本，分两类：

评测后处理：

- `merge_route_json.py`
- `ability_benchmark.py`
- `efficiency_smoothness_benchmark.py`

运行/数据辅助：

- `split_xml.py`
- `clean_carla.sh`
- `generate_video.py`
- `visualize.py`
- `gen_hdmap.py`
- `data_collect.py`
- `download_mini.sh`

详见：

- `docs/BENCH2DRIVE_METRICS_TOOLS_ZH.md`

## 3. 闭环运行总调用链

最核心调用链如下：

```text
leaderboard/scripts/run_evaluation*.sh
  -> leaderboard/leaderboard/leaderboard_evaluator.py
    -> _setup_simulation()
       启动 CARLA，设置同步模式和 Traffic Manager
    -> RouteIndexer
       解析 route XML，支持 resume
    -> RouteScenario
       插值路线、生成 ego vehicle、创建场景树和 criteria
    -> agent.get_entry_point()
       动态加载模型 agent
    -> AgentWrapper.setup_sensors()
       创建 CARLA sensors
    -> ScenarioManager.run_scenario()
       每帧 tick CARLA、调用 agent、应用控制、tick 行为树
    -> StatisticsManager.compute_route_statistics()
       从 criteria events 计算 route 分数
    -> checkpoint JSON
       保存 route 结果
```

## 4. Route XML 到 CARLA 场景

route XML 位于：

```text
leaderboard/data/
```

主要文件：

- `bench2drive220.xml`：官方 220 routes 完整评测。
- `drivetransformer_bench2drive_dev10.xml`：10 条代表性 route，适合快速开发。
- `routes_training.xml`：训练路线。
- `routes_validation.xml`：验证路线。
- `routes_devtest.xml`：开发测试路线。
- `weather.xml`：天气 id 与 CARLA weather 参数。

route 解析：

```text
leaderboard/leaderboard/utils/route_parser.py
```

每条 route 大致包含：

```xml
<route id="..." town="Town...">
  <weathers>
    <weather route_percentage="..." ... />
  </weathers>
  <waypoints>
    <position x="..." y="..." z="..." />
  </waypoints>
  <scenarios>
    <scenario name="..." type="...">
      <trigger_point x="..." y="..." z="..." yaw="..." />
      ...
    </scenario>
  </scenarios>
</route>
```

## 5. 指标从哪里来

闭环实时事件由：

```text
scenario_runner/srunner/scenariomanager/scenarioatomics/atomic_criteria.py
```

生成事件类型：

```text
scenario_runner/srunner/scenariomanager/traffic_events.py
```

route 级分数由：

```text
leaderboard/leaderboard/utils/statistics_manager.py
```

计算。

全局 Bench2Drive 指标由：

```text
tools/merge_route_json.py
tools/ability_benchmark.py
tools/efficiency_smoothness_benchmark.py
```

后处理计算。

## 6. 你最应该优先读的文件

按复现闭环测试的优先级：

1. `leaderboard/scripts/run_evaluation_debug.sh`
2. `leaderboard/scripts/run_evaluation.sh`
3. `leaderboard/leaderboard/leaderboard_evaluator.py`
4. `leaderboard/leaderboard/scenarios/scenario_manager.py`
5. `leaderboard/leaderboard/scenarios/route_scenario.py`
6. `leaderboard/leaderboard/autoagents/agent_wrapper.py`
7. `leaderboard/leaderboard/envs/sensor_interface.py`
8. `leaderboard/leaderboard/utils/statistics_manager.py`
9. `scenario_runner/srunner/scenariomanager/scenarioatomics/atomic_criteria.py`
10. `tools/merge_route_json.py`
11. `tools/ability_benchmark.py`
12. `tools/efficiency_smoothness_benchmark.py`

## 7. 修改自定义地图时最相关的模块

如果你要从 Bench2Drive 地图切换到 RoadTailBench，优先改：

- CARLA 地图资产本身，确保 town 可以 `client.load_world(town)`。
- `leaderboard/data/roadtailbench_eval.xml`，新增自定义 routes。
- route 中的 `town`、`waypoints`、`scenarios`。
- 如果新增 scenario 类型，则在 `scenario_runner/srunner/scenarios/` 中实现对应类。
- 如果 route 数量不是 220，需要修改 `tools/merge_route_json.py` 的固定分母。
- 如果 Ability 分类不同，需要修改 `tools/ability_benchmark.py` 的 `Ability` 字典。

## 8. 一句话总结

`Bench2Drive` 是闭环测试基准本体：它管 CARLA、路线、场景、传感器、事件、指标和结果；`Bench2DriveZoo` 是被测模型和 agent 适配层。
