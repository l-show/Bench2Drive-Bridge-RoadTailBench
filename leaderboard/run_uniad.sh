#!/bin/bash

# 1. 基础路径配置
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export LEADERBOARD_ROOT=$SCRIPT_DIR
export SCENARIO_RUNNER_ROOT="${LEADERBOARD_ROOT}/../scenario_runner"
export ZOO_ROOT="${LEADERBOARD_ROOT}/../../Bench2DriveZoo"
export CARLA_ROOT="/home/hqj/carla"

# 2. 关键：把 Bench2DriveZoo 及其父目录加进环境变量
export PYTHONPATH="${CARLA_ROOT}/PythonAPI/carla/dist/carla-0.9.15-py3.7-linux-x86_64.egg:${CARLA_ROOT}/PythonAPI/carla:${LEADERBOARD_ROOT}:${SCENARIO_RUNNER_ROOT}:${ZOO_ROOT}:${ZOO_ROOT}/..:${PYTHONPATH}"

# 3. 评测参数配置
export ROUTES=${LEADERBOARD_ROOT}/data/routes_rtb007.xml
export ROUTES_SUBSET=0
export REPETITIONS=1
export DEBUG_CHALLENGE=1
export CHALLENGE_TRACK_CODENAME=SENSORS
export CHECKPOINT_ENDPOINT="${LEADERBOARD_ROOT}/results.json"

# 4. 指定 UniAD Agent
export TEAM_AGENT="${ZOO_ROOT}/team_code/uniad_b2d_agent.py"

export AGENT_CONFIG="${ZOO_ROOT}/adzoo/uniad/configs/stage2_e2e/base_e2e_b2d.py"

echo "正在启动 UniAD 闭环测试..."
echo "Config Path: ${AGENT_CONFIG}"
cd ${LEADERBOARD_ROOT}/..

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
