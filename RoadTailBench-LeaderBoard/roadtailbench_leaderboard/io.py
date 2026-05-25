import json
from pathlib import Path


def load_frames(path):
    path = Path(path)
    if path.suffix.lower() == ".jsonl":
        frames = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    frames.append(json.loads(line))
        return frames
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "frames" in data:
        return data["frames"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unsupported frame log format: {path}")


def load_config(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
