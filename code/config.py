from pathlib import Path
import json

# 运行命令必须在项目根目录执行；所有输入输出均保持相对路径。
ROOT = Path('.')
DATA = ROOT
OUT = ROOT / "outputs"
DT = 1.0 / 6.0
POWER_KW = 5000.0
U = POWER_KW * DT
E_MIN, E_MAX, E0, ETA = 1200.0, 10800.0, 6000.0, 0.9
EMERGENCY_MULT, UP_MULT, DOWN_RATE = 5.0, 1.5, 0.5
SEED = 2026
TOL = 1e-6
DEFAULTS = {
    "mode": "smoke", "start": "2025-02-01", "end": "2025-02-03",
    "save_full_solves": False, "max_run_bytes": 500_000_000,
    "history_window": 28, "half_life": 7.0,
}

def read_config(path=None):
    cfg = dict(DEFAULTS)
    if path:
        with Path(path).open(encoding="utf-8") as f: cfg.update(json.load(f))
    return cfg
