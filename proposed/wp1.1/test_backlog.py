"""Synthetic only. Run from proposed/wp1.1: python3.13 -m unittest test_backlog.py"""
import contextlib
import csv
import io
import json
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

import backlog as bl

SCHEMA = """
CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
INSERT INTO schema_version VALUES (22);
CREATE TABLE transactions (id INTEGER PRIMARY KEY, txn_date TEXT, amount_cents INTEGER,
 description TEXT, category TEXT, source TEXT, direction TEXT, is_transfer INTEGER);
CREATE TABLE audit_log (id INTEGER PRIMARY KEY, actor TEXT, action TEXT,
 target TEXT, detail_json TEXT);
"""


def row(i, cat="Other", src="simplefin", direction="out", transfer=0,
        desc="SHOPRITE #12", cents=4250, day="2026-09-01"):
    return i, day, cents, desc, cat, src, direction, transfer


def edit(i, old, new, actor="ui:alta"):
    return actor, "edit_transaction", f"transaction:{i}", json.dumps(
        {"before": {"category": old}, "changed": {"category": new}})


class Backlog(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def database(self, txns=(), audits=(), name="snapshot.db"):
        snapshot = self.root / name
        with contextlib.closing(sqlite3.connect(snapshot)) as conn, conn:
            conn.executescript(SCHEMA)
            conn.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)", txns)
            conn.executemany("INSERT INTO audit_log (actor,action,target,detail_json) "
                             "VALUES (?,?,?,?)", audits)
        return snapshot

    def build(self, txns, audits=()):
        with contextlib.closing(bl.wp1.open_readonly(self.database(txns, audits))) as conn:
            self.assertEqual(bl.wp1.check_schema(conn), 22)
            return bl.build(conn)

    def test_groups_exact_cents_dates_variants_and_order(self):
        groups, verified, counts = self.build([
            row(1, desc="SQ *BLUE BOTTLE", cents=5, day="2026-09-20"),
            row(2, cat=" ", desc=" Blue   Bottle #4 ", cents=675, day="2026-08-01"),
            row(3, cat=None, desc="BLUE BOTTLE #12", cents=-100, day="2026-09-01"),
            row(4, desc="ZED"), row(5, desc="ALPHA")])
        self.assertEqual([g["normalized_merchant"] for g in groups],
                         ["blue bottle", "alpha", "zed"])
        self.assertEqual((groups[0]["count"], groups[0]["total_cents"],
                          groups[0]["first_date"], groups[0]["last_date"]),
                         (3, 580, "2026-08-01", "2026-09-20"))
        self.assertEqual(json.loads(groups[0]["merchant_variants"]),
                         ["BLUE BOTTLE #12", "Blue Bottle #4", "SQ *BLUE BOTTLE"])
        self.assertEqual(verified, [])
        self.assertEqual(counts["skipped_unlabeled"], 5)

    def test_filters_apply_before_backlog_and_verification(self):
        groups, verified, counts = self.build([
            row(1), row(2, cat="Other", direction="in"), row(3, cat="", transfer=1),
            row(4, cat="Other", src="settlement"), row(5, cat=" Settlement "),
            row(6, cat="Dining"), row(7, cat="Dining", src="manual"),
            row(8, cat="Dining", src="manual", direction="in"),
            row(9, cat="Dining", src="manual", transfer=1),
            row(10, cat="Settlement", src="manual")])
        self.assertEqual(sum(g["count"] for g in groups), 1)
        self.assertEqual([r["txn_id"] for r in verified], ["L7"])
        self.assertEqual(counts, {"skipped_unlabeled": 1, "skipped_inflow": 2,
                                 "skipped_transfer": 2, "skipped_settlement": 3,
                                 "exported_imported": 1, "exported_verified": 1})

    def test_uses_accepted_normalization_and_preserves_distinguishing_numbers(self):
        descriptions = ["TST*CAFE #1", "PAYPAL *CAFE #2", "CAFE", "7-ELEVEN",
                        "ELEVEN", "ROUTE 18 DINER", "ROUTE 19 DINER"]
        groups, _, _ = self.build([row(i, desc=d) for i, d in enumerate(descriptions, 1)])
        self.assertEqual([g["normalized_merchant"] for g in groups],
                         ["cafe", "7-eleven", "eleven", "route 18 diner", "route 19 diner"])
        self.assertEqual(groups[0]["count"], 3)

    def test_masks_before_normalization_in_both_reports(self):
        groups, verified, _ = self.build([
            row(1, desc="SHOP #123456"), row(2, desc="SHOP #654321"),
            row(3, cat="Category 123456", src="manual", desc="POS 4417123456 #1234")])
        self.assertEqual(groups[0]["normalized_merchant"], "shop ##")
        self.assertEqual(groups[0]["count"], 2)
        self.assertEqual(verified[0]["merchant_raw"], "POS # #1234")
        self.assertEqual(verified[0]["category"], "Category #")
        self.assertNotIn("123456", json.dumps([groups, verified]))
        self.assertNotIn("4417123456", json.dumps([groups, verified]))

    def test_verified_matches_accepted_provenance_not_adjudication(self):
        txns = [row(i, cat="Dining", src="manual" if i in (3, 4) else "simplefin")
                for i in range(1, 8)] + [row(8, cat="Dining", src="bill")]
        audits = [edit(1, "Other", "Dining"), edit(1, "Dining", "Dining", "mcp:agent"),
                  edit(2, "Dining", "Dining"), edit(3, "Other", "Dining", "mcp:agent"),
                  edit(5, "Other", "Dining"), edit(5, "Dining", "Groceries", "mcp:agent"),
                  edit(6, "Other", "Groceries"), edit(7, "Other", "Dining")]
        _, verified, _ = self.build(txns, audits)
        self.assertEqual([r["txn_id"] for r in verified], ["L1", "L4", "L7"])
        self.assertTrue(all(r["review_status"] == "verified" for r in verified))
        self.assertEqual(verified[0]["amount"], "-42.50")

    def test_empty_snapshot_produces_headers(self):
        groups, verified, counts = self.build([])
        self.assertEqual((groups, verified, counts), ([], [], {}))
        out = self.root / "empty-report"
        bl.write(out, groups, verified)
        for filename, columns in (("backlog.csv", bl.BACKLOG_COLUMNS),
                                  ("verified.csv", bl.VERIFIED_COLUMNS)):
            with (out / filename).open(newline="") as stream:
                self.assertEqual(list(csv.reader(stream)), [list(columns)])

    def test_readonly_special_uri_filename_and_unchanged_snapshot(self):
        snapshot = self.database([row(1)], name="snap?part#1.db")
        original = snapshot.read_bytes()
        with contextlib.closing(bl.wp1.open_readonly(snapshot)) as conn:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("DELETE FROM transactions")
            bl.build(conn)
        self.assertEqual(snapshot.read_bytes(), original)

    def test_refuses_finance_db_direct_and_alias(self):
        snapshot = self.database(name="FiNaNcE.Db")
        alias = self.root / "alias.db"
        alias.symlink_to(snapshot)
        for candidate in (snapshot, alias):
            with self.subTest(candidate=candidate), self.assertRaises(SystemExit):
                bl.wp1.open_readonly(candidate)

    def test_missing_snapshot_is_not_created(self):
        missing = self.root / "missing.db"
        with self.assertRaises(SystemExit):
            bl.wp1.open_readonly(missing)
        self.assertFalse(missing.exists())

    def test_cli_rejects_missing_schema_before_output(self):
        snapshot = self.database()
        with contextlib.closing(sqlite3.connect(snapshot)) as conn, conn:
            conn.execute("ALTER TABLE audit_log DROP COLUMN actor")
        with self.assertRaisesRegex(ValueError, "audit_log: missing columns"):
            bl.main(["--db", str(snapshot), "--out", str(self.root / "report")])
        self.assertFalse((self.root / "report").exists())

    def test_refuses_git_directory_and_worktree_file_in_ancestors(self):
        for marker_type in ("directory", "file"):
            root = self.root / marker_type
            root.mkdir()
            marker = root / ".git"
            marker.mkdir() if marker_type == "directory" else marker.write_text("gitdir: elsewhere")
            with self.subTest(marker_type=marker_type), self.assertRaisesRegex(ValueError, "outside Git"):
                bl.write(root / "nested" / "report", [], [])
            self.assertFalse((root / "nested").exists())

    def test_refuses_existing_folder_files_and_symlinks_without_overwrite(self):
        out = self.root / "report"
        out.mkdir()
        with self.assertRaisesRegex(ValueError, "fresh folder"):
            bl.write(out, [], [])
        existing = out / "backlog.csv"
        existing.write_text("keep")
        (out / "verified.csv").symlink_to(self.root / "missing-target")
        with self.assertRaisesRegex(ValueError, "fresh folder"):
            bl.write(out, [], [])
        self.assertEqual(existing.read_text(), "keep")
        self.assertFalse((self.root / "missing-target").exists())
        for target in (out, self.root / "absent-folder"):
            alias = self.root / ("alias-" + target.name)
            alias.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                bl.write(alias, [], [])
        self.assertFalse((self.root / "absent-folder").exists())

    def test_cli_private_csv_roundtrip_counts_only_and_snapshot_unchanged(self):
        snapshot = self.database([row(1, desc='CAFE, "A" 123456'),
                                  row(2, cat="Dining", src="manual", cents=5)])
        original = snapshot.read_bytes()
        out = self.root / "report"
        console = io.StringIO()
        with contextlib.redirect_stdout(console):
            bl.main(["--db", str(snapshot), "--out", str(out)])
        self.assertEqual(console.getvalue(), "schema_version=22 merchants=1 verified=1\n"
                         "  exported_verified=1\n  skipped_unlabeled=1\n")
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)
        for filename in ("backlog.csv", "verified.csv"):
            self.assertEqual(stat.S_IMODE((out / filename).stat().st_mode), 0o600)
        with (out / "backlog.csv").open(newline="") as stream:
            self.assertEqual(list(csv.DictReader(stream))[0]["normalized_merchant"], 'cafe, "a" #')
        with (out / "verified.csv").open(newline="") as stream:
            self.assertEqual(list(csv.DictReader(stream))[0]["category"], "Dining")
        self.assertEqual(snapshot.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "fresh folder"):
            bl.write(out, [], [])


if __name__ == "__main__":
    unittest.main()
