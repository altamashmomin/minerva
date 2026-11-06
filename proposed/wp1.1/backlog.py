#!/usr/bin/env python3
"""MINERVA WP1.1: private backlog and verified-row adjudication report.

Python 3.11+, standard library; run ONLY on Alta's consistent offline snapshot:
    python3.13 proposed/wp1.1/backlog.py --db ~/private/snapshot.db --out ~/private/backlog-new
Writes backlog.csv and verified.csv in a fresh private folder outside Git.
total_cents sums Ledger's stored integer cents (outflows are normally positive).
known_label shows a masked category when all of the merchant's WP1 labels agree.
A blank with labeled_count zero means no history. A blank with a positive count
means conflicting labels. Both imported and verified labels count. Alta reviews
each hint. txn_ids lists the group's L-prefixed Ledger IDs by date, then numeric ID.
Verified is WP1's provenance proxy, NOT adjudicated ground truth. Six-digit
masking is partial, NOT anonymization. Keep real reports out of Git/cloud/chat.
"""
import argparse
import csv
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _accepted(name, relative):
    """Load the repository's accepted code, never a similarly named local module."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "accepted" / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # Required by evaluate.py's dataclasses.
    spec.loader.exec_module(module)
    return module


wp1 = _accepted("_minerva_wp1", "wp1/export.py")
wp23 = _accepted("_minerva_wp23", "wp2-wp3/evaluate.py")
BACKLOG_COLUMNS = ("normalized_merchant", "count", "total_cents", "first_date",
                   "last_date", "known_label", "labeled_count", "txn_ids",
                   "merchant_variants")
VERIFIED_COLUMNS = ("txn_id", "date", "merchant_raw", "amount", "category", "review_status")


def mask(text):
    return wp1.LONG_DIGITS.sub("#", " ".join(text.split()))


def build(conn):
    """Return (merchant groups, verified rows, WP1 counts); no database writes.

    Mask BEFORE normalizing, matching WP1 export -> WP2/WP3 evaluation. Retain
    masked raw variants so Alta can review merges and find merchants in Ledger.
    """
    labeled, categories, counts = wp1.build(conn)
    known = {}  # normalized merchant -> {category name: labeled row count}
    for row in labeled:
        hits = known.setdefault(wp23.normalize(row["merchant_raw"]), {})
        name = categories[row["label"]]
        hits[name] = hits.get(name, 0) + 1
    verified = [{"txn_id": row["txn_id"], "date": row["date"],
                 "merchant_raw": row["merchant_raw"], "amount": row["amount"],
                 "category": mask(categories[row["label"]]),
                 "review_status": row["review_status"]}
                for row in labeled if row["review_status"] == "verified"]
    groups = {}
    for txn in conn.execute("SELECT * FROM transactions ORDER BY txn_date, id"):
        category = (txn["category"] or "").strip()
        if (txn["direction"] != "out" or txn["is_transfer"]
                or txn["source"] == "settlement" or category == "Settlement"):
            continue
        if category and category != "Other":
            continue
        raw = mask(txn["description"])
        key = wp23.normalize(raw)
        group = groups.setdefault(key, {
            "normalized_merchant": key, "count": 0, "total_cents": 0,
            "first_date": txn["txn_date"], "last_date": txn["txn_date"],
            "txn_ids": [], "merchant_variants": set()})
        group["count"] += 1
        group["txn_ids"].append(f"L{txn['id']}")
        group["total_cents"] += txn["amount_cents"]
        group["first_date"] = min(group["first_date"], txn["txn_date"])
        group["last_date"] = max(group["last_date"], txn["txn_date"])
        group["merchant_variants"].add(raw)
    backlog = sorted(groups.values(), key=lambda group: (-group["count"],
                                                        group["normalized_merchant"]))
    for group in backlog:
        hits = known.get(group["normalized_merchant"], {})
        group["known_label"] = mask(next(iter(hits))) if len(hits) == 1 else ""
        group["labeled_count"] = sum(hits.values())
        group["txn_ids"] = json.dumps(group["txn_ids"])
        group["merchant_variants"] = json.dumps(sorted(group["merchant_variants"]),
                                                ensure_ascii=False)
    return backlog, verified, counts


def write(out_dir, backlog, verified):
    """Refuse Git/worktrees, symlink output, and every existing output folder."""
    requested = Path(out_dir).expanduser()
    if requested.is_symlink():
        raise ValueError("refusing symlink output; use a fresh folder")
    out = requested.resolve()
    if any((parent / ".git").exists() for parent in (out, *out.parents)):
        raise ValueError("financial reports must be written outside Git repositories")
    if out.exists():
        raise ValueError("refusing existing output; use a fresh folder")
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    for name, columns, rows in (("backlog.csv", BACKLOG_COLUMNS, backlog),
                                ("verified.csv", VERIFIED_COLUMNS, verified)):
        with (out / name).open("x", newline="", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="offline SQLite snapshot, never finance.db")
    parser.add_argument("--out", required=True, help="fresh private folder OUTSIDE Git")
    args = parser.parse_args(argv)
    conn = wp1.open_readonly(args.db)
    try:
        version = wp1.check_schema(conn)
        backlog, verified, counts = build(conn)
    finally:
        conn.close()
    write(args.out, backlog, verified)
    hinted = sum(1 for group in backlog if group["known_label"])
    print(f"schema_version={version} merchants={len(backlog)} hinted={hinted} "
          f"verified={len(verified)}")
    for key in sorted(counts):
        print(f"  {key}={counts[key]}")


if __name__ == "__main__":
    main()
