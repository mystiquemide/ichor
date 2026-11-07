import json

from ichor.export_dpo import to_record, write


def _pair(i=1, **kw):
    p = dict(id=i, kind="correction", prompt="build it", rejected="npm run build", accepted="pnpm build",
             feedback="no, use pnpm", model="m", created_at=1.0, category=None)
    p.update(kw)
    return p


def test_record_shape_is_trl_conversational():
    rec = to_record(_pair())
    assert rec["prompt"] == [{"role": "user", "content": "build it"}]
    assert rec["chosen"] == [{"role": "assistant", "content": "pnpm build"}]
    assert rec["rejected"] == [{"role": "assistant", "content": "npm run build"}]
    assert rec["metadata"]["source"] == "ichor"


def test_write_skips_incomplete_and_counts(tmp_path):
    path, n = write([_pair(1), _pair(2, accepted=""), _pair(3)], tmp_path / "out")
    assert n == 2
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["metadata"]["id"] for r in rows] == [1, 3]
    assert not list((tmp_path / "out").glob("*.tmp"))


def test_unicode_is_kept(tmp_path):
    path, _ = write([_pair(accepted="café ✓")], tmp_path)
    assert "café ✓" in path.read_text(encoding="utf-8")
