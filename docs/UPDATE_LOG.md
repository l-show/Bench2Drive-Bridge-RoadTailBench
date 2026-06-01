# 更新日志：RTB007 UniAD 闭环测试入口

本文记录并说明本次新增的两个文件：

- `leaderboard/data/routes_rtb007.xml`
- `leaderboard/run_uniad.sh`

这两个文件共同提供了一个面向 `RTB007` 地图的 UniAD 闭环测试最小入口：`routes_rtb007.xml` 定义测试路线、天气和场景触发点，`run_uniad.sh` 负责配置环境变量并调用 Bench2Drive leaderboard evaluator 启动评测。

## 1. 新增文件用途

| 文件 | 用途 |
|---|---|
| `leaderboard/data/routes_rtb007.xml` | 定义一条 `RTB007` 地图上的测试路线，包括路线起终点、天气参数和 `ControlLoss` 场景触发点。 |
| `leaderboard/run_uniad.sh` | UniAD 闭环评测启动脚本，自动设置 Bench2Drive、ScenarioRunner、Bench2DriveZoo、CARLA 的路径，并调用 `leaderboard_evaluator.py` 执行路线。 |

## 2. `run_uniad.sh` 脚本功能分析

`run_uniad.sh` 的主要作用是把一次 UniAD 闭环测试需要的路径、评测参数和 agent 参数集中起来，避免每次手动输入完整 evaluator 命令。

脚本流程如下：

1. 计算脚本所在目录，并将其作为 `LEADERBOARD_ROOT`。
2. 设置 `SCENARIO_RUNNER_ROOT`、`ZOO_ROOT`、`CARLA_ROOT`。
3. 拼接 `PYTHONPATH`，让 Python 能找到 CARLA API、leaderboard、ScenarioRunner 和 Bench2DriveZoo 代码。
4. 指定路线文件 `routes_rtb007.xml`、路线子集、重复次数、debug 开关、track 类型和结果输出文件。
5. 指定 UniAD agent 文件和 UniAD 配置文件。
6. 切换到 Bench2Drive 根目录。
7. 调用 `leaderboard/leaderboard_evaluator.py`，连接 CARLA 并执行闭环评测。

当前脚本固定使用：

- 路线文件：`leaderboard/data/routes_rtb007.xml`
- Agent：`Bench2DriveZoo/team_code/uniad_b2d_agent.py`
- Agent 配置：`Bench2DriveZoo/adzoo/uniad/configs/stage2_e2e/base_e2e_b2d.py`
- CARLA RPC 端口：`2000`
- Traffic Manager 端口：`8000`
- 结果输出：`leaderboard/results.json`

## 3. 参数说明

### 3.1 路径相关环境变量

| 参数 | 当前值 | 说明 |
|---|---|---|
| `SCRIPT_DIR` | 脚本所在目录 | 通过 Bash 自动计算，通常为 `Bench2Drive/leaderboard`。 |
| `LEADERBOARD_ROOT` | `$SCRIPT_DIR` | leaderboard 工具根目录。 |
| `SCENARIO_RUNNER_ROOT` | `${LEADERBOARD_ROOT}/../scenario_runner` | ScenarioRunner 根目录，提供场景执行、行为树和评测基础能力。 |
| `ZOO_ROOT` | `${LEADERBOARD_ROOT}/../../Bench2DriveZoo` | Bench2DriveZoo 根目录，用于加载 UniAD agent、配置和模型代码。 |
| `CARLA_ROOT` | `/home/hqj/carla` | 本地 CARLA 安装目录。需要根据机器实际 CARLA 路径调整。 |
| `PYTHONPATH` | 多路径拼接 | 将 CARLA PythonAPI、leaderboard、ScenarioRunner、Bench2DriveZoo 加入 Python 模块搜索路径。 |

### 3.2 评测相关环境变量

| 参数 | 当前值 | 说明 |
|---|---|---|
| `ROUTES` | `${LEADERBOARD_ROOT}/data/routes_rtb007.xml` | 本次要执行的 route XML 文件。 |
| `ROUTES_SUBSET` | `0` | 只执行 route id 为 `0` 的路线。`route_parser.py` 支持单个 id、逗号分隔 id，以及 `start-end` 范围。 |
| `REPETITIONS` | `1` | 每条 route 重复执行次数。 |
| `DEBUG_CHALLENGE` | `1` | 开启 debug 输出。传给 evaluator 的 `--debug` 参数。 |
| `CHALLENGE_TRACK_CODENAME` | `SENSORS` | 评测 track。UniAD 使用传感器输入闭环驾驶，因此为 `SENSORS`。 |
| `CHECKPOINT_ENDPOINT` | `${LEADERBOARD_ROOT}/results.json` | 评测统计和恢复进度的 checkpoint 文件。 |

### 3.3 Agent 相关环境变量

| 参数 | 当前值 | 说明 |
|---|---|---|
| `TEAM_AGENT` | `${ZOO_ROOT}/team_code/uniad_b2d_agent.py` | leaderboard 动态加载的 UniAD agent 文件。 |
| `AGENT_CONFIG` | `${ZOO_ROOT}/adzoo/uniad/configs/stage2_e2e/base_e2e_b2d.py` | 传给 UniAD agent 的配置路径。 |

注意：Bench2DriveZoo 的 UniAD agent 通常需要 `config+checkpoint+保存名` 形式的 `agent-config`，例如：

```bash
--agent-config=/path/to/base_e2e_b2d.py+/path/to/uniad_base_b2d.pth+UniAD-Base
```

当前脚本只传入了 config 文件路径。如果本地 `uniad_b2d_agent.py` 仍按 `+` 分隔解析 checkpoint，则需要把 `AGENT_CONFIG` 改成完整的三段式参数。

### 3.4 evaluator 命令行参数

脚本最终调用：

```bash
python3 ${LEADERBOARD_ROOT}/leaderboard/leaderboard_evaluator.py \
  --routes=${ROUTES} \
  --routes-subset=${ROUTES_SUBSET} \
  --repetitions=${REPETITIONS} \
  --track=${CHALLENGE_TRACK_CODENAME} \
  --checkpoint=${CHECKPOINT_ENDPOINT} \
  --agent=${TEAM_AGENT} \
  --agent-config=${AGENT_CONFIG} \
  --debug=${DEBUG_CHALLENGE} \
  --port=2000 \
  --traffic-manager-port=8000
```

| 参数 | 说明 |
|---|---|
| `--routes` | 指定要加载的 route XML。 |
| `--routes-subset` | 指定 XML 中要执行的 route id。当前只执行 `0`。 |
| `--repetitions` | 每条路线重复次数。 |
| `--track` | leaderboard track，常用值为 `SENSORS` 或 `MAP`。 |
| `--checkpoint` | 保存评测结果和恢复进度的 JSON 文件。 |
| `--agent` | 被评测 agent 的 Python 文件路径。 |
| `--agent-config` | 传给 agent 的配置字符串。UniAD 通常包含 config、checkpoint 和保存名。 |
| `--debug` | debug 输出等级。 |
| `--port` | CARLA server RPC 端口，需要和 CARLA 启动端口一致。 |
| `--traffic-manager-port` | CARLA Traffic Manager 端口。 |

## 4. `routes_rtb007.xml` 文件作用

`routes_rtb007.xml` 是 leaderboard evaluator 的路线配置文件。它告诉 Bench2Drive 在哪个地图运行、ego 车从哪里出发、目标点在哪里、使用什么天气，以及沿途需要触发哪些场景。

当前 XML 结构如下：

```xml
<routes>
  <route id="0" town="RTB007">
    ...
  </route>
</routes>
```

### 4.1 Route 基本信息

| 字段 | 当前值 | 说明 |
|---|---|---|
| `route id` | `0` | 路线编号，和脚本中的 `ROUTES_SUBSET=0` 对应。 |
| `town` | `RTB007` | CARLA/Bench2Drive 需要加载的地图名称。 |

### 4.2 天气配置

`weathers` 中只定义了一个默认晴天配置：

| 参数 | 当前值 | 说明 |
|---|---|---|
| `route_percentage` | `0` | 从路线 0% 位置开始使用该天气。 |
| `cloudiness` | `5.0` | 云量较低。 |
| `precipitation` | `0.0` | 无降雨。 |
| `precipitation_deposits` | `0.0` | 无积水。 |
| `wetness` | `0.0` | 路面干燥。 |
| `wind_intensity` | `10.0` | 轻微风。 |
| `sun_azimuth_angle` | `-1.0` | 太阳方位角。 |
| `sun_altitude_angle` | `90.0` | 太阳高度角，接近正午光照。 |
| `fog_density` | `2.0` | 很低的雾密度。 |

### 4.3 路线关键点

`waypoints` 定义 ego 车需要经过的路线关键点：

| 顺序 | x | y | z | 说明 |
|---|---:|---:|---:|---|
| 1 | `34.843` | `72.746` | `0.5` | 起点附近。 |
| 2 | `25.3` | `-77.5` | `0.5` | 终点附近。 |

leaderboard 会根据这些关键点生成导航路线，并将全局路线传给 UniAD agent。agent 每帧根据当前位置和全局路线生成导航 command，再输出车辆控制量。

### 4.4 场景配置

`scenarios` 中定义了一个场景：

| 字段 | 当前值 | 说明 |
|---|---|---|
| `name` | `ControlLoss_1` | 场景名称。 |
| `type` | `ControlLoss` | 场景类型，用于测试车辆控制稳定性或失控恢复能力。 |
| `trigger_point` | `x=34.8, y=72.7, z=0.5, yaw=0` | 场景触发位置和朝向。 |

该触发点靠近第一个 waypoint，因此车辆进入路线初始区域后就可能触发 `ControlLoss` 场景。评测过程中，ScenarioRunner 会根据 route 配置构建对应场景，并在 ego 车接近触发点时启动场景逻辑。

## 5. 示例运行命令

### 5.1 使用脚本运行

先启动 CARLA，并确保 RPC 端口为 `2000`：

```bash
cd /home/hqj/carla
./CarlaUE4.sh -RenderOffScreen -nosound -carla-rpc-port=2000
```

然后运行 UniAD 闭环测试脚本：

```bash
cd /home/hqj/Bench2Drive-Bridge-RoadTailBench/leaderboard
bash run_uniad.sh
```

### 5.2 使用完整 checkpoint 配置运行

如果 UniAD agent 需要 `config+checkpoint+保存名`，需要修改 `leaderboard/run_uniad.sh` 中的 `AGENT_CONFIG` 行：

```bash
export AGENT_CONFIG="${ZOO_ROOT}/adzoo/uniad/configs/stage2_e2e/base_e2e_b2d.py+${ZOO_ROOT}/ckpts/uniad_base_b2d.pth+UniAD-Base-RTB007"
```

然后再运行：

```bash
cd /home/hqj/Bench2Drive-Bridge-RoadTailBench/leaderboard
bash run_uniad.sh
```

### 5.3 直接调用 evaluator

也可以不通过脚本，直接调用 evaluator：

```bash
cd /home/hqj/Bench2Drive-Bridge-RoadTailBench

python3 leaderboard/leaderboard/leaderboard_evaluator.py \
  --routes=leaderboard/data/routes_rtb007.xml \
  --routes-subset=0 \
  --repetitions=1 \
  --track=SENSORS \
  --checkpoint=leaderboard/results.json \
  --agent=/home/hqj/Bench2DriveZoo-Bridge-RoadTailBench/team_code/uniad_b2d_agent.py \
  --agent-config=/home/hqj/Bench2DriveZoo-Bridge-RoadTailBench/adzoo/uniad/configs/stage2_e2e/base_e2e_b2d.py+/home/hqj/Bench2DriveZoo-Bridge-RoadTailBench/ckpts/uniad_base_b2d.pth+UniAD-Base-RTB007 \
  --debug=1 \
  --port=2000 \
  --traffic-manager-port=8000
```

## 6. 使用注意事项

1. `CARLA_ROOT` 需要和本机 CARLA 安装路径一致。
2. `--port` 必须和 CARLA server 的 `-carla-rpc-port` 一致。
3. `--traffic-manager-port` 需要避免和其他评测进程冲突。
4. `ZOO_ROOT` 需要指向包含 `team_code/uniad_b2d_agent.py` 和 `adzoo/uniad` 的 Bench2DriveZoo 目录。
5. 如果 UniAD agent 加载失败，优先检查 `PYTHONPATH`、`TEAM_AGENT`、`AGENT_CONFIG` 和 checkpoint 路径。
6. `routes_rtb007.xml` 只有一条 route，适合快速验证环境和单场景调试，不等价于完整 Bench2Drive benchmark。
