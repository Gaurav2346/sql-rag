import sqlite3

import pandas as pd
import streamlit as st

from config import CONFIG
from week2 import ask
from auth import (
    apply_style,
    require_login,
    sidebar_user,
)


# ============================================================
# DATABASE
# ============================================================

DB = "data/big.db"


# ============================================================
# STREAMLIT PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="Agentic Enterprise Database QA",
    page_icon="🗄️",
    layout="wide",
)


# ============================================================
# AUTH
# ============================================================

apply_style()

require_login()

sidebar_user()


# ============================================================
# PAGE HEADER
# ============================================================

st.title(
    "Agentic Enterprise Database QA"
)

st.caption(
    "Natural language querying over an enterprise "
    "SQLite database using schema retrieval, "
    "value retrieval, self-correction, SQL safety, "
    "hybrid BM25 retrieval, and calibrated abstention."
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.divider()

st.sidebar.subheader(
    "System Status"
)

st.sidebar.success(
    "Database connected"
)

st.sidebar.caption(
    "SQLite enterprise database"
)

st.sidebar.caption(
    "Read-only SQL execution"
)


# ============================================================
# PIPELINE FEATURES
# ============================================================

st.sidebar.header(
    "Pipeline Features"
)


schema_retrieval = st.sidebar.toggle(
    "Schema Retrieval",
    value=True,
)


value_retrieval = st.sidebar.toggle(
    "Value Retrieval",
    value=True,
)


self_correction = st.sidebar.toggle(
    "Self-Correction",
    value=True,
)


safety_check = st.sidebar.toggle(
    "SQL Safety",
    value=True,
)


hybrid_bm25 = st.sidebar.toggle(
    "Hybrid BM25",
    value=True,
)


abstention = st.sidebar.toggle(
    "Calibrated Abstention",
    value=True,
)


# ============================================================
# CONFIG UPDATE
# ============================================================

CONFIG["use_schema_retrieval"] = (
    schema_retrieval
)

CONFIG["use_value_retrieval"] = (
    value_retrieval
)

CONFIG["use_self_correction"] = (
    self_correction
)

CONFIG["use_safety_check"] = (
    safety_check
)

CONFIG["use_hybrid_bm25"] = (
    hybrid_bm25
)

CONFIG["use_abstention"] = (
    abstention
)

CONFIG["verbose"] = False


# ============================================================
# DATABASE CONNECTION
# ============================================================

@st.cache_resource
def get_connection():

    return sqlite3.connect(
        DB,
        check_same_thread=False,
    )


conn = get_connection()


# ============================================================
# EXAMPLE QUESTIONS
# ============================================================

st.subheader(
    "Example Questions"
)


examples = [
    "How many customers do we have?",
    "List all customers from Maharashtra.",
    "How many delivered orders are there?",
    "Which customer spent the most in total?",
]


if "question_input" not in st.session_state:

    st.session_state.question_input = ""


example_cols = st.columns(4)


for i, (col, example) in enumerate(
    zip(
        example_cols,
        examples,
    )
):

    with col:

        if st.button(
            example,
            key=f"example_{i}",
            use_container_width=True,
        ):

            st.session_state.question_input = (
                example
            )


# ============================================================
# QUESTION
# ============================================================

question = st.text_input(
    "Ask a question about the enterprise database",
    key="question_input",
    placeholder=(
        "Example: How many delivered "
        "orders are there?"
    ),
)


# ============================================================
# RUN BUTTON
# ============================================================

run_button = st.button(
    "Run Query",
    type="primary",
)


# ============================================================
# RUN PIPELINE
# ============================================================

if run_button:

    if not question.strip():

        st.warning(
            "Please enter a question."
        )

    else:

        with st.spinner(
            "Understanding the question and "
            "querying the database..."
        ):

            try:

                rows, cols, sql, tokens, trace = ask(
                    question,
                    conn,
                    return_trace=True,
                )

                # ====================================================
                # ABSTENTION
                # ====================================================

                if sql == "ABSTAIN":

                    st.warning(
                        rows[0][0]
                        if rows
                        else (
                            "The system is not confident "
                            "enough to answer this question."
                        )
                    )

                # ====================================================
                # SUCCESS
                # ====================================================

                else:

                    st.success(
                        "Query completed successfully."
                    )

                    if CONFIG[
                        "use_safety_check"
                    ]:

                        st.info(
                            "🛡️ SQL safety validation enabled"
                        )

                    # ------------------------------------------------
                    # Metrics
                    # ------------------------------------------------

                    metric1, metric2 = st.columns(2)


                    metric1.metric(
                        "Rows Returned",
                        len(rows),
                    )


                    metric2.metric(
                        "Approx. Prompt Tokens",
                        tokens,
                    )


                    # ------------------------------------------------
                    # SQL
                    # ------------------------------------------------

                    st.subheader(
                        "Generated SQL"
                    )

                    st.code(
                        sql,
                        language="sql",
                    )


                    # ------------------------------------------------
                    # RESULT
                    # ------------------------------------------------

                    st.subheader(
                        "Result"
                    )

                    if rows:

                        df = pd.DataFrame(
                            rows,
                            columns=cols,
                        )

                        st.dataframe(
                            df,
                            use_container_width=True,
                        )

                    else:

                        st.info(
                            "The query returned no rows."
                        )


                # ====================================================
                # AGENT TRACE
                # ====================================================

                st.divider()

                with st.expander(
                    "Agent Trace",
                    expanded=False,
                ):

                    # ------------------------------------------------
                    # Retrieval Confidence
                    # ------------------------------------------------

                    st.subheader(
                        "Retrieval Confidence"
                    )


                    confidence = trace.get(
                        "confidence_distance"
                    )


                    if confidence is not None:

                        st.metric(
                            "Embedding Distance",
                            f"{confidence:.3f}",
                        )

                        st.caption(
                            "Lower distance indicates "
                            "a stronger schema match."
                        )


                    # ------------------------------------------------
                    # Abstention Reason
                    # ------------------------------------------------

                    abstention_reason = trace.get(
                        "abstention"
                    )


                    if abstention_reason:

                        st.write(
                            abstention_reason
                        )


                    # ------------------------------------------------
                    # Retrieved Tables
                    # ------------------------------------------------

                    st.subheader(
                        "Retrieved Tables"
                    )


                    tables = trace.get(
                        "retrieved_tables",
                        [],
                    )


                    if tables:

                        for i, table in enumerate(
                            tables,
                            start=1,
                        ):

                            st.write(
                                f"{i}. `{table}`"
                            )

                    else:

                        st.caption(
                            "No tables retrieved."
                        )


                    # ------------------------------------------------
                    # Retrieved Values
                    # ------------------------------------------------

                    st.subheader(
                        "Retrieved Database Values"
                    )


                    values = trace.get(
                        "retrieved_values",
                        [],
                    )


                    if values:

                        value_rows = []


                        for hit in values:

                            value_rows.append(
                                {
                                    "Table": hit[
                                        "table"
                                    ],

                                    "Column": hit[
                                        "column"
                                    ],

                                    "Value": hit[
                                        "value"
                                    ],

                                    "Meaning": hit[
                                        "aliases"
                                    ],

                                    "Distance": round(
                                        hit[
                                            "distance"
                                        ],
                                        3,
                                    ),
                                }
                            )


                        st.dataframe(
                            pd.DataFrame(
                                value_rows
                            ),
                            use_container_width=True,
                        )

                    else:

                        st.caption(
                            "No value-level matches."
                        )


                    # ------------------------------------------------
                    # Execution Feedback
                    # ------------------------------------------------

                    st.subheader(
                        "Execution Feedback"
                    )


                    retries = trace.get(
                        "retries",
                        0,
                    )


                    if retries:

                        st.warning(
                            f"Self-correction retries: "
                            f"{retries}"
                        )

                    else:

                        st.success(
                            "No SQL correction was required."
                        )


            except Exception as e:

                st.error(
                    f"Query failed: {e}"
                )