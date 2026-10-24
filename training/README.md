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


## Smoke-test a completed adapter

After extracting a GitHub Actions adapter artifact so the adapter files are directly inside `models/mj-ai-lora/`, install inference dependencies and run:

~~~bash
pip install -r training/requirements-inference.txt
python training/test_adapter.py --adapter models/mj-ai-lora --model Qwen/Qwen2.5-0.5B-Instruct
~~~

The script runs three fixed prompts covering Hinglish storyboarding, FFmpeg subtitles, and short-video captions. It reports the generated answers and fails if any answer is empty. **This is only a load/generation smoke test**, not a benchmark of factuality, instruction-following, or overall quality. Review outputs manually and compare against the unmodified base model before deployment.

## Latest small training run

The GitHub Actions run [40051547131](https://github.com/singwithsashu-a11y/Ai-video-free/actions/runs/40051547131) completed successfully. Its logs show 64 validated examples and 2 epochs, with an adapter artifact uploaded. This verifies that training and artifact export ran; it does not mean the model was trained on one million examples or that its quality is production-ready. The adapter requires the matching `Qwen/Qwen2.5-0.5B-Instruct` base model.
