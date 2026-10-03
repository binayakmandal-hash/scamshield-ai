"""Train ScamShield's learner on a labelled dataset (CSV).

Usage:
    python train.py path/to/dataset.csv                 # auto-detects the columns
    python train.py data.csv --text "Email Text" --label "Email Type"
    python train.py data.csv --limit 5000               # use a random sample
    python train.py --reset-dataset                     # remove all imported examples

Works with common public datasets, for example:
  * Phishing Email Dataset (Kaggle):  columns "Email Text", "Email Type" (Phishing Email / Safe Email)
  * SMS Spam Collection (UCI/Kaggle): columns "v1" (ham/spam), "v2" (text)
  * Any CSV with a text column and a label column (1/0, spam/ham, phishing/safe, scam/legit ...)

Your own feedback from the inbox always counts 3x more than dataset rows.
"""
import argparse
import csv
import random
import sys

import database as db
from config import Config
from services.learner import Learner

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

TEXT_NAMES = ["text", "email text", "message", "body", "content", "email", "v2", "sms", "mail"]
LABEL_NAMES = ["label", "email type", "class", "category", "type", "v1", "target", "is_spam", "spam"]
SCAM_WORDS = {"1", "spam", "phishing", "phishing email", "scam", "fraud", "smishing", "malicious", "true", "yes"}
SAFE_WORDS = {"0", "ham", "safe", "safe email", "legit", "legitimate", "normal", "false", "no", "not spam"}


def _pick(headers, wanted, explicit):
    if explicit:
        if explicit not in headers:
            sys.exit(f"Column '{explicit}' not found. Columns are: {', '.join(headers)}")
        return explicit
    lower = {h.lower().strip(): h for h in headers}
    for name in wanted:
        if name in lower:
            return lower[name]
    sys.exit(f"Couldn't guess the column. Use --text/--label. Columns are: {', '.join(headers)}")


def load_rows(path, text_col=None, label_col=None):
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        t, l = _pick(headers, TEXT_NAMES, text_col), _pick(headers, LABEL_NAMES, label_col)
        rows, skipped = [], 0
        for row in reader:
            text, raw = (row.get(t) or "").strip(), (row.get(l) or "").strip().lower()
            if raw in SCAM_WORDS:
                label = 1
            elif raw in SAFE_WORDS:
                label = 0
            else:
                skipped += 1
                continue
            if len(text) >= 10:
                rows.append((label, text[:5000]))
    return rows, skipped, (t, l)


def main():
    parser = argparse.ArgumentParser(description="Train ScamShield's learner on a CSV dataset.")
    parser.add_argument("csv", nargs="?", help="path to the CSV file")
    parser.add_argument("--text", help="name of the text column")
    parser.add_argument("--label", help="name of the label column")
    parser.add_argument("--limit", type=int, default=20000, help="max rows to import (default 20000)")
    parser.add_argument("--reset-dataset", action="store_true", help="remove previously imported dataset rows")
    args = parser.parse_args()

    db.init_db(Config.DATABASE_PATH)
    if args.reset_dataset:
        db.clear_examples(Config.DATABASE_PATH, "dataset")
        db.clear_models(Config.DATABASE_PATH)
        print("Removed imported dataset examples.")
    if args.csv:
        rows, skipped, cols = load_rows(args.csv, args.text, args.label)
        if len(rows) > args.limit:
            random.Random(42).shuffle(rows)
            rows = rows[: args.limit]
        scam = sum(1 for label, _ in rows if label)
        print(f"Using columns text='{cols[0]}', label='{cols[1]}'.")
        print(f"Importing {len(rows)} rows ({scam} scam, {len(rows) - scam} safe); skipped {skipped} unrecognised labels.")
        db.add_examples_bulk(Config.DATABASE_PATH, rows, "dataset")
    elif not args.reset_dataset:
        parser.print_help()
        return

    print("Training...")
    db.clear_models(Config.DATABASE_PATH)  # every user's model retrains with the new data
    stats = Learner(Config.DATABASE_PATH).retrain()
    m = stats.get("metrics") or {}
    print(f"Trained on {stats['total_examples']} examples, vocabulary {stats['vocabulary']} words.")
    if m:
        print(f"Cross-validated accuracy {m['accuracy']:.1%}, precision {m['precision'] or 0:.1%}, "
              f"recall {m['recall'] or 0:.1%} (on {m['evaluated_on']} examples).")
    print("Restart app.py to use the new model.")


if __name__ == "__main__":
    main()
