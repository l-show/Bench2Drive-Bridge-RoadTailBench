# RoadTailBench 接入 Bench2Drive 闭环测试说明

本文说明如何在尽量少改 Bench2Drive 原代码的前提下，把 RoadTailBench 的 10 个指标接到 Bench2Drive/CARLA 闭环测试环境里。

## 1. 当前接入方式

新增代码不替换原始 `leaderboard/leaderboard_evaluator.py` 和 `leaderboard/scenarios/scenario_manager.py`，而是新增派生入口：

- `run_roadtailbench_bridge.py`
- `roadtailbench_leaderboard/bench2drive_bridge.py`
- `roadtailbench_leaderboard/roadtailbench_bridge_scenario_manager.py`

运行逻辑：

```text
Bench2Drive route/scenario/agent 正常运行
  -> RoadTailBenchBridgeScenarioManager 每 tick 采集 CARLA 状态
  -> roadtailbench_frame_log.jsonl
  -> roadtailbench_scenario_config.json
  -> RoadTailBench 10 个指标 + 综合分
  -> roadtailbench_metrics.json
```

## 2. CARLA 闭环仿真可直接输出的信息

在 Bench2Drive 的 `ScenarioManager._tick_scenario()` 中，每帧能稳定拿到：

| 信息 | 来源 | RoadTailBench 用途 |
|---|---|---|
| ego 位置/姿态 | `ego_actor.get_transform()` | route completion、drivable area、hazard zone 判断 |
| ego 速度 | `ego_actor.get_velocity()` | efficiency、speed appropriateness、interaction risk |
| ego 加速度 | `ego_actor.get_acceleration()` | comfort |
| ego 角速度 | `ego_actor.get_angular_velocity()` | comfort |
| agent 控制量 | `ego_action` | control stability、hazard response |
| 周边 actor 位置/速度/类型 | `world.get_actors()` | interaction risk |
| 碰撞/红灯/Stop/偏航/blocked 等事件 | Bench2Drive criteria events | collision penalty、hazard violation fallback |
| route polyline | `RouteScenario.route` | route completion、drivable area fallback |
| weather | `config.weather` | metadata 记录，后续可用于 C 类环境能力 |
| town/scenario/route id | route config | 输出归档和 metadata 匹配 |

当前 bridge 默认记录 ego 周围 `actor_log_radius_m=100` 米内的 `vehicle.*`、`walker.*`、`static.*` actor。

## 3. 原 Bench2Drive 指标输入

原始 Bench2Drive 指标不是直接读逐帧 JSON，而是由 `scenario_runner` 的 criteria 在仿真时产生 `TrafficEvent`：

| 原指标 | 主要输入 |
|---|---|
| Route Completion | route waypoint、ego location |
| Collision | collision sensor event |
| Red Light | traffic light actor、stop line、ego box |
| Stop Sign | stop sign trigger volume、ego speed |
| Outside Route Lanes | map waypoint、route、ego location |
| Route Deviation | route、ego location |
| Vehicle Blocked | ego speed、持续时间 |
| Min Speed | ego speed、周边 traffic speed |
| Scenario Timeout | scenario blackboard |
| Yield Emergency Vehicle | 急救车场景 actor 状态 |

最后 `StatisticsManager` 把事件汇总成：

```text
score_route
score_penalty
score_composed = score_route * score_penalty
infractions
status
```

## 4. RoadTailBench 10 个指标输入对齐

| RoadTailBench 指标 | 已由 bridge 自动提供 | 仍建议由场景 metadata 提供 |
|---|---|---|
| Route Completion | route、ego location | 无 |
| Collision Penalty | Bench2Drive collision events | hazard 类型可提高分类精度 |
| Driving Efficiency | ego speed、reference speed fallback | `reference_speed_kmh` |
| Speed Appropriateness | ego speed、speed zones | `speed_zones` |
| Drivable Area | route 横向误差 fallback | `drivable_polygons` |
| Omnidirectional Interaction Risk | ego/actors 位置速度类型 | actor 语义增强可选 |
| Road-Engineering Hazard Adaptation | hazard zones + 全局/局部分数 | `hazard_zones`、`scenario_tags` |
| Comfort | acceleration、angular velocity | 阈值可选 |
| Control Stability | steer/throttle/brake | 权重可选 |
| Long-Tail Hazard Response | ego control/speed、events | `hazards` |

结论：RoadTailBench 当前 10 个指标大部分可以直接从 CARLA/Bench2Drive 运行时采集；真正必须补的是场景级 metadata，尤其是限速、hazard 区域、能力标签、可行驶区域。

## 5. 每个 RoadTailBench 场景建议制定的元数据

每个场景至少建议定义：

| 字段 | 必填 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定为 `roadtailbench.scenario.v1` |
| `scenario_id` | 是 | RoadTailBench 场景唯一 ID |
| `scenario_family` | 否 | 场景族，例如 `RoadEngineeringLongTail` |
| `scenario_tags` | 是 | 能力标签，例如 `A.pavement_condition` |
| `reference_speed_kmh` | 是 | 默认参考速度 |
| `allowed_lateral_error_m` | 是 | route fallback 的允许横向误差 |
| `speed_zones` | 建议 | 局部限速区 |
| `hazards` | 建议 | 长尾 hazard 事件 |
| `hazard_zones` | 建议 | 道路工程/环境/交互能力区域 |
| `drivable_polygons` | 建议 | 可行驶区域 polygon；没有则用 route 横向误差 |

模板见：

```text
examples/roadtailbench_scene_metadata_template.json
```

metadata 匹配顺序：

```text
<route_id>.json
<route_name>.json
<scenario_name>.json
default.json
```

放置目录由环境变量或参数指定：

```text
ROADTAILBENCH_METADATA_ROOT=/path/to/metadata
```

## 6. 运行方式

原 Bench2Drive 启动方式不变，只把入口脚本换成 RoadTailBench bridge 版本，并增加可选输出/metadata 参数：

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

每条 route 会输出：

```text
roadtailbench_frame_log.jsonl
roadtailbench_scenario_config.json
roadtailbench_metrics.json
```

## 7. 目前仍需注意

- 如果不提供 metadata，指标仍能运行，但 speed/hazard/ability 会使用默认值，不能代表你的 RoadTailBench 场景真实语义。
- `drivable_polygons` 如果没有提供，`DrivableArea` 会退化为 route 中心线横向误差。
- `hazards` 如果没有提供，`LongTailHazardResponse` 默认 1.0，并在 details 中标记 `no_hazard_events`。
- RoadRunner 静态场景中的道路缺陷最好在 metadata 中同步描述为 `hazard_zones`，动态蓝图生成的障碍/车辆/行人最好同步描述为 `hazards`。
