"""
WEEK 7 -- compare vector retrieval vs hybrid BM25 retrieval.

No LLM calls.
"""

import sqlite3

from config import CONFIG
from week2 import (
    retrieve_tables_vector,
    retrieve_tables_hybrid,
)

DB = "data/big.db"

QUESTIONS = [
    {
        "id": "r01",
        "q": "Which customer spent the most in total?",
        "expected": {"cust_mst", "ord_txn"},
    },
    {
        "id": "r02",
        "q": "How many delivered orders are there?",
        "expected": {"ord_txn"},
    },
    {
        "id": "r03",
        "q": "List all customers from Maharashtra.",
        "expected": {"cust_mst"},
    },
    {
        "id": "r04",
        "q": "Which products have been ordered?",
        "expected": {"prod_mst", "ord_txn"},
    },
]


def get_rank(names, table):
    try:
        return names.index(table) + 1
    except ValueError:
        return None


def main():

    conn = sqlite3.connect(DB)

    print("=" * 70)
    print("WEEK 7 HYBRID RETRIEVAL COMPARISON")
    print("=" * 70)

    for item in QUESTIONS:

        question = item["q"]

        vector_hits = retrieve_tables_vector(
            question,
            k=8,
        )

        hybrid_hits = retrieve_tables_hybrid(
            conn,
            question,
            k=8,
        )

        vector_names = [
            table
            for table, _ in vector_hits
        ]

        hybrid_names = [
            hit["table"]
            for hit in hybrid_hits
        ]

        print(f"\n{item['id']} — {question}")

        print("\nVECTOR ONLY:")

        for i, (table, distance) in enumerate(
            vector_hits,
            start=1,
        ):
            marker = "*" if table in item["expected"] else " "

            print(
                f"  {marker} {i}. "
                f"{table:14} "
                f"distance={distance:.3f}"
            )

        print("\nHYBRID:")

        for i, hit in enumerate(
            hybrid_hits,
            start=1,
        ):
            table = hit["table"]

            marker = "*" if table in item["expected"] else " "

            print(
                f"  {marker} {i}. "
                f"{table:14} "
                f"hybrid={hit['score']:.3f} "
                f"vector={hit['vector']:.3f} "
                f"bm25={hit['bm25']:.3f}"
            )

        print("\nEXPECTED TABLE RANKS:")

        for table in sorted(item["expected"]):

            vector_rank = get_rank(
                vector_names,
                table,
            )

            hybrid_rank = get_rank(
                hybrid_names,
                table,
            )

            print(
                f"  {table:14} "
                f"vector={vector_rank} "
                f"hybrid={hybrid_rank}"
            )

    conn.close()


if __name__ == "__main__":
    main()