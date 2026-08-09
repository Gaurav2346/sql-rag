"""
WEEK 1 -- the walking skeleton.  (Gemini version)

Setup:
    pip install openai python-dotenv
    create a file named .env containing:
        GEMINI_API_KEY=your-key-here

Run:
    python skeleton.py
    python skeleton.py "which customers ordered more than twice?"
"""

import hashlib
import os
import re
import sqlite3
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

from config import CONFIG

load_dotenv()

# Gemini exposes an OpenAI-compatible endpoint, so we keep the openai
# package and just point it at Google's servers.
client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

# Week 2 replaces this hardcoded string with ChromaDB retrieval.
SCHEMA = """
cust_mst(cust_id INTEGER PK, cust_nm TEXT, st_cd TEXT, city_nm TEXT, crtd_dt TEXT)
prod_mst(prod_id INTEGER PK, prod_nm TEXT, cat_cd TEXT, unit_prc REAL)
ord_txn(ord_id INTEGER PK, cust_id INTEGER FK, prod_id INTEGER FK, qty INTEGER, amt REAL, ord_dt TEXT, stat_cd INTEGER)
emp_rec(emp_id INTEGER PK, emp_nm TEXT, dept_cd TEXT, sal REAL, join_dt TEXT)
"""

PROMPT = """You are a SQL expert working with a SQLite database.

Available tables:
{schema}

Question: {question}

Rules:
- Return ONLY the SQL query. No explanation, no markdown fences.
- Use only the tables and columns listed above.
- The query must be a SELECT statement.

SQL:"""


def _cache_path(prompt):
    key = hashlib.md5(prompt.encode()).hexdigest()
    return os.path.join("cache", f"{key}.txt")


def call_llm(prompt):
    if CONFIG["cache_llm"]:
        path = _cache_path(prompt)
        if os.path.exists(path):
            return open(path, encoding="utf-8").read()

    resp = client.chat.completions.create(
        model=CONFIG["llm_model"],
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    out = resp.choices[0].message.content.strip()

    if CONFIG["cache_llm"]:
        os.makedirs("cache", exist_ok=True)
        with open(_cache_path(prompt), "w", encoding="utf-8") as f:
            f.write(out)
    return out


def clean_sql(raw):
    raw = re.sub(r"```(?:sql)?", "", raw).strip()
    m = re.search(r"\b(SELECT|WITH)\b", raw, re.IGNORECASE)
    if m:
        raw = raw[m.start():]
    return raw.rstrip(";").strip()


def ask(question, conn):
    prompt = PROMPT.format(schema=SCHEMA.strip(), question=question)

    t0 = time.time()
    sql = clean_sql(call_llm(prompt))
    gen_ms = (time.time() - t0) * 1000

    if CONFIG["verbose"]:
        print(f"\n  generated in {gen_ms:.0f} ms")
        print(f"  SQL: {sql}")

    cur = conn.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return rows, cols, sql


def show(rows, cols):
    if not rows:
        print("  (no rows)")
        return
    widths = [max(len(str(c)), max(len(str(r[i])) for r in rows))
              for i, c in enumerate(cols)]
    header = "  " + " | ".join(str(c).ljust(w) for c, w in zip(cols, widths))
    print(header)
    print("  " + "-" * (len(header) - 2))
    for r in rows[:20]:
        print("  " + " | ".join(str(v).ljust(w) for v, w in zip(r, widths)))
    if len(rows) > 20:
        print(f"  ... {len(rows) - 20} more rows")


DEMO_QUESTIONS = [
    "who are our top customers by total spend?",
    "how many orders were placed in July 2025?",
    "which product category earns the most revenue?",
    "the interesting failure: user says Maharashtra, column stores 'MH'"
    "list customers from Maharashtra",
]


def main():
    if not os.path.exists(CONFIG["db_path"]):
        sys.exit("data/demo.db missing -- run: python setup_db.py")
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY missing -- create a .env file")

    conn = sqlite3.connect(CONFIG["db_path"])

    questions = sys.argv[1:] or DEMO_QUESTIONS
    for q in questions:
        print(f"\n{'=' * 60}\nQ: {q}")
        try:
            rows, cols, _ = ask(q, conn)
            show(rows, cols)
        except Exception as e:
            print(f"  FAILED: {e}")

    conn.close()


if __name__ == "__main__":
    main()