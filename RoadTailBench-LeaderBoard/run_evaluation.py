import argparse

from roadtailbench_leaderboard.io import load_config, load_frames, save_json
from roadtailbench_leaderboard.metrics import CORE_METRICS
from roadtailbench_leaderboard.metrics.ability_score import AbilityScoreMetric
from roadtailbench_leaderboard.metrics.composite_score import CompositeScoreMetric


def evaluate(frames, config):
    results = {}
    for metric_cls in CORE_METRICS:
        metric = metric_cls()
        result = metric.compute(frames, config, results)
        results[result["name"]] = result
    for metric in (CompositeScoreMetric(), AbilityScoreMetric()):
        result = metric.compute(frames, config, results)
        results[result["name"]] = result
    return {
        "scenario_id": config.get("scenario_id", "unknown"),
        "route_id": config.get("route_id", "unknown"),
        "metrics": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate RoadTailBench closed-loop frame logs.")
    parser.add_argument("--frames", required=True, help="Path to frame log JSON or JSONL.")
    parser.add_argument("--config", required=True, help="Path to scenario config JSON.")
    parser.add_argument("--output", required=True, help="Output metrics JSON.")
    args = parser.parse_args()
    frames = load_frames(args.frames)
    config = load_config(args.config)
    save_json(args.output, evaluate(frames, config))
    print(f"Saved RoadTailBench metrics to {args.output}")


if __name__ == "__main__":
    main()
