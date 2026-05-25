# RoadTailBench-LeaderBoard

RoadTailBench-LeaderBoard 是面向 RoadTailBench CARLA 闭环测试的指标计算原型。它参考 Bench2Drive 的“route JSON + 后处理”思路，但指标体系改为面向道路工程缺陷长尾风险。

当前版本不侵入原 `leaderboard/` 代码，采用离线计算方式：

```text
CARLA 场景运行
  -> 每帧记录 frame_log.jsonl
  -> 编写 scenario_config.json
  -> python run_evaluation.py
  -> route_metrics.json
```

## 1. 10 个指标

| 编号 | 指标 | 文件 |
|---|---|---|
| 1 | Route Completion | `metrics/route_completion.py` |
| 2 | Collision Penalty | `metrics/collision_penalty.py` |
| 3 | Driving Efficiency | `metrics/driving_efficiency.py` |
| 4 | Speed Appropriateness | `metrics/speed_appropriateness.py` |
| 5 | Drivable Area Score | `metrics/drivable_area.py` |
| 6 | Omnidirectional Interaction Risk Score | `metrics/interaction_risk.py` |
| 7 | Road-Engineering Hazard Adaptation Score | `metrics/road_engineering_hazard_adaptation.py` |
| 8 | Comfort Score | `metrics/comfort.py` |
| 9 | Control Stability Score | `metrics/control_stability.py` |
| 10 | Long-Tail Hazard Response Score | `metrics/long_tail_hazard_response.py` |

综合分：

```text
metrics/composite_score.py
```

能力分：

```text
metrics/ability_score.py
```

## 2. 快速运行

```bash
cd /path/to/Bench2Drive/RoadTailBench-LeaderBoard
python run_evaluation.py \
  --frames examples/frame_log_example.jsonl \
  --config examples/scenario_config_example.json \
  --output outputs/example_metrics.json
```

## 3. 日志格式

每帧一行 JSON。最小字段：

```json
{
  "frame": 1,
  "time": 0.05,
  "ego": {
    "location": [0, 0, 0],
    "rotation": [0, 0, 0],
    "velocity": [10, 0, 0],
    "acceleration": [0, 0, 0],
    "angular_velocity": [0, 0, 0],
    "control": {"steer": 0, "throttle": 0.2, "brake": 0}
  },
  "actors": [],
  "collisions": []
}
```

推荐字段见 `docs/METRICS_DESIGN_ZH.md`。

## 4. 设计原则

- 不再使用 Bench2Drive 的红灯、Stop、救护车让行作为核心能力。
- 以道路工程缺陷为主线，同时覆盖动态交通参与者和环境天气。
- 不只看是否碰撞，也看是否近碰撞、是否龟速、是否控制抖动、是否舒适。
- 能力分通过场景标签聚合，便于你后续定义 125 个参数化测试用例。
