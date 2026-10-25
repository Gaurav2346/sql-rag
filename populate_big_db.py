"""Fill every table in data/big.db to at least 5,000 realistic demo rows.

Existing records are preserved. The script is safe to rerun: it only adds the
rows needed to bring each table up to the target count.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from demo_cache import refresh_demo_answers


DB_PATH = Path(__file__).resolve().parent / "data" / "big.db"
TARGET_ROWS = 5_000
CORE_TARGETS = {
    "cust_mst": 5_000,
    "prod_mst": 3_000,
    "ord_txn": 12_000,
    "emp_rec": 1_500,
    "st_mst": TARGET_ROWS,
}
DATE_START = date(2020, 1, 1)
STATES = [
    ("MH", "Maharashtra", "WEST", ["Mumbai", "Pune", "Nagpur", "Nashik"]),
    ("KA", "Karnataka", "SOUTH", ["Bengaluru", "Mysuru", "Mangaluru"]),
    ("TN", "Tamil Nadu", "SOUTH", ["Chennai", "Coimbatore", "Madurai"]),
    ("DL", "Delhi", "NORTH", ["New Delhi", "Dwarka", "Rohini"]),
    ("GJ", "Gujarat", "WEST", ["Ahmedabad", "Surat", "Vadodara"]),
    ("UP", "Uttar Pradesh", "NORTH", ["Lucknow", "Kanpur", "Noida"]),
]
FIRST_NAMES = ["Aarav", "Anaya", "Ishaan", "Diya", "Kabir", "Meera", "Rohan", "Sara"]
LAST_NAMES = ["Sharma", "Patel", "Iyer", "Reddy", "Verma", "Nair", "Das", "Khan"]
PRODUCTS = [
    ("Laptop", "ELEC", 62000.0), ("Wireless Mouse", "ACCS", 799.0),
    ("Office Chair", "FURN", 8500.0), ("LED Monitor", "ELEC", 11500.0),
    ("Mechanical Keyboard", "ACCS", 4200.0), ("Desk Lamp", "FURN", 1800.0),
    ("USB-C Hub", "ELEC", 3200.0), ("Headphones", "ACCS", 5600.0),
]
DEPARTMENTS = ["SALES", "TECH", "OPS", "FINANCE", "SUPPORT", "HR"]
STATUSES = [1, 2, 3, 3, 3, 4]


def iso_date(index: int, offset_days: int = 0, total: int = TARGET_ROWS) -> str:
    """Spread generated dates evenly from 2020-01-01 through today."""
    today = date.today()
    span_days = (today - DATE_START).days
    position = (index + offset_days) % max(total, 1)
    day_offset = round(position * span_days / max(total - 1, 1))
    return (DATE_START + timedelta(days=day_offset)).isoformat()


def table_columns(conn: sqlite3.Connection, table: str) -> list[tuple[str, str, int]]:
    return [
        (row[1], row[2].upper(), row[5])
        for row in conn.execute(f'PRAGMA table_info("{table}")')
    ]


def ids_for(conn: sqlite3.Connection, table: str, column: str) -> list[object]:
    try:
        return [row[0] for row in conn.execute(f'SELECT "{column}" FROM "{table}"')]
    except sqlite3.OperationalError:
        return []


def append_rows(conn: sqlite3.Connection, table: str, columns: list[str], rows: list[tuple]) -> None:
    quoted_cols = ", ".join(f'"{name}"' for name in columns)
    marks = ", ".join("?" for _ in columns)
    conn.executemany(f'INSERT INTO "{table}" ({quoted_cols}) VALUES ({marks})', rows)


def fill_core_table(conn: sqlite3.Connection, table: str, missing: int) -> None:
    if missing <= 0:
        return
    if table == "cust_mst":
        start = conn.execute("SELECT COALESCE(MAX(cust_id), 100) FROM cust_mst").fetchone()[0] + 1
        rows = []
        for i in range(missing):
            state, _, _, cities = STATES[i % len(STATES)]
            name = f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[(i // len(FIRST_NAMES)) % len(LAST_NAMES)]} {start + i}"
            rows.append((start + i, name, state, cities[(i // len(STATES)) % len(cities)], iso_date(i, total=missing)))
        append_rows(conn, table, ["cust_id", "cust_nm", "st_cd", "city_nm", "crtd_dt"], rows)
    elif table == "prod_mst":
        start = conn.execute("SELECT COALESCE(MAX(prod_id), 0) FROM prod_mst").fetchone()[0] + 1
        rows = []
        for i in range(missing):
            base_name, category, price = PRODUCTS[i % len(PRODUCTS)]
            rows.append((start + i, f"{base_name} Model {start + i}", category, round(price * (0.85 + (i % 31) / 100), 2)))
        append_rows(conn, table, ["prod_id", "prod_nm", "cat_cd", "unit_prc"], rows)
    elif table == "emp_rec":
        start = conn.execute("SELECT COALESCE(MAX(emp_id), 0) FROM emp_rec").fetchone()[0] + 1
        rows = []
        for i in range(missing):
            name = f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[(i // len(FIRST_NAMES)) % len(LAST_NAMES)]} {start + i}"
            rows.append((start + i, name, DEPARTMENTS[i % len(DEPARTMENTS)], 42_000 + (i % 16) * 6_500, iso_date(i, total=missing)))
        append_rows(conn, table, ["emp_id", "emp_nm", "dept_cd", "sal", "join_dt"], rows)
    elif table == "ord_txn":
        customer_ids = ids_for(conn, "cust_mst", "cust_id")
        products = list(conn.execute("SELECT prod_id, unit_prc FROM prod_mst ORDER BY prod_id"))
        start = conn.execute("SELECT COALESCE(MAX(ord_id), 5000) FROM ord_txn").fetchone()[0] + 1
        rows = []
        for i in range(missing):
            customer_id = customer_ids[i % len(customer_ids)]
            product_id, unit_price = products[(i * 7) % len(products)]
            qty = 1 + (i % 8)
            amount = round(float(unit_price) * qty, 2)
            rows.append((start + i, customer_id, product_id, qty, amount, iso_date(i, total=missing), STATUSES[i % len(STATUSES)]))
        append_rows(conn, table, ["ord_id", "cust_id", "prod_id", "qty", "amt", "ord_dt", "stat_cd"], rows)
    elif table == "st_mst":
        rows = []
        start = conn.execute("SELECT COUNT(*) FROM st_mst").fetchone()[0]
        for i in range(missing):
            state, name, region, _ = STATES[i % len(STATES)]
            rows.append((f"{state}{start + i:04d}", f"{name} Demo Zone {start + i + 1}", region))
        append_rows(conn, table, ["st_cd", "st_nm", "regn_cd"], rows)


def generic_value(
    table: str,
    column: str,
    row_index: int,
    own_id_column: str,
    reference_ids: dict[str, list[object]],
) -> str:
    name = column.lower()
    if column == own_id_column:
        return str(row_index + 1)

    reference_tables = {
        "cust_id": "cust_mst", "prod_id": "prod_mst", "ord_id": "ord_txn",
        "emp_id": "emp_rec", "supp_id": "supp_mst", "inv_id": "inv_hdr",
        "pay_id": "pay_txn", "ship_id": "ship_hdr", "po_id": "po_hdr",
        "grn_id": "grn_hdr", "wh_id": "wh_mst", "tkt_id": "tkt_hdr",
        "cart_id": "cart_hdr", "promo_id": "promo_mst", "veh_id": "veh_mst",
        "job_id": "job_sched", "usr_id": "usr_mst", "trip_id": "trip_log",
    }
    target = reference_tables.get(name)
    if target and reference_ids.get(target):
        ids = reference_ids[target]
        return str(ids[(row_index * 13) % len(ids)])

    if name in {"st_cd", "state_code"}:
        return STATES[row_index % len(STATES)][0]
    if name in {"regn_cd", "region", "region_cd"}:
        return ["WEST", "SOUTH", "NORTH", "EAST"][row_index % 4]
    if name in {"cntry_cd", "country_cd"}:
        return ["IN", "US", "SG", "AE"][row_index % 4]
    if name in {"cat_cd", "category"}:
        return PRODUCTS[row_index % len(PRODUCTS)][1]
    if name in {"dept_cd", "department"}:
        return DEPARTMENTS[row_index % len(DEPARTMENTS)]
    if name in {"role_cd"}:
        return ["ADMIN", "ANALYST", "MANAGER", "STAFF"][row_index % 4]
    if name in {"stat_cd", "status", "proc_flg", "sent_flg", "actv_flg", "can_rd", "can_wr"}:
        return str([1, 2, 3, 1, 1, 0][row_index % 6])
    if name.endswith(("_dt", "_ts")) or name in {"eff_dt", "valid_to", "att_dt", "recv_dt", "fill_dt", "sent_dt", "last_run"}:
        return iso_date(row_index, len(table))
    if name.endswith("_tm"):
        return f"{8 + row_index % 10:02d}:{(row_index * 7) % 60:02d}:00"
    if any(token in name for token in ("amt", "price", "rate", "sal", "budget", "gross", "ded", "net", "spent", "alloc", "wdv", "litres", "dist", "rating", "pct", "cap", "on_hand", "qty", "grade", "lvl", "min_sal")):
        if "rating" in name:
            return str(1 + row_index % 5)
        if "pct" in name:
            return str(5 + row_index % 35)
        if "qty" in name or "units" in name or "on_hand" in name:
            return str(1 + row_index % 500)
        return str(round(500 + (row_index * 173 % 250_000) / 100, 2))
    if name == "raw_json":
        return json.dumps({"source": "demo_seed", "table": table, "row": row_index + 1})
    if "email" in name or name == "to_addr":
        return f"contact{row_index + 1}@example.test"
    if "mob_no" in name:
        return f"9{row_index % 10}{(row_index * 7919) % 100_000_000:08d}"
    if "gstin" in name:
        return f"27DEMO{row_index + 1:09d}Z1"
    if "pin_cd" in name:
        return f"{100000 + row_index % 899999}"
    if "city" in name or name.startswith("frm_city") or name.startswith("to_city"):
        return STATES[row_index % len(STATES)][3][(row_index // 3) % len(STATES[row_index % len(STATES)][3])]
    if "nm" in name or "name" in name:
        if "emp" in table or name.startswith("hod"):
            return f"{FIRST_NAMES[row_index % len(FIRST_NAMES)]} {LAST_NAMES[(row_index // 8) % len(LAST_NAMES)]}"
        return f"{table.replace('_', ' ').title()} {row_index + 1:05d}"
    if name in {"cron_exp"}:
        return f"{row_index % 60} {row_index % 24} * * *"
    if name in {"mode_cd", "mov_typ", "sender_typ", "prio_cd", "chnl_cd", "acct_typ", "carrier_cd", "typ_cd", "rsn_cd", "lv_typ", "res_cd", "curr_cd", "cntry_cd", "actn", "tbl_nm", "subj", "line1", "body", "cmnt", "trk_no", "reg_no", "ref_no", "src_file", "modu_cd", "prm_cd", "prm_val", "to_city", "frm_city", "strt_ts", "end_ts", "last_run", "upd_dt", "mth", "fy", "cyc_yr"}:
        return f"{name.replace('_', ' ').title()} {row_index + 1:05d}"
    if name.endswith("_cd"):
        return f"{name[: -3].upper()}{row_index % 20:02d}"
    if name.endswith("_id"):
        return str(row_index + 1)
    return f"{table}_{name}_{row_index + 1:05d}"


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}. Run make_big_db.py first.")

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        if not tables:
            raise SystemExit("No application tables found in data/big.db")

        # Shrink the three requested fixed-size dimensions first. Repoint
        # dependent dummy records before deleting their referenced rows.
        for table, key_column in (("cust_mst", "cust_id"), ("prod_mst", "prod_id"), ("emp_rec", "emp_id")):
            if table not in tables:
                continue
            target = CORE_TARGETS[table]
            current = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            if current <= target:
                continue
            keep_ids = [row[0] for row in conn.execute(
                f'SELECT "{key_column}" FROM "{table}" ORDER BY "{key_column}" LIMIT ?',
                (target,),
            )]
            keep_set = {int(value) for value in keep_ids}
            ref_column = {"cust_mst": "cust_id", "prod_mst": "prod_id", "emp_rec": "emp_id"}[table]
            for ref_table in tables:
                if ref_table == table:
                    continue
                ref_cols = {column for column, _, _ in table_columns(conn, ref_table)}
                if ref_column not in ref_cols:
                    continue
                distinct_values = [row[0] for row in conn.execute(
                    f'SELECT DISTINCT "{ref_column}" FROM "{ref_table}" WHERE "{ref_column}" IS NOT NULL'
                )]
                for old_value in distinct_values:
                    try:
                        numeric_value = int(old_value)
                    except (TypeError, ValueError):
                        continue
                    if numeric_value in keep_set:
                        continue
                    new_value = keep_ids[(numeric_value - 1) % len(keep_ids)]
                    if ref_table == "ord_txn" and ref_column == "prod_id":
                        conn.execute(
                            "UPDATE ord_txn SET prod_id=?, amt=qty * "
                            "(SELECT unit_prc FROM prod_mst WHERE prod_id=?) WHERE prod_id=?",
                            (new_value, new_value, old_value),
                        )
                    else:
                        conn.execute(
                            f'UPDATE "{ref_table}" SET "{ref_column}"=? WHERE "{ref_column}"=?',
                            (new_value, old_value),
                        )
            conn.execute(
                f'DELETE FROM "{table}" WHERE "{key_column}" NOT IN '
                f'(SELECT "{key_column}" FROM "{table}" ORDER BY "{key_column}" LIMIT ?)',
                (target,),
            )

        # Grow the core tables to their requested totals so every generated
        # foreign-key reference points to an existing record.
        for table in ("cust_mst", "prod_mst", "emp_rec", "ord_txn", "st_mst"):
            if table in tables:
                count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                target = CORE_TARGETS.get(table, TARGET_ROWS)
                fill_core_table(conn, table, max(0, target - count))

        conn.commit()
        reference_columns = {
            "cust_mst": "cust_id", "prod_mst": "prod_id", "ord_txn": "ord_id",
            "emp_rec": "emp_id", "supp_mst": "supp_id", "inv_hdr": "inv_id",
            "pay_txn": "pay_id", "ship_hdr": "ship_id", "po_hdr": "po_id",
            "grn_hdr": "grn_id", "wh_mst": "wh_id", "tkt_hdr": "tkt_id",
            "cart_hdr": "cart_id", "promo_mst": "promo_id", "veh_mst": "veh_id",
            "job_sched": "job_id", "usr_mst": "usr_id", "trip_log": "trip_id",
        }
        reference_ids = {
            parent: ids_for(conn, parent, column)
            for parent, column in reference_columns.items()
            if parent in tables
        }

        for table in tables:
            if table in {"cust_mst", "prod_mst", "emp_rec", "ord_txn", "st_mst"}:
                continue
            count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            missing = max(0, TARGET_ROWS - count)
            if not missing:
                continue
            info = table_columns(conn, table)
            columns = [column for column, _, _ in info]
            own_id = next((column for column, _, pk in info if pk), columns[0])
            rows = [
                tuple(generic_value(table, column, count + i, own_id, reference_ids) for column in columns)
                for i in range(missing)
            ]
            append_rows(conn, table, columns, rows)

        # Normalize generated dates across the large mock tables to the full
        # requested window. Keep the hand-entered starter rows unchanged.
        date_columns = {"eff_dt", "valid_to", "att_dt", "recv_dt", "fill_dt", "sent_dt", "last_run"}
        for table in tables:
            for column, _, _ in table_columns(conn, table):
                if not (column.endswith(("_dt", "_ts")) or column in date_columns):
                    continue
                if table in {"cust_mst", "ord_txn", "emp_rec"}:
                    key_column = {"cust_mst": "cust_id", "ord_txn": "ord_id", "emp_rec": "emp_id"}[table]
                    generated_floor = {"cust_mst": 110, "ord_txn": 5011, "emp_rec": 5}[table]
                    ids = [row[0] for row in conn.execute(
                        f'SELECT "{key_column}" FROM "{table}" WHERE "{key_column}" >= ? ORDER BY "{key_column}"',
                        (generated_floor,),
                    )]
                    for i, row_id in enumerate(ids):
                        conn.execute(
                            f'UPDATE "{table}" SET "{column}"=? WHERE "{key_column}"=?',
                            (iso_date(i, total=len(ids)), row_id),
                        )
                else:
                    row_ids = [row[0] for row in conn.execute(f'SELECT rowid FROM "{table}" ORDER BY rowid')]
                    for i, row_id in enumerate(row_ids):
                        conn.execute(
                            f'UPDATE "{table}" SET "{column}"=? WHERE rowid=?',
                            (iso_date(i, total=len(row_ids)), row_id),
                        )

        # Add indexes used by joins and the dashboard's common filters.
        for table in tables:
            for column, _, _ in table_columns(conn, table):
                if column.endswith(("_id", "_cd", "_dt")):
                    index_name = f"idx_{table}_{column}"
                    conn.execute(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table}"("{column}")')
        conn.commit()

        # Keep exact-match demo answers aligned with the newly seeded database.
        refresh_demo_answers(conn)
        conn.commit()

        counts = [(table, conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]) for table in tables]
        under_target = [
            (table, count) for table, count in counts
            if count < CORE_TARGETS.get(table, TARGET_ROWS)
        ]
        print(f"Updated {DB_PATH} ({len(tables)} tables).")
        print("Core table counts:")
        for table in ("cust_mst", "prod_mst", "ord_txn", "emp_rec"):
            print(f"  {table:10} {dict(counts)[table]:,}")
        print(f"Other table counts: {min(count for table, count in counts if table not in CORE_TARGETS):,}–{max(count for table, count in counts if table not in CORE_TARGETS):,}.")
        print(f"Total rows: {sum(count for _, count in counts):,}.")
        print("All tables meet the 5,000 row target." if not under_target else f"Below target: {under_target}")
        print("Saved demo answers refreshed from the expanded database.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
