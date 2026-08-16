"""
WEEK 2 + WEEK 4 PIPELINE

Pipeline:

question
    ↓
schema retrieval
    ↓
value retrieval (Week 4, optional)
    ↓
focused prompt
    ↓
LLM
    ↓
SQL
    ↓
SQLite execution
"""

import os
import re
import sqlite3
import sys
import sqlglot
import chromadb

from sqlglot import exp
from rank_bm25 import BM25Okapi
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

from config import CONFIG
from indexer import (
    compact_schema,
    describe_table,
    get_tables,
)
from llm import call_llm


load_dotenv()


PROMPT = """You are a SQL expert working with a SQLite database.

Available tables:
{schema}

Relevant database values:
{values}

Question: {question}

Rules:
- Return ONLY the SQL query. No explanation, no markdown fences.
- Use only the tables and columns listed above.
- The query must be a SELECT statement.
- When a relevant database value is provided, use the EXACT stored value shown.
- Do not replace encoded database values with their English meanings.

SQL:"""

CORRECTION_PROMPT = """You are correcting a SQLite query that failed during execution.

Available tables:
{schema}

Relevant database values:
{values}

Original question:
{question}

The SQL query that failed:
{sql}

SQLite returned this error:
{error}

Rules:
- Return ONLY the corrected SQL query.
- No explanation.
- No markdown fences.
- Use only the tables and columns listed above.
- The query must be a SELECT statement.
- Fix the database error using the SQLite error message.
- Preserve the user's original intent.
- When relevant database values are provided, use the EXACT stored value shown.

Corrected SQL:"""




# ------------------------------------------------------------
# Chroma collections
# ------------------------------------------------------------

_schema_collection = None
_value_collection = None
_embedding_function = None

_bm25 = None
_bm25_tables = None
_bm25_documents = None


def get_embedding_function():
    global _embedding_function

    if _embedding_function is None:
        _embedding_function = (
            embedding_functions
            .SentenceTransformerEmbeddingFunction(
                model_name=CONFIG[
                    "embedding_model"
                ]
            )
        )

    return _embedding_function


def get_collection():
    """
    Week 2 schema collection.
    """

    global _schema_collection

    if _schema_collection is None:

        client = chromadb.PersistentClient(
            path=CONFIG["index_path"]
        )

        _schema_collection = (
            client.get_collection(
                "schema_index",
                embedding_function=(
                    get_embedding_function()
                ),
            )
        )

    return _schema_collection


def get_value_collection():
    """
    Week 4 value collection.
    """

    global _value_collection

    if _value_collection is None:

        client = chromadb.PersistentClient(
            path=CONFIG["index_path"]
        )

        _value_collection = (
            client.get_collection(
                "value_index",
                embedding_function=(
                    get_embedding_function()
                ),
            )
        )

    return _value_collection


def bm25_tokenize(text):
    """
    Lightweight tokenizer for BM25.

    Lowercases text, removes common question words,
    and normalizes simple English plurals.

    No external NLP package required.
    """

    tokens = re.findall(
        r"[a-z0-9]+",
        text.lower(),
    )

    stopwords = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "how",
        "what",
        "which",
        "who",
        "where",
        "when",
        "why",
        "from",
        "in",
        "on",
        "at",
        "to",
        "of",
        "for",
        "and",
        "or",
        "all",
        "there",
        "have",
        "has",
        "had",
        "our",
    }

    cleaned = []

    for token in tokens:

        if token in stopwords:
            continue

        # Very small plural normalisation.
        # customers -> customer
        # orders    -> order
        # products  -> product
        if (
            token.endswith("s")
            and len(token) > 3
            and not token.endswith("ss")
        ):
            token = token[:-1]

        cleaned.append(token)

    return cleaned

def get_bm25(conn):
    """
    Build the BM25 schema index once per process.

    BM25 uses the same enriched table descriptions as the
    embedding index.

    This is intentionally kept in memory because the toy
    enterprise schema has only ~63 tables.
    """

    global _bm25
    global _bm25_tables
    global _bm25_documents

    if _bm25 is None:

        _bm25_tables = get_tables(conn)

        _bm25_documents = [
            describe_table(conn, table)
            for table in _bm25_tables
        ]

        tokenized_documents = [
            bm25_tokenize(doc)
            for doc in _bm25_documents
        ]

        _bm25 = BM25Okapi(
            tokenized_documents
        )

    return (
        _bm25,
        _bm25_tables,
        _bm25_documents,
    )

# ------------------------------------------------------------
# Week 2 schema retrieval
# ------------------------------------------------------------

def retrieve_tables_vector(question, k=None):

    k = k or CONFIG["top_k_tables"]

    collection = get_collection()

    total = collection.count()

    if total == 0:
        return []

    n_results = min(
        k * 3,
        40,
        total,
    )

    res = collection.query(
        query_texts=[question],
        n_results=n_results,
    )

    ids = res["ids"][0]
    dists = res["distances"][0]

    metas = (
        res["metadatas"][0]
        if res.get("metadatas")
        else [{}] * len(ids)
    )

    rows = []

    for name, dist, meta in zip(
        ids,
        dists,
        metas,
    ):

        empty = bool(
            meta.get("empty", False)
        )

        rows.append(
            (name, dist, empty)
        )

    # Populated tables first.
    rows.sort(
        key=lambda r: (
            r[2],
            r[1],
        )
    )

    return [
        (name, dist)
        for name, dist, _
        in rows[:k]
    ]

def should_abstain(question):
    """
    WEEK 7 -- calibrated retrieval-confidence abstention.

    Uses the raw embedding distance of the best populated
    schema-table match.

    Lower distance = stronger schema match.
    Higher distance = weaker / out-of-domain match.

    Threshold was calibrated on clear vs OOD questions.
    """

    hits = retrieve_tables_vector(
        question,
        k=3,
    )

    if not hits:
        return (
            True,
            None,
            "No relevant schema tables were retrieved.",
        )

    top_table, top_distance = hits[0]

    threshold = CONFIG[
        "abstain_threshold"
    ]

    abstain = (
        top_distance > threshold
    )

    if abstain:
        reason = (
            f"Low schema confidence: "
            f"best table={top_table}, "
            f"distance={top_distance:.3f}, "
            f"threshold={threshold:.3f}"
        )
    else:
        reason = (
            f"Schema confidence sufficient: "
            f"best table={top_table}, "
            f"distance={top_distance:.3f}, "
            f"threshold={threshold:.3f}"
        )

    return (
        abstain,
        top_distance,
        reason,
    )

def normalize_scores(score_dict):
    """
    Min-max normalize scores into 0..1.

    Important:
    if every raw score is 0, there is no retrieval evidence,
    so every normalized score must stay 0.
    """

    if not score_dict:
        return {}

    values = list(score_dict.values())

    low = min(values)
    high = max(values)

    # All scores identical.
    if high == low:

        # No evidence at all.
        if high == 0:
            return {
                key: 0.0
                for key in score_dict
            }

        # Every item genuinely received
        # the same positive score.
        return {
            key: 1.0
            for key in score_dict
        }

    return {
        key: (
            (value - low)
            /
            (high - low)
        )
        for key, value
        in score_dict.items()
    }

def retrieve_tables_hybrid(
    conn,
    question,
    k=None,
):
    """
    WEEK 7 -- hybrid schema retrieval.

    Combines:

        semantic embedding similarity
        +
        BM25 lexical relevance

    Final score:

        70% embedding
        30% BM25

    Higher final score = better.

    Populated tables are still preferred over empty filler
    tables, preserving the Week 2 behavior.
    """

    k = k or CONFIG["top_k_tables"]

    # ------------------------------------------------
    # 1. Semantic scores
    # ------------------------------------------------

    collection = get_collection()

    total = collection.count()

    vector_res = collection.query(
        query_texts=[question],
        n_results=min(
            max(k * 5, 30),
            total,
        ),
    )

    vector_scores = {}

    empty_flags = {}

    for (
        table,
        distance,
        metadata,
    ) in zip(
        vector_res["ids"][0],
        vector_res["distances"][0],
        vector_res["metadatas"][0],
    ):

        # Chroma distance:
        # lower = better
        #
        # Convert to similarity:
        # higher = better.
        similarity = 1.0 - float(distance)

        vector_scores[table] = similarity

        empty_flags[table] = bool(
            metadata.get(
                "empty",
                False,
            )
        )

    vector_scores = normalize_scores(
        vector_scores
    )

    # ------------------------------------------------
    # 2. BM25 scores
    # ------------------------------------------------

    (
        bm25,
        bm25_tables,
        _,
    ) = get_bm25(conn)

    query_tokens = bm25_tokenize(
        question
    )

    raw_bm25 = bm25.get_scores(
        query_tokens
    )

    bm25_scores = {
        table: float(score)
        for table, score
        in zip(
            bm25_tables,
            raw_bm25,
        )
    }

    bm25_scores = normalize_scores(
        bm25_scores
    )

    # ------------------------------------------------
    # 3. Combine
    # ------------------------------------------------

    all_tables = set(
        vector_scores
    ) | set(
        bm25_scores
    )

    ranked = []

    for table in all_tables:

        vector = vector_scores.get(
            table,
            0.0,
        )

        lexical = bm25_scores.get(
            table,
            0.0,
        )

        hybrid = (
            0.70 * vector
            +
            0.30 * lexical
        )

        # Tables not returned in the vector over-fetch
        # may still come from BM25. Determine whether
        # they are populated.
        if table not in empty_flags:

            row_count = conn.execute(
                f'SELECT COUNT(*) '
                f'FROM "{table}"'
            ).fetchone()[0]

            empty = row_count == 0

        else:

            empty = empty_flags[table]

        ranked.append({
            "table": table,
            "score": hybrid,
            "vector": vector,
            "bm25": lexical,
            "empty": empty,
        })

    # Same Week 2 principle:
    # populated tables before empty filler tables.
    ranked.sort(
        key=lambda x: (
            x["empty"],
            -x["score"],
        )
    )

    return ranked[:k]

def retrieve_tables(
    question,
    k=None,
    conn=None,
):
    """
    Chooses which table retrieval method to use.

    Hybrid OFF:
        original embedding/vector retrieval

    Hybrid ON:
        embedding + BM25 retrieval
    """

    if (
        CONFIG["use_hybrid_bm25"]
        and conn is not None
    ):
        hits = retrieve_tables_hybrid(
            conn,
            question,
            k=k,
        )

        return [
            (
                hit["table"],
                1.0 - hit["score"],
            )
            for hit in hits
        ]

    return retrieve_tables_vector(
        question,
        k=k,
    )

# ------------------------------------------------------------
# Week 4 value retrieval
# ------------------------------------------------------------

def sql_literal(value, value_type):
    """
    Format a retrieved database value for the prompt.

    INTEGER/REAL:
        3

    TEXT:
        'MH'
    """

    value_type = (
        value_type or ""
    ).upper()

    if (
        "INT" in value_type
        or "REAL" in value_type
        or "NUM" in value_type
        or "FLOAT" in value_type
        or "DOUBLE" in value_type
    ):
        return str(value)

    escaped = str(value).replace(
        "'",
        "''",
    )

    return f"'{escaped}'"


def retrieve_values(
    question,
    allowed_tables=None,
    k=5,
):
    """
    Search Week 4 value index.

    Returns relevant mappings such as:

        delivered ->
        ord_txn.stat_cd = 3
    """

    collection = get_value_collection()

    total = collection.count()

    if total == 0:
        return []

    # Over-fetch because some results may
    # belong to irrelevant tables.
    n_results = min(
        max(k * 4, 10),
        total,
    )

    res = collection.query(
        query_texts=[question],
        n_results=n_results,
    )

    metas = res["metadatas"][0]
    dists = res["distances"][0]

    hits = []

    for meta, dist in zip(
        metas,
        dists,
    ):

        table = meta["table"]

        if (
            allowed_tables
            and table not in allowed_tables
        ):
            continue

        value = meta["value"]

        hits.append({
            "table": table,
            "column": meta["column"],
            "value": value,
            "value_type": meta.get(
                "value_type",
                "",
            ),
            "aliases": meta.get(
                "aliases",
                "",
            ),
            "distance": float(dist),
        })

        if len(hits) >= k:
            break

    return hits


def format_value_context(hits):
    """
    Convert retrieved values into prompt hints.
    """

    if not hits:
        return "(none)"

    lines = []

    for hit in hits:

        literal = sql_literal(
            hit["value"],
            hit["value_type"],
        )

        aliases = hit["aliases"]

        if aliases:
            meaning = (
                f" meaning: {aliases};"
            )
        else:
            meaning = ""

        lines.append(
            f"- {hit['table']}."
            f"{hit['column']} = "
            f"{literal};"
            f"{meaning} "
            f"use this exact stored value "
            "when relevant."
        )

    return "\n".join(lines)


# ------------------------------------------------------------
# SQL cleanup
# ------------------------------------------------------------

class UnsafeSQLError(Exception):
    """
    Raised when generated SQL violates the Week 6 read-only policy.

    This intentionally does NOT inherit from sqlite3.Error.

    Why?
    Week 5 self-correction catches sqlite3.Error.
    A dangerous query should be BLOCKED, not sent back to the
    LLM for repeated attempts.
    """

    pass

def clean_sql(raw):

    raw = re.sub(
        r"```(?:sql)?",
        "",
        raw,
    ).strip()

    match = re.search(
        r"\b(SELECT|WITH)\b",
        raw,
        re.IGNORECASE,
    )

    if match:
        raw = raw[match.start():]

    return raw.rstrip(";").strip()


def validate_sql(sql):
    """
    WEEK 6 -- static SQL safety check using sqlglot.

    Policy:
    - exactly one SQL statement
    - must be a read-only query
    - SELECT / WITH SELECT / UNION-style queries are allowed
    - INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, etc. are blocked

    Returns:
        True when safe

    Raises:
        UnsafeSQLError when unsafe or unparsable
    """

    if not sql or not sql.strip():
        raise UnsafeSQLError(
            "Empty SQL query."
        )

    try:
        statements = sqlglot.parse(
            sql,
            read="sqlite",
        )

    except Exception as e:
        raise UnsafeSQLError(
            f"SQL could not be safely parsed: {e}"
        )

    # Never allow:
    #
    # SELECT ...;
    # DELETE ...;
    #
    # even if the first statement is safe.
    if len(statements) != 1:
        raise UnsafeSQLError(
            "Multiple SQL statements are not allowed."
        )

    tree = statements[0]

    if tree is None:
        raise UnsafeSQLError(
            "SQL could not be parsed."
        )

    # Explicitly forbidden statement/node types.
    forbidden_types = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Create,
        exp.Alter,
        exp.Command,
        exp.Merge,
    )

    for forbidden in forbidden_types:

        if tree.find(forbidden):

            raise UnsafeSQLError(
                f"Unsafe SQL blocked: "
                f"{forbidden.__name__} "
                f"operations are not allowed."
            )

    # A read-only query must contain a SELECT.
    #
    # This also supports:
    #
    # WITH x AS (...) SELECT ...
    #
    # and UNION queries.
    if tree.find(exp.Select) is None:

        raise UnsafeSQLError(
            "Only read-only SELECT queries are allowed."
        )

    return True

def correct_sql(question,failed_sql,error,schema_text,values_text,):
    """
    Week 5: ask the LLM to repair SQL using SQLite execution feedback.
    """

    prompt = CORRECTION_PROMPT.format(
        schema=schema_text,
        values=values_text,
        question=question,
        sql=failed_sql,
        error=error,
    )

    corrected = clean_sql(
        call_llm(prompt)
    )

    return corrected
# --------------------------


def execute_sql(
    conn,
    sql,
):
    """
    Execute one SQL query.

    Week 6 adds two safety layers:

    1. sqlglot validates the SQL before execution.
    2. SQLite query_only mode prevents writes as a backup.
    """

    if CONFIG["use_safety_check"]:

        # Layer 1:
        # Parse and inspect generated SQL.
        validate_sql(sql)

        # Layer 2:
        # SQLite itself refuses write operations.
        conn.execute(
            "PRAGMA query_only = ON"
        )

    else:

        # Important for ablation experiments.
        # If safety was previously ON for this connection,
        # restore normal SQLite behaviour when flag is OFF.
        conn.execute(
            "PRAGMA query_only = OFF"
        )

    cur = conn.execute(sql)

    rows = cur.fetchall()

    cols = (
        [d[0] for d in cur.description]
        if cur.description
        else []
    )

    return rows, cols


def execute_with_correction(
    conn,
    question,
    sql,
    schema_text,
    values_text,
):
    """
    Week 5 execution-feedback loop.

    If self-correction is OFF:
        execute once exactly like the old pipeline.

    If self-correction is ON:
        on SQLite error, send the failed SQL + error back
        to the LLM and retry up to max_retries.
    """

    attempts = 0
    current_sql = sql

    while True:

        try:

            rows, cols = execute_sql(
                conn,
                current_sql,
            )

            return (
                rows,
                cols,
                current_sql,
                attempts,
            )

        except sqlite3.Error as e:

            # Old behaviour when Week 5 is disabled.
            if not CONFIG["use_self_correction"]:
                raise

            # Have we already used all allowed retries?
            if attempts >= CONFIG["max_retries"]:
                raise

            attempts += 1

            error_text = str(e)

            if CONFIG["verbose"]:

                print(
                    f"  execution failed "
                    f"(attempt {attempts}): "
                    f"{error_text}"
                )

                print(
                    f"  failed SQL: "
                    f"{current_sql}"
                )

            corrected_sql = correct_sql(
                question=question,
                failed_sql=current_sql,
                error=error_text,
                schema_text=schema_text,
                values_text=values_text,
            )

            if CONFIG["verbose"]:

                print(
                    f"  corrected SQL: "
                    f"{corrected_sql}"
                )

            # Avoid endlessly retrying exactly the same SQL.
            if (
                corrected_sql.strip().lower()
                ==
                current_sql.strip().lower()
            ):
                raise RuntimeError(
                    "Self-correction returned "
                    "the same failing SQL."
                )

            current_sql = corrected_sql
# ------------------------------------------------------------
# Schema text
# ------------------------------------------------------------

def build_schema_text(
    conn,
    question,
):

    if CONFIG["use_schema_retrieval"]:

        hits = retrieve_tables(
            question,
            conn=conn,
        )

        if CONFIG["verbose"]:

            print("  retrieved tables:")

            for name, dist in hits:
                print(
                    f"    {name:14} "
                    f"distance {dist:.3f}"
                )

        tables = [
            name
            for name, _ in hits
        ]

    else:

        tables = get_tables(conn)

    schema_text = "\n".join(
        compact_schema(conn, t)
        for t in tables
    )

    return (
        schema_text,
        len(tables),
        tables,
    )


# ------------------------------------------------------------
# Main pipeline
# ------------------------------------------------------------

def ask(
    question,
    conn,
    return_trace=False,
):
    trace = {
        "abstention": None,
        "confidence_distance": None,
        "retrieved_tables": [],
        "retrieved_values": [],
        "retries": 0,
    }
    # ------------------------------------------------
    # WEEK 7 -- calibrated abstention
    # ------------------------------------------------
    if CONFIG["use_abstention"]:

        abstain, distance, reason = should_abstain(
            question
        )

        trace["abstention"] = reason
        trace["confidence_distance"] = distance

        if CONFIG["verbose"]:
            print(
                f"  abstention check: {reason}"
            )

        # Important:
        # Stop BEFORE schema prompt, LLM call,
        # SQL generation, or database execution.
        if abstain:

            result = (
                [(
                    "I am not confident enough "
                    "that this question can be "
                    "answered from the database."
                ,)],
                ["message"],
                "ABSTAIN",
                0,
            )

            if return_trace:
                return (*result, trace)

            return result

    (
        schema_text,
        n_tables,
        tables,
    ) = build_schema_text(
        conn,
        question,
    )

    trace["retrieved_tables"] = tables

    # Week 4 is completely guarded
    # by the ablation flag.
    value_hits = []

    if CONFIG["use_value_retrieval"]:

        value_hits = retrieve_values(
            question,
            allowed_tables=tables,
        )

        if CONFIG["verbose"]:

            print("  value matches:")

            if not value_hits:
                print("    (none)")

            for hit in value_hits:

                literal = sql_literal(
                    hit["value"],
                    hit["value_type"],
                )

                aliases = (
                    hit["aliases"]
                    or "-"
                )

                print(
                    f"    "
                    f"{hit['table']}."
                    f"{hit['column']} = "
                    f"{literal}"
                    f"  [{aliases}]"
                    f"  distance "
                    f"{hit['distance']:.3f}"
                )

    values_text = format_value_context(
        value_hits
    )

    trace["retrieved_values"] = value_hits

    prompt = PROMPT.format(
        schema=schema_text,
        values=values_text,
        question=question,
    )

    # Same rough estimate you already use.
    approx_tokens = len(prompt) // 4

    sql = clean_sql(
        call_llm(prompt)
    )

    if CONFIG["verbose"]:

        print(
            f"  schema sent: "
            f"{n_tables} tables, "
            f"~{approx_tokens} tokens"
        )

        print(
            f"  SQL: {sql}"
        )

    rows, cols, final_sql, retries = (
        execute_with_correction(
            conn=conn,
            question=question,
            sql=sql,
            schema_text=schema_text,
            values_text=values_text,
        )
    )

    trace["retries"] = retries

    if CONFIG["verbose"] and retries:

        print(
            f"  self-correction retries: "
            f"{retries}"
        )

    result = (
        rows,
        cols,
        final_sql,
        approx_tokens,
    )

    if return_trace:
        return (*result, trace)

    return result


# ------------------------------------------------------------
# Display
# ------------------------------------------------------------

def show(rows, cols):

    if not rows:

        print("  (no rows)")
        return

    widths = [
        max(
            len(str(c)),
            max(
                len(str(r[i]))
                for r in rows
            ),
        )
        for i, c
        in enumerate(cols)
    ]

    header = (
        "  "
        + " | ".join(
            str(c).ljust(w)
            for c, w
            in zip(cols, widths)
        )
    )

    print(header)

    print(
        "  "
        + "-"
        * (len(header) - 2)
    )

    for row in rows[:20]:

        print(
            "  "
            + " | ".join(
                str(v).ljust(w)
                for v, w
                in zip(row, widths)
            )
        )

    if len(rows) > 20:

        print(
            f"  ... "
            f"{len(rows) - 20} "
            "more rows"
        )


# ------------------------------------------------------------
# Comparison helper
# ------------------------------------------------------------

DEMO_QUESTIONS = [
    "who are our top customers by total spend?",
    "how many orders were placed in July 2025?",
    "which product category earns the most revenue?",
    "list customers from Maharashtra",
    "How many delivered orders are there?",
]


def compare(conn):

    q = (
        "who are our top customers "
        "by total spend?"
    )

    print(f"\nQ: {q}\n")

    previous_value_flag = CONFIG[
        "use_value_retrieval"
    ]

    CONFIG["use_value_retrieval"] = False

    for flag in (False, True):

        CONFIG[
            "use_schema_retrieval"
        ] = flag

        CONFIG["verbose"] = False

        label = (
            "retrieval ON "
            if flag
            else "full schema  "
        )

        try:

            _, _, _, tok = ask(
                q,
                conn,
            )

            n = (
                CONFIG["top_k_tables"]
                if flag
                else len(
                    get_tables(conn)
                )
            )

            print(
                f"  {label} "
                f"{n:3} tables "
                f"~{tok:6} tokens"
            )

        except Exception as e:

            print(
                f"  {label} FAILED: "
                f"{str(e)[:60]}"
            )

    CONFIG["verbose"] = True

    CONFIG[
        "use_value_retrieval"
    ] = previous_value_flag


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def main():

    db = "data/big.db"

    if not os.path.exists(db):

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

    # Week 2 retrieval stays enabled.
    CONFIG["use_schema_retrieval"] = True

    # Week 4 value retrieval is enabled
    # only when --values is supplied.
    CONFIG["use_value_retrieval"] = (
        "--values" in sys.argv
    )
    CONFIG["use_hybrid_bm25"] = (
        "--hybrid" in sys.argv
    )
    CONFIG["use_abstention"] = (
        "--abstain" in sys.argv
    )

    conn = sqlite3.connect(db)

    if "--compare" in sys.argv:

        compare(conn)

        conn.close()

        return

    questions = [
        arg
        for arg in sys.argv[1:]
        if not arg.startswith("--")
    ] or DEMO_QUESTIONS

    for q in questions:

        print(
            f"\n{'=' * 60}"
            f"\nQ: {q}"
        )

        try:

            rows, cols, _, _ = ask(
                q,
                conn,
            )

            show(rows, cols)

        except Exception as e:

            print(
                f"  FAILED: {e}"
            )

    conn.close()


if __name__ == "__main__":
    main()
