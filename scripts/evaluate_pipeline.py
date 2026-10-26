"""Score the whole app pipeline against the model alone, on the CPU with the exported GGUF model.

    python scripts/evaluate_pipeline.py                       # matching study + Kinyarwanda test questions
    python scripts/evaluate_pipeline.py --lang all            # English test questions too
    python scripts/evaluate_pipeline.py --matching-only       # threshold study only (seconds, no model)

1. **Matching study** (``nutriassist.evaluation.pipeline``): chooses the similarity threshold for
   reviewed answers on the validation split and reports it on the test split.
2. **Model alone vs pipeline** on the test questions. *Model alone* is the safety rules plus the model
   answering directly, which is what the app did before. *Pipeline* adds reviewed answers (index of
   training pairs only, so no test answer can leak) and, for Kinyarwanda, translation through English.
   Both use the same GGUF model and the same metrics as the notebook.

Answers are saved as they are generated (``outputs/pipeline/*_answers.jsonl``), so an interrupted run
continues where it stopped. On a laptop CPU the translated route takes about 40 s per question.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nutriassist.api.settings import find_model_file  # noqa: E402
from nutriassist.assistant import NutritionAssistant  # noqa: E402
from nutriassist.evaluation import Evaluator, compare  # noqa: E402
from nutriassist.evaluation.pipeline import (PipelineChatModel, choose_threshold, knowledge_for,  # noqa: E402
                                             matching_study, threshold_table)
from nutriassist.training.dataset import QADataset  # noqa: E402

DATA = Path("data/QA_data/processed")
OUTPUT = Path("outputs/pipeline")


def run_matching_study(dataset: QADataset, output: Path) -> float:
    validation = threshold_table(matching_study("val", dataset.paraphrases))
    threshold = choose_threshold(validation)
    test = threshold_table(matching_study("test", dataset.paraphrases), [threshold])
    validation.to_csv(output / "matching_thresholds_val.csv", index=False)
    test.to_csv(output / "matching_test.csv", index=False)
    print(f"Threshold chosen on val: {threshold}")
    print(test.round(1).to_string(index=False))
    return threshold


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, default=None, help="GGUF file (default: the one in models/)")
    parser.add_argument("--lang", choices=["rw", "en", "all"], default="rw")
    parser.add_argument("--limit", type=int, default=None, help="only the first N test questions")
    parser.add_argument("--matching-only", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    dataset = QADataset.load(DATA)
    threshold = run_matching_study(dataset, args.output)
    if args.matching_only:
        return

    from nutriassist.inference.base import GenerationSettings
    from nutriassist.inference.llamacpp_model import LlamaCppChatModel
    from nutriassist.translation import NllbTranslator, TermAwareTranslator

    examples = [ex for ex in dataset.test if args.lang == "all" or ex.lang == args.lang][: args.limit]
    model = LlamaCppChatModel.from_file(args.model or find_model_file(), settings=GenerationSettings(batch_size=1))
    systems = {
        "model_alone": NutritionAssistant(model),
        "pipeline": NutritionAssistant(model, knowledge=knowledge_for("test", threshold=threshold),
                                       translator=TermAwareTranslator(NllbTranslator())),
    }
    evaluator, results = Evaluator(), {}
    for name, assistant in systems.items():
        system = PipelineChatModel(assistant, name)
        results[name] = evaluator.evaluate(system, examples, cache_path=args.output / f"{name}_test_answers.jsonl",
                                           chunk_size=4)
        results[name].save(args.output, f"{name}_test")
        if system.replies:  # empty when every answer came from the cache
            system.sources().value_counts().to_csv(args.output / f"{name}_sources.csv")

    comparison = compare(results["model_alone"], results["pipeline"])
    comparison = comparison.rename(columns={"base": "model_alone", "fine_tuned": "pipeline"})
    comparison.to_csv(args.output / "pipeline_vs_model.csv", index=False)
    table = comparison.pivot(index="metric", columns="group", values=["model_alone", "pipeline", "improvement_%"])
    print(table.round(1).to_string())

    side_by_side = results["model_alone"].predictions[["id", "lang", "category", "question", "reference", "prediction"]] \
        .rename(columns={"prediction": "model_alone"}) \
        .merge(results["pipeline"].predictions[["id", "prediction"]].rename(columns={"prediction": "pipeline"}), on="id")
    side_by_side.to_csv(args.output / "pipeline_answers_test.csv", index=False)
    print(f"Answers side by side: {args.output / 'pipeline_answers_test.csv'}")


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    main()
