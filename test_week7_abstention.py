"""
WEEK 7 -- abstention calibration.

No LLM calls.

Goal:
Compare retrieval confidence for:
1. clear database questions
2. ambiguous / out-of-domain questions

We will choose the abstention threshold AFTER seeing these scores.
"""

from config import CONFIG

from week2 import (
    retrieve_tables_vector,
    should_abstain,
)

TESTS = [
    # -------------------------------------------------
    # CLEAR / ANSWERABLE
    # -------------------------------------------------
    {
        "id": "clear01",
        "q": "How many customers do we have?",
        "expected": "ANSWER",
    },
    {
        "id": "clear02",
        "q": "List all customers from Maharashtra.",
        "expected": "ANSWER",
    },
    {
        "id": "clear03",
        "q": "How many delivered orders are there?",
        "expected": "ANSWER",
    },
    {
        "id": "clear04",
        "q": "Which customer spent the most in total?",
        "expected": "ANSWER",
    },
    {
        "id": "clear05",
        "q": "Which products have been ordered?",
        "expected": "ANSWER",
    },

    # -------------------------------------------------
    # AMBIGUOUS / OUT OF DOMAIN
    # -------------------------------------------------
    {
        "id": "bad01",
        "q": "What is the weather today?",
        "expected": "ABSTAIN",
    },
    {
        "id": "bad02",
        "q": "Who is the Prime Minister of India?",
        "expected": "ABSTAIN",
    },
    {
        "id": "bad03",
        "q": "Tell me a joke.",
        "expected": "ABSTAIN",
    },
    {
        "id": "bad04",
        "q": "Show me the best ones.",
        "expected": "ABSTAIN",
    },
    {
        "id": "bad05",
        "q": "What should I eat for dinner?",
        "expected": "ABSTAIN",
    },
]


def main():

    print("=" * 72)
    print("WEEK 7 ABSTENTION CALIBRATION")
    print("=" * 72)

    for item in TESTS:

        hits = retrieve_tables_vector(
            item["q"],
            k=3,
        )

        top1_table, top1_distance = hits[0]

        if len(hits) > 1:
            top2_table, top2_distance = hits[1]

            margin = (
                top2_distance
                -
                top1_distance
            )

        else:
            top2_table = "-"
            top2_distance = 999
            margin = 0

        print(
            f"\n{item['id']} "
            f"[{item['expected']}]"
        )

        print(
            f"  Question: {item['q']}"
        )

        print(
            f"  Top 1: "
            f"{top1_table:14} "
            f"distance={top1_distance:.3f}"
        )

        print(
            f"  Top 2: "
            f"{top2_table:14} "
            f"distance={top2_distance:.3f}"
        )

        print(
            f"  Margin: {margin:.3f}"
        )

        abstain, distance, reason = should_abstain(
            item["q"]
        )

        predicted = (
            "ABSTAIN"
            if abstain
            else "ANSWER"
        )

        correct = (
            predicted
            ==
            item["expected"]
        )

        print(
            f"  Decision: "
            f"{predicted} "
            f"{'OK' if correct else 'XX'}"
        )


if __name__ == "__main__":
    main()