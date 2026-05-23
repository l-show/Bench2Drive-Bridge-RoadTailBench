# Bench2Drive 运行脚本与调试说明

本文档说明如何理解 `leaderboard/scripts/` 和常见调试点。

## 1. 运行方式总览

Bench2Drive 闭环运行有两层脚本：

```text
run_evaluation_debug.sh 或 run_evaluation_multi_*.sh
  -> run_evaluation.sh
    -> leaderboard/leaderboard/leaderboard_evaluator.py
```

`run_evaluation.sh` 是底层统一入口；其他脚本主要是给它组装参数。

## 2. `run_evaluation.sh`

路径：

```text
leaderboard/scripts/run_evaluation.sh
```

参数顺序：

```bash
bash leaderboard/scripts/run_evaluation.sh \
  $PORT \
  $TM_PORT \
  $IS_BENCH2DRIVE \
  $ROUTES \
  $TEAM_AGENT \
  $TEAM_CONFIG \
  $CHECKPOINT_ENDPOINT \
  $SAVE_PATH \
  $PLANNER_TYPE \
  $GPU_RANK
```

### 2.1 关键环境变量

脚本内部设置：

```bash
export CARLA_ROOT=YOUR_CARLA_PATH
export CARLA_SERVER=${CARLA_ROOT}/CarlaUE4.sh
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla
export PYTHONPATH=$PYTHONPATH:$CARLA_ROOT/PythonAPI/carla/dist/carla-0.9.15-py3.7-linux-x86_64.egg
export PYTHONPATH=$PYTHONPATH:leaderboard
export PYTHONPATH=$PYTHONPATH:leaderboard/team_code
export PYTHONPATH=$PYTHONPATH:scenario_runner
export SCENARIO_RUNNER_ROOT=scenario_runner
export LEADERBOARD_ROOT=leaderboard
export CHALLENGE_TRACK_CODENAME=SENSORS
```

你必须把：

```bash
export CARLA_ROOT=YOUR_CARLA_PATH
```

改成真实 CARLA 路径。

### 2.2 Python 入口

最终执行：

```bash
CUDA_VISIBLE_DEVICES=${GPU_RANK} python leaderboard/leaderboard/leaderboard_evaluator.py \
  --routes=${ROUTES} \
  --repetitions=${REPETITIONS} \
  --track=${CHALLENGE_TRACK_CODENAME} \
  --checkpoint=${CHECKPOINT_ENDPOINT} \
  --agent=${TEAM_AGENT} \
  --agent-config=${TEAM_CONFIG} \
  --debug=${DEBUG_CHALLENGE} \
  --record=${RECORD_PATH} \
  --resume=${RESUME} \
  --port=${PORT} \
  --traffic-manager-port=${TM_PORT} \
  --gpu-rank=${GPU_RANK}
```

注意：

- `CUDA_VISIBLE_DEVICES` 控制模型用的 CUDA。
- CARLA 渲染 GPU 由 `leaderboard_evaluator.py` 中的 `-graphicsadapter=${gpu_rank}` 控制。
- 两者不是同一个机制。

## 3. `run_evaluation_debug.sh`

路径：

```text
leaderboard/scripts/run_evaluation_debug.sh
```

这是单进程 debug 模板。

默认内容中需要你改：

```bash
BASE_PORT=30000
BASE_TM_PORT=50000
IS_BENCH2DRIVE=True
BASE_ROUTES=leaderboard/data/bench2drive220
TEAM_AGENT=leaderboard/team_code/your_team_agent.py
TEAM_CONFIG=your_team_agent_ckpt.pth
BASE_CHECKPOINT_ENDPOINT=eval
SAVE_PATH=./eval_v1/
PLANNER_TYPE=only_traj
GPU_RANK=3
```

### 3.1 UniAD 示例

假设你把 Bench2DriveZoo 链接到 Bench2Drive 根目录：

```text
Bench2Drive/Bench2DriveZoo -> /path/to/Bench2DriveZoo
```

并把 agent 链接到：

```text
leaderboard/team_code/uniad_b2d_agent.py
```

可设置：

```bash
BASE_ROUTES=leaderboard/data/drivetransformer_bench2drive_dev10
TEAM_AGENT=leaderboard/team_code/uniad_b2d_agent.py
TEAM_CONFIG=Bench2DriveZoo/adzoo/uniad/configs/stage2_e2e/base_e2e_b2d.py+Bench2DriveZoo/ckpts/uniad_base_b2d.pth
BASE_CHECKPOINT_ENDPOINT=eval_uniad_dev10
SAVE_PATH=./eval_uniad_dev10/
PLANNER_TYPE=traj
GPU_RANK=0
```

### 3.2 VAD 示例

```bash
BASE_ROUTES=leaderboard/data/drivetransformer_bench2drive_dev10
TEAM_AGENT=leaderboard/team_code/vad_b2d_agent.py
TEAM_CONFIG=Bench2DriveZoo/adzoo/vad/configs/VAD/VAD_base_e2e_b2d.py+Bench2DriveZoo/ckpts/vad_b2d_base.pth
BASE_CHECKPOINT_ENDPOINT=eval_vad_dev10
SAVE_PATH=./eval_vad_dev10/
PLANNER_TYPE=traj
GPU_RANK=0
```

## 4. 多进程脚本

路径：

```text
leaderboard/scripts/run_evaluation_multi_uniad.sh
leaderboard/scripts/run_evaluation_multi_uniad_tiny.sh
leaderboard/scripts/run_evaluation_multi_vad.sh
leaderboard/scripts/run_evaluation_multi_tcp.sh
leaderboard/scripts/run_evaluation_multi_admlp.sh
```

这些脚本结构类似。

### 4.1 基本流程

1. 设置 base route：

```bash
BASE_ROUTES=leaderboard/data/bench2drive220
```

2. 如果未切分过，调用：

```bash
python tools/split_xml.py $BASE_ROUTES $TASK_NUM $ALGO $PLANNER_TYPE
```

3. 设置：

```bash
GPU_RANK_LIST=(0 1 2 3 4 5 6 7)
TASK_LIST=(0 1 2 3 4 5 6 7)
```

4. 每个任务启动：

```bash
bash -e leaderboard/scripts/run_evaluation.sh ...
```

5. 每个任务写自己的 checkpoint JSON 和 log。

### 4.2 端口

脚本中：

```bash
PORT=$((BASE_PORT + i * 150))
TM_PORT=$((BASE_TM_PORT + i * 150))
```

这样避免多进程端口冲突。

如果端口被占用，换更大的 `BASE_PORT` 和 `BASE_TM_PORT`。

### 4.3 TASK_NUM 与 GPU 数

官方脚本常用：

```bash
TASK_NUM=8
GPU_RANK_LIST=(0 1 2 3 4 5 6 7)
TASK_LIST=(0 1 2 3 4 5 6 7)
```

如果你只有 1 张 GPU：

```bash
TASK_NUM=1
GPU_RANK_LIST=(0)
TASK_LIST=(0)
```

如果你有 2 张 GPU：

```bash
TASK_NUM=2
GPU_RANK_LIST=(0 1)
TASK_LIST=(0 1)
```

## 5. 推荐初次复现流程

### 5.1 先检查 CARLA 单独可启动

```bash
$CARLA_ROOT/CarlaUE4.sh -RenderOffScreen -nosound -carla-rpc-port=30000
```

看到 CARLA 不退出，再继续 leaderboard。

### 5.2 先跑 Dev10

把 route 改成：

```bash
leaderboard/data/drivetransformer_bench2drive_dev10.xml
```

或：

```bash
BASE_ROUTES=leaderboard/data/drivetransformer_bench2drive_dev10
```

### 5.3 确认输出

检查：

```text
checkpoint json 是否生成
SAVE_PATH 下是否有 save_name 目录
metric_info.json 是否生成
终端是否有 route statistics
```

### 5.4 再跑完整 220

确认 dev10 正常后再跑：

```bash
leaderboard/scripts/run_evaluation_multi_uniad.sh
```

或 VAD/TCP/ADMLP 对应脚本。

## 6. 结果合并

多进程评测完成后，例如输出目录：

```text
uniad_b2d_traj/
  eval_bench2drive220_0.json
  eval_bench2drive220_1.json
  ...
```

合并：

```bash
python tools/merge_route_json.py -f uniad_b2d_traj/
```

Ability：

```bash
python tools/ability_benchmark.py -r uniad_b2d_traj/merged.json
```

Efficiency/Smoothness：

```bash
python tools/efficiency_smoothness_benchmark.py \
  -f uniad_b2d_traj/merged.json \
  -m eval_bench2drive220_uniad_traj/
```

## 7. 常见问题

### 7.1 `No module named leaderboard`

检查：

```bash
export PYTHONPATH=$PYTHONPATH:leaderboard:scenario_runner
```

必须在 Bench2Drive 根目录运行脚本。

### 7.2 `No module named srunner`

检查：

```bash
export PYTHONPATH=$PYTHONPATH:scenario_runner
export SCENARIO_RUNNER_ROOT=scenario_runner
```

### 7.3 `No module named Bench2DriveZoo`

需要在 Bench2Drive 根目录创建软链接：

```bash
ln -s /path/to/Bench2DriveZoo Bench2DriveZoo
```

或者把 Zoo 根目录加入 `PYTHONPATH`。

### 7.4 agent 文件找不到

检查：

```bash
TEAM_AGENT=leaderboard/team_code/uniad_b2d_agent.py
```

如果 `leaderboard/team_code/` 不存在，需要创建并链接：

```bash
mkdir -p leaderboard/team_code
ln -s /path/to/Bench2DriveZoo/team_code/uniad_b2d_agent.py leaderboard/team_code/uniad_b2d_agent.py
```

### 7.5 CARLA port 冲突

检查端口：

```bash
lsof -i:30000
lsof -i:50000
```

换端口或清理进程。

### 7.6 CARLA 残留进程

使用：

```bash
bash tools/clean_carla.sh
```

或手动 kill `CarlaUE4`、`leaderboard_evaluator.py`。

### 7.7 CARLA 启动后立刻退出

常见原因：

- Vulkan/显卡驱动问题。
- `-graphicsadapter` 不匹配。
- 服务器无可用渲染设备。

检查：

```bash
vulkaninfo | head -n 5
```

尝试改：

```bash
--gpu-rank
```

或 `leaderboard_evaluator.py` 中启动 CARLA 的 `-graphicsadapter`。

### 7.8 sensor took too long

报错来自：

```text
leaderboard/leaderboard/envs/sensor_interface.py
```

可能原因：

- CARLA tick 卡住。
- sensor 创建失败。
- agent.sensors() 中 id 重复。
- GPU/渲染过慢。
- 队列里没有当前 frame 的所有 sensor。

### 7.9 route 被忽略 scenario

日志：

```text
WARNING: Ignoring scenario ... as it is too far from the route
```

说明 trigger point 与 route 不匹配。

修改 route XML 的 trigger point 或 waypoint。

### 7.10 指标不准

如果不是 220 route，`merge_route_json.py` 仍然除以 220。

RoadTailBench 必须改分母，或单独写后处理脚本。

## 8. Windows 与 Ubuntu

Bench2Drive 闭环评测建议 Ubuntu。

原因：

- 脚本是 bash。
- CARLA 0.9.15 Linux server 更适合服务器。
- `leaderboard_evaluator.py` 使用 `preexec_fn=os.setsid`，这是 Unix 机制。
- 多进程脚本、`lsof`、`pkill`、`awk` 等都是 Linux 命令。

Windows 可以看代码和文档，但不建议直接复现闭环。

## 9. RoadTailBench 调试建议

1. 先只放一个无交互 `FreeRide` route。
2. 确认 ego 能从起点到终点。
3. 再加入 traffic light/stop。
4. 再加入动态 actor scenario。
5. 每次只改一个变量，保留 route JSON 和视频。
6. route 数量稳定后再改指标后处理分母。
