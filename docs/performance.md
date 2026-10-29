# Performance measurements

Produced by `scripts/benchmark.py`.

## laptop: Intel i5-1135G7 (4 cores / 8 threads), 7.8 GB RAM, Windows 11 — 2026-10-29

- Model: `nutriassist-rw-q4_k_m.gguf` (0.92 GB), answers up to 200 tokens
- os: Windows-11-10.0.26300-SP0
- cpu: Intel64 Family 6 Model 140 Stepping 1, GenuineIntel
- cores: 4 physical / 8 logical
- ram_gb: 7.8
- python: 3.12.7

### Model speed by CPU threads

| threads | load_s | median_answer_s | max_answer_s | tokens_per_s | memory_gb |
|---|---|---|---|---|---|
| 1 | 4.2 | 12.7 | 27.3 | 7.7 | 1.56 |
| 2 | 2.1 | 11.5 | 18.9 | 9.5 | 1.36 |
| 4 | 1.7 | 8.1 | 13.9 | 13.4 | 1.54 |
| 8 | 1.5 | 8.3 | 12.8 | 13.6 | 1.58 |

### API response times (8 threads)

| request | median_ms | max_ms |
|---|---|---|
| POST /chat - danger sign (safety rules) | 3.5 | 14.3 |
| POST /chat - feeding question (model) | 7477.4 | 8156.3 |
| POST /meal-plan - 1 day | 6.0 | 11.5 |
| POST /meal-plan - 7 days | 7.5 | 9.0 |
| GET /foods | 3.3 | 4.9 |


## Online: Hugging Face ZeroGPU Space — 2026-10-29

- Space: https://huggingface.co/spaces/pauline-ish/nutriAssist_Rw (Gradio, ZeroGPU: half an NVIDIA RTX Pro 6000)
- Model: `unsloth/gemma-3-4b-it` + LoRA adapter (exp9), merged, bfloat16
- Measured from a laptop in Kigali through the Gradio client, so times include the network round trip

| request | questions | median_s | max_s |
|---|---|---|---|
| Model answer (Gemma-3-4B on GPU) | 6 | 4.6 | 11.6 |
| Reviewed answer (no GPU) | 3 | 2.2 | 2.2 |
| Safety rule (no GPU) | 3 | 2.1 | 2.1 |
| Meal plan, 7 days (no GPU) | 1 | 3.4 | 3.4 |

## Analysis

- **Low-end vs high-end hardware.** On the laptop CPU, the 1.5B model needs about 1.5 GB of RAM at every
  thread count, so it fits on an ordinary 8 GB laptop. One CPU thread (a stand-in for a weak machine)
  writes 7.7 tokens/s and gives a typical answer in 12.7 s; four threads reach 13.4 tokens/s (8.1 s).
  More threads than physical cores (8 vs 4) gain nothing, so the app uses one thread per core.
- **GPU vs CPU.** On the ZeroGPU Space, the 2.6× larger Gemma-3-4B answers in a median of 4.6 s
  including the network, about half the laptop time for a much larger model. The first answer after the
  Space starts is slower (11.6 s) while a GPU is attached.
- **Answers that skip the model are instant.** Safety-rule answers take 3.5 ms in the API and reviewed
  answers about the same; on the Space both take about 2.1 s, which is the network round trip alone. So
  the urgent danger-sign message never waits for the model or a GPU queue.
- **Meal planner.** A 7-day plan takes 7.5 ms in the API: the greedy planner is not a bottleneck.

## Compatibility

| Environment | How it was checked | Result |
|---|---|---|
| Linux, Windows, macOS (Python 3.12) and Linux (Python 3.10) | GitHub Actions runs the full test suite on each push (`.github/workflows/tests.yml`) | all pass |
| Windows 11 laptop, CPU only | Docker app and `scripts/benchmark.py` (above) | works; 8 s per model answer |
| Hugging Face ZeroGPU Space | live measurements (above) | works; 4.6 s per model answer |
| Browsers and phones | manual check of the Space: chat, language switch, 7-day plan | _fill in_ |

| Device | Operating system | Browser | Chat | Kinyarwanda switch | Meal plan | Notes |
|---|---|---|---|---|---|---|
| Laptop | Windows 11 | Chrome | | | | |
| Laptop | Windows 11 | Edge or Firefox | | | | |
| Phone | Android / iOS | Chrome / Safari | | | | |
