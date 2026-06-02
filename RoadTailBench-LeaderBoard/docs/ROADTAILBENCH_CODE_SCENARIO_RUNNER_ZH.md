# RoadTailBench 代码场景批量评测入口

这个入口不把 RoadTailBench 场景转换成 Bench2Drive XML/XOSC，而是把每个 `RTBXXX.py` 当作一个完整的动态场景脚本来运行，同时从 CARLA world 逐帧采集 ego、周围 actor、碰撞和控制量，然后计算 RoadTailBench 指标。

## 两种 ego 模式

### `scene_ego`

`scene_ego` 是默认模式，适合先验证你的 CARLA 关卡、代码场景和指标链路。

在这个模式下：

- `RTBXXX.py` 自己生成并控制 ego。
- runner 不控制车，只负责找到 ego 并挂碰撞传感器。
- runner 按 `role_name` 优先查找 `hero` 或 `ego`。
- 如果脚本没有设置 role_name，可以通过 `--ego-type-id vehicle.xxx` 指定车型。
- 如果当前 world 中只有一辆车，runner 会把这辆车作为 ego。
- 如果同一车型有多辆车，runner 会报错，避免把背景车误当 ego。

示例：

```powershell
python bridge/Bench2Drive/RoadTailBench-LeaderBoard/batch_scenario_runner/run_batch_scenarios.py `
  --host localhost `
  --port 2000 `
  --scene-root "G:\RoadTailCode\dynamic_map_code" `
  --scenes RTB001-RTB020 `
  --ego-mode scene_ego `
  --ego-type-id vehicle.tesla.model3
```

### `agent_ego`

`agent_ego` 是真实模型评测模式。

在这个模式下：

- runner 根据元数据里的 `ego_start` 生成 `role_name=hero` 的 ego。
- runner 给 ego 挂 Bench2DriveZoo agent 需要的传感器。
- 每一帧由模型 agent 输出控制量。
- `RTBXXX.py` 只能生成背景车、行人、静态障碍、蓝图触发器、天气、低附着区域等场景元素。
- `RTBXXX.py` 必须删除或禁用原本的 ego 生成和 ego 控制逻辑，否则会出现两个 ego。

示例：

```powershell
python bridge/Bench2Drive/RoadTailBench-LeaderBoard/batch_scenario_runner/run_batch_scenarios.py `
  --host localhost `
  --port 2000 `
  --scene-root "G:\RoadTailCode\dynamic_map_code" `
  --metadata-root "G:\RoadTailCode\metadata" `
  --scenes RTB101 `
  --ego-mode agent_ego `
  -a G:\Bench2DriveZoo-Bridge-RoadTailBench\team_code\vad_b2d_agent.py `
  --agent-config "path\to\config.py+path\to\checkpoint.pth"
```

旧名字仍然兼容：

- `script_ego` 等价于 `scene_ego`
- `external_ego` 等价于 `agent_ego`

后续建议统一使用新名字。

## RTB 脚本适配约定

如果希望同一个 `RTBXXX.py` 同时支持两种模式，可以在脚本里读取环境变量：

```python
import os

EGO_MODE = os.environ.get("ROADTAILBENCH_EGO_MODE", "scene_ego")
USE_AGENT_EGO = EGO_MODE == "agent_ego"
```

然后在脚本里做两处判断：

- `USE_AGENT_EGO` 为 `True` 时，不生成 ego。
- `USE_AGENT_EGO` 为 `True` 时，不执行脚本内部 ego controller。

如果你选择真实评测时手动删除 RTB 脚本里的 ego，也可以不加这个开关；但要保证 `agent_ego` 模式下场景脚本不会再创建或控制主车。

## 输出

批量汇总：

```text
RoadTailBench-LeaderBoard/outputs/code_scenarios/roadtailbench_batch_summary.json
```

每个场景单独输出：

```text
outputs/code_scenarios/RTB101_YYYYMMDD_HHMMSS/
  roadtailbench_frame_log.jsonl
  roadtailbench_scenario_config.json
  roadtailbench_metrics.json
  roadtailbench_run_summary.json
```

## 元数据

`agent_ego` 至少需要每个场景有 `ego_start`。为了给模型和指标提供更完整上下文，建议同时写：

- `town`
- `ego_blueprint`
- `ego_start`
- `ego_end`
- `route_waypoints`
- `reference_speed_kmh`
- `speed_zones`
- `hazard_zones`
- `hazards`
- `scenario_tags`

模板见：

```text
RoadTailBench-LeaderBoard/examples/roadtailbench_code_scene_metadata_template.json
```
