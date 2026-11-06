#!/usr/bin/env python3
"""MINERVA WP1: export a Ledger SNAPSHOT to WP3-compatible CSV files.

Standard library, Python 3.11+. Never run against the live Ledger database.
    python3 export.py --db /private/ledger-snapshot.db --out /private/export
The snapshot must be a consistent offline copy (sqlite3 finance.db
".backup snap.db" or VACUUM INTO), made by Alta on the Ledger Pi.
The output contains sensitive financial information. Keep it out of Git/cloud.
"""
import argparse
import csv
import json
import re
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

TXN_COLUMNS = {"id", "txn_date", "amount_cents", "description", "category",
               "source", "direction", "is_transfer"}
AUDIT_COLUMNS = {"id", "actor", "action", "target", "detail_json"}
COLUMNS = ("txn_id", "date", "merchant_raw", "amount", "description_redacted",
           "label", "review_status")
LONG_DIGITS = re.compile(r"\d{6,}")  # Partial masking, NOT complete anonymization.
CENTS = Decimal("0.01")


def open_readonly(path):
    p = Path(path).expanduser().resolve()
    if p.name.casefold() == "finance.db":
        sys.exit("Refusing finance.db; use a consistent snapshot copy")
    if not p.is_file():
        sys.exit(f"{p}: snapshot file not found")
    conn = sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def check_schema(conn):
    for table, required in (("transactions", TXN_COLUMNS),
                            ("audit_log", AUDIT_COLUMNS),
                            ("schema_version", {"version"})):
        have = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if required - have:
            raise ValueError(f"{table}: missing columns {sorted(required - have)}")
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    if version is None:
        raise ValueError("schema_version is empty")
    return version


def _category_change(detail):
    """Return (changed, new category) for Ledger's edit_transaction audit shape:
    {"before": <row>, "changed": <validated columns>}. A payload that resubmits
    the current category unchanged (the edit form always sends it) is NOT a
    category-setting event. Any other shape is non-verifying."""
    if not isinstance(detail, dict):
        return False, None
    before, changed = detail.get("before"), detail.get("changed")
    if not isinstance(changed, dict) or "category" not in changed:
        return False, None
    new = changed["category"]
    if not isinstance(new, str):
        return True, None  # Category touched but the value is unknowable.
    old = before.get("category") if isinstance(before, dict) else None
    if isinstance(old, str) and old.strip() == new.strip():
        return False, None  # No-op resubmit: neither verifies nor downgrades.
    return True, new.strip()


def category_edits(conn):
    """Latest real category change per row, by audit id: (by UI actor, value)."""
    latest = {}
    for row in conn.execute("SELECT actor, target, detail_json FROM audit_log "
                            "WHERE action='edit_transaction' ORDER BY id"):
        target = row["target"] or ""
        if not re.fullmatch(r"transaction:[0-9]+", target):
            continue  # Malformed audit targets cannot establish provenance.
        try:
            detail = json.loads(row["detail_json"])
        except (TypeError, ValueError):
            continue
        changed, new_value = _category_change(detail)
        if changed:
            latest[int(target.split(":", 1)[1])] = (
                (row["actor"] or "").startswith("ui:"), new_value)
    return latest


def slug(name):
    result = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not result:
        raise ValueError(f"category {name!r} has no usable ID")
    return result


def build(conn):
    """Return (CSV rows, category lookup, counts); never mutate the database."""
    edits = category_edits(conn)
    rows, categories, counts = [], {}, {}

    def count(reason):
        counts[reason] = counts.get(reason, 0) + 1

    for txn in conn.execute("SELECT * FROM transactions ORDER BY txn_date, id"):
        category = (txn["category"] or "").strip()
        if txn["direction"] != "out":
            count("skipped_inflow"); continue
        if txn["is_transfer"]:
            count("skipped_transfer"); continue
        if txn["source"] == "settlement" or category == "Settlement":
            count("skipped_settlement"); continue
        if not category or category == "Other":
            count("skipped_unlabeled"); continue
        cid = slug(category)
        if categories.setdefault(cid, category) != category:
            raise ValueError(f"categories {categories[cid]!r} and {category!r} share ID {cid!r}")

        # verified = the latest real category change was made under a UI session
        # and still matches, or a manually entered row nobody has relabeled since.
        # This is a provenance proxy, not independent human review (see HANDOFF).
        last = edits.get(txn["id"])
        verified = (last == (True, category)) if last is not None else txn["source"] == "manual"
        status = "verified" if verified else "imported"
        count(f"exported_{status}")
        rows.append({
            "txn_id": f"L{txn['id']}", "date": txn["txn_date"],
            "merchant_raw": LONG_DIGITS.sub("#", " ".join(txn["description"].split())),
            "amount": str((-Decimal(txn["amount_cents"]) / 100).quantize(CENTS)),
            "description_redacted": "", "label": cid, "review_status": status,
        })
    return rows, categories, counts


def write(out_dir, rows, categories):
    """Keep potentially sensitive exports outside any Git worktree."""
    out = Path(out_dir).expanduser().resolve()
    if any((parent / ".git").exists() for parent in (out, *out.parents)):
        raise ValueError("financial exports must be written outside Git repositories")
    for name in ("labeled.csv", "categories.csv"):
        if (out / name).is_symlink():
            raise ValueError(f"refusing symlink output {out / name}")
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(out / "labeled.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with open(out / "categories.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category_id", "name"])
        writer.writerows(sorted(categories.items()))
    (out / "labeled.csv").chmod(0o600)
    (out / "categories.csv").chmod(0o600)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="local SQLite snapshot, not live Ledger")
    parser.add_argument("--out", required=True, help="private folder OUTSIDE Git")
    args = parser.parse_args(argv)
    conn = open_readonly(args.db)
    try:
        version = check_schema(conn)
        rows, categories, counts = build(conn)
    finally:
        conn.close()
    write(args.out, rows, categories)
    print(f"schema_version={version} categories={len(categories)} rows={len(rows)}")
    for key in sorted(counts):
        print(f"  {key}={counts[key]}")


if __name__ == "__main__":
    main()
