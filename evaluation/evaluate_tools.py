"""Measure the rule-based safety tools on the hand-written cases in tool_cases.py.

Run from the repo root:  python -m evaluation.evaluate_tools
"""
from collections import Counter

from services import call_tactics, rule_engine, scam_scripts, upi_check
from services.schema import normalize_analysis
from services.sender_analyzer import analyze_sender
from services.url_analyzer import analyze_urls

from . import tool_cases as cases


def pct(n, d):
    return f"{(100 * n / d):.0f}%" if d else "n/a"


def chats(CHATS):
    print(f"\nChat check: {len(CHATS)} chats ({sum(1 for l, _ in CHATS if l != 'none')} scam, "
          f"{sum(1 for l, _ in CHATS if l == 'none')} normal)")
    tp = fp = fn = tn = right_script = 0
    misses = []
    for label, chat in CHATS:
        r = scam_scripts.track(chat)
        predicted = r["script"]["id"] if r.get("matched") else "none"
        if label != "none" and predicted != "none":
            tp += 1
            right_script += predicted == label
        elif label != "none":
            fn += 1
        elif predicted != "none":
            fp += 1
        else:
            tn += 1
        if predicted != label:
            misses.append((label, predicted, chat.splitlines()[0][:70]))
    scams = tp + fn
    print(f"  Scam chats flagged (recall):        {tp}/{scams} = {pct(tp, scams)}")
    print(f"  Right script when flagged:          {right_script}/{tp} = {pct(right_script, tp)}")
    print(f"  Normal chats wrongly flagged:       {fp}/{fp + tn} = {pct(fp, fp + tn)}")
    print(f"  Exact label accuracy (incl. none):  {len(CHATS) - len(misses)}/{len(CHATS)} = {pct(len(CHATS) - len(misses), len(CHATS))}")
    for m in misses:
        print(f"    miss: expected {m[0]:<15} got {m[1]:<15} | {m[2]}")


def upi(UPI):
    print(f"\nUPI check: {len(UPI)} messages")
    confusion = Counter()
    misses = []
    for label, text in UPI:
        verdict = upi_check.check(text)["verdict"]
        confusion[(label, verdict)] += 1
        if verdict != label:
            misses.append((label, verdict, text[:70]))
    dangers = sum(v for (l, _), v in confusion.items() if l == "danger")
    caught = confusion[("danger", "danger")]
    false_alarm = sum(v for (l, p), v in confusion.items() if l != "danger" and p == "danger")
    non_danger = len(UPI) - dangers
    print(f"  Tricks marked 'danger' (recall):    {caught}/{dangers} = {pct(caught, dangers)}")
    print(f"  Others wrongly marked 'danger':     {false_alarm}/{non_danger} = {pct(false_alarm, non_danger)}")
    print(f"  Exact verdict accuracy:             {len(UPI) - len(misses)}/{len(UPI)} = {pct(len(UPI) - len(misses), len(UPI))}")
    for m in misses:
        print(f"    miss: expected {m[0]:<8} got {m[1]:<8} | {m[2]}")


def calls(CALLS):
    print(f"\nCall copilot: {len(CALLS)} transcripts")
    tp = fp = fn = tn = 0
    misses = []
    for label, text in CALLS:
        level = call_tactics.risk([h["id"] for h in call_tactics.scan(text)])
        predicted = "scam" if level in ("warning", "scam") else "safe"
        if label == "scam":
            tp += predicted == "scam"
            fn += predicted != "scam"
        else:
            fp += predicted == "scam"
            tn += predicted != "scam"
        if predicted != label:
            misses.append((label, level, text[:70]))
    print(f"  Scam calls warned (recall):         {tp}/{tp + fn} = {pct(tp, tp + fn)}")
    print(f"  Normal calls wrongly warned:        {fp}/{fp + tn} = {pct(fp, fp + tn)}")
    for m in misses:
        print(f"    miss: expected {m[0]:<5} level {m[1]:<9} | {m[2]}")


def messages(MESSAGES):
    print(f"\nMessage analyzer, offline rules only: {len(MESSAGES)} messages")
    tp = fp = fn = tn = 0
    misses = []
    for label, text in MESSAGES:
        r = normalize_analysis(rule_engine.analyze(text, analyze_urls(text), analyze_sender(text)), text)
        predicted = "scam" if r["risk_score"] >= 25 else "safe"
        if label == "scam":
            tp += predicted == "scam"
            fn += predicted != "scam"
        else:
            fp += predicted == "scam"
            tn += predicted != "scam"
        if predicted != label:
            misses.append((label, r["risk_score"], text[:70]))
    print(f"  Scams flagged (recall):             {tp}/{tp + fn} = {pct(tp, tp + fn)}")
    print(f"  Precision:                          {tp}/{tp + fp} = {pct(tp, tp + fp)}")
    print(f"  Safe messages wrongly flagged:      {fp}/{fp + tn} = {pct(fp, fp + tn)}")
    print(f"  Accuracy:                           {tp + tn}/{len(MESSAGES)} = {pct(tp + tn, len(MESSAGES))}")
    for m in misses:
        print(f"    miss: expected {m[0]:<5} score {m[1]:<4} | {m[2]}")


if __name__ == "__main__":
    print("=== Batch 1 (rules were fixed after its first run) ===")
    chats(cases.CHATS)
    upi(cases.UPI)
    calls(cases.CALLS)
    print("\n=== Batch 2, held out (never used to change the rules) ===")
    chats(cases.HELDOUT_CHATS)
    upi(cases.HELDOUT_UPI)
    calls(cases.HELDOUT_CALLS)
    messages(cases.HELDOUT_MESSAGES)
