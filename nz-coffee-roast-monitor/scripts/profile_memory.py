#!/usr/bin/env python3
"""Maintain user memory for coffee preferences and order events."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS catalog (
            sku TEXT PRIMARY KEY,
            roaster TEXT,
            name TEXT,
            brew_methods TEXT,
            roast_level TEXT,
            flavor_tags TEXT,
            price_nzd REAL,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            sku TEXT,
            grams INTEGER,
            ordered_at TEXT
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            sku TEXT,
            rating INTEGER,
            note TEXT,
            created_at TEXT
        );
        """
    )
    conn.commit()


def ingest_catalog(conn: sqlite3.Connection, input_path: str) -> int:
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if "sku" not in row:
                continue
            conn.execute(
                """
                INSERT INTO catalog (sku, roaster, name, brew_methods, roast_level, flavor_tags, price_nzd, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sku) DO UPDATE SET
                  roaster=excluded.roaster,
                  name=excluded.name,
                  brew_methods=excluded.brew_methods,
                  roast_level=excluded.roast_level,
                  flavor_tags=excluded.flavor_tags,
                  price_nzd=excluded.price_nzd,
                  updated_at=excluded.updated_at
                """,
                (
                    row["sku"],
                    row.get("roaster"),
                    row.get("name"),
                    json.dumps(row.get("brew_methods", [])),
                    row.get("roast_level", "unknown"),
                    json.dumps(row.get("flavor_tags", [])),
                    row.get("price_nzd"),
                    now,
                ),
            )
            inserted += 1
    conn.commit()
    return inserted


def record_feedback(conn: sqlite3.Connection, user_id: str, sku: str, rating: int, note: str) -> None:
    conn.execute(
        "INSERT INTO feedback(user_id, sku, rating, note, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, sku, rating, note, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def recommend(conn: sqlite3.Connection, user_id: str, limit: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT f.rating, c.brew_methods, c.roast_level, c.flavor_tags
        FROM feedback f JOIN catalog c ON c.sku = f.sku
        WHERE f.user_id = ?
        """,
        (user_id,),
    ).fetchall()
    brew_pref: Counter[str] = Counter()
    roast_pref: Counter[str] = Counter()
    tag_pref: Counter[str] = Counter()

    for row in rows:
        weight = max(row["rating"], 1)
        for m in json.loads(row["brew_methods"] or "[]"):
            brew_pref[m] += weight
        roast_pref[row["roast_level"]] += weight
        for tag in json.loads(row["flavor_tags"] or "[]"):
            tag_pref[tag] += weight

    all_catalog = conn.execute("SELECT * FROM catalog").fetchall()
    scored = []
    for c in all_catalog:
        score = 0
        methods = json.loads(c["brew_methods"] or "[]")
        tags = json.loads(c["flavor_tags"] or "[]")
        score += sum(brew_pref[m] for m in methods)
        score += roast_pref[c["roast_level"]]
        score += sum(tag_pref[t] for t in tags)
        scored.append({"sku": c["sku"], "name": c["name"], "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init")
    init.add_argument("--db", required=True)

    ingest = sub.add_parser("ingest-catalog")
    ingest.add_argument("--db", required=True)
    ingest.add_argument("--input", required=True)

    feedback = sub.add_parser("feedback")
    feedback.add_argument("--db", required=True)
    feedback.add_argument("--user", required=True)
    feedback.add_argument("--sku", required=True)
    feedback.add_argument("--rating", required=True, type=int)
    feedback.add_argument("--note", default="")

    rec = sub.add_parser("recommend")
    rec.add_argument("--db", required=True)
    rec.add_argument("--user", required=True)
    rec.add_argument("--limit", default=10, type=int)

    return parser.parse_args()


def main() -> None:
    args = cli()
    conn = connect(args.db)

    if args.cmd == "init":
        init_db(conn)
        print("initialized")
    elif args.cmd == "ingest-catalog":
        init_db(conn)
        count = ingest_catalog(conn, args.input)
        print(f"ingested {count}")
    elif args.cmd == "feedback":
        init_db(conn)
        record_feedback(conn, args.user, args.sku, args.rating, args.note)
        print("feedback recorded")
    elif args.cmd == "recommend":
        init_db(conn)
        print(json.dumps(recommend(conn, args.user, args.limit), indent=2))


if __name__ == "__main__":
    main()
