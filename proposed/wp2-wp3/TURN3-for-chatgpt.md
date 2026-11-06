# MINERVA 0.1, WP2 + WP3, Turn 3 (Claude)

## Verdict
I accept all five Turn 2 findings and keep every listed decision. Turn 3 makes three small changes. This file is the Turn 3 candidate to go into Turn 4.

## Verification
- ChatGPT's Turn 2 files: 19/19 pass with `python3 -m unittest test_evaluate.py`, but `python3 test_evaluate.py` runs only 16 of them (see finding 1).
- Turn 3 candidate: 21/21 pass both ways. The end-to-end sample report runs on both splits.
- Sizes: evaluate.py 264 lines, test_evaluate.py 152. I agree not to compress for its own sake.

## How Turn 2 landed
1. Answer-key exposure: Agree. `score()` passes `txn.features()` only, and a test enforces it.
2. Degenerate splits: Agree. Splits raise rather than resample.
3. NaN, infinity and status typos: Agree. Note that a blank `review_status` is now rejected, so WP1's export must write an explicit status for every row (limitation, logged).
4. True-label counts: Agree.
5. Merchant-split imbalance: Agree. Keep the hash and report the caveat. In the sample, the merchant-grouped test set is 10 dining rows, all unseen, so rules coverage is 0% there. That is expected for a rules-only method, not a bug.

## Turn 3 findings (ranked)
1. **Bug, tests:** the `AdditionalSafety` class sat after `if __name__ == "__main__": unittest.main()`, so running the file directly silently skipped the 3 new safety tests. Fix: moved them above the main guard.
2. **Report clarity:** in the merchant-grouped split, "seen merchants" is empty by construction and printed six lines of "undefined". Fix: an empty subset now prints one line, `n=0 (none in this split)`.
3. **Test gap:** the new malformed-row check (extra CSV field) had no test. Fix: added one, plus a test for finding 2.

## Disagreements
None.

## Proposed Turn 4 acceptance record
| Item | Proposed status |
|---|---|
| T2-1 Features-only predictor contract | Agree |
| T2-2 Non-empty split validation | Agree |
| T2-3 Finite amounts, explicit review_status | Agree with limitation: WP1 must emit status on every row |
| T2-4 True-label counts | Agree |
| T2-5 Hash split kept, imbalance as caveat | Agree with limitation: small samples can give single-class test sets |
| T3-1 Tests above main guard | Agree |
| T3-2 One-line empty subsets | Agree |
| T3-3 Malformed-row test | Agree |
| File length over 200 lines | Agree with limitation: readability over compression |

## Parking list (unchanged)
Threshold sweep, three-way split, more normalization rules, Txn composition instead of inheritance (Txn still subclasses Features; harmless while score() is the only caller).

## Complete evaluate.py
```python
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

```

## Complete test_evaluate.py
```python
"""Synthetic tests for evaluate.py. Run: python3 -m unittest test_evaluate.py"""
import tempfile, unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import evaluate as ev

CATS = {"groceries", "dining", "shopping"}


def txn(i, merchant, label, day=0):
    return ev.Txn(f"T{i}", date(2026, 9, 1) + timedelta(days=day), merchant,
                  Decimal("-10.00"), "", label, True)


def history(merchant, labels, start=0):
    return [txn(start + k, merchant, lab, start + k) for k, lab in enumerate(labels)]


class Predictor(unittest.TestCase):
    def predict(self, train, merchant, ambiguous=frozenset()):
        return ev.RulesPredictor(train, set(ambiguous))(txn(999, merchant, "groceries"))

    def test_known_merchant_accepted(self):
        p = self.predict(history("SHOPRITE", ["groceries"] * 3), "SHOPRITE")
        self.assertEqual(p, ev.Prediction("groceries", "ok"))

    def test_unseen_merchant(self):
        p = self.predict(history("SHOPRITE", ["groceries"] * 3), "WEGMANS")
        self.assertEqual(p.reason_code, "unseen_merchant")

    def test_insufficient_history(self):
        p = self.predict(history("SHOPRITE", ["groceries"] * 2), "SHOPRITE")
        self.assertEqual(p.reason_code, "insufficient_history")

    def test_mixed_history_abstains_even_at_90_percent(self):
        p = self.predict(history("WALGREENS", ["shopping"] * 9 + ["groceries"]), "WALGREENS")
        self.assertEqual(p.reason_code, "mixed_history")

    def test_ambiguous_merchant_abstains(self):
        p = self.predict(history("AMAZON", ["shopping"] * 5), "AMAZON", {"amazon"})
        self.assertEqual(p.reason_code, "ambiguous_merchant")

    def test_normalization_collision_merges_known_variants(self):
        train = history("SQ *BLUE BOTTLE", ["dining"] * 2) + history("Blue Bottle #4", ["dining"], 10)
        self.assertEqual(self.predict(train, "BLUE BOTTLE #12").category_id, "dining")

    def test_normalization_keeps_distinguishing_numbers(self):
        self.assertNotEqual(ev.normalize("7-ELEVEN"), ev.normalize("ELEVEN"))
        self.assertEqual(ev.normalize("ROUTE 18 DINER"), "route 18 diner")


class Splits(unittest.TestCase):
    rows = [txn(i, f"MERCHANT {i % 7}", "groceries", i) for i in range(70)]

    def test_merchant_split_isolation(self):
        train, test = ev.merchant_split(self.rows)
        self.assertFalse({ev.normalize(t.merchant_raw) for t in train}
                         & {ev.normalize(t.merchant_raw) for t in test})
        self.assertEqual(len(train) + len(test), len(self.rows))

    def test_temporal_split_order(self):
        train, test = ev.temporal_split(self.rows)
        self.assertLess(max(t.day for t in train), min(t.day for t in test))

    def test_no_leakage_from_test_labels(self):
        train, test = ev.temporal_split(self.rows[:50] + history("LATE SHOP", ["shopping"] * 5, 100))
        p = ev.RulesPredictor(train, set())(test[-1])
        self.assertEqual(p.reason_code, "unseen_merchant")


class Metrics(unittest.TestCase):
    def test_wilson_known_values(self):
        lo, hi = ev.wilson(95, 100)
        self.assertAlmostEqual(lo, 0.888, places=3)
        self.assertAlmostEqual(hi, 0.978, places=3)
        self.assertIsNone(ev.wilson(0, 0))

    def test_zero_accepted_precision_undefined(self):
        s = ev.score(ev.RulesPredictor([], set()), [txn(1, "X", "dining")], CATS)
        self.assertIsNone(s["precision"])
        self.assertEqual(s["coverage"], 0.0)

    def test_false_acceptance_and_oracle(self):
        train = history("CAFE", ["dining"] * 3)
        test = [txn(50, "CAFE", "dining"), txn(51, "CAFE", "groceries"), txn(52, "NEW", "dining")]
        s = ev.score(ev.RulesPredictor(train, set()), test, CATS)
        self.assertEqual((s["accepted"], s["correct"]), (2, 1))
        self.assertAlmostEqual(s["false_acceptance"], 0.5)
        self.assertAlmostEqual(s["wrong_of_all"], 1 / 3)
        self.assertAlmostEqual(s["oracle_upper_bound"], 2 / 3)


class Loading(unittest.TestCase):
    def write(self, body):
        d = Path(tempfile.mkdtemp())
        (d / "labeled.csv").write_text(
            "txn_id,date,merchant_raw,amount,description_redacted,label\n" + body)
        return d / "labeled.csv"

    def test_rejects_duplicate_ids(self):
        p = self.write("T1,2026-09-01,A,-1.00,,dining\nT1,2026-09-02,B,-1.00,,dining\n")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            ev.load_transactions(p, CATS)

    def test_rejects_unknown_label_and_bad_date(self):
        with self.assertRaisesRegex(ValueError, "unknown label"):
            ev.load_transactions(self.write("T1,2026-09-01,A,-1.00,,travel\n"), CATS)
        with self.assertRaisesRegex(ValueError, "bad amount or date"):
            ev.load_transactions(self.write("T1,09/01/2026,A,-1.00,,dining\n"), CATS)

    def test_amount_is_decimal(self):
        t = ev.load_transactions(self.write("T1,2026-09-01,A,-6.75,,dining\n"), CATS)[0]
        self.assertEqual(t.amount, Decimal("-6.75"))


class AdditionalSafety(unittest.TestCase):
    def test_predictor_never_receives_label(self):
        def inspect(features):
            self.assertIsInstance(features, ev.Features)
            self.assertFalse(hasattr(features, 'label'))
            return ev.Prediction(None, 'unseen_merchant')
        ev.score(inspect, [txn(100, 'A', 'dining')], CATS)

    def test_split_rejects_degenerate_samples(self):
        with self.assertRaisesRegex(ValueError, 'two dates'):
            ev.temporal_split([txn(1, 'A', 'dining'), txn(2, 'B', 'dining')])
        with self.assertRaisesRegex(ValueError, 'empty'):
            ev.merchant_split([txn(1, 'A', 'dining')])

    def test_rejects_nonfinite_and_unknown_review_status(self):
        loader = Loading()
        with self.assertRaisesRegex(ValueError, 'non-finite'):
            ev.load_transactions(loader.write('T1,2026-09-01,A,NaN,,dining\n'), CATS)
        path = loader.write('T1,2026-09-01,A,-1.00,,dining\n')
        path.write_text('txn_id,date,merchant_raw,amount,description_redacted,label,review_status\n'
                        'T1,2026-09-01,A,-1.00,,dining,typo\n')
        with self.assertRaisesRegex(ValueError, 'unknown review_status'):
            ev.load_transactions(path, CATS)

    def test_rejects_malformed_row(self):
        with self.assertRaisesRegex(ValueError, "malformed"):
            ev.load_transactions(Loading().write("T1,2026-09-01,A,-1.00,,dining,EXTRA\n"), CATS)

    def test_empty_subset_reported_in_one_line(self):
        s = ev.score(ev.RulesPredictor([], set()), [], CATS)
        self.assertEqual(ev.describe("seen merchants", s), ["  [seen merchants] n=0 (none in this split)"])


if __name__ == "__main__":
    unittest.main()
```
