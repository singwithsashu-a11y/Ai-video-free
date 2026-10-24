"""Optional LoRA fine-tuning starter for a compatible Hugging Face causal LM.

Install optional packages separately as described in training/README.md.
This trains model adapters, not a new foundation model from scratch.
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
    args = parser.parse_args()

    try:
        from datasets import Dataset
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments, DataCollatorForLanguageModeling
    except ImportError as exc:
        raise SystemExit("Missing optional training packages. Follow training/README.md to install them.") from exc

    rows = [json.loads(line) for line in args.data.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise SystemExit("Training dataset is empty.")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model)
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=8, lora_alpha=16, lora_dropout=0.05,
        target_modules="all-linear",
    ))

    def render(row):
        text = tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False)
        return {"text": text}

    dataset = Dataset.from_list(rows).map(render)
    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=args.max_length)
    tokenized = dataset.map(tokenize, batched=True, remove_columns=dataset.column_names)
    args.output.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=str(args.output), num_train_epochs=args.epochs,
        per_device_train_batch_size=1, gradient_accumulation_steps=8,
        learning_rate=2e-4, logging_steps=10, save_strategy="epoch",
        report_to="none", fp16=False,
    )
    trainer = Trainer(model=model, args=training_args, train_dataset=tokenized,
                      data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False))
    trainer.train()
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    print(f"LoRA adapter saved to {args.output}. Test quality and licensing before deployment.")


if __name__ == "__main__":
    main()
