"""
WEEK 2 -- the pipeline, now with retrieval.

Difference from skeleton.py: the schema is no longer hardcoded. We
search ChromaDB for the tables most relevant to the question and send
only those.

That is limitation L1 solved -- the one InfoTech Assistant lists in
their own paper ("full schema embedded in prompt limits scalability").

Before you run this:
    python make_big_db.py     # 63-table database
    python indexer.py         # build the index

Run:
    python week2.py
    python week2.py "which customers ordered more than twice?"
    python week2.py --compare      # shows retrieval vs full schema
"""

import hashlib
import os
import re
import sqlite3
import sys
import time

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

from config import CONFIG
from indexer import compact_schema, get_tables
from llm import call_llm

load_dotenv()

PROMPT = """You are a SQL expert working with a SQLite database.

Available tables:
{schema}

Question: {question}

Rules:
- Return ONLY the SQL query. No explanation, no markdown fences.
- Use only the tables and columns listed above.
- The query must be a SELECT statement.

SQL:"""


# --------------------------------------------------------- retrieval

_collection = None


def get_collection():
    """Opens the index once and reuses it."""
    global _collection
    if _collection is None:
        cl = chromadb.PersistentClient(path=CONFIG["index_path"])
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=CONFIG["embedding_model"]
        )
        _collection = cl.get_collection("schema_index", embedding_function=ef)
    return _collection


def retrieve_tables(question, k=None):
    """
    Returns [(table_name, distance)] for the k best tables.

    Distance is 1 - cosine_similarity, so LOWER is a better match.

    We over-fetch (3x k), then sort so that POPULATED tables come before
    empty ones. An empty table can never answer a question, so even if it
    scores slightly better on wording, a populated table is the right
    pick. This directly fixed our biggest failure mode: retrieval was
    handing the model empty invoice/shipment tables instead of the
    populated customer/order tables. Week 7 (hybrid BM25) improves the
    ranking further.
    """
    k = k or CONFIG["top_k_tables"]
    res = get_collection().query(
        query_texts=[question], n_results=min(k * 3, 40))

    ids = res["ids"][0]
    dists = res["distances"][0]
    metas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(ids)

    rows = []
    for name, dist, meta in zip(ids, dists, metas):
        empty = bool(meta.get("empty", False))
        rows.append((name, dist, empty))

    # populated first (empty=False sorts before True), then by distance
    rows.sort(key=lambda r: (r[2], r[1]))
    return [(name, dist) for name, dist, _ in rows[:k]]




def clean_sql(raw):
    raw = re.sub(r"```(?:sql)?", "", raw).strip()
    m = re.search(r"\b(SELECT|WITH)\b", raw, re.IGNORECASE)
    if m:
        raw = raw[m.start():]
    return raw.rstrip(";").strip()


# ------------------------------------------------------------ pipeline

def build_schema_text(conn, question):
    """
    The heart of Week 2.

    Flag ON  -> retrieve the relevant few tables
    Flag OFF -> dump every table (the baseline our ablation compares to)
    """
    if CONFIG["use_schema_retrieval"]:
        hits = retrieve_tables(question)
        if CONFIG["verbose"]:
            print("  retrieved:")
            for name, dist in hits:
                print(f"    {name:14} distance {dist:.3f}")
        tables = [name for name, _ in hits]
    else:
        tables = get_tables(conn)

    return "\n".join(compact_schema(conn, t) for t in tables), len(tables)


def ask(question, conn):
    schema_text, n_tables = build_schema_text(conn, question)
    prompt = PROMPT.format(schema=schema_text, question=question)

    # rough token estimate: ~4 characters per token
    approx_tokens = len(prompt) // 4

    sql = clean_sql(call_llm(prompt))

    if CONFIG["verbose"]:
        print(f"  schema sent: {n_tables} tables, ~{approx_tokens} tokens")
        print(f"  SQL: {sql}")

    cur = conn.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    return rows, cols, sql, approx_tokens


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


# ---------------------------------------------------------------- main

DEMO_QUESTIONS = [
    "who are our top customers by total spend?",
    "how many orders were placed in July 2025?",
    "which product category earns the most revenue?",
    "list customers from Maharashtra",     # still fails -- Week 4 fixes it
]


def compare(conn):
    """
    Side by side: retrieval on vs off. This produces the first two rows
    of the Week 9 ablation table.
    """
    q = "who are our top customers by total spend?"
    print(f"\nQ: {q}\n")

    for flag in (False, True):
        CONFIG["use_schema_retrieval"] = flag
        CONFIG["verbose"] = False
        label = "retrieval ON " if flag else "full schema  "
        try:
            _, _, _, tok = ask(q, conn)
            n = CONFIG["top_k_tables"] if flag else len(get_tables(conn))
            print(f"  {label}  {n:3} tables  ~{tok:6} tokens")
        except Exception as e:
            print(f"  {label}  FAILED: {str(e)[:60]}")

    CONFIG["verbose"] = True


def main():
    db = "data/big.db"
    if not os.path.exists(db):
        sys.exit("data/big.db missing -- run: python make_big_db.py")
    if not os.path.exists(CONFIG["index_path"]):
        sys.exit("index missing -- run: python indexer.py")
    # provider/key validation now lives in llm.py

    CONFIG["use_schema_retrieval"] = True      # Week 2 turns this on
    conn = sqlite3.connect(db)

    if "--compare" in sys.argv:
        compare(conn)
        conn.close()
        return

    questions = [a for a in sys.argv[1:] if not a.startswith("--")] \
        or DEMO_QUESTIONS

    for q in questions:
        print(f"\n{'=' * 60}\nQ: {q}")
        try:
            rows, cols, _, _ = ask(q, conn)
            show(rows, cols)
        except Exception as e:
            print(f"  FAILED: {e}")

    conn.close()


if __name__ == "__main__":
    main()