"""
WEEK 5 -- controlled self-correction test.

We deliberately start with broken SQL:

    SELECT customer_name FROM cust_mst

The real column is:

    cust_nm

SQLite should return:
    no such column: customer_name

The self-correction loop should give this error to the LLM,
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


def main():

    question = "List all customer names."

    broken_sql = (
        "SELECT customer_name "
        "FROM cust_mst"
    )

    conn = sqlite3.connect(DB)

    CONFIG["use_schema_retrieval"] = True
    CONFIG["use_value_retrieval"] = False
    CONFIG["use_self_correction"] = True
    CONFIG["verbose"] = True

    schema_text, _, tables = build_schema_text(
        conn,
        question,
    )

    value_hits = []

    if CONFIG["use_value_retrieval"]:
        value_hits = retrieve_values(
            question,
            allowed_tables=tables,
        )

    values_text = format_value_context(
        value_hits
    )

    print("\n" + "=" * 60)
    print("WEEK 5 CONTROLLED SELF-CORRECTION TEST")
    print("=" * 60)

    print(f"\nQuestion: {question}")
    print(f"Initial broken SQL: {broken_sql}\n")

    try:

        rows, cols, final_sql, retries = (
            execute_with_correction(
                conn=conn,
                question=question,
                sql=broken_sql,
                schema_text=schema_text,
                values_text=values_text,
            )
        )

        print("\n" + "=" * 60)
        print("RESULT")
        print("=" * 60)

        print(f"Final SQL: {final_sql}")
        print(f"Retries: {retries}")
        print(f"Rows returned: {len(rows)}")
        print(f"Columns: {cols}")

        print("\nFirst few rows:")

        for row in rows[:5]:
            print(" ", row)

        print("\nWEEK 5 SELF-CORRECTION: PASS")

    except Exception as e:

        print("\nWEEK 5 SELF-CORRECTION: FAIL")
        print(f"Error: {e}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()