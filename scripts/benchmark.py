"""Measure NutriAssist-RW performance on this machine.

    python scripts/benchmark.py --model models/nutriassist-rw-q8_0.gguf --threads 1 2 4 8

For each CPU thread count (a stand-in for weaker and stronger machines) it loads the GGUF model,
answers the same English and Kinyarwanda questions, and records load time, answer time, generation
speed (tokens/s) and memory. It also times the API end to end: an urgent question (answered by the
safety rules), a model question, and 1-day and 7-day meal plans. Results are appended to
docs/performance.md with the machine's details, so runs on different computers can be compared.
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import sys
import time
from datetime import date
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nutriassist.inference.base import GenerationSettings  # noqa: E402
from nutriassist.inference.llamacpp_model import LlamaCppChatModel  # noqa: E402
from nutriassist.prompts import build_messages  # noqa: E402

QUESTIONS = [
    "What foods should I give my 8-month-old baby?",
    "How can I add more iron to my child's food using local foods?",
    "Umwana w'amezi 9 yarya iki?",
    "Ni ibihe biryo byongera amaraso ku mwana?",
]
REPORT = Path("docs/performance.md")


def machine() -> dict:
    memory = psutil.virtual_memory()
    return {
        "os": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "cores": f"{psutil.cpu_count(logical=False)} physical / {psutil.cpu_count()} logical",
        "ram_gb": round(memory.total / 2**30, 1),
        "python": platform.python_version(),
    }


def rss_gb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 2**30


def benchmark_model(path: Path, threads: int, max_new_tokens: int) -> dict:
    start = time.perf_counter()
    model = LlamaCppChatModel.from_file(path, threads=threads,
                                        settings=GenerationSettings(max_new_tokens=max_new_tokens, batch_size=1))
    load_s = time.perf_counter() - start
    model.generate(build_messages("Hello"))  # warm-up

    times, tokens = [], []
    for question in QUESTIONS:
        start = time.perf_counter()
        answer = model.generate(build_messages(question))
        times.append(time.perf_counter() - start)
        tokens.append(len(model.llama.tokenize(answer.encode("utf-8"), add_bos=False)))
    result = {
        "threads": threads,
        "load_s": round(load_s, 1),
        "median_answer_s": round(statistics.median(times), 1),
        "max_answer_s": round(max(times), 1),
        "tokens_per_s": round(sum(tokens) / sum(times), 1),
        "memory_gb": round(rss_gb(), 2),
    }
    del model
    return result


def benchmark_api(path: Path, threads: int, max_new_tokens: int) -> list[dict]:
    from fastapi.testclient import TestClient

    from nutriassist.api.app import create_app

    model = LlamaCppChatModel.from_file(path, threads=threads,
                                        settings=GenerationSettings(max_new_tokens=max_new_tokens, batch_size=1))
    cases = [
        ("POST /chat - danger sign (safety rules)", "/chat", {"question": "My child is having a seizure"}),
        ("POST /chat - feeding question (model)", "/chat", {"question": QUESTIONS[0]}),
        ("POST /meal-plan - 1 day", "/meal-plan", {"age_months": 12}),
        ("POST /meal-plan - 7 days", "/meal-plan", {"age_months": 12, "days": 7}),
        ("GET /foods", "/foods", None),
    ]
    rows = []
    with TestClient(create_app(model=model)) as client:
        for label, path_, body in cases:
            timings = []
            for _ in range(3 if "model" in label else 20):
                start = time.perf_counter()
                response = client.post(path_, json=body) if body is not None else client.get(path_)
                timings.append(1000 * (time.perf_counter() - start))
                response.raise_for_status()
            rows.append({"request": label, "median_ms": round(statistics.median(timings), 1),
                         "max_ms": round(max(timings), 1)})
    return rows


def table(rows: list[dict]) -> str:
    header = list(rows[0])
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(row[h]) for h in header) + " |" for row in rows]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", type=Path, default=Path("models/nutriassist-rw-q8_0.gguf"))
    parser.add_argument("--threads", type=int, nargs="+", default=[1, 2, 4, os.cpu_count()])
    parser.add_argument("--max-new-tokens", type=int, default=200)
    parser.add_argument("--label", default="", help="a name for this machine, e.g. 'my laptop'")
    args = parser.parse_args()

    info = machine()
    print(info)
    model_rows = []
    for threads in sorted(set(args.threads)):
        row = benchmark_model(args.model, threads, args.max_new_tokens)
        print(row)
        model_rows.append(row)
    api_rows = benchmark_api(args.model, max(args.threads), args.max_new_tokens)
    for row in api_rows:
        print(row)

    size_gb = args.model.stat().st_size / 2**30
    section = [
        f"## {args.label or info['os']} — {date.today().isoformat()}",
        "",
        f"- Model: `{args.model.name}` ({size_gb:.2f} GB), answers up to {args.max_new_tokens} tokens",
        *[f"- {key}: {value}" for key, value in info.items()],
        "",
        "### Model speed by CPU threads",
        "",
        table(model_rows),
        "",
        f"### API response times ({max(args.threads)} threads)",
        "",
        table(api_rows),
        "",
    ]
    REPORT.parent.mkdir(exist_ok=True)
    if not REPORT.exists():
        REPORT.write_text("# Performance measurements\n\nProduced by `scripts/benchmark.py`.\n\n", encoding="utf-8")
    with REPORT.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(section) + "\n")
    print(f"Appended to {REPORT}")


if __name__ == "__main__":
    main()
