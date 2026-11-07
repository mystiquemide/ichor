import base64
import io
import json
import urllib.error

import pytest

from ichor.share_hf import ShareError, share


class FakeHub:
    def __init__(self, create_status=200, commit_status=200, whoami_status=200, has_readme=True):
        self.calls = []
        self.has_readme = has_readme
        self.create_status, self.commit_status, self.whoami_status = create_status, commit_status, whoami_status

    def __call__(self, req):
        self.calls.append(req)
        path = req.full_url.split("huggingface.co", 1)[1]
        if path == "/api/whoami-v2":
            return self._resp(self.whoami_status, {"name": "mide"})
        if path == "/api/repos/create":
            return self._resp(self.create_status, {"url": "x"})
        if path == "/api/datasets/mide/ichor-pairs":
            files = [{"rfilename": "README.md"}] if self.has_readme else [{"rfilename": ".gitattributes"}]
            return self._resp(200, {"siblings": files})
        if path.endswith("/commit/main"):
            return self._resp(self.commit_status, {"commitOid": "abc"})
        raise AssertionError(path)

    def _resp(self, status, payload):
        if status >= 400:
            raise urllib.error.HTTPError("u", status, "err", {}, io.BytesIO(json.dumps(payload).encode()))
        body = io.BytesIO(json.dumps(payload).encode())
        body.status = status
        return body


def _pairs():
    return [dict(id=1, kind="correction", prompt="p", rejected="r", accepted="a", feedback="no")]


def test_first_share_creates_repo_and_card():
    hub = FakeHub()
    url, n = share(_pairs(), token="t", opener=hub)
    assert (url, n) == ("https://huggingface.co/datasets/mide/ichor-pairs", 1)
    create = json.loads(hub.calls[1].data)
    assert create == {"type": "dataset", "name": "ichor-pairs", "private": True}
    ops = [json.loads(line) for line in hub.calls[2].data.decode().splitlines()]
    paths = [op["value"]["path"] for op in ops if op["key"] == "file"]
    assert paths[0].startswith("data/") and paths[0].endswith("-1.jsonl")
    assert "README.md" in paths
    row = json.loads(base64.b64decode(ops[1]["value"]["content"]))
    assert row["chosen"] == [{"role": "assistant", "content": "a"}]
    assert hub.calls[0].headers["Authorization"] == "Bearer t"


def test_existing_repo_skips_card():
    hub = FakeHub(create_status=409)
    share(_pairs(), token="t", opener=hub)
    ops = [json.loads(line) for line in hub.calls[-1].data.decode().splitlines()]
    assert all(op["value"].get("path") != "README.md" for op in ops if op["key"] == "file")


def test_errors_are_user_messages(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    with pytest.raises(ShareError, match="needs a Hugging Face token"):
        share(_pairs(), opener=FakeHub())
    with pytest.raises(ShareError, match="nothing queued"):
        share([], token="t", opener=FakeHub())
    with pytest.raises(ShareError, match="rejected the token"):
        share(_pairs(), token="t", opener=FakeHub(whoami_status=401))
    with pytest.raises(ShareError, match="can't create repos"):
        share(_pairs(), token="t", opener=FakeHub(create_status=403))
    with pytest.raises(ShareError, match="can't write"):
        share(_pairs(), token="t", opener=FakeHub(commit_status=403))


def test_existing_repo_without_card_gets_one():
    hub = FakeHub(create_status=409, has_readme=False)
    share(_pairs(), token="t", opener=hub)
    ops = [json.loads(line) for line in hub.calls[-1].data.decode().splitlines()]
    assert any(op["value"].get("path") == "README.md" for op in ops if op["key"] == "file")


def test_odd_whoami_payload_is_a_share_error():
    class ListHub(FakeHub):
        def __call__(self, req):
            if req.full_url.endswith("/api/whoami-v2"):
                return self._resp(200, ["not", "a", "dict"])
            return super().__call__(req)
    with pytest.raises(ShareError, match="rejected the token"):
        share(_pairs(), token="t", opener=ListHub())
