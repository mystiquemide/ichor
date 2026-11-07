"""Atropos environment built from your Ichor corrections.

Each item is a prompt where Hermes was corrected. The policy samples completions, and each one is
scored by how close it lands to the answer you accepted versus the one you rejected
(see ichor_reward.py). Data comes from pairs.jsonl next to this file, written by `/ichor export`.

Run with Atropos installed (https://github.com/NousResearch/atropos):
    python ichor_env.py serve --env.tokenizer_name <model> --openai.base_url http://localhost:9001/v1

Experimental: string similarity is a weak reward. Treat this as a starting point for RL on your own
failure cases, not a finished benchmark.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List, Optional, Tuple

from atroposlib.envs.base import APIServerConfig, BaseEnv, BaseEnvConfig, ScoredDataGroup

from ichor_reward import reward

HERE = Path(__file__).resolve().parent


def tokenize(tokenizer, chat: List[dict]) -> dict:
    """Tokens plus prompt-masked labels. Works on transformers 4 and 5.

    atroposlib's tokenize_for_trainer calls apply_chat_template without return_dict=False, which on
    transformers 5 returns a BatchEncoding, so len() counts its keys instead of tokens.
    """
    def ids(messages, **kw):
        out = tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False, **kw)
        return list(out["input_ids"]) if hasattr(out, "keys") else list(out)

    tokens = ids(chat)
    prefix = len(ids(chat[:-1], add_generation_prompt=True))
    return {"tokens": tokens, "masks": [-100] * prefix + tokens[prefix:]}


def load_pairs(path: Path = HERE / "pairs.jsonl") -> List[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            rows.append({
                "prompt": rec["prompt"][0]["content"],
                "accepted": rec["chosen"][0]["content"],
                "rejected": rec["rejected"][0]["content"],
            })
    return rows


class IchorEnv(BaseEnv):
    name = "ichor_corrections"

    def __init__(self, config: BaseEnvConfig, server_configs: List[APIServerConfig], slurm=False, testing=False):
        super().__init__(config, server_configs, slurm, testing)
        self.pairs: List[dict] = []
        self.iter = 0

    @classmethod
    def config_init(cls) -> Tuple[BaseEnvConfig, List[APIServerConfig]]:
        env_config = BaseEnvConfig(
            tokenizer_name="NousResearch/Hermes-3-Llama-3.1-8B",
            group_size=8,
            use_wandb=False,
            total_steps=200,
            batch_size=16,
            max_token_length=1024,
            wandb_name="ichor",
        )
        servers = [APIServerConfig(model_name="NousResearch/Hermes-3-Llama-3.1-8B",
                                   base_url="http://localhost:9001/v1", api_key="x")]
        return env_config, servers

    async def setup(self) -> None:
        self.pairs = load_pairs()
        random.Random(0).shuffle(self.pairs)

    async def get_next_item(self) -> dict:
        item = self.pairs[self.iter % len(self.pairs)]
        self.iter += 1
        return item

    async def collect_trajectories(self, item: dict) -> Tuple[Optional[ScoredDataGroup], list]:
        messages = [{"role": "user", "content": item["prompt"]}]
        completions = await self.server.chat_completion(
            messages=messages, n=self.config.group_size, max_tokens=self.config.max_token_length, temperature=1.0)
        rollouts = [messages + [{"role": "assistant", "content": c.message.content or ""}] for c in completions.choices]
        return self.score_rollouts(rollouts, item), []

    def score_rollouts(self, rollouts: List[List[dict]], item: dict) -> Optional[ScoredDataGroup]:
        group = ScoredDataGroup(tokens=[], masks=[], scores=[])
        for msgs in rollouts:
            out = tokenize(self.tokenizer, msgs)
            group["tokens"].append(out["tokens"])
            group["masks"].append(out["masks"])
            group["scores"].append(reward(msgs[-1]["content"], item["accepted"], item["rejected"]))
        if len(set(group["scores"])) <= 1:
            return None  # no signal when every completion scores the same
        return group

    async def evaluate(self, *args, **kwargs) -> None:
        return None


if __name__ == "__main__":
    IchorEnv.cli()
