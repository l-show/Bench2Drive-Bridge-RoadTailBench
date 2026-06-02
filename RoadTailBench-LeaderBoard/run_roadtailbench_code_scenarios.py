#!/usr/bin/env python
"""兼容旧入口；真实批量运行逻辑在 batch_scenario_runner 下。"""

import sys
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from batch_scenario_runner.run_batch_scenarios import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())

