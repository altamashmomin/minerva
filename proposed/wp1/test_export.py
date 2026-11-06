"""Synthetic WP1 tests. Run: python3 -m unittest test_export.py"""
import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import export as ex

SCHEMA = """
CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
INSERT INTO schema_version VALUES (22);
CREATE TABLE transactions (id INTEGER PRIMARY KEY, txn_date TEXT, amount_cents INTEGER,
  description TEXT, category TEXT, source TEXT, direction TEXT, is_transfer INTEGER);
CREATE TABLE audit_log (id INTEGER PRIMARY KEY, actor TEXT, action TEXT,
  target TEXT, detail_json TEXT);
"""


def make_db(txns, audits=()):
    p = Path(tempfile.mkdtemp()) / "snapshot.db"
    with sqlite3.connect(p) as conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)", txns)
        conn.executemany("INSERT INTO audit_log (actor, action, target, detail_json) "
                         "VALUES (?,?,?,?)", audits)
    return p


def row(i, cat="Groceries", src="simplefin", direction="out", transfer=0,
        desc="SHOPRITE #12", cents=4250):
    return i, f"2026-09-{i:02d}", cents, desc, cat, src, direction, transfer


def edit(i, detail, actor="ui:alta"):
    return actor, "edit_transaction", f"transaction:{i}", json.dumps(detail)


def ledger_edit(i, old, new, actor="ui:alta", **more):
    """Ledger's real edit_transaction shape: full before-image + validated cols."""
    return edit(i, {"before": {"id": i, "category": old, "description": "SHOPRITE #12"},
                    "changed": {"category": new, **more}}, actor)


class Export(unittest.TestCase):
    def build(self, txns, audits=()):
        conn = ex.open_readonly(make_db(txns, audits))
        try:
            self.assertEqual(ex.check_schema(conn), 22)
            return ex.build(conn)
        finally:
            conn.close()

    def statuses(self, txns, audits=()):
        return [r["review_status"] for r in self.build(txns, audits)[0]]

    def test_filters_and_counts(self):
        rows, cats, counts = self.build([
            row(1), row(2, direction="in"), row(3, transfer=1),
            row(4, cat="Settlement", src="settlement"), row(5, cat="Other")])
        self.assertEqual([r["txn_id"] for r in rows], ["L1"])
        self.assertEqual(cats, {"groceries": "Groceries"})
        self.assertEqual(sum(counts.get(k, 0) for k in (
            "skipped_inflow", "skipped_transfer", "skipped_settlement",
            "skipped_unlabeled")), 4)

    def test_review_status_from_audit_and_source(self):
        self.assertEqual(self.statuses(
            [row(1), row(2), row(3, src="manual"), row(4), row(5), row(6, src="bill")],
            [edit(1, {"changed": {"category": "Groceries"}}),
             edit(2, {"changed": {"description": "corrected"}}),
             edit(4, {"changed": {"category": "Groceries"}}, actor="mcp:laptop"),
             ledger_edit(5, "Other", "Groceries")]),
            ["verified", "imported", "verified", "imported", "verified", "imported"])

    def test_last_category_edit_determines_status(self):
        self.assertEqual(self.statuses([
            row(1, cat="Dining"), row(2, cat="Dining"), row(3, cat="Dining"),
            row(4, cat="Dining", src="manual")], [
            edit(1, {"changed": {"category": "Groceries"}}),
            edit(1, {"changed": {"category": "Dining"}}, actor="mcp:agent"),
            edit(2, {"changed": {"category": "Groceries"}}, actor="mcp:agent"),
            edit(2, {"changed": {"category": "Dining"}}),
            edit(3, {"changed": {"category": "Groceries"}}),
            edit(4, {"changed": {"category": "Dining"}}, actor="mcp:agent")]),
            ["imported", "verified", "imported", "imported"])

    def test_unchanged_category_resubmit_is_not_a_category_event(self):
        """The Ledger edit form always resubmits category; a form save that
        only fixed the description must not verify, and an mcp no-op must not
        downgrade an earlier real UI change."""
        self.assertEqual(self.statuses([row(1), row(2), row(3)], [
            ledger_edit(1, "Groceries", "Groceries", description="ShopRite"),
            ledger_edit(2, "Dining", "Groceries"),
            ledger_edit(2, "Groceries", "Groceries", actor="mcp:agent"),
            ledger_edit(3, "Groceries", " Groceries ")]),
            ["imported", "verified", "imported"])

    def test_merge_category_limitation_is_pinned(self):
        """merge_category relabels in bulk with no per-row audit. A manual row
        keeps 'verified' under its NEW name (accepted limitation); a UI-edited
        row whose label no longer matches its last edit downgrades."""
        merge = ("ui:alta", "merge_category", None,
                 json.dumps({"from_category": "Dining", "into_category": "Food"}))
        self.assertEqual(self.statuses(
            [row(1, cat="Food", src="manual"), row(2, cat="Food")],
            [ledger_edit(2, "Other", "Dining"), merge]),
            ["verified", "imported"])

    def test_legacy_ambiguous_or_malformed_audits_do_not_verify(self):
        self.assertEqual(self.statuses([row(1), row(2), row(3), row(4)], [
            edit(1, {"changed": ["category"]}),
            edit(2, {"changed": {"category": "Groceries"}}, actor="ui:alta"),
            ("ui:alta", "edit_transaction", "transaction:bad", "{}"),
            ("ui:alta", "edit_transaction", "transaction:3", "{invalid"),
            edit(4, {"before": {"category": "Other"}, "after": {"category": "Groceries"}})]),
            ["imported", "verified", "imported", "imported"])

    def test_amount_is_exact_negative_two_decimal(self):
        rows, _, _ = self.build([row(1, cents=675), row(2, cents=100), row(3, cents=5)])
        self.assertEqual([r["amount"] for r in rows], ["-6.75", "-1.00", "-0.05"])

    def test_masks_long_digits_but_is_not_full_redaction(self):
        rows, _, _ = self.build([row(1, desc="POS 4417123456 7-ELEVEN #1234")])
        self.assertEqual(rows[0]["merchant_raw"], "POS # 7-ELEVEN #1234")

    def test_slug_collision_rejected(self):
        with self.assertRaisesRegex(ValueError, "share ID"):
            self.build([row(1, cat="Home Goods"), row(2, cat="home-goods")])

    def test_refuses_live_path_even_through_symlink(self):
        p = make_db([]).with_name("finance.db")
        p.write_bytes(make_db([]).read_bytes())
        alias = p.with_name("alias.db")
        alias.symlink_to(p)
        with self.assertRaises(SystemExit):
            ex.open_readonly(alias)

    def test_readonly_and_uri_special_characters(self):
        p = make_db([row(1)])
        funny = p.with_name("snap?part#1.db")
        p.rename(funny)
        conn = ex.open_readonly(funny)
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("DELETE FROM transactions")
        conn.close()

    def test_schema_requires_transactions_columns(self):
        p = make_db([])
        with sqlite3.connect(p) as conn:
            conn.execute("ALTER TABLE transactions DROP COLUMN is_transfer")
        conn = ex.open_readonly(p)
        with self.assertRaisesRegex(ValueError, "transactions: missing columns"):
            ex.check_schema(conn)
        conn.close()

    def test_schema_requires_audit_columns(self):
        p = make_db([])
        with sqlite3.connect(p) as conn:
            conn.execute("ALTER TABLE audit_log DROP COLUMN actor")
        conn = ex.open_readonly(p)
        with self.assertRaisesRegex(ValueError, "audit_log: missing columns"):
            ex.check_schema(conn)
        conn.close()

    def test_refuses_git_worktree_and_symlink_output(self):
        root = Path(tempfile.mkdtemp())
        (root / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "outside Git"):
            ex.write(root / "exports", [], {})
        out = Path(tempfile.mkdtemp())
        (out / "labeled.csv").symlink_to(out / "target.csv")
        with self.assertRaisesRegex(ValueError, "symlink"):
            ex.write(out, [], {})

    def test_output_loads_in_accepted_harness(self):
        harness = Path(__file__).resolve().parents[2] / "accepted" / "wp2-wp3"
        sys.path.insert(0, str(harness))
        import evaluate as ev
        out = Path(tempfile.mkdtemp()) / "private-out"
        ex.main(["--db", str(make_db([row(1), row(2, cat="Dining")])),
                 "--out", str(out)])
        cats = ev.load_categories(out / "categories.csv")
        txns = ev.load_transactions(out / "labeled.csv", cats)
        self.assertEqual(cats, {"groceries", "dining"})
        self.assertEqual([t.verified for t in txns], [False, False])
        with (out / "labeled.csv").open(newline="") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 2)


if __name__ == "__main__":
    unittest.main()
