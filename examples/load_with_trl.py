"""Load an Ichor export with Hugging Face datasets and run TRL's own preference preprocessing on it.

Usage:
    python examples/load_with_trl.py path/to/dpo.jsonl [tokenizer]

Default tokenizer is a small chat model (Qwen/Qwen2.5-0.5B-Instruct). Only the tokenizer is downloaded.
"""

import sys

from datasets import load_dataset
from transformers import AutoTokenizer
from trl.data_utils import apply_chat_template, is_conversational


def main() -> None:
    path = sys.argv[1]
    tok_name = sys.argv[2] if len(sys.argv) > 2 else "Qwen/Qwen2.5-0.5B-Instruct"
    ds = load_dataset("json", data_files=path, split="train")
    print(f"rows: {len(ds)}  columns: {ds.column_names}")
    assert is_conversational(ds[0]), "not in TRL conversational format"
    tok = AutoTokenizer.from_pretrained(tok_name)
    ds = ds.map(apply_chat_template, fn_kwargs={"processing_class": tok}, remove_columns=["metadata"])
    row = ds[0]
    print("--- prompt ---\n" + row["prompt"])
    print("--- chosen ---\n" + row["chosen"])
    print("--- rejected ---\n" + row["rejected"])
    print(f"ok: {len(ds)} preference pairs ready for trl.DPOTrainer")


if __name__ == "__main__":
    main()
