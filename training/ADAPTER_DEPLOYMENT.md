# Deploy the trained MJ AI adapter

The LoRA adapter is not a standalone model. It must be loaded with the same base model used for training (`Qwen/Qwen2.5-0.5B-Instruct` by default). The successful starter run used a tiny seed dataset, so treat this as an integration test and evaluate responses before relying on it.

## 1. Download and extract the artifact

Download the `mj-ai-lora-adapter` artifact from the successful GitHub Actions training run before its 14-day expiry. Extract the ZIP on the backend host so the directory contains `adapter_config.json`, `adapter_model.safetensors`, `tokenizer.json`, and related files. Do not commit model weights to Git.

Recommended location from the repository root: `models/mj-ai-lora/`.

## 2. Install optional inference dependencies

Use a Python environment compatible with the backend and install a PyTorch build appropriate for your CPU/GPU, then run:

```bash
pip install -r training/requirements-inference.txt
```

The default requirements use the installed PyTorch package from pip; for CUDA, follow the official PyTorch installation selector to install a compatible CUDA build first. The base model is downloaded from Hugging Face on first use unless already cached.

## 3. Configure the backend

Set these environment variables in the backend environment (not in frontend JavaScript):

```env
MJ_AI_ADAPTER_PATH=models/mj-ai-lora
MJ_AI_BASE_MODEL=Qwen/Qwen2.5-0.5B-Instruct
```

Paths are resolved relative to the backend process working directory when supplied as relative paths. Start/restart the FastAPI backend after setting the variables.

## 4. Use it

In the website's **AI creative assistant**, choose **MJ AI Fine-tuned Adapter**. You can also send a chat request to `POST /api/mj-ai/chat` with `provider: "adapter"`. Check `GET /api/mj-ai/status`; `adapter.configured` is true when the adapter config file is present.

## Troubleshooting and limitations

- `Adapter config not found`: verify the extracted folder and `MJ_AI_ADAPTER_PATH`.
- Missing dependencies: install `training/requirements-inference.txt` in the same Python environment as the backend.
- Memory errors or slow CPU inference: use a host with more RAM or a compatible GPU. Shared hosting may not support this workload.
- Adapter/base-model mismatch can cause loading errors or poor outputs. Use the same base model as training.
- The initial training dataset is only a handful of examples. A green workflow means training and artifact packaging succeeded, not that the model is high quality. Build a larger lawful dataset and compare against held-out test prompts before production use.
- Keep model weights out of public web directories, do not expose the model service without authentication/rate limits, and check all relevant model licences.
