"""Validate and normalize JSONL chat data for future MJ AI fine-tuning.

Input accepts either {"messages":[{"role":"user","content":"..."}, ...]} per line
or {"prompt":"...", "completion":"..."} per line. Output is chat JSONL.
This script prepares data; it does not train a model.
"""
import argparse
import json
from pathlib import Path

ALLOWED = {"system", "user", "assistant"}


def normalize(row):
    if isinstance(row.get("messages"), list):
        messages = row["messages"]
    elif isinstance(row.get("prompt"), str) and isinstance(row.get("completion"), str):
        messages = [{"role": "user", "content": row["prompt"]},
                    {"role": "assistant", "content": row["completion"]}]
    else:
        raise ValueError("expected 'messages' or both 'prompt' and 'completion'")
    cleaned = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in ALLOWED:
            raise ValueError("each message needs role system/user/assistant")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("message content must be a non-empty string")
        cleaned.append({"role": message["role"], "content": content.strip()})
    if not any(m["role"] == "user" for m in cleaned) or not any(m["role"] == "assistant" for m in cleaned):
        raise ValueError("each example needs at least one user and assistant message")
    return {"messages": cleaned}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    good, skipped = 0, 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.input.open(encoding="utf-8") as source, args.output.open("w", encoding="utf-8") as target:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                row = normalize(json.loads(line))
            except (json.JSONDecodeError, ValueError) as exc:
                skipped += 1
                print(f"Skipping line {line_number}: {exc}")
                continue
            target.write(json.dumps(row, ensure_ascii=False) + "\n")
            good += 1
    print(f"Prepared {good} examples; skipped {skipped}. Output: {args.output}")


if __name__ == "__main__":
    main()
