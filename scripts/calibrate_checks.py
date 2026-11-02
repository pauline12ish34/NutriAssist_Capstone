"""Choose the thresholds of the answer checks from the reviewed data. No model and no Gemini calls: LaBSE only.

    python scripts/calibrate_checks.py

1. **Scope** (``RelevanceChecker.in_scope``): held-out val/test questions (in scope) against the training
   questions, and a list of questions the app is not for (``OUT_OF_SCOPE``). The threshold keeps 95%
   of the in-scope questions.
2. **Answer relevance** (``RelevanceChecker.on_topic``): each question with its own reviewed answer (on
   topic) and with the answer of a question from another category (off topic). The threshold keeps 95%
   of the right answers. Wrong-category answers are a stand-in for the model answering the wrong question.
3. **Topic rules** (``TopicRules``, meaning part): rewordings that must trigger the tea and honey rules
   (``REWORDINGS``, not used as the rules' examples) against every other reviewed question, none of which
   may trigger them. The threshold is the lowest with no false trigger.

Writes ``outputs/checks/calibration.md``.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nutriassist.knowledge import QA_MASTER, SentenceEmbedder  # noqa: E402
from nutriassist.safety.topics import CHILD, RULES  # noqa: E402

OUT = Path("outputs/checks")
KEEP = 0.95

# Questions the app is not for. NEEDS REVIEW: the Kinyarwanda ones were drafted by Claude.
OUT_OF_SCOPE = [
    "How do I fix my phone screen?", "Who won the football match yesterday?", "What is the capital of Kenya?",
    "How do I apply for a driving licence?", "What is the price of fuel today?", "Write me a love poem.",
    "How do I install Windows on my laptop?", "What medicine treats high blood pressure in adults?",
    "How can I make money online?", "When is the next election?", "How do I grow tomatoes in my garden?",
    "What is the best smartphone to buy?", "Tell me a joke.", "How do I open a bank account?",
    "Telefoni yanjye yapfuye, nayikora nte?", "Ni nde watsinze umukino w'umupira ejo?",
    "Umurwa mukuru wa Kenya ni uwuhe?", "Nabona nte uruhushya rwo gutwara imodoka?",
    "Lisansi igura angahe uyu munsi?", "Nkwandikire umuvugo w'urukundo.", "Nashaka amafaranga nte kuri interineti?",
    "Amatora ataha azaba ryari?", "Nahinga nte inyanya mu murima wanjye?", "Mbwira urwenya.",
    "Nafungura nte konti muri banki?", "Ni iyihe telefoni nziza yo kugura?",
]

# Rewordings that must trigger a rule (not in the rules' own examples). NEEDS REVIEW: Kinyarwanda by Claude.
REWORDINGS = {
    "tea": ["Uruhinja rwanjye rwanywa icyai?", "Umwana w'umwaka umwe yahabwa chai?",
            "Ese nshobora guha akana kanjye icyayi?", "Can my little one have a cup of tea?",
            "Is black tea safe for babies?", "Umwana wanjye w'amezi 7 ashobora kunywa icyayi kirimo amata?",
            "Should children under two drink tea?", "Abana bato bemerewe kunywa icyayi?"],
    "honey": ["Can I put honey in my 5 month old's porridge?", "Is a little honey ok for a newborn?",
              "Umwana w'amezi 6 yarya ubuki?", "Uruhinja rwahabwa ubuki ngo rukire inkorora?",
              "Is it true honey helps babies sleep?", "Nshobora gushyira ubuki mu mata y'umwana?"],
}


def rows() -> list[dict]:
    with QA_MASTER.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def keep_threshold(scores: np.ndarray, keep: float = KEEP) -> float:
    """The threshold that keeps ``keep`` of these (good) scores."""
    return float(np.quantile(scores, 1 - keep))


def main() -> None:
    data, embed = rows(), SentenceEmbedder()
    train = [r for r in data if r["split"] == "train"]
    held_out = [r for r in data if r["split"] != "train"]
    report = ["# Calibration of the answer checks", "", "Produced by `scripts/calibrate_checks.py` (LaBSE only).", ""]

    # 1. Scope
    index = embed([r["question"] for r in train])
    in_scope = np.max(embed([r["question"] for r in held_out]) @ index.T, axis=1)
    off_scope = np.max(embed(OUT_OF_SCOPE) @ index.T, axis=1)
    scope = keep_threshold(in_scope)
    report += ["## 1. Scope", "", f"- threshold **{scope:.2f}** keeps {100 * np.mean(in_scope >= scope):.0f}% of "
               f"{len(in_scope)} held-out reviewed questions",
               f"- it declines {100 * np.mean(off_scope < scope):.0f}% of {len(OUT_OF_SCOPE)} out-of-scope questions",
               f"- out-of-scope scores: max {off_scope.max():.2f}, mean {off_scope.mean():.2f}; "
               f"in-scope mean {in_scope.mean():.2f}", ""]

    # 2. Answer relevance
    rng = random.Random(0)
    questions = embed([r["question"] for r in data])
    answers = embed([r["answer"] for r in data])
    right = np.sum(questions * answers, axis=1)
    by_category: dict[tuple[str, str], list[int]] = {}
    for i, r in enumerate(data):
        by_category.setdefault((r["lang"], r["category"]), []).append(i)
    wrong_other, wrong_same = [], []
    for i, r in enumerate(data):
        others = [j for (lang, cat), js in by_category.items() if lang == r["lang"] and cat != r["category"] for j in js]
        same = [j for j in by_category[(r["lang"], r["category"])] if j != i]
        wrong_other.append(float(questions[i] @ answers[rng.choice(others)]))
        if same:
            wrong_same.append(float(questions[i] @ answers[rng.choice(same)]))
    wrong_other, wrong_same = np.array(wrong_other), np.array(wrong_same)
    answer = keep_threshold(right)
    report += ["## 2. Answer relevance", "",
               f"- threshold **{answer:.2f}** keeps {100 * np.mean(right >= answer):.0f}% of {len(right)} right answers",
               f"- it blocks {100 * np.mean(wrong_other < answer):.0f}% of answers from another category",
               f"- it blocks {100 * np.mean(wrong_same < answer):.0f}% of answers to another question of the same "
               "category (hard: same topic area)", ""]
    for lang in ("en", "rw"):
        mask = np.array([r["lang"] == lang for r in data])
        report.append(f"- {lang}: keeps {100 * np.mean(right[mask] >= answer):.0f}% right, blocks "
                      f"{100 * np.mean(wrong_other[mask] < answer):.0f}% other-category")
    report.append("")

    # 3. Topic rules (meaning part)
    report += ["## 3. Topic rules (meaning)", ""]
    for rule in RULES:
        examples = embed(list(rule.examples))
        must = np.max(embed(REWORDINGS[rule.key]) @ examples.T, axis=1)
        others = [r["question"] for r in data if not rule.keywords.search(r["question"])
                  and (not rule.child_only or CHILD.search(r["question"]))]
        must_not = np.max(embed(others) @ examples.T, axis=1)
        threshold = float(np.ceil(must_not.max() * 100) / 100)   # just above the closest other question
        caught = [w for w, s in zip(REWORDINGS[rule.key], must)
                  if rule.keywords.search(w) or s >= threshold]
        report += [f"### {rule.key}", "", f"- lowest threshold with no false trigger on {len(others)} other "
                   f"reviewed questions: **{threshold:.2f}**",
                   f"- keywords or meaning catch {len(caught)} of {len(must)} rewordings "
                   f"(keywords alone: {sum(bool(rule.keywords.search(w)) for w in REWORDINGS[rule.key])})",
                   f"- missed: {[w for w in REWORDINGS[rule.key] if w not in caught]}", ""]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "calibration.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
