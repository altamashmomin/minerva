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
