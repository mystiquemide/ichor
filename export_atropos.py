"""Write an Atropos environment folder: pairs.jsonl plus the environment and reward modules."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from .export_dpo import to_record

TEMPLATE_DIR = Path(__file__).resolve().parent / "atropos"
FILES = ("ichor_env.py", "ichor_reward.py")


def write(pairs: Iterable[dict[str, Any]], out_dir: Path) -> tuple[Path, int]:
    env_dir = out_dir / "atropos_env"
    env_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(env_dir / "pairs.jsonl", "w", encoding="utf-8") as fh:
        for pair in pairs:
            if pair.get("prompt") and pair.get("accepted") and pair.get("rejected"):
                fh.write(json.dumps(to_record(pair), ensure_ascii=False) + "\n")
                n += 1
    for name in FILES:
        shutil.copyfile(TEMPLATE_DIR / name, env_dir / name)
    return env_dir, n
