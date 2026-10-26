"""Answer from the reviewed question-answer pairs when a question matches one of them.

The fine-tuned model writes poor Kinyarwanda (see ``docs/kinyarwanda.md``), but every Kinyarwanda
answer in ``qa_master.jsonl`` was approved by a native speaker. When a caregiver's question asks the
same thing as a stored question (or one of its paraphrases), the stored answer is returned word for
word. Matching is per language, by character n-gram TF-IDF cosine similarity: it copes with
Kinyarwanda prefixes and suffixes and needs no download. A multilingual sentence embedding (LaBSE)
can be averaged in, but on the validation questions it matched Kinyarwanda rewordings less often than
characters alone, so the app leaves it off (``docs/kinyarwanda.md``).

Questions built from one template differ only in a food, an illness or an age ("Garama 100
z'ibijumba..." vs "Garama 100 z'ibirayi...", "cough" vs "fever"), so they score high although their
answers differ. A match is therefore accepted only when both questions name the same foods and
illnesses and no conflicting numbers (:class:`~nutriassist.terms.KeyTerms`).
Below the threshold the app does not guess: it offers the closest reviewed questions as "Did you
mean...?" suggestions (:meth:`KnowledgeBase.suggest`), and the caregiver picks one. The threshold is
chosen on the validation split by ``scripts/evaluate_pipeline.py``.

Besides each pair's question and paraphrases, the index holds extra wordings approved in the wording
review (``nutriassist.qa_data.wording_review``). They make matching recognise more ways of asking;
they are not used for training, so the training data and its evaluation do not change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Sequence

import numpy as np

from .terms import FOOD_NAMES, KeyTerms

QA_MASTER = Path("data/QA_data/processed/qa_master.jsonl")
EXTRA_WORDINGS = Path("data/QA_data/processed/extra_wordings.jsonl")   # approved in the wording review
DEFAULT_THRESHOLD = 0.75     # chosen on the validation split by scripts/evaluate_pipeline.py
EMBEDDING_MODEL = "sentence-transformers/LaBSE"


@dataclass(frozen=True)
class ReviewedPair:
    id: str
    lang: str
    category: str
    question: str
    answer: str


@dataclass(frozen=True)
class Match:
    pair: ReviewedPair
    matched_question: str      # the stored wording that matched: the question or one of its paraphrases
    score: float               # 0-1

    def is_confident(self, threshold: float) -> bool:
        return self.score >= threshold


class Embedder(Protocol):
    def __call__(self, texts: Sequence[str]) -> np.ndarray:
        """One L2-normalised row per text."""


class SentenceEmbedder:
    """LaBSE sentence embeddings (needs ``sentence-transformers``; about 1.8 GB on first use)."""

    def __init__(self, model_name: str = EMBEDDING_MODEL, device: str = "cpu") -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device=device)

    def __call__(self, texts: Sequence[str]) -> np.ndarray:
        return self.model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)


def load_extra_wordings(path: str | Path | None = EXTRA_WORDINGS) -> dict[str, list[str]]:
    """Approved extra wordings per pair id (none when the file does not exist yet)."""
    if path is None or not Path(path).exists():
        return {}
    wordings: dict[str, list[str]] = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            wordings.setdefault(row["id"], []).extend(row["wordings"])
    return wordings


def load_pairs(path: str | Path = QA_MASTER, splits: Iterable[str] | None = None,
               paraphrase_splits: Iterable[str] | None = None,
               extra_wordings: str | Path | None = EXTRA_WORDINGS) -> list[tuple[ReviewedPair, list[str]]]:
    """Reviewed pairs with the wordings to index for each.

    ``splits`` limits which pairs are loaded (all by default). Paraphrases are indexed only for pairs
    in ``paraphrase_splits`` (all by default): evaluation leaves out the val/test paraphrases, because
    they are the held-out questions it asks. An extra wording that repeats a left-out paraphrase is
    left out too.
    """
    splits = set(splits) if splits is not None else None
    paraphrase_splits = set(paraphrase_splits) if paraphrase_splits is not None else None
    extra = load_extra_wordings(extra_wordings)
    pairs = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if splits is not None and row["split"] not in splits:
                continue
            pair = ReviewedPair(row["id"], row["lang"], row["category"], row["question"], row["answer"])
            paraphrases = row.get("paraphrases") or []
            wordings = [row["question"]]
            if paraphrase_splits is None or row["split"] in paraphrase_splits:
                wordings += paraphrases
                held_out = set()
            else:
                held_out = {p.strip().lower() for p in paraphrases}
            wordings += [w for w in extra.get(row["id"], []) if w.strip().lower() not in held_out]
            pairs.append((pair, list(dict.fromkeys(wordings))))
    return pairs


class _LanguageIndex:
    """The stored wordings of one language, as TF-IDF vectors and (optionally) embeddings."""

    def __init__(self, entries: list[tuple[ReviewedPair, str]], embedder: Embedder | None) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.entries = entries
        texts = [wording for _, wording in entries]
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, lowercase=True)
        self.tfidf = self.vectorizer.fit_transform(texts)
        self.embedder = embedder
        self.embeddings = embedder(texts) if embedder is not None else None

    def scores(self, question: str) -> np.ndarray:
        """Similarity of ``question`` to every stored wording (0-1)."""
        tfidf = (self.vectorizer.transform([question]) @ self.tfidf.T).toarray()[0]
        if self.embeddings is None:
            return tfidf
        embedding = self.embeddings @ self.embedder([question])[0]
        return (tfidf + np.clip(embedding, 0, 1)) / 2


class KnowledgeBase:
    """Finds the reviewed pair whose question best matches a caregiver's question."""

    def __init__(self, pairs: Sequence[tuple[ReviewedPair, Sequence[str]]], embedder: Embedder | None = None,
                 threshold: float = DEFAULT_THRESHOLD, key_terms: KeyTerms | None = None) -> None:
        self.threshold = threshold
        self.key_terms = key_terms
        by_language: dict[str, list[tuple[ReviewedPair, str]]] = {}
        for pair, wordings in pairs:
            by_language.setdefault(pair.lang, []).extend((pair, wording) for wording in wordings)
        self._indexes = {lang: _LanguageIndex(entries, embedder) for lang, entries in by_language.items()}

    @classmethod
    def load(cls, path: str | Path = QA_MASTER, embedder: Embedder | None = None,
             threshold: float = DEFAULT_THRESHOLD, food_names: str | Path | None = FOOD_NAMES,
             **filters) -> "KnowledgeBase":
        key_terms = KeyTerms.load(food_names) if food_names is not None else None
        return cls(load_pairs(path, **filters), embedder, threshold, key_terms)

    def __len__(self) -> int:
        return sum(len({pair.id for pair, _ in index.entries}) for index in self._indexes.values())

    def best(self, question: str, lang: str) -> Match | None:
        """The closest stored question in ``lang`` that names the same foods, illnesses and numbers, however weak the match."""
        index = self._indexes.get(lang)
        if index is None:
            return None
        scores = index.scores(question)
        wanted = self.key_terms(question) if self.key_terms else None
        for i in np.argsort(-scores):
            pair, wording = index.entries[i]
            if wanted is None or self.key_terms(wording).agrees_with(wanted):
                return Match(pair, wording, float(scores[i]))
        return None

    def find(self, question: str, lang: str) -> Match | None:
        """The closest stored question if it scores at least the threshold, else ``None``."""
        match = self.best(question, lang)
        return match if match is not None and match.is_confident(self.threshold) else None

    def suggest(self, question: str, lang: str, k: int = 3, min_score: float = 0.25) -> list[Match]:
        """Up to ``k`` different reviewed pairs to offer as "Did you mean...?", best first.

        Questions on exactly the same foods and illnesses come first. A suggestion never brings in a
        food or illness the question does not name, and weak matches
        (below ``min_score``, e.g. sharing only "Ni ryari...") are never offered. The caregiver judges
        whether a suggestion fits, so this floor is lower than the threshold for answering directly.
        """
        index = self._indexes.get(lang)
        if index is None:
            return []
        scores = index.scores(question)
        wanted = self.key_terms(question) if self.key_terms else None
        ranked = [i for i in np.argsort(-scores) if scores[i] >= min_score]
        if wanted is not None:
            terms = {i: self.key_terms(index.entries[i][1]) for i in ranked}
            ranked = [i for i in ranked if terms[i].fits_within(wanted)]
            ranked.sort(key=lambda i: not terms[i].agrees_with(wanted))  # same foods first; stable, so by score
        suggestions: list[Match] = []
        for i in ranked:
            pair, wording = index.entries[i]
            if all(pair.id != s.pair.id for s in suggestions):
                suggestions.append(Match(pair, wording, float(scores[i])))
            if len(suggestions) == k:
                break
        return suggestions
