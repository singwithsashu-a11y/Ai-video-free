# MJ AI — video-editing specialist model plan

## Target base model

The upgraded training workflow now defaults to **Qwen/Qwen2.5-1.5B-Instruct** (approximately 1.5 billion parameters, larger than the previous 0.5B target). It is a general instruct language model fine-tuned with LoRA for MJ AI's video-editing workflow. Check the exact Hugging Face model card and license before use.

**Compatibility rule:** a LoRA adapter must be loaded with the exact base model it was trained on. The old Qwen2.5-0.5B adapter is not interchangeable with a new 1.5B adapter. Set `MJ_AI_BASE_MODEL=Qwen/Qwen2.5-1.5B-Instruct` only after placing a newly trained matching adapter at `MJ_AI_ADAPTER_PATH`.

## What the editing examples cover

- Trimming, splitting, reframing, aspect ratios and batch workflows.
- SRT subtitles, timing offsets, captions and accessibility.
- Voice/music mixing, fades, beat-sync and audio checks.
- Transitions, speed ramps, keyframes, stabilization and motion tracking.
- Masks, green screen, background blur and compositing.
- Color correction, color-space metadata, codecs, pixel formats and export settings.
- FFmpeg diagnostics, render failures, proxy workflows, image sequences and GIFs.
- Storyboards, character continuity, editing-plan JSON, safety and honest tool limitations.

The reviewed domain dataset is `training/video_editing_skill_data.jsonl`; the training workflow combines it with `training/seed_data.jsonl`. These examples teach language patterns and editing knowledge, not new physical abilities by themselves.

## Train

The workflow is manually triggered at GitHub Actions → **MJ AI Video Editing Model Training**. It downloads the selected base model, validates and combines the two JSONL files, fine-tunes a LoRA adapter, verifies the output and uploads an artifact.

The standard GitHub-hosted runner is CPU-only and may run out of RAM or exceed its time limit with a 1.5B model. For reliable training, use a GPU-enabled hosted notebook or server with adequate VRAM, and save the adapter artifact to persistent storage. Do not assume training completed until the workflow reports success and the artifact exists.

Equivalent local commands on a compatible machine:

```bash
cat training/seed_data.jsonl training/video_editing_skill_data.jsonl > /tmp/mj-ai-all.jsonl
python training/prepare_dataset.py /tmp/mj-ai-all.jsonl /tmp/mj-ai-processed.jsonl
python training/train_lora.py --model Qwen/Qwen2.5-1.5B-Instruct --data /tmp/mj-ai-processed.jsonl --output training/output/mj-ai-lora --epochs 1 --max-length 512 --rank 8 --gradient-checkpointing
python training/test_adapter.py --adapter training/output/mj-ai-lora --model Qwen/Qwen2.5-1.5B-Instruct
```

Install a compatible PyTorch build plus `transformers datasets peft accelerate safetensors`. GPU is strongly recommended.

## Important capability boundary

LoRA fine-tuning teaches the model how to explain, plan and troubleshoot editing tasks. It does not give a text model the ability to directly modify video pixels, perform real motion tracking, generate new video, or run FFmpeg unless the app connects those tools. The existing editor renders uploaded clips through FFmpeg; generative text-to-video/image-to-video is a separate integration.

## Quality standard

The current domain file contains a small curated starter set, not a massive professional dataset. Add licensed, reviewed examples and a separate held-out evaluation set over time. Compare base and fine-tuned answers for correctness, reproducibility, safe file handling, and quality. A non-empty answer or low training loss is not proof of expertise.
