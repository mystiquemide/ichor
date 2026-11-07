"""Write kept and shared pairs as preference JSONL in TRL's conversational format."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterable


def to_record(pair: dict[str, Any]) -> dict[str, Any]:
    """One TRL conversational preference example: prompt, chosen, rejected as message lists."""
    return {
        "prompt": [{"role": "user", "content": pair["prompt"]}],
        "chosen": [{"role": "assistant", "content": pair["accepted"]}],
        "rejected": [{"role": "assistant", "content": pair["rejected"]}],
        "metadata": {
            "source": "ichor",
            "id": pair.get("id"),
            "kind": pair.get("kind"),
            "category": pair.get("category"),
            "feedback": pair.get("feedback") or "",
            "model": pair.get("model"),
            "created_at": pair.get("created_at"),
        },
    }


def write(pairs: Iterable[dict[str, Any]], out_dir: Path) -> tuple[Path, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "dpo.jsonl"
    tmp = path.with_suffix(".jsonl.tmp")
    n = 0
    with open(tmp, "w", encoding="utf-8") as fh:
        for pair in pairs:
            if not (pair.get("prompt") and pair.get("accepted") and pair.get("rejected")):
                continue
            fh.write(json.dumps(to_record(pair), ensure_ascii=False) + "\n")
            n += 1
    tmp.replace(path)
    return path, n


def default_dir() -> Path:
    from plugins.plugin_storage import plugin_data_dir

    return plugin_data_dir("ichor") / "exports" / time.strftime("%Y%m%d-%H%M%S")
