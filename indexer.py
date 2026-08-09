"""
WEEK 2 -- schema indexing.  (v2: enriched descriptions)

Turns a database into a searchable index. Runs once, offline.

    PRAGMA  ->  ENRICHED description  ->  embedding  ->  ChromaDB

Why "enriched": cryptic column names like cust_nm share no words with
a question like "who are our customers". The embedding model then has
nothing to match on and retrieval fails. We expand abbreviations into
human words so the description actually mentions "customer", "order",
etc. This is a standard RAG technique (enriching the index), not a hack,
and it is worth a sentence in the report.

Run:  python indexer.py            (indexes data/big.db)
      python indexer.py data/demo.db
"""

import os
import sqlite3
import sys

import chromadb
from chromadb.utils import embedding_functions

from config import CONFIG

# Maps common abbreviation fragments to the words a human would use.
# Extend this freely -- more coverage means better retrieval.
GLOSS = {
    "cust": "customer", "mst": "master", "ord": "order", "txn": "transaction",
    "prod": "product", "emp": "employee", "rec": "record", "nm": "name",
    "cd": "code", "dt": "date", "amt": "amount", "qty": "quantity",
    "st": "state", "stat": "status", "inv": "invoice", "ln": "line",
    "pay": "payment", "ship": "shipment", "ret": "return", "wh": "warehouse",
    "stk": "stock", "mov": "movement", "supp": "supplier", "po": "purchase order",
    "grn": "goods receipt", "dept": "department", "desig": "designation",
    "attn": "attendance", "hdr": "header", "sal": "salary", "appr": "appraisal",
    "cat": "category", "disc": "discount", "promo": "promotion",
    "cpn": "coupon", "rev": "review", "tkt": "ticket", "msg": "message",
    "addr": "address", "regn": "region", "cntry": "country", "curr": "currency",
    "rt": "rate", "led": "ledger", "acct": "account", "bank": "bank",
    "asset": "asset", "veh": "vehicle", "fuel": "fuel", "usr": "user",
    "perm": "permission", "audit": "audit", "cfg": "config", "prm": "parameter",
    "notif": "notification", "eml": "email", "sms": "sms", "stg": "staging",
    "err": "error", "crtd": "created", "prc": "price", "unit": "unit",
    "city": "city", "brand": "brand", "budget": "budget", "trip": "trip",
    "route": "route", "role": "role", "job": "job", "sched": "schedule",
}


def humanize(token):
    """cust_nm -> 'customer name'. Splits on _, expands each fragment."""
    words = []
    for frag in token.split("_"):
        words.append(GLOSS.get(frag, frag))
    return " ".join(words)


# --------------------------------------------------------- extraction

def get_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [r[0] for r in rows]


def describe_table(conn, table):
    """
    Enriched description written for the embedding model.

    Includes the human-readable table name and human-readable column
    names, so a question phrased in plain English can match it.
    """
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()

    human_table = humanize(table)
    col_human = ", ".join(humanize(c[1]) for c in cols)

    # Lead with the human name (embeddings weight early tokens), repeat it,
    # then list human-readable columns. We deliberately DO NOT include the
    # raw cryptic column names -- they add noise and pull the embedding
    # away from the plain-English words a question uses.
    desc = (f"{human_table}. {human_table} table. "
            f"Stores {human_table} records. "
            f"Columns: {col_human}.")

    # Row-count hint. A table with no rows cannot answer any question,
    # so we note it. build_index also stores this in metadata so the
    # retriever can push empty tables down or filter them entirely.
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    if n == 0:
        desc += " (currently empty, no data)."
    else:
        desc += f" ({n} rows of data)."
    return desc


def compact_schema(conn, table):
    """Terse form for the LLM prompt: table(col, col, col)."""
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return f"{table}({', '.join(c[1] for c in cols)})"


# ----------------------------------------------------------- indexing

def build_index(db_path, index_path=None, reset=True):
    index_path = index_path or CONFIG["index_path"]
    conn = sqlite3.connect(db_path)
    tables = get_tables(conn)
    descriptions = [describe_table(conn, t) for t in tables]

    client = chromadb.PersistentClient(path=index_path)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=CONFIG["embedding_model"]
    )

    if reset:
        try:
            client.delete_collection("schema_index")
        except Exception:
            pass

    counts = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in tables]
    metadatas = [{"rows": c, "empty": c == 0} for c in counts]

    col = client.get_or_create_collection("schema_index", embedding_function=ef)
    col.add(documents=descriptions, ids=tables, metadatas=metadatas)
    conn.close()
    return len(tables)


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "data/big.db"
    if not os.path.exists(db):
        sys.exit(f"{db} not found -- run: python make_big_db.py")

    print(f"indexing {db} ...")
    n = build_index(db)
    print(f"indexed {n} tables into {CONFIG['index_path']}")

    conn = sqlite3.connect(db)
    print("\nexample enriched description (cust_mst):")
    print("  " + describe_table(conn, "cust_mst"))
    conn.close()


if __name__ == "__main__":
    main()