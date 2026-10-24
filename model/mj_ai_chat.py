"""Run MJ AI with an open-weight base model and an optional MJ AI LoRA adapter."""
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="MJ AI local model chat")
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--adapter", default=None, help="Optional trained MJ AI LoRA adapter directory")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.7)
    args = parser.parse_args()
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit("Install: pip install torch transformers peft accelerate") from exc
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)
    kwargs = {"low_cpu_mem_usage": True}
    if torch.cuda.is_available():
        kwargs.update(torch_dtype=torch.float16, device_map="auto")
    else:
        kwargs["torch_dtype"] = torch.float32
    model = AutoModelForCausalLM.from_pretrained(args.model, **kwargs)
    if args.adapter:
        try:
            from peft import PeftModel
        except ImportError as exc:
            raise SystemExit("Adapter loading requires PEFT: pip install peft") from exc
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()
    device = next(model.parameters()).device
    messages = [{"role":"system","content":"You are MJ AI, a careful multilingual video-editing assistant. Help with clip timing, transitions, subtitles, audio, color, keyframes, masks, motion tracking, FFmpeg, export settings, storyboards and troubleshooting. Reply in the user language, preserve source files, give technically accurate steps, and never claim a tool ran unless it did. Text-model advice does not itself render or generate video."}]
    print("MJ AI ready. Type /exit to quit or /reset to clear chat.")
    while True:
        try: user_text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt): print("\nBye."); break
        if user_text == "/exit": break
        if user_text == "/reset": messages = messages[:1]; print("Conversation cleared."); continue
        if not user_text: continue
        messages.append({"role":"user","content":user_text})
        try:
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(rendered, return_tensors="pt").to(device)
            gen = {"max_new_tokens":max(1,min(args.max_new_tokens,2048)),"do_sample":args.temperature>0,"pad_token_id":tokenizer.eos_token_id}
            if args.temperature > 0: gen.update(temperature=args.temperature, top_p=0.9)
            with torch.inference_mode(): output = model.generate(**inputs, **gen)
            answer = tokenizer.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
            print("\nMJ AI: " + (answer or "[Empty model response]"))
            messages.append({"role":"assistant","content":answer})
            if len(messages) > 13: messages = [messages[0]] + messages[-12:]
        except Exception as exc:
            messages.pop(); print("Generation failed: " + str(exc), file=sys.stderr)

if __name__ == "__main__": main()