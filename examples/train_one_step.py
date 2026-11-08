"""Run real DPOTrainer steps on an Ichor export with a tiny model, on CPU, in about a minute.

Usage:
    python examples/train_one_step.py path/to/dpo.jsonl [model] [steps]

Default model is TRL's own tiny test model, so this proves the format, not model quality.
"""

import sys
import tempfile

from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DPOConfig, DPOTrainer


def main() -> None:
    path = sys.argv[1]
    model_id = sys.argv[2] if len(sys.argv) > 2 else "trl-internal-testing/tiny-Qwen2ForCausalLM-2.5"
    steps = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    ds = load_dataset("json", data_files=path, split="train").remove_columns(["metadata"])
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id)
    with tempfile.TemporaryDirectory() as out:
        args = DPOConfig(output_dir=out, max_steps=steps, per_device_train_batch_size=2,
                         gradient_accumulation_steps=max(1, min(len(ds), 8) // 2),
                         learning_rate=5e-4, logging_steps=1, report_to=[], save_strategy="no", use_cpu=True,
                         max_length=512, truncation_mode="keep_end")  # logits are batch x 512 x 152k vocab: small batches fit a laptop
        trainer = DPOTrainer(model=model, args=args, train_dataset=ds, processing_class=tok)
        result = trainer.train()
    losses = [round(h["loss"], 4) for h in trainer.state.log_history if "loss" in h]
    print(f"DPOTrainer ran {result.global_step} step(s) on {len(ds)} Ichor pairs. losses: {losses}")


if __name__ == "__main__":
    main()
