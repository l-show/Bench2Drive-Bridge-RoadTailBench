# RoadTailBench Bridge 本次更新说明

本文档记录本次把 RoadTailBench 指标接入 Bench2Drive 闭环测试环境时做的代码更新、设计取舍、数据流、运行方式和后续待完善事项。它面向项目维护，不是论文指标定义文档。

## 1. 更新目标

你的目标是：

1. 基于已经 git 下来的 Bench2Drive 测试环境和模型接口运行闭环 CARLA 仿真。
2. 尽量少改 Bench2Drive 原始代码，避免破坏原 benchmark。
3. 在同一套闭环仿真中输出 RoadTailBench 自定义 10 个指标。
4. 支持 RoadRunner 静态场景 + CARLA 脚本/蓝图动态长尾场景。
5. 给每个 RoadTailBench 场景补一份可被指标读取的场景元数据。

这次更新采用的策略是：

```text
不直接改 Bench2Drive 原始 evaluator/manager
  -> 新增 RoadTailBench 派生入口
  -> 新增 bridge logger
  -> 在每帧仿真 tick 后采集 CARLA/Bench2Drive 运行时信息
  -> route 结束后调用 RoadTailBench 指标代码
```

这样原 Bench2Drive 还能按原方式运行；RoadTailBench 只需要换启动脚本。

## 2. 新增和修改文件

### 2.1 新增：Bench2Drive 到 RoadTailBench 的桥接采集器

文件：

```text
RoadTailBench-LeaderBoard/roadtailbench_leaderboard/bench2drive_bridge.py
```

核心内容：

- `RoadTailBenchBridgeLogger`
- `evaluate_roadtailbench()`
- `roadtailbench_output_root()`
- `roadtailbench_metadata_root()`

职责：

1. 在 route 开始时生成 RoadTailBench 的 `scenario_config`。
2. 每个 CARLA tick 记录一行 frame log。
3. 每条 route 结束后调用 RoadTailBench 10 个指标和综合分。
4. 输出：

```text
roadtailbench_frame_log.jsonl
roadtailbench_scenario_config.json
roadtailbench_metrics.json
```

记录的每帧字段包括：

```json
{
  "frame": 123,
  "time": 6.15,
  "ego": {},
  "actors": [],
  "collisions": [],
  "bench2drive_events": []
}
```

其中：

- `ego`：自车位置、姿态、速度、加速度、角速度、控制量。
- `actors`：自车周围指定半径内的车辆、行人、静态物。
- `collisions`：从 Bench2Drive criteria event 转换来的碰撞事件。
- `bench2drive_events`：原 Bench2Drive 的 `TrafficEvent`，例如 route completion、collision、outside route、blocked 等。

### 2.2 新增：RoadTailBench 派生 ScenarioManager

文件：

```text
RoadTailBench-LeaderBoard/roadtailbench_leaderboard/roadtailbench_bridge_scenario_manager.py
```

核心类：

```python
RoadTailBenchBridgeScenarioManager(ScenarioManager)
```

它继承原 Bench2Drive 的 `ScenarioManager`，只重写 `_tick_scenario()`。

接入点在原流程：

```text
world.tick()
GameTime 更新
CarlaDataProvider 更新
agent 产生 ego_action
ego.apply_control(ego_action)
scenario_tree.tick_once()
RoadTailBenchBridgeLogger.log_tick()
```

为什么放在 `scenario_tree.tick_once()` 之后：

- Bench2Drive 的碰撞、越界、红灯、Stop、route completion 等 criteria 会在 `scenario_tree.tick_once()` 中更新。
- 放在它之后，本帧新产生的 criteria events 可以同步写入 RoadTailBench frame log。

### 2.3 新增：RoadTailBench bridge 启动入口

文件：

```text
RoadTailBench-LeaderBoard/run_roadtailbench_bridge.py
```

核心类：

```python
RoadTailBenchBridgeEvaluator(LeaderboardEvaluator)
```

它继承原 Bench2Drive 的 `LeaderboardEvaluator`，保持原 route、scenario、agent、statistics 逻辑，主要替换：

```text
ScenarioManager -> RoadTailBenchBridgeScenarioManager
```

并在每条 route 加载完成后创建：

```python
RoadTailBenchBridgeLogger(...)
```

新增参数：

```text
--roadtailbench-output
--roadtailbench-metadata-root
```

也支持环境变量：

```text
ROADTAILBENCH_OUTPUT
ROADTAILBENCH_METADATA_ROOT
```

### 2.4 新增：场景 metadata 模板

文件：

```text
RoadTailBench-LeaderBoard/examples/roadtailbench_scene_metadata_template.json
```

这是每个 RoadTailBench 场景建议维护的一份元数据模板。

它不是 CARLA 原生必须字段，而是 RoadTailBench 指标需要的语义补充，例如：

- 场景属于哪类道路工程长尾风险。
- 哪些位置是 hazard zone。
- 哪些区域需要降低目标速度。
- 哪些障碍物是长尾 hazard。
- 可行驶区域 polygon 是什么。
- 场景能力标签是什么。

### 2.5 新增：简版集成说明

文件：

```text
RoadTailBench-LeaderBoard/docs/BRIDGE_INTEGRATION_ZH.md
```

这个文件主要回答：

- CARLA 闭环仿真能输出什么。
- 原 Bench2Drive 指标输入是什么。
- RoadTailBench 10 个指标输入是什么。
- 哪些字段 bridge 自动提供。
- 哪些字段需要你后续给每个场景写 metadata。
- 如何运行 bridge 入口。

### 2.6 修改：`collision_penalty.py`

原草稿问题：

- 按 `(frame, actor_id, actor_type)` 去重。
- 同一次碰撞持续多帧时，可能被重复计为多次碰撞。

本次改动：

```text
按 actor_id + actor_type + collision_type 做 key
并用 collision_merge_window_s 时间窗去重
默认 5 秒内同一对象同类碰撞只算一次
```

新增配置项：

```json
{
  "collision_merge_window_s": 5.0
}
```

### 2.7 修改：`road_engineering_hazard_adaptation.py`

原草稿问题：

- 每个 hazard zone 的得分直接复用全局 `drivable_area`、`speed_appropriateness`、`interaction_risk`。
- 这会让局部道路工程风险能力退化成全局均值，不能很好反映某个缺陷区内的表现。

本次改动：

- 如果 `hazard_zones` 里提供 `target_speed_kmh`，则对该 zone 内的帧重新计算局部速度合理性。
- 如果未提供，则继续使用全局 `speed_appropriateness` 作为 fallback。

示例：

```json
{
  "id": "wet_curve_marking_zone",
  "category": "A",
  "subtype": "pavement_condition",
  "center": [120.0, 35.0],
  "radius_m": 40.0,
  "target_speed_kmh": 30
}
```

### 2.8 修改：`long_tail_hazard_response.py`

原草稿问题：

- 只根据 ego 是否进入 danger radius 判断危险。
- 没有读取 Bench2Drive 已经产生的 collision/outside/deviation 事件。

本次改动：

- 读取每帧 `collisions`。
- 读取每帧 `bench2drive_events`。
- 如果事件类型包含 collision、outside、deviation，则作为 hazard violation fallback。
- 修复空 hazard id/type 会误匹配所有 collision 文本的问题。

## 3. RoadTailBench bridge 的数据流

完整数据流如下：

```text
Bench2Drive routes XML
  -> RouteIndexer
  -> RouteScenario
  -> CARLA world + ego vehicle + dynamic scenario actors
  -> agent run_step()
  -> ego_action
  -> scenario_tree.tick_once()
  -> Bench2Drive criteria events
  -> RoadTailBenchBridgeLogger.log_tick()
  -> frame_log.jsonl
  -> route end
  -> StatisticsManager.compute_route_statistics()
  -> RoadTailBenchBridgeLogger.close_and_evaluate()
  -> RoadTailBench metrics JSON
```

这意味着 RoadTailBench 当前是闭环仿真后的 route 级评价器，不会影响车辆控制，也不会影响原 Bench2Drive 的 route 是否提前终止。

## 4. 原 Bench2Drive 指标和输入

原 Bench2Drive 主要依赖 `scenario_runner` criteria 产生 `TrafficEvent`。

| 原指标 | 输入来源 | 是否由 bridge 复用 |
|---|---|---|
| Route Completion | route waypoint + ego location | 是 |
| Collision | collision sensor/criteria | 是 |
| Red Light | traffic light + stop line + ego bbox | 记录为 event |
| Stop Sign | stop sign trigger + ego speed | 记录为 event |
| Outside Route Lanes | route + map waypoint + ego location | 记录为 event |
| Route Deviation | route + ego location | 记录为 event |
| Vehicle Blocked | ego speed + duration | 记录为 event |
| Min Speed | ego speed + background traffic speed | 记录为 event |
| Scenario Timeout | scenario blackboard | 记录为 event |
| Yield Emergency Vehicle | emergency vehicle scenario logic | 记录为 event |

原 Bench2Drive 最终分数：

```text
score_composed = score_route * score_penalty
```

其中：

- `score_route` 是 0 到 100。
- `score_penalty` 是 0 到 1。
- `score_composed` 是 0 到 100。

RoadTailBench 的分数独立计算，不覆盖原 Bench2Drive 分数。

## 5. RoadTailBench 10 个指标需要的信息

| 指标 | bridge 自动提供 | 需要 metadata 补充 |
|---|---|---|
| Route Completion | route、ego location | 无 |
| Collision Penalty | collision events | hazard 类型可选 |
| Driving Efficiency | ego speed | `reference_speed_kmh` |
| Speed Appropriateness | ego speed | `speed_zones` |
| Drivable Area | route 横向误差 fallback | `drivable_polygons` |
| Omnidirectional Interaction Risk | ego/actors 位置速度类型 | actor 语义增强可选 |
| Road-Engineering Hazard Adaptation | hazard zone 内 ego 轨迹 + 全局指标 | `hazard_zones`、`scenario_tags` |
| Comfort | acceleration、angular velocity | 阈值可选 |
| Control Stability | steer/throttle/brake | 权重可选 |
| Long-Tail Hazard Response | ego speed/control + events | `hazards` |

如果没有 metadata：

- 指标可以运行。
- 但速度区、hazard 区、能力标签会缺失。
- 这时结果更像“默认配置下的技术跑通结果”，不是 RoadTailBench 的正式测评口径。

## 6. 场景 metadata 的建议格式

每个 RoadTailBench 场景建议提供一个 JSON。

最小推荐字段：

```json
{
  "schema_version": "roadtailbench.scenario.v1",
  "scenario_id": "roadtail_town01_curve_wet_001",
  "scenario_tags": ["A.pavement_condition", "C.rain_wet"],
  "reference_speed_kmh": 50,
  "allowed_lateral_error_m": 2.0,
  "speed_zones": [],
  "hazards": [],
  "hazard_zones": [],
  "drivable_polygons": []
}
```

### 6.1 `scenario_tags`

用于 `AbilityScoreMetric`。

当前支持：

```text
A.traffic_sign_marking
A.separation_protection
A.speed_control_facility
A.lighting_facility
A.pavement_condition
A.alignment_geometry
A.sight_distance
A.clearance_intrusion

B.overtaking_bypass
B.merging_flow
B.emergency_avoidance
B.yielding_priority

C.low_light
C.glare
C.fog
C.rain_wet
C.snow_low_friction
C.wind_dust_visibility
```

### 6.2 `speed_zones`

用于速度合理性。

```json
{
  "id": "wet_curve_slow_zone",
  "center": [120.0, 35.0],
  "radius": 35.0,
  "target_speed_kmh": 30,
  "reason": "wet_curve"
}
```

注意：

- `center` 使用 CARLA 世界坐标 x/y。
- `radius` 单位是米。
- ego 在该圆形区域内时，用 `target_speed_kmh` 替代默认参考速度。

### 6.3 `hazards`

用于长尾风险响应。

```json
{
  "id": "fallen_rock_001",
  "type": "rock",
  "center": [135.0, 36.5],
  "radius_m": 2.0,
  "perception_radius_m": 35.0,
  "danger_radius_m": 4.0,
  "allow_enter_danger_zone": false,
  "expected_behavior": "slow_or_bypass"
}
```

指标逻辑：

- ego 进入 `perception_radius_m` 后开始计时。
- 首次 brake/steer/speed drop 作为响应时间。
- 如果进入 `danger_radius_m`，并且 `allow_enter_danger_zone=false`，得分会乘 0.2。

### 6.4 `hazard_zones`

用于道路工程缺陷适应能力。

```json
{
  "id": "wet_curve_marking_zone",
  "category": "A",
  "subtype": "pavement_condition",
  "center": [120.0, 35.0],
  "radius_m": 40.0,
  "target_speed_kmh": 30
}
```

字段说明：

- `category`：`A`、`B`、`C`。
- `subtype`：具体小类。
- `target_speed_kmh`：可选。提供后会做局部速度合理性估计。

### 6.5 `drivable_polygons`

用于可行驶区域。

```json
[
  [
    [80.0, 20.0],
    [170.0, 20.0],
    [170.0, 50.0],
    [80.0, 50.0]
  ]
]
```

当前实现用 ego 中心点判断是否在 polygon 内。没有 polygon 时，退化为 route centerline 横向误差。

## 7. metadata 文件命名规则

RoadTailBench bridge 会按顺序查找：

```text
<route_id>.json
<route_name>.json
<scenario_name>.json
default.json
```

例如某条 route：

```text
route_id = RouteScenario_12_rep0
route_name = RouteScenario_12
scenario_name = ParkingCutIn
```

则查找顺序：

```text
RouteScenario_12_rep0.json
RouteScenario_12.json
ParkingCutIn.json
default.json
```

后读取的字段会覆盖前面默认值。建议：

1. `default.json` 放通用阈值。
2. `<scenario_name>.json` 放同类场景通用语义。
3. `<route_id>.json` 放具体 route 的坐标、hazard、polygon。

## 8. 运行方式

原 Bench2Drive 通常运行：

```bash
python leaderboard/leaderboard/leaderboard_evaluator.py ...
```

RoadTailBench 版本改为：

```bash
python RoadTailBench-LeaderBoard/run_roadtailbench_bridge.py \
  --routes leaderboard/data/bench2drive220.xml \
  --repetitions 1 \
  --agent /path/to/team_code/vad_b2d_agent.py \
  --agent-config /path/to/config.py+/path/to/checkpoint.pth \
  --checkpoint ./simulation_results.json \
  --roadtailbench-output ./roadtailbench_outputs \
  --roadtailbench-metadata-root ./roadtailbench_metadata
```

也可以用环境变量：

```bash
export ROADTAILBENCH_OUTPUT=./roadtailbench_outputs
export ROADTAILBENCH_METADATA_ROOT=./roadtailbench_metadata
```

Windows PowerShell 示例：

```powershell
$env:ROADTAILBENCH_OUTPUT="./roadtailbench_outputs"
$env:ROADTAILBENCH_METADATA_ROOT="./roadtailbench_metadata"
python RoadTailBench-LeaderBoard/run_roadtailbench_bridge.py `
  --routes leaderboard/data/bench2drive220.xml `
  --repetitions 1 `
  --agent G:/Bench2DriveZoo-Bridge-RoadTailBench/team_code/vad_b2d_agent.py `
  --agent-config "config.py+checkpoint.pth" `
  --checkpoint ./simulation_results.json
```

## 9. 输出目录结构

每条 route 的输出目录：

```text
roadtailbench_outputs/
  <save_name>/
    roadtailbench_frame_log.jsonl
    roadtailbench_scenario_config.json
    roadtailbench_metrics.json
```

其中 `save_name` 和 Bench2Drive 原逻辑保持一致：

```text
<route_name>_<town>_<scenario_name>_<weather_id>_<time>
```

## 10. 输出 JSON 说明

### 10.1 `roadtailbench_frame_log.jsonl`

每帧一行 JSON。

主要字段：

```text
frame
time
ego
actors
collisions
bench2drive_events
```

这是 RoadTailBench 指标最底层的原始输入。后续如果指标算得不合理，优先检查这个文件。

### 10.2 `roadtailbench_scenario_config.json`

由两部分合并：

```text
Bench2Drive 自动生成字段
+ metadata JSON 手工补充字段
```

包括 route、town、weather、scenario tags、hazards、hazard zones 等。

### 10.3 `roadtailbench_metrics.json`

输出所有指标：

```text
route_completion
collision_penalty
driving_efficiency
speed_appropriateness
drivable_area
omnidirectional_interaction_risk
road_engineering_hazard_adaptation
comfort
control_stability
long_tail_hazard_response
roadtailbench_driving_score
ability_score
```

## 11. 本次验证

已做两类验证：

### 11.1 语法检查

执行：

```bash
python -m py_compile ...
```

覆盖：

- `bench2drive_bridge.py`
- `roadtailbench_bridge_scenario_manager.py`
- `run_roadtailbench_bridge.py`
- 修改过的 3 个指标文件

结果：通过。

### 11.2 离线示例评估

执行：

```bash
python RoadTailBench-LeaderBoard/run_evaluation.py \
  --frames RoadTailBench-LeaderBoard/examples/frame_log_example.jsonl \
  --config RoadTailBench-LeaderBoard/examples/scenario_config_example.json \
  --output RoadTailBench-LeaderBoard/outputs/example_metrics_check.json
```

结果：能成功生成 RoadTailBench 指标 JSON。

说明：

- 这只验证 RoadTailBench 离线指标能跑。
- 没有在当前环境真实启动 CARLA，因为需要 CARLA server、地图、agent checkpoint、GPU 运行环境。

## 12. 当前局限和后续建议

### 12.1 需要真实 CARLA 跑一次端到端

目前新增 bridge 已经能编译，但真实闭环还需要在 CARLA 环境中验证：

- import 路径是否和你的启动脚本一致。
- route 输出目录是否符合预期。
- 每帧 actors 数量是否过大。
- criteria events 是否按预期进入 `bench2drive_events`。
- route 结束时是否总能写出 metrics。

### 12.2 `drivable_area` 仍是中心点判断

当前 polygon 分支用 ego 中心点判断是否在可行驶区域。

更严格的 RoadTailBench 口径应该是：

```text
ego bbox outside drivable polygon 的面积比例
```

后续可以基于 ego transform + vehicle extent 实现。

### 12.3 `RoadEngineeringHazardAdaptation` 仍有全局 fallback

本次只增强了 zone 内局部速度合理性。

后续建议进一步局部化：

- zone 内 drivable area score
- zone 内 interaction risk
- zone 内 collision/safe pass

这样 REHA 才能更准确评价具体道路工程缺陷区域。

### 12.4 动态蓝图 hazard 需要和 metadata 对齐

如果 CARLA 蓝图动态生成石块、施工区域、行人、动物、侧向侵入车辆等，建议同步记录：

```text
hazard id
hazard type
CARLA actor id
center
trigger time 或 trigger zone
expected behavior
```

当前 metadata 先用静态 `center/radius` 表达 hazard。后续可以扩展为时间段或 actor 绑定。

### 12.5 场景类型文件还需要体系化

建议后续建立：

```text
roadtailbench_metadata/
  default.json
  scenario_families/
  routes/
```

或者直接：

```text
roadtailbench_metadata/
  default.json
  RouteScenario_001_rep0.json
  RouteScenario_002_rep0.json
```

短期最简单做法是按 route_id 一个 JSON，先跑通正式评测。

## 13. 推荐下一步

1. 选 1 个最简单 RoadTailBench 场景。
2. 给它写一个 route_id 级 metadata JSON。
3. 用 `run_roadtailbench_bridge.py` 跑一次闭环。
4. 检查三个输出文件：

```text
roadtailbench_frame_log.jsonl
roadtailbench_scenario_config.json
roadtailbench_metrics.json
```

5. 如果 frame log 内容稳定，再批量整理场景 metadata。

这条路径最稳，因为它先不改模型 agent，也不改 Bench2Drive 原始 evaluator，只在派生入口里加 RoadTailBench 指标采集。
