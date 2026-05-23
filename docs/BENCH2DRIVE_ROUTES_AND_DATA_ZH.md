# Bench2Drive Routes、天气与数据文件说明

本文档说明 `leaderboard/data/`、`scenario_runner/srunner/data/` 和 `docs/*.json` 数据清单。

## 1. `leaderboard/data/`

这是闭环 leaderboard 直接使用的 routes 和 weather 配置。

```text
leaderboard/data/
├── bench2drive220.xml
├── drivetransformer_bench2drive_dev10.xml
├── routes_devtest.xml
├── routes_training.xml
├── routes_validation.xml
└── weather.xml
```

## 2. 主要 route 文件

### 2.1 `bench2drive220.xml`

官方完整闭环 benchmark。

特点：

- 220 条 routes。
- Bench2Drive 官方 Driving Score、Success Rate、Ability 默认以 220 为分母。
- `tools/merge_route_json.py` 和 `tools/ability_benchmark.py` 默认假设完整 220 routes。

用途：

- 正式复现论文/排行榜结果。
- 最终报告三模型闭环成绩。

不建议初次 debug 直接跑完整 220，因为耗时长且 CARLA 可能中途崩溃。

### 2.2 `drivetransformer_bench2drive_dev10.xml`

10 条代表性 routes。

README 中说明这是 DriveTransformer 提出的快速开发集合，适合：

- 快速验证环境。
- debug agent。
- 做 ablation。
- 避免一开始就跑完整 220。

注意：用它跑出的 Driving Score/Success Rate 不能直接和官方 220 benchmark 比。

### 2.3 `routes_training.xml`

训练路线集合，更多用于数据生成/训练，不是官方闭环测试主入口。

### 2.4 `routes_validation.xml`

验证路线集合。

### 2.5 `routes_devtest.xml`

开发测试路线集合。

## 3. `weather.xml`

路径：

```text
leaderboard/data/weather.xml
```

作用：

- 定义天气 case id 和 CARLA `WeatherParameters` 的映射。
- `leaderboard_evaluator.py` 中 `get_weather_id()` 会读取它，根据 route 里的 weather 参数反查 weather id。

route 结果 JSON 中的：

```text
weather_id
```

来自这个映射。

## 4. route XML 结构

典型结构：

```xml
<routes>
  <route id="0" town="Town...">
    <weathers>
      <weather route_percentage="0" cloudiness="..." precipitation="..." />
    </weathers>
    <waypoints>
      <position x="..." y="..." z="..." />
      ...
    </waypoints>
    <scenarios>
      <scenario name="..." type="...">
        <trigger_point x="..." y="..." z="..." yaw="..." />
        <other_actor ... />
        ...
      </scenario>
    </scenarios>
  </route>
</routes>
```

## 5. route 解析流程

代码：

```text
leaderboard/leaderboard/utils/route_parser.py
```

`RouteParser.parse_routes_file(route_filename, routes_subset)` 会生成 `RouteScenarioConfiguration`。

每条 route config 包括：

- `town`
- `name = RouteScenario_<id>`
- `weather`
- `keypoints`
- `scenario_configs`

### 5.1 waypoints

XML 中的：

```xml
<position x="..." y="..." z="..." />
```

会转成：

```python
carla.Location(x, y, z)
```

随后在 `RouteScenario._get_route()` 中通过：

```python
interpolate_trajectory(config.keypoints)
```

插值为更密集的 route。

### 5.2 scenarios

XML 中的 scenario 会转成 `ScenarioConfiguration`：

- `name`
- `type`
- `trigger_points`
- `other_actors`
- `other_parameters`

`type` 必须能在 `scenario_runner/srunner/scenarios/*.py` 中找到同名 class。

例如：

```xml
<scenario type="PedestrianCrossing" ...>
```

必须存在：

```python
class PedestrianCrossing(BasicScenario):
    ...
```

### 5.3 trigger point 过滤

`RouteParser.is_scenario_at_route()` 会检查 trigger point 是否在 route 附近。

阈值：

```text
DIST_THRESHOLD = 2.0 m
ANGLE_THRESHOLD = 10 deg
```

如果 trigger 离 route 太远，会被忽略：

```text
WARNING: Ignoring scenario ... as it is too far from the route
```

## 6. route subset

`leaderboard_evaluator.py` 支持：

```bash
--routes-subset
```

格式：

```text
单条：5
多条：5,8,20
区间：10-20
组合：1,5,10-20
```

解析逻辑在 `RouteParser.parse_routes_file()` 中。

调试时可以用 subset 只跑一两条 route。

## 7. route index 与 resume

代码：

```text
leaderboard/leaderboard/utils/route_indexer.py
```

`RouteIndexer` 会：

- 解析 route XML。
- 根据 repetitions 生成 route list。
- 维护当前 index。
- 根据 checkpoint JSON 恢复进度。

checkpoint 中的：

```json
"_checkpoint": {
  "progress": [current, total],
  "records": [...]
}
```

会用于 resume。

## 8. `scenario_runner/srunner/data/`

这里有 ScenarioRunner 原始 route 文件：

```text
scenario_runner/srunner/data/
├── routes_devtest.xml
├── routes_town10.xml
├── routes_training.xml
└── routes_validation.xml
```

Bench2Drive leaderboard 闭环主要使用 `leaderboard/data/` 下的 route 文件。

除非你直接运行 `scenario_runner/scenario_runner.py`，否则优先改 `leaderboard/data/`。

## 9. `docs/*.json` 数据清单

```text
docs/bench2drive_mini_10.json
docs/bench2drive_base_1000.json
docs/bench2drive_full+sup_13638.json
```

这些是离线数据集文件清单，不是闭环 route XML。

用途：

- 下载/校验 Mini/Base/Full 数据集。
- 训练模型或做开环评测。

闭环 leaderboard 运行 CARLA 时，不直接读取这些 JSON。

## 10. `docs/anno.md`

Bench2Drive 离线数据集标注说明。

包括：

- 数据结构。
- 传感器数据。
- 标注字段。
- 可视化说明。

如果你只复现闭环，不训练模型，可以先不深入看。

如果你要用 RoadTailBench 采集训练数据或做开环评测，必须回头读它。

## 11. 新建 RoadTailBench route XML

建议新建：

```text
leaderboard/data/roadtailbench_eval.xml
```

最小 route 示例：

```xml
<routes>
  <route id="0" town="RoadTailBench">
    <weathers>
      <weather route_percentage="0" cloudiness="0" precipitation="0" sun_altitude_angle="70" />
    </weathers>
    <waypoints>
      <position x="0.0" y="0.0" z="0.0" />
      <position x="50.0" y="0.0" z="0.0" />
      <position x="100.0" y="0.0" z="0.0" />
    </waypoints>
    <scenarios>
      <scenario name="RoadTail_FreeRide_0" type="FreeRide">
        <trigger_point x="20.0" y="0.0" z="0.0" yaw="0.0" />
      </scenario>
    </scenarios>
  </route>
</routes>
```

实际使用时要保证：

- `town` 等于 CARLA 可加载地图名。
- waypoint 落在道路中心线附近。
- z 坐标合理。
- trigger point 离 route 小于 2m。
- scenario type 已存在或你自己实现。

## 12. 换地图时的检查清单

CARLA 地图：

- `client.load_world("RoadTailBench")` 成功。
- 地图 OpenDRIVE 可用。
- spawn point 不为空。
- traffic light/stop sign trigger volume 正确。

route XML：

- town 名称正确。
- waypoint 连续且可插值。
- 起点能生成 ego。
- 终点可达。
- trigger point 在 route 附近。

指标工具：

- route 数量不是 220 时修改分母。
- Ability 分类是否仍适用。
- Traffic_Signs 的 junction 判断是否适用。

agent：

- GPS/world 坐标转换是否仍正确。
- route command 是否合理。
- 地图道路方向是否和 route yaw 一致。
