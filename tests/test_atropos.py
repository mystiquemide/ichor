import importlib.util
from pathlib import Path

from ichor.export_atropos import write

ROOT = Path(__file__).resolve().parent.parent


def _reward_module():
    spec = importlib.util.spec_from_file_location("ichor_reward", ROOT / "atropos" / "ichor_reward.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reward_prefers_accepted():
    r = _reward_module().reward
    accepted, rejected = "fd -e py -x cat | wc -l", 'find . -name "*.py" -exec cat {} + | wc -l'
    assert r("```bash\nfd -e py -x cat | wc -l\n```", accepted, rejected) > 0.5
    assert r(rejected, accepted, rejected) < -0.5
    assert -1.0 <= r("something else entirely", accepted, rejected) <= 1.0
    assert r("<think>use find</think>fd -e py -x cat | wc -l", accepted, rejected) > 0.5
    assert r("", accepted, rejected) == 0.0


def test_export_writes_env_folder(tmp_path):
    pair = dict(id=1, kind="correction", prompt="p", rejected="r", accepted="a")
    env_dir, n = write([pair, dict(pair, accepted="")], tmp_path)
    assert n == 1
    assert sorted(p.name for p in env_dir.iterdir()) == ["ichor_env.py", "ichor_reward.py", "pairs.jsonl"]
