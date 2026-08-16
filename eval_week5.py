"""
WEEK 5 -- self-correction ablation test.

Tests the execution-feedback mechanism with intentionally broken SQL.

OFF:
    broken SQL should fail.

ON:
    SQLite error should be fed back to the LLM,
    which should repair the SQL.
"""

import sqlite3

from config import CONFIG
from week2 import (
    build_schema_text,
    format_value_context,
    retrieve_values,
    execute_with_correction,
)

DB = "data/big.db"


TESTS = [
    {
        "id": "sc01",
        "question": "List all customer names.",
        "broken_sql": "SELECT customer_name FROM cust_mst",
        "gold_sql": "SELECT cust_nm FROM cust_mst",
    },
    {
        "id": "sc02",
        "question": "How many orders are there?",
        "broken_sql": "SELECT COUNT(*) FROM orders",
        "gold_sql": "SELECT COUNT(*) FROM ord_txn",
    },
]


def normalize(rows):
    return sorted(str(tuple(r)) for r in rows)


def run_one(conn, item):

    schema_text, _, tables = build_schema_text(
        conn,
        item["question"],
    )

    value_hits = []

    if CONFIG["use_value_retrieval"]:
        value_hits = retrieve_values(
            item["question"],
            allowed_tables=tables,
        )

    values_text = format_value_context(
        value_hits
    )

    gold_rows = conn.execute(
        item["gold_sql"]
    ).fetchall()

    try:

        rows, _, final_sql, retries = (
            execute_with_correction(
                conn=conn,
                question=item["question"],
                sql=item["broken_sql"],
                schema_text=schema_text,
                values_text=values_text,
            )
        )

        correct = (
            normalize(rows)
            ==
            normalize(gold_rows)
        )

        return {
            "correct": correct,
            "final_sql": final_sql,
            "retries": retries,
            "error": "",
        }

    except Exception as e:

        return {
            "correct": False,
            "final_sql": "",
            "retries": 0,
            "error": str(e),
        }


def main():

    conn = sqlite3.connect(DB)

    CONFIG["use_schema_retrieval"] = True
    CONFIG["use_value_retrieval"] = False
    CONFIG["verbose"] = False

    print("=" * 60)
    print("WEEK 5 SELF-CORRECTION ABLATION")
    print("=" * 60)

    for flag in (False, True):

        CONFIG["use_self_correction"] = flag

        print(
            f"\nself_correction={flag}"
        )

        passed = 0

        for item in TESTS:

            result = run_one(
                conn,
                item,
            )

            mark = (
                "OK"
                if result["correct"]
                else "XX"
            )

            print(
                f"  {mark} {item['id']} "
                f"{item['question']}"
            )

            if result["final_sql"]:
                print(
                    f"     final SQL: "
                    f"{result['final_sql']}"
                )

            if result["error"]:
                print(
                    f"     error: "
                    f"{result['error']}"
                )

            print(
                f"     retries: "
                f"{result['retries']}"
            )

            if result["correct"]:
                passed += 1

        print(
            f"\n  SCORE: "
            f"{passed}/{len(TESTS)}"
        )

    conn.close()


if __name__ == "__main__":
    main()