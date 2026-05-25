# RoadTailBench 闭环指标设计说明

RoadTailBench 的核心对象不是普通交通规则，而是“道路工程缺陷诱发的结构性长尾风险”。因此指标体系应以道路基础设施缺陷为主，同时覆盖动态交通参与者和天气环境。

本文设计 10 个 route 级指标，其中第 6 个替代传统 TTC，第 7 个替代单一 Hazard Clearance，改为面向道路工程缺陷的综合适应能力。

## 1. 指标总览

| 编号 | 指标 | 取值 | 越大越好 |
|---|---|---:|---|
| 1 | Route Completion | `[0, 1]` | 是 |
| 2 | Collision Penalty | `[0, 1]` | 是 |
| 3 | Driving Efficiency | `[0, 1]` | 是 |
| 4 | Speed Appropriateness | `[0, 1]` | 是 |
| 5 | Drivable Area Score | `[0, 1]` | 是 |
| 6 | Omnidirectional Interaction Risk Score | `[0, 1]` | 是 |
| 7 | Road-Engineering Hazard Adaptation Score | `[0, 1]` | 是 |
| 8 | Comfort Score | `[0, 1]` | 是 |
| 9 | Control Stability Score | `[0, 1]` | 是 |
| 10 | Long-Tail Hazard Response Score | `[0, 1]` | 是 |

综合分：

```text
RTB-DS = 100 * RC * CollisionPenalty
         * DrivableAreaScore
         * InteractionRiskScore
         * RoadEngineeringHazardAdaptationScore
         * (0.5 + 0.5 * DrivingEfficiency)
         * (0.6 + 0.4 * SpeedAppropriateness)
         * (0.8 + 0.2 * ComfortScore)
         * (0.8 + 0.2 * ControlStabilityScore)
         * (0.7 + 0.3 * LongTailHazardResponseScore)
```

解释：

- `RC` 和 `CollisionPenalty` 是硬约束，必须权重大。
- 交互风险和工程隐患适应是 RoadTailBench 核心。
- 效率、速度合理性、舒适性、稳定性作为乘性软约束。

## 2. 指标 1：Route Completion

衡量 ego 是否完成指定路线。

设 route polyline 总长为 `L_route`，ego 在 route 上的最大投影累计距离为 `L_done`：

```text
RC = clip(L_done / L_route, 0, 1)
```

CARLA 数据来源：

- ego transform：`ego.get_transform().location`
- route polyline：来自场景配置或 waypoint 轨迹。

## 3. 指标 2：Collision Penalty

衡量碰撞严重程度。

每次碰撞按类型给惩罚系数：

| 类型 | 系数 |
|---|---:|
| pedestrian | 0.25 |
| animal | 0.30 |
| vehicle | 0.45 |
| rock/road_intrusion | 0.55 |
| obstacle | 0.60 |
| static/roadside | 0.70 |
| unknown | 0.65 |

公式：

```text
CollisionPenalty = Π penalty(collision_i)
```

CARLA 数据来源：

- `sensor.other.collision`
- `event.other_actor.type_id`
- 手动 hazard actor 的 `role_name` 或配置中的 `hazard_type`。

## 4. 指标 3：Driving Efficiency

防止算法通过龟速拿高分。

设 `v_t` 为 ego 速度，`v_ref_t` 为该时间/位置参考速度。

```text
Efficiency_t = min(v_t / v_ref_t, 1)
DrivingEfficiency = mean(Efficiency_t)
```

低速严重惩罚：

```text
LowSpeedViolation_t = 1 if v_t < 0.6 * v_ref_t else 0
```

CARLA 数据来源：

- `ego.get_velocity()`
- route/区域 speed profile。

## 5. 指标 4：Speed Appropriateness

衡量速度是否同时满足“正常路段不能龟速”和“隐患区域必须合理降速”。

设根据位置、天气、隐患类型动态得到合理速度 `v_target_t`：

```text
error_t = |v_t - v_target_t| / max(v_target_t, eps)
SpeedAppropriateness = 1 - mean(clip(error_t, 0, 1))
```

CARLA 数据来源：

- ego velocity。
- scenario config 中的 speed zones / hazard zones / weather severity。

## 6. 指标 5：Drivable Area Score

衡量 ego 是否保持在安全可行驶区域，不被错误标线、磨损标线、缺失护栏、弯道等误导。

如果有 drivable polygon：

```text
Offroad_t = area(ego_bbox outside drivable_area) / area(ego_bbox)
DrivableAreaScore = 1 - mean(Offroad_t)
```

如果只有 route centerline：

```text
LaneRisk_t = max(0, lateral_error_t - allowed_lateral_error_t) / allowed_lateral_error_t
DrivableAreaScore = 1 - mean(clip(LaneRisk_t, 0, 1))
```

CARLA 数据来源：

- ego bounding box。
- ego transform。
- map waypoint 或自定义 drivable area polygon。

## 7. 指标 6：Omnidirectional Interaction Risk Score

替代 TTC。TTC 常偏向纵向跟车，不能充分覆盖会车、横穿、并线、侧向侵入。这里设计全向交互风险，综合：

- 纵向安全距离。
- 横向安全距离。
- 最近接近点 CPA。
- 车辆/行人/动物/障碍物类型权重。

对 ego 和 actor `i`：

```text
r = p_i - p_ego
v = v_i - v_ego
t_cpa = clip(- dot(r, v) / ||v||^2, 0, T_horizon)
d_cpa = ||r + v * t_cpa||
```

CPA 风险：

```text
R_cpa = exp(-d_cpa / d0) * exp(-t_cpa / tau)
```

把相对位置转到 ego 坐标：

```text
d_long = |r_local.x|
d_lat  = |r_local.y|
v_close_long = max(0, -sign(r_local.x) * v_local.x)
v_close_lat  = max(0, -sign(r_local.y) * v_local.y)
```

简化 RSS 风格安全距离：

```text
d_safe_long = d_min + v_ego_long * rho + 0.5 * a_max * rho^2
              + (v_ego_long + rho * a_max)^2 / (2 * b_min)
              - v_actor_long^2 / (2 * b_max)

d_safe_lat = d_lat_min + v_close_lat * rho + 0.5 * a_lat_max * rho^2
```

纵横向风险：

```text
R_long = clip((d_safe_long - d_long) / d_safe_long, 0, 1)
R_lat  = clip((d_safe_lat - d_lat) / d_safe_lat, 0, 1)
R_rss  = max(R_long * overlap_lat_factor, R_lat * overlap_long_factor)
```

每帧全向交互风险：

```text
R_interaction_t = max_i type_weight_i * max(R_cpa, R_rss)
InteractionRiskScore = 1 - mean(R_interaction_t)
```

CARLA 数据来源：

- ego/actor location。
- ego/actor velocity。
- actor bounding box extent。
- actor type id / role name。

## 8. 指标 7：Road-Engineering Hazard Adaptation Score

这是 RoadTailBench 核心能力指标，替代单一 Hazard Clearance。

总能力由 A/B/C 三类构成：

```text
REHA = w_A * A_InfrastructureRobustness
     + w_B * B_TrafficInteractionRobustness
     + w_C * C_EnvironmentalRobustness
```

建议：

```text
w_A = 0.50
w_B = 0.30
w_C = 0.20
```

### A 类：Road Infrastructure Defect Robustness，道路工程缺陷鲁棒性

8 个小类：

1. Traffic Sign & Marking Robustness：交通标志标线。
2. Separation & Protection Robustness：道路隔离防护。
3. Speed-Control Facility Robustness：限速设施。
4. Lighting Facility Robustness：照明设施。
5. Pavement Condition Robustness：路面情况，含积水。
6. Alignment Geometry Robustness：道路线形，弯度、坡度、曲率。
7. Sight-Distance Robustness：视距不良。
8. Clearance Intrusion Robustness：限界侵入。

每个小类得分可由该类 hazard zone 内的安全通过、速度合理、可行驶区域保持、近碰撞风险综合：

```text
A_j = mean_over_zones(
    0.35 * SafePass
  + 0.25 * LocalDrivableAreaScore
  + 0.20 * LocalSpeedAppropriateness
  + 0.20 * LocalInteractionRiskScore
)
```

### B 类：Traffic Participant Interaction Robustness，交通参与者交互鲁棒性

4 个小类：

1. Overtaking & Obstacle Bypassing：超车、绕行障碍。
2. Merging & Flow Negotiation：汇入、并线、车流交互。
3. Emergency Avoidance：紧急制动、突发风险避让。
4. Yielding & Priority Negotiation：让行和优先权协商。

```text
B_j = successful_tagged_scenarios_j / total_tagged_scenarios_j
```

或在单条 route 内用局部事件：

```text
B_j = mean(0.45 * SafePass + 0.35 * InteractionRiskScore + 0.20 * ComfortScore)
```

### C 类：Environmental Robustness，环境适应鲁棒性

建议小类：

1. Low-Light Robustness：暗光/夜间。
2. Glare Robustness：炫光。
3. Fog Robustness：浓雾。
4. Rain & Wet-Road Robustness：降雨/湿滑/积水。
5. Snow or Low-Friction Robustness：降雪/低附着。
6. Wind/Dust Visibility Robustness：强风/扬尘/低能见度。

```text
C_j = mean_over_environment_segments(
    0.30 * SafePass
  + 0.25 * SpeedAppropriateness
  + 0.25 * DrivableAreaScore
  + 0.20 * InteractionRiskScore
)
```

## 9. 指标 8：Comfort Score

使用车辆动力学：

```text
a_lon, a_lat, jerk, yaw_rate, yaw_acc
```

阈值：

```text
|a_lat| < 4.0 m/s^2
-5.0 < a_lon < 3.0 m/s^2
|jerk| < 8.0 m/s^3
|yaw_rate| < 1.0 rad/s
|yaw_acc| < 2.0 rad/s^2
```

```text
ComfortScore = satisfied_frames / total_frames
```

CARLA 数据来源：

- `ego.get_acceleration()`
- `ego.get_angular_velocity()`
- `ego.get_transform().get_forward_vector()`
- `ego.get_transform().get_right_vector()`

## 10. 指标 9：Control Stability Score

控制平滑性：

```text
J_t = 1.0 * |steer_t - steer_{t-1}|
    + 0.5 * |throttle_t - throttle_{t-1}|
    + 0.8 * |brake_t - brake_{t-1}|
```

```text
ControlStabilityScore = exp(-mean(J_t))
```

额外记录：

```text
BrakeThrottleConflictRate = count(throttle > 0.1 and brake > 0.1) / T
```

CARLA 数据来源：

- `ego.get_control()`。

## 11. 指标 10：Long-Tail Hazard Response Score

衡量进入隐患感知区域后是否及时、合理响应。

对 hazard event `k`：

```text
t_enter = ego 进入 perception zone
t_response = 第一次有效减速/制动/转向避让
ReactionTime = t_response - t_enter
```

连续得分：

```text
ResponseScore_k = SafePass_k * exp(-ReactionTime_k / tau)
```

如果无有效响应：

```text
ResponseScore_k = 0
```

总体：

```text
LongTailHazardResponseScore = mean(ResponseScore_k)
```

CARLA 数据来源：

- ego speed/control/steer/brake。
- hazard zone。
- collision/violation。

## 12. 场景标签能力分

RoadTailBench 的能力分可以模仿 Bench2Drive：

```text
Ability_k = success_count_k / total_count_k
```

但标签体系换成：

```text
A.infrastructure.*
B.traffic_interaction.*
C.environment.*
```

综合能力：

```text
RoadTailBenchAbility =
0.50 * mean(A_sub_abilities)
+0.30 * mean(B_sub_abilities)
+0.20 * mean(C_sub_abilities)
```

成功判定建议：

```text
success = RC >= 0.95
          and no severe collision
          and DrivableAreaScore >= 0.80
          and InteractionRiskScore >= 0.70
```

## 13. 参考思想

该设计参考了三类常见思想：

- TTC、PET、DRAC 等交通冲突替代安全指标，用于发现“没撞但危险”的近失效事件。
- RSS 的纵向/横向安全距离思想，用于避免 TTC 只关注纵向。
- CARLA Python API 提供 actor 位置、速度、加速度、角速度、bounding box 和 collision sensor event，可支持上述指标计算。

