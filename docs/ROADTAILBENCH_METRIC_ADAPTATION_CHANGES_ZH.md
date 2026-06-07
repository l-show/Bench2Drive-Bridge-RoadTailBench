# RoadTailBench 指标适配修改说明

本文记录 Bench2Drive-Bridge-RoadTailBench 为 RTB007 + UniAD 联合仿真所做的指标适配改动。

## 修改范围是否大

改动不大，属于桥接层和运行脚本级别的适配，没有重写 UniAD 算法，也没有改 RoadTailBench 10 个核心指标的公式主体。

主要变化集中在：

- 将 UniAD 运行入口从原版 Bench2Drive evaluator 切到 RoadTailBench bridge evaluator。
- 增加 RoadTailBench 输出目录、metadata 目录、checkpoint 路径。
- 增加 120 秒仿真时间保护。
- 增加指标 warmup 帧剔除，默认剔除前 2 帧。
- 修复 route record 为空时的指标保存健壮性问题。
- 固定连接现有 CARLA 端口，避免 evaluator 自己寻找新端口并启动另一个 CARLA。

## 1. 指标评估前 2 帧剔除

文件：

```text
RoadTailBench-LeaderBoard/roadtailbench_leaderboard/bench2drive_bridge.py
```

新增配置：

```python
"metric_warmup_frames": 2
```

评估时会将原始帧裁成：

```python
warmup_frames = max(0, int(config.get("metric_warmup_frames", 2)))
evaluation_frames = frames[warmup_frames:] if len(frames) > warmup_frames else []
```

所有 RT 核心指标、综合分、能力分都使用 `evaluation_frames`，并在输出 JSON 中记录：

```json
"evaluation": {
  "raw_frame_count": 230,
  "warmup_frames_excluded": 2,
  "evaluated_frame_count": 228
}
```

原因：RTB7 会给主车瞬时初速度，约 120 km/h。CARLA 初始物理帧可能出现不合理加速度尖峰。如果不剔除，comfort、jerk 等数值指标会被初始赋速过程污染。

## 2. RoadTailBench 评测入口替换

文件：

```text
leaderboard/run_uniad.sh
```

原来运行：

```bash
python3 ${LEADERBOARD_ROOT}/leaderboard/leaderboard_evaluator.py
```

现在运行：

```bash
python3 ${RTB_ROOT}/run_roadtailbench_bridge.py
```

同时设置：

```bash
export RTB_ROOT="${LEADERBOARD_ROOT}/../RoadTailBench-LeaderBoard"
export CHECKPOINT_ENDPOINT="${LEADERBOARD_ROOT}/rtb_results.json"
export ROADTAILBENCH_OUTPUT="${LEADERBOARD_ROOT}/roadtailbench_outputs"
export ROADTAILBENCH_METADATA_ROOT="${LEADERBOARD_ROOT}/roadtailbench_metadata"
export ROADTAILBENCH_MAX_TICKS="${ROADTAILBENCH_MAX_TICKS:-2400}"
```

## 3. 默认 2 分钟仿真超时保护

文件：

```text
RoadTailBench-LeaderBoard/roadtailbench_leaderboard/roadtailbench_bridge_scenario_manager.py
```

新增环境变量：

```bash
ROADTAILBENCH_MAX_TICKS
```

默认在 `leaderboard/run_uniad.sh` 里设置为 `2400`。按 20 Hz 仿真频率计算，约等于 120 秒。超过才触发 RoadTailBench tick 保护。

## 4. 指标保存健壮性修复

文件：

```text
RoadTailBench-LeaderBoard/run_roadtailbench_bridge.py
```

保存 RT 指标时，原逻辑假设 `statistics_manager._results.checkpoint.records[config.index]` 一定存在。现在改为先检查长度：

```python
records = self.statistics_manager._results.checkpoint.records
route_record = records[config.index].to_json() if config.index < len(records) else {}
```

这样中断或异常场景下仍尽量保存 RoadTailBench 指标。

## 5. 固定连接已有 CARLA

文件：

```text
leaderboard/leaderboard/leaderboard_evaluator.py
```

删除：

```python
args.port = find_free_port(args.port)
```

原因：本实验要求 CARLA 必须先通过 `condacarla + make launch` 启动，并连接当前 UE 实例。如果 evaluator 自动找空闲端口，会启动另一个非预期 CARLA 实例。

## 6. 顶层 run_uniad.sh 转发

文件：

```text
run_uniad.sh
```

新增逻辑：如果存在 `leaderboard/run_uniad.sh`，顶层脚本直接转发到该脚本，避免用户误运行旧入口。

## 7. 输出文件说明

每次运行会生成：

```text
leaderboard/roadtailbench_outputs/<route_run_name>/
```

其中主要文件：

- `roadtailbench_frame_log.jsonl`：逐帧记录。
- `roadtailbench_scenario_config.json`：场景配置和原版 Bench2Drive 结果。
- `roadtailbench_metrics.json`：RoadTailBench 指标结果。

这些运行产物已加入 `.gitignore`，不进入仓库。

## 8. 本次验证结果摘要

RTB007 + UniAD 最新验证：

```text
raw_frame_count = 230
warmup_frames_excluded = 2
evaluated_frame_count = 228
route_completion = 0.9963
collision_penalty = 1.0000
driving_efficiency = 0.7148
speed_appropriateness = 0.5274
drivable_area = 1.0000
omnidirectional_interaction_risk = 0.7075
road_engineering_hazard_adaptation = 1.0000
comfort = 0.0833
control_stability = 0.9575
long_tail_hazard_response = 1.0000
```

结论：剔除前 2 帧后，初始赋速尖峰不再直接污染 RT 指标；但 UniAD 后续仍有约 96 帧满刹，因此 comfort 仍然偏低。
