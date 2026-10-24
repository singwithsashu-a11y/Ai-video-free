"""Train an MJ AI LoRA adapter on a compatible Hugging Face causal LM.

This fine-tunes an existing base model; it does not train a foundation model from zero.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Hugging Face model ID or local model directory")
    parser.add_argument("--data", type=Path, required=True, help="Prepared chat JSONL")
    parser.add_argument("--output", type=Path, default=Path("training/output/mj-ai-lora"))
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--rank", type=int, default=8)
    parser.add_argument(
        "--target-modules",
        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
        help="Comma-separated module names; Qwen2.5 default provided",
    )
    args = parser.parse_args()

    if not args.data.is_file():
        raise SystemExit(f"Training data file not found: {args.data}")
    if args.epochs <= 0 or args.max_length < 32 or args.rank < 1:
        raise SystemExit("--epochs must be > 0, --max-length >= 32 and --rank >= 1")

    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise SystemExit(
            "Missing training packages. Run: pip install transformers datasets peft accelerate"
        ) from exc

    rows = []
    for line_number, line in enumerate(args.data.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON on line {line_number}: {exc}") from exc
        if not isinstance(row, dict) or not isinstance(row.get("messages"), list):
            raise SystemExit(f"Line {line_number} must contain a messages list.")
        rows.append(row)
    if not rows:
        raise SystemExit("Training dataset is empty. Check the dataset preparation output.")

    print(f"Loading tokenizer and base model: {args.model}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model)
    model.config.use_cache = False

    target_modules = [name.strip() for name in args.target_modules.split(",") if name.strip()]
    model = get_peft_model(
        model,
        LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=args.rank,
            lora_alpha=args.rank * 2,
            lora_dropout=0.05,
            target_modules=target_modules,
        ),
    )
    model.print_trainable_parameters()

    def render(row):
        text = tokenizer.apply_chat_template(
            row["messages"], tokenize=False, add_generation_prompt=False
        )
        return {"text": text}

    dataset = Dataset.from_list(rows).map(render)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=args.max_length)

    tokenized = dataset.map(tokenize, batched=True, remove_columns=dataset.column_names)
    args.output.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(args.output / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=2,
        report_to="none",
        fp16=torch.cuda.is_available(),
        dataloader_pin_memory=torch.cuda.is_available(),
        optim="adamw_torch",
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    print(f"Starting training: {len(rows)} examples, {args.epochs} epoch(s)", flush=True)
    trainer.train()
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)

    required = ["adapter_config.json"]
    missing = [name for name in required if not (args.output / name).is_file()]
    if missing:
        raise SystemExit(f"Training ended but adapter files are missing: {missing}")
    print(f"SUCCESS: LoRA adapter saved to {args.output}", flush=True)
    print("Files:", ", ".join(sorted(p.name for p in args.output.iterdir())), flush=True)


if __name__ == "__main__":
    main()
