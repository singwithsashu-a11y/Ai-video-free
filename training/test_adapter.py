"""Smoke-test a trained MJ AI LoRA adapter with held-out prompts.

This verifies loading and generation only; it is not a rigorous quality benchmark.
Install training/requirements-inference.txt and pass the extracted adapter folder.
"""
import argparse
from pathlib import Path


PROMPTS = [
    "Hinglish mein ek 3-scene sad music video storyboard likho. Har scene mein visual aur camera movement do.",
    "Create a concise FFmpeg command to burn an SRT subtitle file into an MP4 video.",
    "Mujhe ek short video ke liye 3 original caption ideas do.",
    "Landscape MP4 ko 9:16 Shorts mein reframe karne ka safe FFmpeg plan do.",
    "SRT subtitles burn karne aur audio fade-in/fade-out ke liye accurate workflow batao.",
    "FFmpeg render black screen de raha hai; pehle kaun se logs aur checks chahiye?",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", type=Path, default=Path("models/mj-ai-lora"))
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--max-new-tokens", type=int, default=160)
    args = parser.parse_args()

    if not (args.adapter / "adapter_config.json").is_file():
        raise SystemExit(
            f"Adapter not found at {args.adapter}. Extract the GitHub Actions artifact "
            "so adapter_config.json and adapter_model.safetensors are directly in this folder."
        )
    if args.max_new_tokens < 1 or args.max_new_tokens > 1024:
        raise SystemExit("--max-new-tokens must be between 1 and 1024.")

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "Missing inference packages. Run: pip install -r training/requirements-inference.txt"
        ) from exc

    print(f"Loading base model: {args.model}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model)
    model = PeftModel.from_pretrained(model, str(args.adapter))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()
    print(f"Loaded adapter on {device}. Running {len(PROMPTS)} smoke tests.\n", flush=True)

    failures = 0
    for index, prompt in enumerate(PROMPTS, 1):
        messages = [
            {
                "role": "system",
                "content": "You are MJ AI, a careful video-editing assistant. Give actionable and technically accurate steps, preserve source files, and state tool limitations.",
            },
            {"role": "user", "content": prompt},
        ]
        rendered = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(rendered, return_tensors="pt")
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        answer = tokenizer.decode(
            output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        ).strip()
        print(f"--- Test {index} ---\nPROMPT: {prompt}\nOUTPUT: {answer or '[EMPTY OUTPUT]'}\n")
        if not answer:
            failures += 1

    if failures:
        raise SystemExit(f"Smoke test failed: {failures} empty output(s). Review model quality manually.")
    print("Smoke test passed: all prompts produced non-empty output.")
    print("Note: non-empty output does not prove factual accuracy or high quality.")


if __name__ == "__main__":
    main()
