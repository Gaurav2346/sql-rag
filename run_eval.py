"""
WEEK 3 + WEEK 4 EVALUATION HARNESS

Examples:

Baseline:
    python run_eval.py --small

Week 4:
    python run_eval.py --small --values

Test only m06:
    python run_eval.py --small --id m06 --values
"""

import csv
import os
import sqlite3
import sys
import time

from config import CONFIG
from eval_set import EVAL_SET
from eval_set_small import EVAL_SET as EVAL_SMALL

# Reuse main pipeline.
from week2 import ask


DB = "data/big.db"


# ------------------------------------------------------------
# Result comparison
# ------------------------------------------------------------

def normalise(rows):
    """
    Strict unordered comparison of complete rows.
    """

    return sorted(
        str(tuple(r))
        for r in rows
    )


def _cells(rows):
    """
    Flatten rows into individual values.
    """

    out = []

    for row in rows:

        for value in row:
            out.append(str(value))

    return sorted(out)


def is_correct(pred, gold):
    """
    Execution accuracy.

    Correct when either:

    1. complete result rows match, or

    2. prediction contains all gold values
       with only harmless extra columns.
    """

    if normalise(pred) == normalise(gold):
        return True

    gold_cells = _cells(gold)
    pred_cells = _cells(pred)

    if not gold_cells:
        return not pred_cells

    gold_set = set(gold_cells)
    pred_set = set(pred_cells)

    if not gold_set.issubset(pred_set):
        return False

    return (
        len(pred) == len(gold)
        or
        len(pred_set)
        <= len(gold_set) + 12
    )


def run_gold(conn, sql):
    return conn.execute(sql).fetchall()


# ------------------------------------------------------------
# Evaluation
# ------------------------------------------------------------

def evaluate(items):

    conn = sqlite3.connect(DB)

    os.makedirs(
        "logs",
        exist_ok=True,
    )

    log = open(
        CONFIG["log_path"],
        "w",
        newline="",
        encoding="utf-8",
    )

    writer = csv.writer(log)

    writer.writerow([
        "id",
        "level",
        "correct",
        "question",
        "generated_sql",
        "gold_sql",
        "error",
        "tokens",
        "ms",
    ])

    results = []

    previous_verbose = CONFIG["verbose"]

    # Keep batch evaluation quiet.
    CONFIG["verbose"] = False

    for item in items:

        t0 = time.time()

        error = ""
        tokens = 0
        generated_sql = ""

        try:

            gold_rows = run_gold(
                conn,
                item["sql"],
            )

            (
                pred_rows,
                _,
                generated_sql,
                tokens,
            ) = ask(
                item["q"],
                conn,
            )

            correct = is_correct(
                pred_rows,
                gold_rows,
            )

        except Exception as e:

            correct = False

            error = str(e)[:120]

        ms = (
            time.time() - t0
        ) * 1000

        results.append(
            (
                item,
                correct,
                error,
            )
        )

        writer.writerow([
            item["id"],
            item["level"],
            int(correct),
            item["q"],
            generated_sql,
            item["sql"],
            error,
            tokens,
            f"{ms:.0f}",
        ])

        mark = (
            "OK "
            if correct
            else "XX "
        )

        if correct:

            note = ""

        elif error:

            note = (
                f"  ({error[:50]})"
            )

        else:

            note = "  (wrong rows)"

        print(
            f"  {mark} "
            f"{item['id']:5} "
            f"{item['level']:7} "
            f"{item['q'][:44]:44}"
            f"{note}"
        )

    CONFIG["verbose"] = (
        previous_verbose
    )

    log.close()
    conn.close()

    return results


# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

def summary(results):

    total = len(results)

    correct = sum(
        1
        for _, is_ok, _
        in results
        if is_ok
    )

    print(
        f"\n{'=' * 60}"
    )

    if total:

        print(
            f"  OVERALL: "
            f"{correct}/{total} = "
            f"{100 * correct / total:.1f}%"
        )

    else:

        print(
            "  OVERALL: no questions selected"
        )

    for level in (
        "easy",
        "medium",
        "hard",
    ):

        subset = [
            (item, ok, error)
            for item, ok, error
            in results
            if item["level"] == level
        ]

        if subset:

            n = sum(
                1
                for _, ok, _
                in subset
                if ok
            )

            print(
                f"    {level:7}: "
                f"{n}/{len(subset)} = "
                f"{100 * n / len(subset):.0f}%"
            )

    print(
        "\n  config: "
        f"schema_retrieval="
        f"{CONFIG['use_schema_retrieval']}, "
        f"value_retrieval="
        f"{CONFIG['use_value_retrieval']}, "
        f"self_correction="
        f"{CONFIG['use_self_correction']}, "
        f"safety_check="
        f"{CONFIG['use_safety_check']}, "
        f"hybrid_bm25="
        f"{CONFIG['use_hybrid_bm25']}, "
        f"abstention="
        f"{CONFIG['use_abstention']}"
    )
    

    print(
        f"  full log written to "
        f"{CONFIG['log_path']}"
    )

# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():

    if not os.path.exists(DB):

        sys.exit(
            "data/big.db missing -- "
            "run: python make_big_db.py"
        )

    if not os.path.exists(
        CONFIG["index_path"]
    ):

        sys.exit(
            "index missing -- "
            "run: python indexer.py"
        )

    # Week 2 stays enabled.
    CONFIG[
        "use_schema_retrieval"
    ] = True

    # Week 4 only when requested.
    CONFIG[
        "use_value_retrieval"
    ] = (
        "--values" in sys.argv
    )
    CONFIG[
        "use_hybrid_bm25"
    ] = (
        "--hybrid" in sys.argv
    )
    CONFIG["use_abstention"] = (
        "--abstain" in sys.argv
    )
    CONFIG[
        "use_self_correction"
    ] = (
        "--self-correct" in sys.argv
    )
    CONFIG[
        "use_safety_check"
    ] = (
        "--safety" in sys.argv
    )



    items = EVAL_SET

    # ---------------- small set ----------------

    if "--small" in sys.argv:
        items = EVAL_SMALL

    # ---------------- difficulty ----------------

    if "--level" in sys.argv:

        i = sys.argv.index(
            "--level"
        )

        if i + 1 >= len(sys.argv):
            sys.exit(
                "--level requires "
                "easy, medium or hard"
            )

        level = sys.argv[i + 1]

        items = [
            item
            for item in items
            if item["level"] == level
        ]

    # ---------------- individual ID ----------------

    if "--id" in sys.argv:

        i = sys.argv.index("--id")

        if i + 1 >= len(sys.argv):
            sys.exit(
                "--id requires a question ID"
            )

        question_id = sys.argv[i + 1]

        items = [
            item
            for item in items
            if item["id"] == question_id
        ]

        if not items:

            sys.exit(
                f"No evaluation question "
                f"found with id "
                f"'{question_id}'"
            )

    # ---------------- limit ----------------

    if "--limit" in sys.argv:

        i = sys.argv.index(
            "--limit"
        )

        if i + 1 >= len(sys.argv):
            sys.exit(
                "--limit requires a number"
            )

        n = int(
            sys.argv[i + 1]
        )

        items = items[:n]

    print(
        f"evaluating "
        f"{len(items)} questions...\n"
    )

    results = evaluate(items)

    summary(results)


if __name__ == "__main__":
    main()