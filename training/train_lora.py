"""Train an MJ AI LoRA adapter on a compatible Hugging Face causal LM.

This fine-tunes an existing base model; it does not train a foundation model from zero.
The JSONL file is loaded through Hugging Face Datasets' Arrow cache rather than a
Python list, which is more memory-efficient for large datasets (including 1M rows).
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
    parser.add_argument("--max-samples", type=int, default=0, help="Optional cap for smoke tests; 0 uses all examples")
    parser.add_argument("--gradient-checkpointing", action="store_true")
    parser.add_argument("--target-modules", default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj")
    args = parser.parse_args()

    if not args.data.is_file():
        raise SystemExit(f"Training data file not found: {args.data}")
    if args.epochs <= 0 or args.max_length < 32 or args.rank < 1 or args.max_samples < 0:
        raise SystemExit("Invalid epochs, max length, rank, or max-samples value.")

    try:
        import torch
        from datasets import load_dataset
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import (
            AutoModelForCausalLM, AutoTokenizer,
            DataCollatorForLanguageModeling, Trainer, TrainingArguments,
        )
    except ImportError as exc:
        raise SystemExit("Missing packages. Run: pip install torch transformers datasets peft accelerate") from exc

    print(f"Loading JSONL into disk-backed Arrow cache: {args.data}", flush=True)
    try:
        dataset = load_dataset("json", data_files=str(args.data), split="train")
    except Exception as exc:
        raise SystemExit(f"Could not load JSONL dataset: {exc}") from exc
    if len(dataset) == 0:
        raise SystemExit("Training dataset is empty.")
    if args.max_samples:
        dataset = dataset.select(range(min(args.max_samples, len(dataset))))
    print(f"Training examples selected: {len(dataset):,}", flush=True)

    def validate_row(row, index):
        messages = row.get("messages")
        if not isinstance(messages, list) or not any(
            isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str) and m["content"].strip()
            for m in messages
        ) or not any(
            isinstance(m, dict) and m.get("role") == "assistant" and isinstance(m.get("content"), str) and m["content"].strip()
            for m in messages
        ):
            raise ValueError(f"Example {index} must contain non-empty user and assistant messages.")
        for message in messages:
            if not isinstance(message, dict) or message.get("role") not in {"system", "user", "assistant"}:
                raise ValueError(f"Example {index} contains an invalid message role.")
            if not isinstance(message.get("content"), str) or not message["content"].strip():
                raise ValueError(f"Example {index} contains empty message content.")

    # Validate in batches to avoid copying the full dataset into RAM.
    for start in range(0, len(dataset), 10000):
        batch = dataset.select(range(start, min(start + 10000, len(dataset))))
        for offset, row in enumerate(batch):
            validate_row(row, start + offset)

    print(f"Loading tokenizer and base model: {args.model}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model)
    model.config.use_cache = False
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()

    target_modules = [name.strip() for name in args.target_modules.split(",") if name.strip()]
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=args.rank, lora_alpha=args.rank * 2,
        lora_dropout=0.05, target_modules=target_modules,
    ))
    model.print_trainable_parameters()

    def render(row):
        rendered = tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False)
        return {"text": rendered}

    dataset = dataset.map(render, desc="Rendering chat templates", load_from_cache_file=True)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=args.max_length)

    tokenized = dataset.map(
        tokenize, batched=True, batch_size=256, remove_columns=dataset.column_names,
        desc="Tokenizing training examples", load_from_cache_file=True,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    use_cuda = torch.cuda.is_available()
    training_args = TrainingArguments(
        output_dir=str(args.output / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        logging_steps=50,
        save_strategy="epoch",
        save_total_limit=2,
        report_to="none",
        fp16=use_cuda and not (torch.cuda.is_bf16_supported() if hasattr(torch.cuda, "is_bf16_supported") else False),
        bf16=use_cuda and (torch.cuda.is_bf16_supported() if hasattr(torch.cuda, "is_bf16_supported") else False),
        dataloader_pin_memory=use_cuda,
        optim="adamw_torch",
        gradient_checkpointing=args.gradient_checkpointing,
        gradient_checkpointing_kwargs={"use_reentrant": False} if args.gradient_checkpointing else None,
        save_safetensors=True,
    )
    trainer = Trainer(
        model=model, args=training_args, train_dataset=tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    print(f"Starting training: {len(tokenized):,} examples, {args.epochs} epoch(s)", flush=True)
    trainer.train()
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)

    if not (args.output / "adapter_config.json").is_file():
        raise SystemExit("Training ended but adapter_config.json is missing.")
    weights = list(args.output.glob("*.safetensors")) + list(args.output.glob("*.bin"))
    if not weights or not all(p.stat().st_size > 0 for p in weights):
        raise SystemExit("Adapter weights are missing or empty.")
    print(f"SUCCESS: LoRA adapter saved to {args.output}", flush=True)


if __name__ == "__main__":
    main()
