# RoadTailBench 无 XML 代码场景评测说明

本文档对应 `RTB116` 到 `RTB125` 这一批 RoadTailBench 场景。结论很明确：这条链路不再把 RoadTailBench 场景改写成 Bench2Drive XML/XOSC。

## 为什么不再使用 XML

Bench2Drive 的 XML 适合它自己的参数化 route/scenario 体系：XML 负责组合地图、route、天气、触发点和场景参数。

RoadTailBench 的后期场景不同。`RTB116` 到 `RTB125` 的动态逻辑、天气、交通参与者、危险构造、ego 初始轨迹和控制逻辑都已经写在 `RTBXXX.py` 代码里，并且依赖 `RoadTailBenchInitV9.py` 或同类本地函数。对这类场景，再写 Bench2Drive XML 只会重复表达一部分信息，还容易让 XML 参数和 RTB 脚本内参数不一致。

因此当前方案是：

```text
CARLA map RTBXXX
  -> 直接运行 RTBXXX.py
  -> runner 在 CARLA world 中找到 ego
  -> 逐帧记录 ego、周围 actor、collision、control
  -> 读取 metadata JSON 提供指标语义
  -> 计算 RoadTailBench 指标
```

## 运行入口

使用入口：

```powershell
python G:\Bench2Drive\RoadTailBench-LeaderBoard\run_roadtailbench_code_scenarios.py `
  --host localhost `
  --port 2000 `
  --scene-root "G:\RoadTailCode\codex优化动态地图代码\_codex_backup_20260615_191440" `
  --metadata-root "G:\Bench2Drive\RoadTailBench-LeaderBoard\metadata\rtb116_125" `
  --scenes RTB116-RTB125 `
  --ego-mode scene_ego `
  --ego-role-name ego,hero `
  --output-root "G:\Bench2Drive\RoadTailBench-LeaderBoard\outputs\rtb116_125_scene_ego"
```

`--ego-mode scene_ego` 表示 ego 仍由 RTB 场景代码生成和控制，runner 只负责找到这辆车并评估指标。这是当前先验证场景和指标的推荐方式。

后续要接 Bench2DriveZoo 模型时再使用 `--ego-mode agent_ego`。那时 runner 会根据 metadata 的 `ego_start` 生成 `role_name=hero` 的 ego，并把全局路径交给 agent；对应 RTB 脚本需要关闭或删除内部 ego 生成和内部 ego 控制逻辑，避免出现两个 ego。

## Ego 匹配规则

runner 当前按以下顺序找 ego：

1. 优先按 `role_name` 匹配，默认查找 `ego,hero`，metadata 也可以写 `ego_role_names`。
2. 如果没有 role_name，使用 metadata 中的 `ego_type_id` 或 `ego_blueprint` 过滤车型。
3. 如果同车型有多辆车，再使用 metadata 中的 `ego_start`，选择离起点最近且唯一的车辆。
4. 如果仍然不唯一，会报错，而不是随机选一辆背景车。

这能覆盖 RTB116-120 这种已经设置 `role_name='ego'` 的脚本，也能覆盖 RTB121-125 这种没有设置 role_name、但有明确 ego 车型和起点轨迹的脚本。

## Metadata

本次新增目录：

```text
RoadTailBench-LeaderBoard/metadata/rtb116_125/
  RTB116.json
  RTB117.json
  ...
  RTB125.json
```

这些 JSON 不再承担 XML 的场景加载功能，只承担指标语义功能：

- `town`：要加载的 CARLA map，当前为 `RTB116` 到 `RTB125`。
- `ego_type_id` / `ego_blueprint`：无 role_name 时用于匹配 ego。
- `ego_start` / `ego_end`：起终点，来自 RTB 脚本内 ego 轨迹。
- `route` / `centerline_route`：来自 RTB 脚本内 ego 清洗轨迹。
- `reference_speed_kmh`：默认参考速度。
- `scenario_tags`：能力指标标签。
- `hazards` / `hazard_zones` / `speed_zones`：危险点、危险区和局部限速语义。

当前危险点多数是从 ego 轨迹中点自动生成的保守占位，并带有 `metadata_quality=auto_extracted_review_recommended`。这些点可以先让指标跑通，但最终论文或正式 benchmark 统计前建议人工校正。

## 可行区域指标的新定义

原 `drivable_area` 试图支持 `drivable_polygons`，但 RoadTailBench 自定义 CARLA 关卡里的可行区域通常是不规则的，手工写 polygon 成本高、还容易和地图真实车道不一致。

现在 `drivable_area` 保留指标名，但定义改为中心线偏差：

```text
lateral_error_t = distance(ego_center_t, nearest configured centerline segment)
violation_t = max(0, lateral_error_t - allowed_lateral_error_m)
score_t = 1 - clamp(violation_t / (hard_lateral_error_m - allowed_lateral_error_m))
drivable_area = mean(score_t)
```

默认：

```json
{
  "allowed_lateral_error_m": 2.0,
  "hard_lateral_error_m": 4.0
}
```

换道场景的处理方式是：如果 metadata 提供 `centerline_segments`，每帧会投影到最近的中心线段，因此换到新车道后会自然使用新车道中心线。如果没有 `centerline_segments`，则使用 `centerline_route`。本次 RTB116-125 的 `centerline_route` 直接来自 RTB 脚本内 ego 轨迹，因此能先覆盖已有换道或绕行路径。

输出示例：

```json
{
  "name": "drivable_area",
  "score": 0.93,
  "details": {
    "mode": "centerline_deviation",
    "used_polygon": false,
    "max_centerline_deviation_m": 2.6,
    "mean_centerline_deviation_m": 0.7,
    "allowed_lateral_error_m": 2.0,
    "hard_lateral_error_m": 4.0
  }
}
```

如果 metadata 里没有任何中心线，指标会返回 1.0，并在 details 中写 `reason=missing_centerline`。这表示该指标本次未参与惩罚，不表示车辆一定合规。

## 验证命令

只检查发现和 metadata：

```powershell
python G:\Bench2Drive\RoadTailBench-LeaderBoard\run_roadtailbench_code_scenarios.py `
  --scene-root "G:\RoadTailCode\codex优化动态地图代码\_codex_backup_20260615_191440" `
  --metadata-root "G:\Bench2Drive\RoadTailBench-LeaderBoard\metadata\rtb116_125" `
  --scenes RTB116-RTB125 `
  --dry-run
```

真实运行前需要确保：

- CARLA server 已启动，端口和 `--port` 一致。
- `RTB116` 到 `RTB125` 地图已经能被 CARLA 加载。
- RTB 脚本内硬编码的函数库路径和当前机器一致。

