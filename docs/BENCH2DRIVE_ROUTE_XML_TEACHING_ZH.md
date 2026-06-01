# Bench2Drive 场景 XML 速读

这个文档用于快速看懂 Bench2Drive 的路线和场景定义。教学 XML 文件在同目录的 `BENCH2DRIVE_ROUTE_XML_DEMO_ZH.xml`，它不会参与原始评测，只是一个带中文注释的模板。

## 文件在哪

Bench2Drive leaderboard 评测主要用这些路线 XML：

- `leaderboard/data/bench2drive220.xml`：Bench2Drive 220 条主评测路线。
- `leaderboard/data/drivetransformer_bench2drive_dev10.xml`：较小的开发测试集合。
- `leaderboard/data/routes_devtest.xml`：开发调试路线，内容比较适合学习。
- `leaderboard/data/routes_training.xml`：训练路线。
- `leaderboard/data/routes_validation.xml`：验证路线。
- `leaderboard/data/weather.xml`：天气配置相关文件。

ScenarioRunner 自己也带了一份路线和示例：

- `scenario_runner/srunner/data/*.xml`
- `scenario_runner/srunner/examples/*.xml`
- `scenario_runner/srunner/examples/*.xosc`
- `scenario_runner/srunner/examples/catalogs/*.xosc`

## Bench2Drive XML 的核心结构

一个典型文件长这样：

```xml
<routes>
  <route id="0" town="Town12">
    <weathers>...</weathers>
    <waypoints>...</waypoints>
    <scenarios>...</scenarios>
  </route>
</routes>
```

`route` 是一次评测路线。`id` 是路线编号，`town` 是 CARLA 地图名。运行 leaderboard 时，`--routes` 指向 XML 文件，`--routes-subset` 可以只选择某些 route id。

`waypoints` 是 ego 的全局路线关键点。Bench2Drive 会把这些稀疏点插值成密集路线，然后 ego 按这条路线执行闭环评测。

`weathers` 是路线上的天气设置。每个 `weather` 用 `route_percentage` 表示作用在路线的哪个百分比位置，其余字段映射到 `carla.WeatherParameters`。

`scenarios` 是挂在这条 route 上的触发式动态场景。每个 `scenario` 必须有 `name` 和 `type`。`type` 必须对应到 `scenario_runner/srunner/scenarios/*.py` 里的 Python 场景类名。

## 解析代码怎么读

入口文件：

```text
leaderboard/leaderboard/utils/route_parser.py
```

关键逻辑：

- 遍历 XML 里的每个 `<route>`。
- 读取 `route.attrib["id"]` 和 `route.attrib["town"]`。
- 读取 `<waypoints>/<position>`，转成 `carla.Location` 列表。
- 读取 `<weathers>/<weather>`，转成 `[route_percentage, carla.WeatherParameters]`。
- 读取 `<scenarios>/<scenario>`，生成 `ScenarioConfiguration`。
- `trigger_point` 会转成 `carla.Transform`。
- `other_actor` 会转成 `ActorConfigurationData`。
- 其他子标签会原样放进 `scenario_config.other_parameters`，再由具体场景类解释。

场景是否挂到路线上的判断在同一个文件里：

```text
DIST_THRESHOLD = 2.0
ANGLE_THRESHOLD = 10
```

也就是说，`trigger_point` 要贴近插值后的路线点，水平距离小于 2 米，yaw 差小于 10 度，否则这个场景可能不会被认为属于当前路线。

## XML 和 Python 场景类的关系

路线运行入口会进入：

```text
leaderboard/scenarios/route_scenario.py
```

它会根据 `scenario.type` 找到对应 Python 类并实例化。例如：

- `type="ParkingCutIn"` 对应 `scenario_runner/srunner/scenarios/parking_cut_in.py` 里的 `class ParkingCutIn`。
- `type="ParkingExit"` 对应 `parking_exit.py` 里的 `class ParkingExit`。
- `type="ControlLoss"` 对应 `control_loss.py` 里的 `class ControlLoss`。
- `type="DynamicObjectCrossing"` 对应 `object_crash_vehicle.py` 里的 `class DynamicObjectCrossing`。
- `type="ParkedObstacle"` 对应 `route_obstacles.py` 里的 `class ParkedObstacle`。

所以 XML 不是完整行为脚本。XML 主要负责说明：在哪条路线、哪个触发点、用哪个场景类、传哪些参数。真正生成 actor、控制行为树、判断场景结束，都在 Python 场景类里。

## 对 RoadTailBench 的启发

如果以后要把 RoadTailBench 场景接进 Bench2Drive 的原生路线机制，建议每个 RoadTailBench 场景至少准备这些元数据：

- `scene_id`：例如 `RTB101`。
- `town`：使用的 CARLA 地图。
- `route_id`：对应评测路线编号。
- `ego_start`：ego 起点位置和 yaw。
- `route_waypoints`：ego 需要行驶的关键点。
- `trigger_point`：动态长尾事件触发点。
- `scenario_type`：RoadTailBench 自己的场景类型或桥接类名。
- `actors`：除 ego 外的车辆、行人、动物、静态网格体、蓝图 actor。
- `weather`：天气和光照。
- `speed_limit`：局部限速或道路工程限速。
- `success_condition`：场景期望完成条件。
- `risk_zone`：危险区域、多车交互区域、施工区或遮挡区。

短期最少改动方案仍然是保留 Bench2Drive 的启动方式，用桥接 evaluator 记录 CARLA 输出，再把 RoadTailBench 的动态场景脚本在合适时机注入或预先布置。长期如果要完全走 Bench2Drive 原生 route XML，就需要给 RoadTailBench 增加一个类似 `RoadTailBenchScenario` 的 Python 场景类，再让 XML 的 `type` 指向它。
