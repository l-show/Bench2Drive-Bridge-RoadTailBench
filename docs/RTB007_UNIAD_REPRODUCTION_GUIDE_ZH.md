# RTB007 UniAD + RoadTailBench 复现实验傻瓜式流程

本文记录 RTB007 场景下 UniAD 与 RoadTailBench 指标联合仿真的完整复现实验步骤。目标是让第一次接触本项目的人，也能照着一步一步跑出结果。

## 0. 本机路径约定

本文按当前实验机器路径书写：

- CARLA 源码工程：`/home/hqj/carla`
- Bench2Drive + RoadTailBench 桥接仓库：`/home/hqj/Bench2Drive-Bridge-RoadTailBench`
- UniAD 算法工作副本：`/home/hqj/bench2drive-work/Bench2DriveZoo`
- RTB007 背景场景脚本：`/home/hqj/Carla_pythonproj/RTB7.py`
- CARLA/UE 虚拟环境：`condacarla`
- Bench2Drive/UniAD 虚拟环境：`bench_py38`

如果换机器，先把上面路径替换成自己的真实路径。

## 1. 打开终端 1：启动 CARLA/UE

所有 CARLA 相关工作都先检查并清掉废弃进程。打开一个新终端，执行：

```bash
pgrep -af 'RTB7.py|run_roadtailbench_bridge|run_uniad|leaderboard_evaluator|CarlaUE4|UE4Editor|CrashReport' || true
```

如果看到旧的 `RTB7.py`、`run_uniad`、`run_roadtailbench_bridge` 等残留进程，先清掉：

```bash
pkill -f '/home/hqj/Carla_pythonproj/RTB7.py' || true
pkill -f 'run_roadtailbench_bridge.py' || true
pkill -f 'run_uniad.sh' || true
pkill -f 'leaderboard_evaluator.py' || true
```

然后激活 CARLA 环境并用指定方式启动 UE：

```bash
source /home/hqj/anaconda3/etc/profile.d/conda.sh
conda activate condacarla
cd /home/hqj/carla
make launch
```

注意：

- 必须用 `conda activate condacarla` 后的 `make launch`。
- 不要手动运行 `CarlaUE4.sh`。
- 不要用鼠标键盘模拟点击 Play。
- UE 窗口打开后，保持这个终端不要关闭。

## 2. 在 UE 可视化界面确认地图

UE 打开后，在内容浏览器中确认地图是 `RTB007`，不是 `RTB007V2`。

正确地图路径为：

```text
/Game/Carla/Maps/RTB007
```

如果需要用 Python API 确认当前世界，另开一个临时终端执行：

```bash
source /home/hqj/anaconda3/etc/profile.d/conda.sh
conda activate condacarla
python - <<'PY'
import carla
client = carla.Client("127.0.0.1", 2000)
client.set_timeout(10)
world = client.get_world()
print(world.get_map().name)
PY
```

期望输出：

```text
Carla/Maps/RTB007
```

如果不是 RTB007，执行：

```bash
source /home/hqj/anaconda3/etc/profile.d/conda.sh
conda activate condacarla
python - <<'PY'
import carla
client = carla.Client("127.0.0.1", 2000)
client.set_timeout(30)
client.load_world("RTB007")
print(client.get_world().get_map().name)
PY
```

## 3. 用命令方式进入 Play

本实验不使用鼠标键盘点击 Play。Bench2Drive/Leaderboard 运行时会通过 CARLA 客户端连接现有 UE，并设置仿真运行状态。

在运行评测前，建议先清空场景中残留 actor：

```bash
source /home/hqj/anaconda3/etc/profile.d/conda.sh
conda activate condacarla
python - <<'PY'
import carla
client = carla.Client("127.0.0.1", 2000)
client.set_timeout(10)
world = client.get_world()
targets = [a for a in world.get_actors() if a.type_id.startswith(("vehicle.", "walker.", "sensor."))]
print("remaining_targets_before =", len(targets))
if targets:
    client.apply_batch_sync([carla.command.DestroyActor(a) for a in targets], True)
    print("destroyed =", len(targets))
print("map =", world.get_map().name)
PY
```

## 4. 打开终端 2：启动 UniAD + RoadTailBench 评测

打开第二个新终端，执行：

```bash
source /home/hqj/anaconda3/etc/profile.d/conda.sh
conda activate bench_py38
cd /home/hqj/Bench2Drive-Bridge-RoadTailBench
bash run_uniad.sh
```

这个脚本会转到：

```text
/home/hqj/Bench2Drive-Bridge-RoadTailBench/leaderboard/run_uniad.sh
```

它会使用：

- route 文件：`leaderboard/data/routes_rtb007.xml`
- town：`RTB007`
- agent：`/home/hqj/bench2drive-work/Bench2DriveZoo/team_code/uniad_b2d_agent.py`
- agent config：`/home/hqj/bench2drive-work/Bench2DriveZoo/adzoo/uniad/configs/stage2_e2e/base_e2e_b2d.py`
- RT 指标输出：`leaderboard/roadtailbench_outputs/`
- RT checkpoint：`leaderboard/rtb_results.json`
- 超时保护：`ROADTAILBENCH_MAX_TICKS=2400`，约等于 120 秒仿真时间。

看到类似下面内容表示 UniAD 正在启动：

```text
正在启动 UniAD + RoadTailBench 指标闭环测试...
Config Path: ...
RoadTailBench Output: ...
```

## 5. 打开终端 3：立刻启动 RTB7 背景场景

终端 2 启动后，马上打开第三个新终端，执行：

```bash
source /home/hqj/anaconda3/etc/profile.d/conda.sh
conda activate condacarla
python /home/hqj/Carla_pythonproj/RTB7.py
```

RTB7 会等待主车出现。看到下面日志说明场景脚本已经识别到主车并开始执行：

```text
等待 Leaderboard 主车...
检测到主车
Scenario started
[上帝之手] 预热结束！...
```

注意：RTB7.py 是常驻脚本，评测结束后需要手动停止或用命令杀掉。

## 6. 等待评测结束

终端 2 中会持续输出 UniAD 主车速度和仿真时间。RTB007 这次实验通常在 11 到 13 秒仿真时间完成，但因为 UniAD 推理较慢，真实等待时间可能是十几分钟。

看到类似下面内容表示评测已经结束并保存 RT 指标：

```text
> Stopping the route
> RoadTailBench metrics saved: .../roadtailbench_metrics.json
```

原版 Bench2Drive 可能显示 `FAILURE`，常见原因是原版 `MinSpeedTest`，不要把它当作 RT 指标失败。本文只看 RoadTailBench 的 10 个核心指标。

## 7. 停止 RTB7 并清理 actor

评测结束后，在任意终端执行：

```bash
pkill -f '/home/hqj/Carla_pythonproj/RTB7.py' || true
pkill -f 'RTB7.py' || true
```

再清理残留车辆：

```bash
source /home/hqj/anaconda3/etc/profile.d/conda.sh
conda activate condacarla
python - <<'PY'
import carla
client = carla.Client("127.0.0.1", 2000)
client.set_timeout(10)
world = client.get_world()
targets = [a for a in world.get_actors() if a.type_id.startswith(("vehicle.", "walker.", "sensor."))]
print("remaining_targets =", len(targets))
for a in targets:
    print(a.id, a.type_id, a.attributes.get("role_name", ""))
if targets:
    client.apply_batch_sync([carla.command.DestroyActor(a) for a in targets], True)
    print("destroyed =", len(targets))
PY
```

## 8. 查看最新 RT 指标

执行：

```bash
python3 - <<'PY'
import glob, json, os
root = "/home/hqj/Bench2Drive-Bridge-RoadTailBench/leaderboard/roadtailbench_outputs"
out = max(glob.glob(os.path.join(root, "*")), key=os.path.getmtime)
metrics_path = os.path.join(out, "roadtailbench_metrics.json")
data = json.load(open(metrics_path))
print("output_dir =", out)
print("evaluation =", data.get("evaluation"))
keys = [
    "route_completion",
    "collision_penalty",
    "driving_efficiency",
    "speed_appropriateness",
    "drivable_area",
    "omnidirectional_interaction_risk",
    "road_engineering_hazard_adaptation",
    "comfort",
    "control_stability",
    "long_tail_hazard_response",
]
for k in keys:
    print(k, data["metrics"][k]["score"])
PY
```

本次验证运行的关键结果：

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

## 9. 常见问题

如果 RTB7 一直显示等待主车，说明 UniAD/Leaderboard 还没有生成 hero 车辆，继续等或检查终端 2 是否报错。

如果提示 spawn actor 失败：

```text
WARNING: Cannot spawn actor vehicle.* at position ...
```

通常是该位置已有车辆或背景脚本重复刷车。先结束 RTB7，再执行第 7 节清理 actor。

如果 UE 崩溃或窗口不可用，先关闭废弃 UE 进程，再回到第 1 节重新用 `condacarla + make launch` 启动。

如果原版 Bench2Drive 显示 `FAILURE`，先检查 RT 指标文件。RTB007 实验中常见是原版 `MinSpeedTest` 失败，但 RT 路线完成、碰撞、可行驶区域等指标仍可能是成功的。
