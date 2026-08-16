"""
WEEK 2 + WEEK 4 INDEXER

Builds two ChromaDB collections:

1. schema_index
   Used to retrieve relevant tables.

2. value_index
   Used to retrieve database values / coded meanings.

Examples:
    Maharashtra -> cust_mst.st_cd = 'MH'
    electronics -> prod_mst.cat_cd = 'ELEC'
    delivered   -> ord_txn.stat_cd = 3
"""

import os
import sqlite3
import sys

import chromadb
from chromadb.utils import embedding_functions

from config import CONFIG
from value_mappings import VALUE_ALIASES


# ------------------------------------------------------------
# Schema enrichment dictionary
# ------------------------------------------------------------

GLOSS = {
    "cust": "customer",
    "mst": "master",
    "ord": "order",
    "txn": "transaction",
    "prod": "product",
    "emp": "employee",
    "rec": "record",
    "nm": "name",
    "cd": "code",
    "dt": "date",
    "amt": "amount",
    "qty": "quantity",
    "st": "state",
    "stat": "status",
    "inv": "invoice",
    "ln": "line",
    "pay": "payment",
    "ship": "shipment",
    "ret": "return",
    "wh": "warehouse",
    "stk": "stock",
    "mov": "movement",
    "supp": "supplier",
    "po": "purchase order",
    "grn": "goods receipt",
    "dept": "department",
    "desig": "designation",
    "attn": "attendance",
    "hdr": "header",
    "sal": "salary",
    "appr": "appraisal",
    "cat": "category",
    "disc": "discount",
    "promo": "promotion",
    "cpn": "coupon",
    "rev": "review",
    "tkt": "ticket",
    "msg": "message",
    "addr": "address",
    "regn": "region",
    "cntry": "country",
    "curr": "currency",
    "rt": "rate",
    "led": "ledger",
    "acct": "account",
    "bank": "bank",
    "asset": "asset",
    "veh": "vehicle",
    "fuel": "fuel",
    "usr": "user",
    "perm": "permission",
    "audit": "audit",
    "cfg": "config",
    "prm": "parameter",
    "notif": "notification",
    "eml": "email",
    "sms": "sms",
    "stg": "staging",
    "err": "error",
    "crtd": "created",
    "prc": "price",
    "unit": "unit",
    "city": "city",
    "brand": "brand",
    "budget": "budget",
    "trip": "trip",
    "route": "route",
    "role": "role",
    "job": "job",
    "sched": "schedule",
}


def humanize(token):
    """cust_nm -> customer name"""
    words = []

    for frag in token.split("_"):
        words.append(GLOSS.get(frag, frag))

    return " ".join(words)


# ------------------------------------------------------------
# Schema extraction
# ------------------------------------------------------------

def get_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()

    return [r[0] for r in rows]


def describe_table(conn, table):
    """
    Natural-language description used for schema embeddings.
    """

    cols = conn.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()

    human_table = humanize(table)

    col_human = ", ".join(
        humanize(c[1]) for c in cols
    )

    desc = (
        f"{human_table}. "
        f"{human_table} table. "
        f"Stores {human_table} records. "
        f"Columns: {col_human}."
    )

    n = conn.execute(
        f'SELECT COUNT(*) FROM "{table}"'
    ).fetchone()[0]

    if n == 0:
        desc += " (currently empty, no data)."
    else:
        desc += f" ({n} rows of data)."

    return desc


def compact_schema(conn, table):
    """
    Compact form sent to the LLM.

    Example:
        cust_mst(cust_id, cust_nm, st_cd)
    """

    cols = conn.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()

    names = ", ".join(c[1] for c in cols)

    return f"{table}({names})"


# ------------------------------------------------------------
# Week 4 -- value indexing
# ------------------------------------------------------------

def should_index_column(table, column, col_type):
    """
    Decide whether a column is suitable for value retrieval.

    We normally index TEXT columns with low cardinality.

    Numeric coded columns such as stat_cd are included only when
    they have an explicit entry in VALUE_ALIASES.
    """

    lower = column.lower()
    col_type = (col_type or "").upper()

    # Never index obvious identifier columns.
    if lower == "id" or lower.endswith("_id"):
        return False

    # Avoid dates/timestamps.
    if (
        lower.endswith("_dt")
        or "date" in lower
        or "time" in lower
        or lower.endswith("_tm")
    ):
        return False

    # Explicit business glossary mapping always wins.
    has_alias = any(
        t == table and c == column
        for t, c, _ in VALUE_ALIASES
    )

    if has_alias:
        return True

    # Otherwise automatically index text columns.
    if "TEXT" in col_type:
        return True

    return False


def value_aliases(table, column, value):
    """
    Get human-readable aliases for one stored value.
    """

    key = (table, column, str(value))

    return VALUE_ALIASES.get(key, [])


def extract_values(conn):
    """
    Extract distinct low-cardinality database values.

    Returns dictionaries containing:
        table
        column
        value
        aliases
        value_type
    """

    records = []

    cardinality_limit = CONFIG["value_cardinality_limit"]

    for table in get_tables(conn):

        # Empty filler tables have nothing useful to index.
        row_count = conn.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()[0]

        if row_count == 0:
            continue

        columns = conn.execute(
            f'PRAGMA table_info("{table}")'
        ).fetchall()

        for col in columns:

            column = col[1]
            col_type = col[2] or ""

            if not should_index_column(
                table,
                column,
                col_type,
            ):
                continue

            count = conn.execute(
                f'''
                SELECT COUNT(DISTINCT "{column}")
                FROM "{table}"
                WHERE "{column}" IS NOT NULL
                '''
            ).fetchone()[0]

            if count == 0:
                continue

            if count > cardinality_limit:
                continue

            values = conn.execute(
                f'''
                SELECT DISTINCT "{column}"
                FROM "{table}"
                WHERE "{column}" IS NOT NULL
                '''
            ).fetchall()

            for row in values:

                value = row[0]

                aliases = value_aliases(
                    table,
                    column,
                    value,
                )

                records.append({
                    "table": table,
                    "column": column,
                    "value": value,
                    "aliases": aliases,
                    "value_type": col_type,
                })

    return records


def value_document(record):
    """
    Text embedded into ChromaDB.

    Example:

    order transaction status code.
    Natural-language meaning: delivered.
    Stored database value: 3.
    """

    table = record["table"]
    column = record["column"]
    value = record["value"]
    aliases = record["aliases"]

    table_words = humanize(table)
    column_words = humanize(column)

    pieces = [
        f"{table_words} {column_words}.",
        f"Database column {table}.{column}.",
        f"Stored database value: {value}.",
    ]

    if aliases:
        pieces.append(
            "Natural language meaning: "
            + ", ".join(aliases)
            + "."
        )
    else:
        pieces.append(
            f"Natural language value: {value}."
        )

    return " ".join(pieces)


def build_value_index(
    conn,
    client,
    embedding_function,
    reset=True,
):
    """
    Build Week 4 Chroma collection.
    """

    if reset:
        try:
            client.delete_collection("value_index")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        "value_index",
        embedding_function=embedding_function,
    )

    records = extract_values(conn)

    if not records:
        return 0

    documents = []
    ids = []
    metadatas = []

    for i, record in enumerate(records):

        documents.append(
            value_document(record)
        )

        ids.append(
            f"value_{i}"
        )

        metadatas.append({
            "table": record["table"],
            "column": record["column"],
            "value": str(record["value"]),
            "value_type": record["value_type"],
            "aliases": " | ".join(record["aliases"]),
        })

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    return len(records)


# ------------------------------------------------------------
# Build both indexes
# ------------------------------------------------------------

def build_index(
    db_path,
    index_path=None,
    reset=True,
):
    index_path = index_path or CONFIG["index_path"]

    conn = sqlite3.connect(db_path)

    tables = get_tables(conn)

    descriptions = [
        describe_table(conn, t)
        for t in tables
    ]

    client = chromadb.PersistentClient(
        path=index_path
    )

    ef = (
        embedding_functions
        .SentenceTransformerEmbeddingFunction(
            model_name=CONFIG["embedding_model"]
        )
    )

    # ---------------- schema index ----------------

    if reset:
        try:
            client.delete_collection(
                "schema_index"
            )
        except Exception:
            pass

    counts = [
        conn.execute(
            f'SELECT COUNT(*) FROM "{t}"'
        ).fetchone()[0]
        for t in tables
    ]

    metadatas = [
        {
            "rows": count,
            "empty": count == 0,
        }
        for count in counts
    ]

    schema_collection = (
        client.get_or_create_collection(
            "schema_index",
            embedding_function=ef,
        )
    )

    schema_collection.add(
        documents=descriptions,
        ids=tables,
        metadatas=metadatas,
    )

    # ---------------- value index ----------------

    value_count = build_value_index(
        conn,
        client,
        ef,
        reset=reset,
    )

    conn.close()

    return len(tables), value_count


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():

    db = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "data/big.db"
    )

    if not os.path.exists(db):
        sys.exit(
            f"{db} not found -- "
            "run: python make_big_db.py"
        )

    print(f"indexing {db} ...")

    table_count, value_count = build_index(db)

    print(
        f"indexed {table_count} tables "
        f"into {CONFIG['index_path']}"
    )

    print(
        f"indexed {value_count} distinct values "
        "into value_index"
    )

    conn = sqlite3.connect(db)

    print(
        "\nexample enriched description "
        "(cust_mst):"
    )

    print(
        "  " + describe_table(
            conn,
            "cust_mst",
        )
    )

    conn.close()


if __name__ == "__main__":
    main()