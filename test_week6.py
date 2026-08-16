"""
WEEK 6 -- SQL safety layer controlled test.

Tests:
- normal SELECT allowed
- CTE SELECT allowed
- DELETE blocked
- UPDATE blocked
- INSERT blocked
- DROP blocked
- multiple statements blocked

No LLM calls are needed.
"""

import sqlite3

from config import CONFIG
from week2 import (
    execute_sql,
    UnsafeSQLError,
)


DB = "data/big.db"


TESTS = [
    {
        "id": "safe01",
        "sql": "SELECT COUNT(*) FROM cust_mst",
        "should_pass": True,
    },
    {
        "id": "safe02",
        "sql": """
            WITH x AS (
                SELECT cust_id
                FROM cust_mst
            )
            SELECT COUNT(*)
            FROM x
        """,
        "should_pass": True,
    },
    {
        "id": "unsafe01",
        "sql": "DELETE FROM cust_mst",
        "should_pass": False,
    },
    {
        "id": "unsafe02",
        "sql": """
            UPDATE cust_mst
            SET cust_nm = 'HACKED'
            WHERE cust_id = 101
        """,
        "should_pass": False,
    },
    {
        "id": "unsafe03",
        "sql": """
            INSERT INTO cust_mst
            (cust_id, cust_nm)
            VALUES (999, 'Bad Row')
        """,
        "should_pass": False,
    },
    {
        "id": "unsafe04",
        "sql": "DROP TABLE cust_mst",
        "should_pass": False,
    },
    {
        "id": "unsafe05",
        "sql": """
            SELECT * FROM cust_mst;
            DELETE FROM cust_mst;
        """,
        "should_pass": False,
    },
]


def main():

    conn = sqlite3.connect(DB)

    CONFIG["use_safety_check"] = True
    CONFIG["use_self_correction"] = True
    CONFIG["verbose"] = False

    passed = 0

    print("=" * 60)
    print("WEEK 6 SQL SAFETY TEST")
    print("=" * 60)

    for item in TESTS:

        try:

            rows, cols = execute_sql(
                conn,
                item["sql"],
            )

            actual_pass = True
            error = ""

        except UnsafeSQLError as e:

            actual_pass = False
            error = str(e)

        except Exception as e:

            actual_pass = False
            error = str(e)

        correct = (
            actual_pass
            ==
            item["should_pass"]
        )

        mark = (
            "OK"
            if correct
            else "XX"
        )

        expected = (
            "ALLOW"
            if item["should_pass"]
            else "BLOCK"
        )

        actual = (
            "ALLOWED"
            if actual_pass
            else "BLOCKED"
        )

        print(
            f"\n  {mark} {item['id']}"
        )

        print(
            f"     expected: {expected}"
        )

        print(
            f"     actual:   {actual}"
        )

        if error:
            print(
                f"     reason:   {error}"
            )

        if correct:
            passed += 1

    print(
        "\n" + "=" * 60
    )

    print(
        f"SCORE: "
        f"{passed}/{len(TESTS)}"
    )

    conn.close()


if __name__ == "__main__":
    main()