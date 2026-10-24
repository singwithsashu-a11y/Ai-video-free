# MJ AI model — actual build plan

## What this repository contains
- model/mj_ai_chat.py: runnable local chat program that loads an open-weight language model and optionally a trained MJ AI LoRA adapter.
- training/prepare_dataset.py: validates and normalizes JSONL examples.
- training/train_lora.py: trains a LoRA adapter on an existing causal language model.
- training/seed_data.jsonl: small starter examples for testing the pipeline.
- The website is a user interface, not the AI model itself.

## First target
Start with Qwen/Qwen2.5-0.5B-Instruct as a small replaceable base. Check the model card and license before use or redistribution. The base model provides general language capability; fine-tuning teaches MJ AI's style and task patterns. A handful of examples is only a smoke test, not enough to create a competitive assistant.

## Train on a compatible Linux machine or hosted notebook
1. Install Python and a compatible PyTorch build.
2. Install optional packages: pip install transformers datasets peft accelerate
3. Prepare examples: python training/prepare_dataset.py training/seed_data.jsonl training/seed_data.processed.jsonl
4. Fine-tune: python training/train_lora.py --model Qwen/Qwen2.5-0.5B-Instruct --data training/seed_data.processed.jsonl --output training/output/mj-ai-lora --epochs 3 --max-length 512
5. Run the fine-tuned model: python model/mj_ai_chat.py --model Qwen/Qwen2.5-0.5B-Instruct --adapter training/output/mj-ai-lora

Training downloads model weights and libraries. A GPU is strongly recommended. Free notebook sessions can disconnect or have quota limits; save the adapter to persistent storage.

## Honest status
The trained adapter, once training is run, will be MJ AI's first model-specific learned artifact. This repository has not yet trained or produced the adapter weights. It is not a new foundation model trained from zero. Quality depends on the base model, data, evaluation and compute.

## Multimodal roadmap
Chat, code and writing first; retrieval over user-approved documents next; then connect separate image, audio and video models through tools. Fine-tuning a text model alone does not automatically create image/audio/video generation.