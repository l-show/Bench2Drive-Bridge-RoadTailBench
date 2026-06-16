#!/bin/bash

# 1. 基础路径配置
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export LEADERBOARD_ROOT=$SCRIPT_DIR
export SCENARIO_RUNNER_ROOT="${LEADERBOARD_ROOT}/../scenario_runner"
export RTB_ROOT="${LEADERBOARD_ROOT}/../RoadTailBench-LeaderBoard"
export ZOO_ROOT="/home/hqj/Bench2DriveZoo-Bridge-RoadTailBench"
export CARLA_ROOT="/home/hqj/carla"
export B2D_ZOO_ROOT="${ZOO_ROOT}"

ZOO_ALIAS="${LEADERBOARD_ROOT}/../Bench2DriveZoo"
if [ -L "${ZOO_ALIAS}" ]; then
  if [ "$(readlink -f "${ZOO_ALIAS}")" != "$(readlink -f "${ZOO_ROOT}")" ]; then
    echo "Bench2DriveZoo symlink points to unexpected target: ${ZOO_ALIAS}" >&2
    exit 1
  fi
elif [ -e "${ZOO_ALIAS}" ]; then
  echo "Bench2DriveZoo path exists but is not the expected symlink: ${ZOO_ALIAS}" >&2
  exit 1
else
  ln -s "${ZOO_ROOT}" "${ZOO_ALIAS}"
fi

# 2. 关键：把 Bench2DriveZoo 及其父目录加进环境变量
export PYTHONPATH="${CARLA_ROOT}/PythonAPI/carla/dist/carla-0.9.15-py3.7-linux-x86_64.egg:${CARLA_ROOT}/PythonAPI/carla:${LEADERBOARD_ROOT}:${SCENARIO_RUNNER_ROOT}:${RTB_ROOT}:${ZOO_ROOT}:${ZOO_ROOT}/..:${LEADERBOARD_ROOT}/..:${PYTHONPATH}"

# 3. 评测参数配置
export ROUTES=${LEADERBOARD_ROOT}/data/routes_rtb007.xml
export ROUTES_SUBSET=0
export REPETITIONS=1
export DEBUG_CHALLENGE=1
export CHALLENGE_TRACK_CODENAME=SENSORS
export CHECKPOINT_ENDPOINT="${LEADERBOARD_ROOT}/rtb_results.json"
export ROADTAILBENCH_OUTPUT="${LEADERBOARD_ROOT}/roadtailbench_outputs"
export ROADTAILBENCH_METADATA_ROOT="${LEADERBOARD_ROOT}/roadtailbench_metadata"
export ROADTAILBENCH_MAX_TICKS="${ROADTAILBENCH_MAX_TICKS:-2400}"

# 4. 指定 UniAD Agent
export TEAM_AGENT="${ZOO_ROOT}/team_code/uniad_b2d_agent.py"

export AGENT_CONFIG="${ZOO_ROOT}/adzoo/uniad/configs/stage2_e2e/base_e2e_b2d.py"

echo "正在启动 UniAD + RoadTailBench 指标闭环测试..."
echo "Config Path: ${AGENT_CONFIG}"
echo "RoadTailBench Output: ${ROADTAILBENCH_OUTPUT}"
cd ${LEADERBOARD_ROOT}/..

python3 ${RTB_ROOT}/run_roadtailbench_bridge.py \
--routes=${ROUTES} \
--routes-subset=${ROUTES_SUBSET} \
--repetitions=${REPETITIONS} \
--track=${CHALLENGE_TRACK_CODENAME} \
--checkpoint=${CHECKPOINT_ENDPOINT} \
--roadtailbench-output=${ROADTAILBENCH_OUTPUT} \
--roadtailbench-metadata-root=${ROADTAILBENCH_METADATA_ROOT} \
--agent=${TEAM_AGENT} \
--agent-config=${AGENT_CONFIG} \
--debug=${DEBUG_CHALLENGE} \
--port=2000 \
--traffic-manager-port=8000
