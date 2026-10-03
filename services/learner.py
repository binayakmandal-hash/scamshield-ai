"""A small classifier that learns from your feedback.

Algorithm: multinomial Naive Bayes with Laplace smoothing, written in plain
Python so the whole team can read it. It trains in milliseconds, so it
retrains every time you mark an email as scam or safe.

Training data, in increasing weight:
  seed examples (services/seed_data.py)        weight 1
  imported datasets (python train.py file.csv)  weight 1
  your own feedback from the inbox              weight 3  (you know your inbox best)

The learner never replaces the explainable signals. It adds one extra,
clearly labelled signal ("Similar to emails you marked as scam") to the score.
"""
import math
import random
import re
import threading
from collections import Counter

import database as db

from .seed_data import SEED_EXAMPLES

TOKEN_RE = re.compile(r"[a-z0-9ऀ-ॿঀ-৿]{2,}")
STOP = set("""
the and for you your are with this that have has was were will from our not but all can its it's out any
been they them their there here what when which who how about into more than then also just only into
a an of to in on at by is be as or if we us me my i it do does did so no yes please dear hi hello regards
""".split())
FEEDBACK_WEIGHT = 3
MIN_PER_CLASS = 3


def features(text: str, sender: str = "") -> list:
    t = (text or "").lower()
    feats = [w for w in TOKEN_RE.findall(t) if w not in STOP and not w.isdigit()]
    feats += [f"{a}_{b}" for a, b in zip(feats, feats[1:])][:400]  # word pairs like "share_otp"
    if re.search(r"https?://|www\.", t):
        feats.append("__has_link")
    if re.search(r"₹|\brs\.?\s?\d|\binr\b|\$\s?\d", t):
        feats.append("__money")
    if re.search(r"\b\d{6,}\b", t):
        feats.append("__long_number")
    if "!!" in t:
        feats.append("__exclaim")
    if sender and "@" in sender:
        domain = sender.lower().split("@", 1)[1]
        feats.append("__from:" + domain)
    return feats


class NaiveBayes:
    def __init__(self):
        self.word_counts = {0: Counter(), 1: Counter()}
        self.doc_counts = {0: 0.0, 1: 0.0}
        self.totals = {0: 0.0, 1: 0.0}

    def fit(self, examples):
        """examples: iterable of (feature_list, label, weight)."""
        for feats, label, weight in examples:
            self.doc_counts[label] += weight
            for f in feats:
                self.word_counts[label][f] += weight
                self.totals[label] += weight
        return self

    @property
    def vocab_size(self):
        return len(set(self.word_counts[0]) | set(self.word_counts[1]))

    def predict_proba(self, feats) -> float:
        """Probability that the text is a scam (0..1)."""
        if not self.doc_counts[0] or not self.doc_counts[1]:
            return 0.5
        v = self.vocab_size or 1
        n = self.doc_counts[0] + self.doc_counts[1]
        score = {c: math.log(self.doc_counts[c] / n) for c in (0, 1)}
        for f in feats:
            if f not in self.word_counts[0] and f not in self.word_counts[1]:
                continue  # unseen words carry no evidence
            for c in (0, 1):
                score[c] += math.log((self.word_counts[c][f] + 1) / (self.totals[c] + v))
        diff = max(-50.0, min(50.0, score[1] - score[0]))
        return 1 / (1 + math.exp(-diff))

    def top_words(self, feats, k=4):
        """Words in this text that pushed most toward 'scam' (for the explanation)."""
        v = self.vocab_size or 1
        ranked = []
        for f in set(feats):
            if f.startswith("__") or "_" in f:
                continue
            a = (self.word_counts[1][f] + 1) / (self.totals[1] + v)
            b = (self.word_counts[0][f] + 1) / (self.totals[0] + v)
            if self.word_counts[1][f] >= 1:
                ranked.append((math.log(a / b), f))
        return [w for s, w in sorted(ranked, reverse=True)[:k] if s > 0.5]

    def to_dict(self):
        return {"w0": dict(self.word_counts[0]), "w1": dict(self.word_counts[1]),
                "d": [self.doc_counts[0], self.doc_counts[1]], "t": [self.totals[0], self.totals[1]]}

    @classmethod
    def from_dict(cls, data):
        m = cls()
        m.word_counts = {0: Counter(data["w0"]), 1: Counter(data["w1"])}
        m.doc_counts = {0: data["d"][0], 1: data["d"][1]}
        m.totals = {0: data["t"][0], 1: data["t"][1]}
        return m


def _evaluate(rows, folds=5, seed=7):
    """Cross-validated accuracy, precision and recall for the scam class."""
    if len(rows) < 10:
        return None
    rows = rows[:]
    random.Random(seed).shuffle(rows)
    k = min(folds, len(rows))
    tp = fp = tn = fn = 0
    for i in range(k):
        test = rows[i::k]
        train = [r for j, r in enumerate(rows) if j % k != i]
        model = NaiveBayes().fit(train)
        for feats, label, _ in test:
            pred = 1 if model.predict_proba(feats) >= 0.5 else 0
            tp += pred == 1 and label == 1
            fp += pred == 1 and label == 0
            tn += pred == 0 and label == 0
            fn += pred == 0 and label == 1
    total = tp + fp + tn + fn
    return {
        "accuracy": round((tp + tn) / total, 3) if total else None,
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "evaluated_on": total,
    }


class Learner:
    def __init__(self, db_path: str, uid: str = db.LOCAL):
        self.db_path = db_path
        self.uid = uid
        self.lock = threading.Lock()
        self.model = None
        self.stats = {}
        saved = db.load_model(db_path, uid)
        if saved:
            self.model = NaiveBayes.from_dict(saved["model"])
            self.stats = saved.get("stats", {})
        else:
            self.retrain()

    def retrain(self) -> dict:
        rows = [(features(t), label, 1) for label, t in SEED_EXAMPLES]
        user_rows = []
        for ex in db.list_examples(self.db_path, self.uid):
            weight = FEEDBACK_WEIGHT if ex["source"] == "feedback" else 1
            row = (features(ex["text"], ex["sender"] or ""), ex["label"], weight)
            (user_rows if ex["source"] == "feedback" else rows).append(row)
        all_rows = rows + user_rows
        model = NaiveBayes().fit(all_rows)
        counts = db.example_counts(self.db_path, self.uid)
        stats = {
            "seed": len(SEED_EXAMPLES),
            "dataset": counts.get("dataset", {"scam": 0, "safe": 0}),
            "feedback": counts.get("feedback", {"scam": 0, "safe": 0}),
            "total_examples": len(all_rows),
            "vocabulary": model.vocab_size,
            "metrics": _evaluate(all_rows),
        }
        with self.lock:
            self.model, self.stats = model, stats
        db.save_model(self.db_path, {"model": model.to_dict(), "stats": stats}, self.uid)
        return stats

    @property
    def ready(self) -> bool:
        m = self.model
        return bool(m and m.doc_counts[0] >= MIN_PER_CLASS and m.doc_counts[1] >= MIN_PER_CLASS)

    def predict(self, text: str, sender: str = ""):
        """Returns (probability_of_scam, top_words) or (None, []) if not ready."""
        if not self.ready:
            return None, []
        feats = features(text, sender)
        with self.lock:
            return self.model.predict_proba(feats), self.model.top_words(feats)

    def status(self) -> dict:
        return {"ready": self.ready, **self.stats}
