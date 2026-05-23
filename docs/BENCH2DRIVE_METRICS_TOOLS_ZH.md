# Bench2Drive 指标与工具脚本说明

本文档说明 `tools/` 目录和闭环指标计算链路。

## 1. 指标计算链路

Bench2Drive 闭环指标分三层：

```text
CARLA 实时状态
  -> atomic_criteria.py 产生 TrafficEvent
  -> statistics_manager.py 生成每条 route 的 JSON 分数
  -> tools/*.py 合并并计算 Benchmark 汇总指标
```

对应文件：

```text
scenario_runner/srunner/scenariomanager/scenarioatomics/atomic_criteria.py
leaderboard/leaderboard/utils/statistics_manager.py
tools/merge_route_json.py
tools/ability_benchmark.py
tools/efficiency_smoothness_benchmark.py
```

## 2. `statistics_manager.py`

路径：

```text
leaderboard/leaderboard/utils/statistics_manager.py
```

它负责把 criteria events 变成 route 级 JSON。

### 2.1 route record 字段

每条 route 记录：

```text
route_id
scenario_name
weather_id
save_name
town_name
status
num_infractions
infractions
scores
meta
```

`scores`：

```text
score_route
score_penalty
score_composed
```

`meta`：

```text
route_length
duration_game
duration_system
```

### 2.2 infraction 字段

`PENALTY_NAME_DICT` 映射事件到 JSON 字段：

| TrafficEventType | JSON 字段 |
|---|---|
| `COLLISION_STATIC` | `collisions_layout` |
| `COLLISION_PEDESTRIAN` | `collisions_pedestrian` |
| `COLLISION_VEHICLE` | `collisions_vehicle` |
| `TRAFFIC_LIGHT_INFRACTION` | `red_light` |
| `STOP_INFRACTION` | `stop_infraction` |
| `OUTSIDE_ROUTE_LANES_INFRACTION` | `outside_route_lanes` |
| `MIN_SPEED_INFRACTION` | `min_speed_infractions` |
| `YIELD_TO_EMERGENCY_VEHICLE` | `yield_emergency_vehicle_infractions` |
| `SCENARIO_TIMEOUT` | `scenario_timeouts` |
| `ROUTE_DEVIATION` | `route_dev` |
| `VEHICLE_BLOCKED` | `vehicle_blocked` |

额外还有：

```text
route_timeout
```

### 2.3 固定惩罚

`PENALTY_VALUE_DICT`：

| 事件 | 系数 |
|---|---:|
| 撞行人 | 0.5 |
| 撞车 | 0.6 |
| 撞静态物 | 0.65 |
| 闯红灯 | 0.7 |
| Stop 未停车 | 0.8 |
| 场景超时 | 0.7 |
| 未给急救车让行 | 0.7 |

公式：

```text
score_penalty = Π penalty_value(event_i)
```

### 2.4 百分比惩罚

当前包含：

```text
OUTSIDE_ROUTE_LANES_INFRACTION: [0, 'increases']
MIN_SPEED_INFRACTION: [0.7, 'unused']
```

`outside_route_lanes` 公式：

```text
score_penalty *= 1 - outside_route_percentage / 100
```

`min_speed_infractions` 当前不扣 Driving Score，只记录。

### 2.5 Driving Score

route 级：

```text
score_composed = max(score_route * score_penalty, 0.0)
```

其中：

- `score_route` 是 route completion 百分制。
- `score_penalty` 是惩罚系数。

### 2.6 status

逻辑：

```text
target_reached 且没有 infraction -> Perfect
target_reached 且有 infraction -> Completed
未到达终点 -> Failed
```

如果有失败原因，会写成：

```text
Failed - Agent deviated from the route
Failed - Agent got blocked
Failed - Agent timed out
...
```

## 3. `merge_route_json.py`

路径：

```text
tools/merge_route_json.py
```

功能：

- 合并一个目录下的多个 evaluation JSON。
- 生成 `merged.json`。
- 计算 Bench2Drive driving score 和 success rate。

命令：

```bash
python tools/merge_route_json.py -f your_json_folder/
```

### 3.1 Driving Score

脚本中固定按 220 条 route 计算：

```text
driving score = Σ score_composed_i / 220
```

如果 `merged_records` 数量不是 220，会打印 warning。

### 3.2 Success Rate

成功条件：

```text
status == Completed 或 Perfect
并且除 min_speed_infractions 外所有 infractions 都为空
```

公式：

```text
success rate = success_num / 220
```

### 3.3 自定义 route 数量注意

如果你的 RoadTailBench 不是 220 条 route，必须修改分母，否则指标会被错误除以 220。

建议改成参数：

```python
total_routes = args.total_routes
```

并把：

```python
sum(driving_score) / 220
success_num / 220
```

改成：

```python
sum(driving_score) / total_routes
success_num / total_routes
```

## 4. `ability_benchmark.py`

路径：

```text
tools/ability_benchmark.py
```

功能：

- 根据 route XML 中 scenario type，把 route 归入能力类别。
- 统计各能力成功率。

命令：

```bash
python tools/ability_benchmark.py -r merged.json
```

默认 route 文件：

```text
leaderboard/data/bench2drive220.xml
```

### 4.1 Ability 分类

代码中 `Ability` 字典定义 5 类：

- `Overtaking`
- `Merging`
- `Emergency_Brake`
- `Give_Way`
- `Traffic_Signs`

每类包含若干 scenario type。

### 4.2 普通 ability 成功条件

```text
route status 为 Completed 或 Perfect
并且除 min_speed_infractions 外没有 infraction
```

公式：

```text
Ability_k = success_count_k / total_count_k
```

### 4.3 Traffic_Signs 特殊逻辑

`Traffic_Signs` 会额外检查 ego 是否已经通过 junction。

流程：

1. 启动 CARLA。
2. 加载 route 所在 town。
3. 用 `GlobalRoutePlanner` 插值 route。
4. 找第一个 `wp.is_junction` 的 waypoint。
5. 计算：

```text
junction_completion = (count + 8) / len(waypoint_route)
```

6. 如果：

```text
record_completion > junction_completion
且 stop_infraction 为空
且 red_light 为空
```

则 Traffic_Signs 成功。

### 4.4 自定义场景注意

如果 RoadTailBench 使用新 scenario type：

- 需要把新 scenario type 放入合适的 ability 列表。
- 如果能力体系不同，建议另写 `roadtail_ability_benchmark.py`。
- route 数量不是 220 时，也要检查 crash route 断言。

## 5. `efficiency_smoothness_benchmark.py`

路径：

```text
tools/efficiency_smoothness_benchmark.py
```

功能：

- 读取 `merged.json`。
- 读取每条 route 对应的 `metric_info.json`。
- 计算 Driving Efficiency 和 Driving Smoothness。

命令：

```bash
python tools/efficiency_smoothness_benchmark.py \
  -f merged.json \
  -m your_metric_folder/
```

其中 `your_metric_folder` 是 evaluation 的 `SAVE_PATH`。

### 5.1 metric_info 路径

脚本读取：

```text
metric_dir / record["save_name"] / metric_info.json
```

因此 route JSON 中的 `save_name` 必须和 agent 保存目录一致。

### 5.2 Driving Efficiency

来源：

```text
record["infractions"]["min_speed_infractions"]
```

脚本从字符串中提取百分比：

```text
Average speed is X% of the surrounding traffic's one
```

输出：

```text
Driving Efficiency = mean(extracted_percentages)
```

注意：

- 大于 1000% 的异常值跳过。
- 当前代码只对存在 min speed infraction 的 route 统计效率。
- 如果列表为空，需要自行加空列表保护。

### 5.3 Driving Smoothness

来源：

```text
metric_info.json
```

字段：

- `acceleration`
- `angular_velocity`
- `forward_vector`
- `right_vector`
- `location`
- `rotation`

舒适性阈值：

| 指标 | 阈值 |
|---|---:|
| jerk magnitude | `|jerk| < 8.37 m/s^3` |
| lateral acceleration | `|lat_acc| < 4.89 m/s^2` |
| longitudinal acceleration | `-4.05 < lon_acc < 2.40 m/s^2` |
| yaw acceleration | `|yaw_acc| < 1.93 rad/s^2` |
| longitudinal jerk | `|lon_jerk| < 4.13 m/s^3` |
| yaw rate | `|yaw_rate| < 0.95 rad/s` |

计算：

```text
Driving Smoothness = comfort_segments / valid_segments
```

全局再对 route 求平均。

## 6. `split_xml.py`

路径：

```text
tools/split_xml.py
```

功能：

- 把一个 routes XML 均分成 N 份。
- 用于多 GPU/多进程评测。

命令格式：

```bash
python tools/split_xml.py BASE_ROUTES TASK_NUM ALGO PLANNER_TYPE
```

例如：

```bash
python tools/split_xml.py leaderboard/data/bench2drive220 8 uniad traj
```

输出：

```text
leaderboard/data/bench2drive220_0_uniad_traj.xml
leaderboard/data/bench2drive220_1_uniad_traj.xml
...
```

注意：`BASE_ROUTES` 不带 `.xml` 后缀。

## 7. `clean_carla.sh`

路径：

```text
tools/clean_carla.sh
```

用途：

- 清理残留 CARLA/leaderboard 进程。
- 多进程评测崩溃后尤其需要。

CARLA 经常残留进程占用端口或 GPU，复现时建议频繁使用。

## 8. `generate_video.py`

路径：

```text
tools/generate_video.py
```

功能：

- 把 agent 保存的连续 RGB 图像转成视频。
- 适合 debug 某条 route 的驾驶过程。

命令：

```bash
python tools/generate_video.py -f your_rgb_folder/
```

## 9. `visualize.py`

路径：

```text
tools/visualize.py
```

用于可视化 Bench2Drive 数据/标注，更多面向离线数据检查，不是 leaderboard 闭环主路径。

## 10. `gen_hdmap.py`

路径：

```text
tools/gen_hdmap.py
```

用于从 CARLA 地图生成 HD map 相关数据。若你要为 RoadTailBench 做离线数据或地图相关处理，需要关注它。

闭环只跑 CARLA route 时，通常不需要先生成离线 HD map。

## 11. `data_collect.py`

路径：

```text
tools/data_collect.py
```

用于采集 Bench2Drive 离线数据集，和闭环 leaderboard 复现不是同一路径。

如果你后续要在 RoadTailBench 上采集自己的训练/开环数据，需要再深入读它。

## 12. 指标文件流

完整闭环评测后通常有：

```text
xxx_b2d_traj/
  eval_bench2drive220_0.json
  eval_bench2drive220_1.json
  ...
  merged.json
  merged_ability.json

eval_bench2drive220_uniad_traj/
  <save_name>/
    metric_info.json
    rgb_front/
    meta/
    ...
```

计算顺序：

```bash
python tools/merge_route_json.py -f xxx_b2d_traj/
python tools/ability_benchmark.py -r xxx_b2d_traj/merged.json
python tools/efficiency_smoothness_benchmark.py \
  -f xxx_b2d_traj/merged.json \
  -m eval_bench2drive220_uniad_traj/
```

## 13. RoadTailBench 适配重点

如果 RoadTailBench route 数量、能力分类或交通规则不同：

- 修改 `merge_route_json.py` 的 220 分母。
- 修改 `ability_benchmark.py` 的 ability 分类。
- 检查 `Traffic_Signs` 的 junction completion 逻辑是否适合你的地图。
- 检查 `efficiency_smoothness_benchmark.py` 是否能找到所有 `metric_info.json`。
- 保留 `min_speed_infractions` 不扣分还是重新纳入扣分，需要你定义新 benchmark 协议。
