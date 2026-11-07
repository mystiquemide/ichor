"""Load an Ichor Atropos export, build IchorEnv, and score sample rollouts with no inference server.

Usage:
    python examples/atropos_smoke.py path/to/atropos_env [tokenizer]
"""

import asyncio
import sys

sys.path.insert(0, sys.argv[1])

from ichor_env import IchorEnv  # noqa: E402


async def main() -> None:
    config, servers = IchorEnv.config_init()
    config.tokenizer_name = sys.argv[2] if len(sys.argv) > 2 else "Qwen/Qwen2.5-0.5B-Instruct"
    env = IchorEnv(config, servers, slurm=False, testing=True)
    await env.setup()
    item = await env.get_next_item()
    print(f"pairs loaded: {len(env.pairs)}")
    print(f"prompt: {item['prompt']}")
    candidates = {"accepted answer": item["accepted"], "rejected answer": item["rejected"],
                  "unrelated answer": "I am not sure, please clarify."}
    rollouts = [[{"role": "user", "content": item["prompt"]}, {"role": "assistant", "content": text}]
                for text in candidates.values()]
    group = env.score_rollouts(rollouts, item)
    for name, score, tokens, masks in zip(candidates, group["scores"], group["tokens"], group["masks"]):
        trained = sum(1 for m in masks if m != -100)
        print(f"  {name:<17} reward {score:+.2f}  tokens {len(tokens)}  trained {trained}")
    print("ok: IchorEnv produced a ScoredDataGroup Atropos can send to a trainer")


if __name__ == "__main__":
    asyncio.run(main())
