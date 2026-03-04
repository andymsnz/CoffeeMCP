#!/usr/bin/env python3
"""Maintain user memory for coffee preferences, stock-aware recommendations, and watchlists."""

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
            in_stock INTEGER DEFAULT 1,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            sku TEXT,
            grams INTEGER,
            price_nzd REAL,
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
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            sku TEXT,
            reason TEXT,
            created_at TEXT,
            UNIQUE(user_id, sku)
        );
        """
    )
    try:
        conn.execute("ALTER TABLE catalog ADD COLUMN in_stock INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN price_nzd REAL")
    except sqlite3.OperationalError:
        pass
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
                INSERT INTO catalog (sku, roaster, name, brew_methods, roast_level, flavor_tags, price_nzd, in_stock, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sku) DO UPDATE SET
                  roaster=excluded.roaster,
                  name=excluded.name,
                  brew_methods=excluded.brew_methods,
                  roast_level=excluded.roast_level,
                  flavor_tags=excluded.flavor_tags,
                  price_nzd=excluded.price_nzd,
                  in_stock=excluded.in_stock,
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
                    1 if row.get("in_stock", True) else 0,
                    now,
                ),
            )
            inserted += 1
    conn.commit()
    return inserted


def record_order(conn: sqlite3.Connection, user_id: str, sku: str, grams: int, price_nzd: float | None = None, ordered_at: str | None = None) -> None:
    ts = ordered_at or datetime.now(timezone.utc).isoformat()
    if price_nzd is None:
        row = conn.execute("SELECT price_nzd FROM catalog WHERE sku = ?", (sku,)).fetchone()
        if row is not None:
            price_nzd = row[0]
    conn.execute(
        "INSERT INTO orders(user_id, sku, grams, price_nzd, ordered_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, sku, grams, price_nzd, ts),
    )
    conn.commit()


def list_orders(conn: sqlite3.Connection, user_id: str, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        """
        SELECT o.id, o.user_id, o.sku, c.name, c.roaster, o.grams, o.price_nzd, o.ordered_at
        FROM orders o LEFT JOIN catalog c ON c.sku = o.sku
        WHERE o.user_id = ?
        ORDER BY o.ordered_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def record_feedback(conn: sqlite3.Connection, user_id: str, sku: str, rating: int, note: str) -> None:
    conn.execute(
        "INSERT INTO feedback(user_id, sku, rating, note, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, sku, rating, note, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def add_watchlist(conn: sqlite3.Connection, user_id: str, sku: str, reason: str) -> None:
    conn.execute(
        """
        INSERT INTO watchlist(user_id, sku, reason, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, sku) DO UPDATE SET
          reason=excluded.reason,
          created_at=excluded.created_at
        """,
        (user_id, sku, reason, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def list_watchlist(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT w.sku, c.name, c.roaster, c.in_stock, w.reason, w.created_at
        FROM watchlist w LEFT JOIN catalog c ON c.sku = w.sku
        WHERE w.user_id = ?
        ORDER BY w.created_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def recommend(conn: sqlite3.Connection, user_id: str, limit: int, include_oos: bool = False) -> list[dict]:
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

    if include_oos:
        all_catalog = conn.execute("SELECT * FROM catalog").fetchall()
    else:
        all_catalog = conn.execute("SELECT * FROM catalog WHERE in_stock = 1").fetchall()

    scored = []
    for c in all_catalog:
        score = 0
        methods = json.loads(c["brew_methods"] or "[]")
        tags = json.loads(c["flavor_tags"] or "[]")
        score += sum(brew_pref[m] for m in methods)
        score += roast_pref[c["roast_level"]]
        score += sum(tag_pref[t] for t in tags)
        score += 1 if c["in_stock"] else -5
        scored.append(
            {
                "sku": c["sku"],
                "name": c["name"],
                "roaster": c["roaster"],
                "in_stock": bool(c["in_stock"]),
                "score": score,
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]



def monthly_summary(conn: sqlite3.Connection, user_id: str, month: str | None = None) -> dict:
    """Return monthly totals for spend and grams, plus average cost per bag."""
    if month:
        ym = month
    else:
        ym = datetime.now(timezone.utc).strftime("%Y-%m")
    rows = conn.execute(
        """
        SELECT grams, COALESCE(price_nzd, 0) AS price_nzd
        FROM orders
        WHERE user_id = ? AND substr(ordered_at, 1, 7) = ?
        """,
        (user_id, ym),
    ).fetchall()
    total_grams = sum((r[0] or 0) for r in rows)
    total_cost = round(sum((r[1] or 0) for r in rows), 2)
    bag_count = len(rows)
    avg_bag_cost = round(total_cost / bag_count, 2) if bag_count else 0
    cost_per_250g = round((total_cost / total_grams) * 250, 2) if total_grams else 0
    return {
        "month": ym,
        "orders": bag_count,
        "total_grams": total_grams,
        "total_cost_nzd": total_cost,
        "avg_bag_cost_nzd": avg_bag_cost,
        "cost_per_250g_nzd": cost_per_250g,
    }

def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init")
    init.add_argument("--db", required=True)

    ingest = sub.add_parser("ingest-catalog")
    ingest.add_argument("--db", required=True)
    ingest.add_argument("--input", required=True)

    order_add = sub.add_parser("order-add")
    order_add.add_argument("--db", required=True)
    order_add.add_argument("--user", required=True)
    order_add.add_argument("--sku", required=True)
    order_add.add_argument("--grams", required=True, type=int)
    order_add.add_argument("--price-nzd", default=None, type=float, help="Optional explicit order price")
    order_add.add_argument("--ordered-at", default="", help="ISO timestamp (optional)")

    order_list = sub.add_parser("order-list")
    order_list.add_argument("--db", required=True)
    order_list.add_argument("--user", required=True)
    order_list.add_argument("--limit", default=20, type=int)

    monthly = sub.add_parser("monthly-summary")
    monthly.add_argument("--db", required=True)
    monthly.add_argument("--user", required=True)
    monthly.add_argument("--month", default="", help="YYYY-MM (default current month)")

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
    rec.add_argument("--include-oos", action="store_true", help="Include out-of-stock items")

    wl_add = sub.add_parser("watchlist-add")
    wl_add.add_argument("--db", required=True)
    wl_add.add_argument("--user", required=True)
    wl_add.add_argument("--sku", required=True)
    wl_add.add_argument("--reason", default="user requested")

    wl_list = sub.add_parser("watchlist-list")
    wl_list.add_argument("--db", required=True)
    wl_list.add_argument("--user", required=True)

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
    elif args.cmd == "order-add":
        init_db(conn)
        record_order(conn, args.user, args.sku, args.grams, args.price_nzd, args.ordered_at or None)
        print("order recorded")
    elif args.cmd == "order-list":
        init_db(conn)
        print(json.dumps(list_orders(conn, args.user, args.limit), indent=2))
    elif args.cmd == "monthly-summary":
        init_db(conn)
        print(json.dumps(monthly_summary(conn, args.user, args.month or None), indent=2))
    elif args.cmd == "feedback":
        init_db(conn)
        record_feedback(conn, args.user, args.sku, args.rating, args.note)
        print("feedback recorded")
    elif args.cmd == "recommend":
        init_db(conn)
        print(json.dumps(recommend(conn, args.user, args.limit, include_oos=args.include_oos), indent=2))
    elif args.cmd == "watchlist-add":
        init_db(conn)
        add_watchlist(conn, args.user, args.sku, args.reason)
        print("watchlist updated")
    elif args.cmd == "watchlist-list":
        init_db(conn)
        print(json.dumps(list_watchlist(conn, args.user), indent=2))


if __name__ == "__main__":
    main()
