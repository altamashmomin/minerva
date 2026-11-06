#!/usr/bin/env python3
"""MINERVA WP2/WP3: deterministic rules baseline and evaluation.

Run: python3 evaluate.py --data /path/to/csvs --out /path/to/results
Python 3.11+, standard library only. No network or production integration.
"""
import argparse
import csv
import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

MIN_HISTORY = 3
TEST_FRACTION = 0.30
Z95 = 1.959964
REQUIRED = ("txn_id", "date", "merchant_raw", "amount", "description_redacted", "label")
REASONS = {"ok", "unseen_merchant", "insufficient_history", "mixed_history", "ambiguous_merchant"}
PREFIXES = ("sq *", "tst*", "paypal *")
STORE_NUMBER = re.compile(r"\s*#\s*\d+\s*$")


@dataclass(frozen=True)
class Features:
    """Unlabeled request passed to predictors; no answer key is accessible."""
    txn_id: str
    day: date
    merchant_raw: str
    amount: Decimal
    description: str


@dataclass(frozen=True)
class Txn(Features):
    label: str
    verified: bool

    def features(self):
        return Features(self.txn_id, self.day, self.merchant_raw,
                        self.amount, self.description)


@dataclass(frozen=True)
class Prediction:
    category_id: str | None
    reason_code: str


def normalize(raw):
    s = " ".join(raw.strip().lower().split())
    for prefix in PREFIXES:
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
            break
    return STORE_NUMBER.sub("", s).strip()


def load_categories(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not {"category_id", "name"} <= set(reader.fieldnames or []):
            raise ValueError(f"{path}: expected category_id,name header")
        ids = [row["category_id"].strip() for row in reader]
    if not ids or any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"{path}: category IDs must be nonblank and unique")
    return set(ids)


def load_ambiguous(path):
    if not Path(path).exists():
        return set()
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return {normalize(line) for line in lines
            if line.strip() and not line.lstrip().startswith("#")}


def load_transactions(path, categories):
    txns, seen = [], set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(REQUIRED) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        has_status = "review_status" in reader.fieldnames
        for line, row in enumerate(reader, 2):
            if None in row or any(row.get(c) is None for c in REQUIRED):
                raise ValueError(f"{path} line {line}: malformed CSV row")
            blank = [c for c in REQUIRED if c != "description_redacted"
                     and not row[c].strip()]
            if blank:
                raise ValueError(f"{path} line {line}: empty {blank}")
            tid = row["txn_id"].strip()
            if tid in seen:
                raise ValueError(f"{path} line {line}: duplicate txn_id {tid}")
            seen.add(tid)
            label = row["label"].strip()
            if label not in categories:
                raise ValueError(f"{path} line {line}: unknown label {label!r}")
            try:
                amount = Decimal(row["amount"].strip())
                day = date.fromisoformat(row["date"].strip())
            except (InvalidOperation, ValueError) as error:
                raise ValueError(f"{path} line {line}: bad amount or date: {error}") from None
            if not amount.is_finite():
                raise ValueError(f"{path} line {line}: non-finite amount")
            status = row["review_status"].strip().lower() if has_status else "verified"
            if status not in {"verified", "imported", "unverified"}:
                raise ValueError(f"{path} line {line}: unknown review_status {status!r}")
            txns.append(Txn(tid, day, row["merchant_raw"], amount,
                            row["description_redacted"], label, status == "verified"))
    return txns


def temporal_split(txns, frac=TEST_FRACTION):
    """Chronological holdout, never splitting transactions from one calendar day."""
    if not 0 < frac < 1 or len({t.day for t in txns}) < 2:
        raise ValueError("temporal split requires at least two dates and 0 < frac < 1")
    ordered = sorted(txns, key=lambda t: (t.day, t.txn_id))
    cut = ordered[min(int(len(ordered) * (1 - frac)), len(ordered) - 1)].day
    train = [t for t in ordered if t.day < cut]
    test = [t for t in ordered if t.day >= cut]
    if not train or not test:
        raise ValueError("temporal split is empty on one side; add more dated rows")
    return train, test


def merchant_split(txns, frac=TEST_FRACTION):
    """Deterministic unseen-merchant holdout; hash groups remain intact."""
    if not 0 < frac < 1:
        raise ValueError("merchant split requires 0 < frac < 1")
    def is_test(t):
        digest = hashlib.sha256(normalize(t.merchant_raw).encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / 2**64 < frac
    train = [t for t in txns if not is_test(t)]
    test = [t for t in txns if is_test(t)]
    if not train or not test:
        raise ValueError("merchant split is empty on one side; add merchant diversity")
    return train, test


class RulesPredictor:
    def __init__(self, train, ambiguous):
        self.ambiguous = set(ambiguous)
        self.history = defaultdict(Counter)
        for txn in train:
            self.history[normalize(txn.merchant_raw)][txn.label] += 1

    def __call__(self, txn: Features) -> Prediction:
        key = normalize(txn.merchant_raw)
        if key in self.ambiguous:
            return Prediction(None, "ambiguous_merchant")
        counts = self.history.get(key)
        if not counts:
            return Prediction(None, "unseen_merchant")
        if sum(counts.values()) < MIN_HISTORY:
            return Prediction(None, "insufficient_history")
        if len(counts) != 1:
            return Prediction(None, "mixed_history")
        return Prediction(next(iter(counts)), "ok")


def wilson(k, n, z=Z95):
    if n == 0:
        return None
    p = k / n
    denom = 1 + z*z/n
    center = (p + z*z/(2*n))/denom
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))/denom
    return max(0.0, center-half), min(1.0, center+half)


def score(predictor, test, categories):
    rows = []
    for txn in test:
        pred = predictor(txn.features())  # Never hand the predictor the true label.
        if not isinstance(pred, Prediction) or pred.reason_code not in REASONS:
            raise ValueError(f"{txn.txn_id}: invalid prediction {pred!r}")
        if (pred.category_id is None) == (pred.reason_code == "ok"):
            raise ValueError(f"{txn.txn_id}: inconsistent prediction {pred!r}")
        if pred.category_id is not None and pred.category_id not in categories:
            raise ValueError(f"{txn.txn_id}: unknown predicted category {pred.category_id!r}")
        rows.append((txn, pred))
    n = len(rows)
    accepted = [(t, p) for t, p in rows if p.category_id is not None]
    correct = sum(t.label == p.category_id for t, p in accepted)
    wrong = len(accepted) - correct
    return {
        "n": n, "accepted": len(accepted), "correct": correct, "wrong": wrong,
        "coverage": len(accepted)/n if n else None,
        "precision": correct/len(accepted) if accepted else None,
        "precision_ci": wilson(correct, len(accepted)),
        "false_acceptance": wrong/len(accepted) if accepted else None,
        "wrong_of_all": wrong/n if n else None,
        "oracle_upper_bound": (n-wrong)/n if n else None,
        "reasons": Counter(p.reason_code for _, p in rows),
        "per_category": Counter((p.category_id, t.label == p.category_id)
                                for t, p in accepted),
        "true_labels": Counter(t.label for t, _ in rows),
    }


def pct(x):
    return "undefined" if x is None else f"{x*100:.1f}%"


def describe(name, result):
    if result["n"] == 0:
        return [f"  [{name}] n=0 (none in this split)"]
    ci = result["precision_ci"]
    lines = [f"  [{name}] n={result['n']}  accepted={result['accepted']}  coverage={pct(result['coverage'])}",
             f"    precision: {pct(result['precision'])}" +
             (f" (95% Wilson {pct(ci[0])} to {pct(ci[1])})" if ci else ""),
             f"    false acceptance (wrong/accepted): {pct(result['false_acceptance'])}",
             f"    wrong/all: {pct(result['wrong_of_all'])}",
             f"    oracle upper bound (perfect fallback, NOT expected): {pct(result['oracle_upper_bound'])}",
             "    outcomes: " + ", ".join(f"{key}={n}" for key, n in sorted(result["reasons"].items())),
             "    true labels: " + ", ".join(f"{key}={n}" for key, n in sorted(result["true_labels"].items()))]
    for cat in sorted({c for c, _ in result["per_category"]}):
        good, bad = result["per_category"][(cat, True)], result["per_category"][(cat, False)]
        lines.append(f"    predicted {cat}: accepted={good+bad}, correct={good}")
    return lines


def run(data_dir, out_dir):
    data = Path(data_dir)
    cats = load_categories(data / "categories.csv")
    ambiguous = load_ambiguous(data / "ambiguous_merchants.txt")
    all_rows = load_transactions(data / "labeled.csv", cats)
    txns = [t for t in all_rows if t.verified]
    lines = [f"MINERVA rules baseline (MIN_HISTORY={MIN_HISTORY}, TEST_FRACTION={TEST_FRACTION})",
             f"rows loaded={len(all_rows)}, verified={len(txns)}"]
    variants = defaultdict(set)
    for txn in txns:
        variants[normalize(txn.merchant_raw)].add(txn.merchant_raw.strip())
    merged = {key: vals for key, vals in variants.items() if len(vals) > 1}
    lines.append(f"normalization merges for review={len(merged)}")
    lines.extend(f"  {key!r} <- {sorted(vals)}" for key, vals in sorted(merged.items()))
    for name, splitter in (("temporal", temporal_split), ("merchant-grouped", merchant_split)):
        train, test = splitter(txns)
        known = {normalize(t.merchant_raw) for t in train}
        predictor = RulesPredictor(train, ambiguous)
        lines += ["", f"{name}: train={len(train)}, test={len(test)}"]
        for label, subset in (("all", test),
                              ("seen merchants", [t for t in test if normalize(t.merchant_raw) in known]),
                              ("unseen merchants", [t for t in test if normalize(t.merchant_raw) not in known])):
            lines.extend(describe(label, score(predictor, subset, cats)))
    report = "\n".join(lines) + "\n"
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.txt").write_text(report, encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(run(args.data, args.out), end="")

