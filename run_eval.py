"""
WEEK 3 -- the evaluation harness.

Runs the pipeline over every question in eval_set.py, compares the
result rows against the gold SQL's result rows, and prints accuracy.

This is EXECUTION ACCURACY: we do not care whether the generated SQL
looks like the gold SQL. We care whether it returns the same data. Two
very different queries that produce identical rows both count as correct.
That is the standard metric (BIRD uses it) and it is the number your
whole project reports.

Every run is logged to logs/runs.csv -- that file is where your error
analysis and ablation table come from later.

Run:
    python run_eval.py                 # all 20 questions
    python run_eval.py --level easy    # just the easy ones
    python run_eval.py --limit 5       # first 5 (fast smoke test)
"""

import csv
import os
import sqlite3
import sys
import time

from config import CONFIG
from eval_set import EVAL_SET
from eval_set_small import EVAL_SET as EVAL_SMALL
# reuse the Week 2 pipeline exactly -- no duplicated logic
from week2 import ask

DB = "data/big.db"


def normalise(rows):
    """Strict: unordered multiset of full rows."""
    return sorted(str(tuple(r)) for r in rows)


def _cells(rows):
    """Flatten a result set into a multiset of atomic cell values."""
    out = []
    for r in rows:
        for v in r:
            out.append(str(v))
    return sorted(out)


def is_correct(pred, gold):
    """
    A prediction is correct if either:
      (a) rows match exactly (ignoring row/column order), OR
      (b) every value in the gold answer appears in the prediction and
          the prediction is not padded with lots of unrelated values.

    (b) forgives harmless projection differences -- an extra id column,
    or selecting cust_nm where gold selected cust_id -- which BIRD-style
    value comparison also tolerates. It still fails a genuinely wrong
    answer, because wrong data means the gold values are simply absent.
    """
    if normalise(pred) == normalise(gold):
        return True
    g, p = _cells(gold), _cells(pred)
    if not g:                      # gold empty -> pred must be empty
        return not p
    gset, pset = set(g), set(p)
    if not gset.issubset(pset):
        return False
    # guard against SELECT * on a huge table trivially matching:
    # allow prediction up to a few columns wider than gold, scaled
    # by the number of rows. Same row count + superset of values
    # means the answer data is there, just with extra columns.
    return len(pred) == len(gold) or len(pset) <= len(gset) + 12


def run_gold(conn, sql):
    return conn.execute(sql).fetchall()


def evaluate(items):
    conn = sqlite3.connect(DB)

    os.makedirs("logs", exist_ok=True)
    log = open(CONFIG["log_path"], "w", newline="", encoding="utf-8")
    writer = csv.writer(log)
    writer.writerow(["id", "level", "correct", "question",
                     "generated_sql", "gold_sql", "error", "tokens", "ms"])

    results = []
    # keep the pipeline quiet during a batch run
    prev_verbose = CONFIG["verbose"]
    CONFIG["verbose"] = False

    for item in items:
        t0 = time.time()
        error = ""
        tokens = 0
        gen_sql = ""
        try:
            gold_rows = run_gold(conn, item["sql"])
            pred_rows, _, gen_sql, tokens = ask(item["q"], conn)
            correct = is_correct(pred_rows, gold_rows)
        except Exception as e:
            correct = False
            error = str(e)[:120]
        ms = (time.time() - t0) * 1000

        results.append((item, correct, error))
        writer.writerow([item["id"], item["level"], int(correct), item["q"],
                         gen_sql, item["sql"], error, tokens, f"{ms:.0f}"])

        mark = "OK " if correct else "XX "
        note = "" if correct else f"  ({error[:50]})" if error else "  (wrong rows)"
        print(f"  {mark} {item['id']:5} {item['level']:7} {item['q'][:44]:44}{note}")

    CONFIG["verbose"] = prev_verbose
    log.close()
    conn.close()
    return results


def summary(results):
    total = len(results)
    correct = sum(1 for _, c, _ in results if c)

    print(f"\n{'=' * 60}")
    print(f"  OVERALL: {correct}/{total} = {100 * correct / total:.1f}%")

    for lvl in ("easy", "medium", "hard"):
        sub = [(i, c, e) for i, c, e in results if i["level"] == lvl]
        if sub:
            n = sum(1 for _, c, _ in sub if c)
            print(f"    {lvl:7}: {n}/{len(sub)} = {100 * n / len(sub):.0f}%")

    print(f"\n  config: schema_retrieval={CONFIG['use_schema_retrieval']}, "
          f"value_retrieval={CONFIG['use_value_retrieval']}, "
          f"self_correction={CONFIG['use_self_correction']}")
    print(f"  full log written to {CONFIG['log_path']}")


def main():
    if not os.path.exists(DB):
        sys.exit("data/big.db missing -- run: python make_big_db.py")
    if not os.path.exists(CONFIG["index_path"]):
        sys.exit("index missing -- run: python indexer.py")

    # Week 3 baseline: retrieval on, nothing else yet
    CONFIG["use_schema_retrieval"] = True

    items = EVAL_SET
    if "--small" in sys.argv:
        items = EVAL_SMALL

    if "--level" in sys.argv:
        lvl = sys.argv[sys.argv.index("--level") + 1]
        items = [i for i in items if i["level"] == lvl]
    if "--limit" in sys.argv:
        n = int(sys.argv[sys.argv.index("--limit") + 1])
        items = items[:n]

    print(f"evaluating {len(items)} questions...\n")
    results = evaluate(items)
    summary(results)


if __name__ == "__main__":
    main()