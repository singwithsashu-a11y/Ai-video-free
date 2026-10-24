# MJ AI training lab (free software, hardware-dependent)

This folder is an honest starting point for customizing an existing open-weight language model. It does **not** create a ChatGPT-class foundation model from scratch. Fine-tuning changes model behavior on examples; it does not guarantee new general capabilities.

## Recommended path
1. Pick a model whose license fits your use. Check the exact model card/license before downloading or redistributing it.
2. Gather examples you own or have permission to use. Remove passwords, private messages, personal identifiers, and copyrighted material you cannot use.
3. Prepare one JSON object per line, either:
   - `{"messages":[{"role":"user","content":"..."} ,{"role":"assistant","content":"..."}]}`
   - or `{"prompt":"...","completion":"..."}`
4. Validate/normalize:
   `python training/prepare_dataset.py data/raw.jsonl data/processed.jsonl`
5. On a compatible Linux machine with adequate RAM/VRAM, install a tested PyTorch build plus:
   `pip install transformers datasets peft accelerate`
6. Run a small experiment first:
   `python training/train_lora.py --model YOUR_MODEL_ID_OR_LOCAL_PATH --data data/processed.jsonl --output training/output/mj-ai-lora --epochs 1`
7. Keep a held-out test set and compare before/after results. Never overwrite the base model; save adapters separately.

## Device choices
- **Android only:** use a hosted notebook/remote machine if available, or connect to a model server you control. Training a useful LLM directly on a phone is generally impractical.
- **Laptop/PC:** smaller quantized models may run locally; LoRA training needs more memory than inference.
- **Cloud GPU/server:** suitable for fine-tuning when you have a GPU allocation. Free tiers can be limited or unavailable; monitor quotas and cost.
- **Shared hosting / GitHub Pages:** can host the UI, but cannot usually run a large model or GPU training job.

## Safety, privacy, and reliability
This is a starter training script, not a one-click production trainer. Verify the base model supports the tokenizer chat template and LoRA target modules; hardware/model compatibility varies. Back up data, test outputs, follow licenses, and don't train on private data without consent. No system can honestly promise zero restrictions or perfect answers.
