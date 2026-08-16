# Agentic SQL RAG — Setup, Run & Evaluation Guide

A schema-aware **Natural-Language-to-SQL** system for querying enterprise relational databases in plain English.

The system retrieves only the relevant database schema, retrieves important stored values such as encoded status/state codes, generates SQL with an LLM, validates it for read-only safety, executes it, retries failed SQL using execution feedback, and abstains when the question does not appear answerable from the database.

---

## Project Title

**Agentic Retrieval-Augmented Generation for Natural Language Querying of Enterprise Databases**

## Core idea

A user asks:

> How many delivered orders are there?

The system:
1. identifies the most relevant tables,
2. retrieves the stored meaning of **delivered**,
3. learns that `delivered -> ord_txn.stat_cd = 3`,
4. generates safe SQLite SQL,
5. executes the SQL,
6. automatically repairs execution errors when necessary,
7. returns the result,
8. refuses unrelated questions when confidence is too low.

Example generated SQL:

```sql
SELECT COUNT(*) FROM ord_txn WHERE stat_cd = 3
```

Result:

```text
5
```

---

# Current Project Status

## Completed

- Week 0 — Environment and project setup ✅
- Week 1 — Walking skeleton / basic Text-to-SQL pipeline ✅
- Week 2 — Schema retrieval with sentence embeddings + ChromaDB ✅
- Week 3 — Evaluation harness and baseline measurement ✅
- Week 4 — Value-level retrieval ✅
- Week 5 — Execution-feedback self-correction ✅
- Week 6 — SQL safety layer ✅
- Week 7 — Hybrid BM25 + vector retrieval and calibrated abstention ✅
- Week 8 — Streamlit user interface and Agent Trace ✅

## Remaining

- Week 9 — Full ablation study
- Week 10 — Final charts, report, screenshots, demo preparation

---

# Current Evaluation Results

Run:

```bash
python run_eval.py --small --values --self-correct --safety --hybrid --abstain
```

Current verified result:

```text
OVERALL: 8/8 = 100.0%

easy   : 3/3 = 100%
medium : 3/3 = 100%
hard   : 2/2 = 100%
```

Feature configuration:

```text
schema_retrieval=True
value_retrieval=True
self_correction=True
safety_check=True
hybrid_bm25=True
abstention=True
```

---

# Week-by-Week Development

## Week 1 — Basic Text-to-SQL Pipeline

The first version implemented:

```text
Question
   ↓
Database schema
   ↓
LLM
   ↓
SQL
   ↓
SQLite
   ↓
Result
```

The original Week 1 version is preserved in `skeleton.py` for comparison and project history.

---

## Week 2 — Schema Retrieval

The system was upgraded so it no longer needs to send the entire enterprise schema to the LLM.

It now:
1. reads the database schema,
2. generates enriched table descriptions,
3. embeds them with `sentence-transformers`,
4. stores them in ChromaDB,
5. retrieves only the most relevant tables for the user question.

Embedding model:

```text
all-MiniLM-L6-v2
```

Vector database:

```text
ChromaDB
```

Default retrieved-table count:

```text
top_k_tables = 8
```

### Why it matters

Full-schema prompting:
- wastes tokens,
- introduces irrelevant tables,
- increases model confusion,
- scales poorly as databases grow.

Retrieval keeps the prompt focused.

---

## Week 3 — Evaluation Harness

Files:
- `eval_set.py`
- `eval_set_small.py`
- `run_eval.py`

The evaluator:
1. asks each question,
2. executes the generated SQL,
3. executes gold SQL,
4. compares returned rows,
5. computes execution accuracy,
6. logs runs to `logs/runs.csv`.

Initial baseline:

```text
6/8 = 75%
```

The key failure was:

```text
How many delivered orders are there?
```

The model used something like:

```sql
WHERE stat_cd = 'delivered'
```

but the database stores:

```text
stat_cd = 3
```

This motivated Week 4.

---

# Week 4 — Value-Level Retrieval

Schema retrieval explains tables and columns, but encoded values still need grounding.

Examples:

```text
Maharashtra -> MH
delivered   -> 3
sales       -> SALES
electronics -> ELEC
```

A dedicated value index was added.

## `value_mappings.py`

Examples:

```python
("cust_mst", "st_cd", "MH"): [
    "Maharashtra",
    "Maharashtra state",
]

("ord_txn", "stat_cd", "3"): [
    "delivered",
    "delivered order",
    "completed delivery",
]
```

The value index stores:
- table,
- column,
- exact stored value,
- data type,
- semantic aliases.

Flow:

```text
Question
   ↓
Schema retrieval
   ↓
Value retrieval
   ↓
Exact stored values
   ↓
LLM prompt
   ↓
SQL
```

For:

```text
How many delivered orders are there?
```

the system retrieves:

```text
ord_txn.stat_cd = 3
```

and generates:

```sql
SELECT COUNT(*) FROM ord_txn WHERE stat_cd = 3
```

### Week 4 result

Without value retrieval:

```text
6/8 = 75%
```

With value retrieval:

```text
8/8 = 100%
```

Improvement:

```text
+25 percentage points
```

Important reporting note: the delivered-order question is direct evidence of value-level grounding. Other improvements should not automatically be attributed to value retrieval unless the retrieved value actually explains the change.

---

# Week 5 — Execution-Feedback Self-Correction

Week 5 handles SQL that fails at execution time.

Example broken SQL:

```sql
SELECT customer_name FROM cust_mst
```

SQLite returns:

```text
no such column: customer_name
```

The actual column is:

```text
cust_nm
```

The correction loop sends the LLM:
- original question,
- failed SQL,
- SQLite error,
- retrieved schema,
- retrieved values.

It then retries the corrected query.

Maximum retries:

```text
max_retries = 3
```

CLI flag:

```bash
--self-correct
```

### Controlled Week 5 test

Broken query 1:

```sql
SELECT customer_name FROM cust_mst
```

Corrected to:

```sql
SELECT cust_nm FROM cust_mst
```

Broken query 2:

```sql
SELECT COUNT(*) FROM orders
```

Corrected to:

```sql
SELECT COUNT(*) FROM ord_txn
```

Result:

```text
Self-correction OFF: 0/2
Self-correction ON : 2/2
```

### Important limitation

Self-correction only activates on SQLite execution errors.

Wrong-but-valid SQL does not trigger it.

Example:

```sql
SELECT COUNT(*) FROM ord_txn WHERE stat_cd = 'delivered'
```

This is valid SQLite, so no correction occurs. This is why value retrieval and self-correction solve different problems.

---

# Week 6 — SQL Safety

Week 6 added two read-only safety layers.

## Layer 1 — `sqlglot` validation

Allowed:
- `SELECT`
- `WITH ... SELECT`
- read-only union-style queries

Blocked:
- `INSERT`
- `UPDATE`
- `DELETE`
- `DROP`
- `CREATE`
- `ALTER`
- multi-statement SQL

Example blocked query:

```sql
SELECT * FROM cust_mst;
DELETE FROM cust_mst;
```

## Layer 2 — SQLite query-only mode

When safety is enabled:

```sql
PRAGMA query_only = ON
```

is applied before generated SQL is executed.

## Safety vs self-correction

Unsafe SQL raises:

```text
UnsafeSQLError
```

This intentionally does not inherit from `sqlite3.Error`.

Therefore:

```text
invalid SQL
→ sqlite3.Error
→ self-correction may retry
```

but:

```text
unsafe SQL
→ UnsafeSQLError
→ blocked immediately
→ no LLM retry
```

### Week 6 test

```bash
python test_week6.py
```

Result:

```text
7/7
```

Verified:
- SELECT allowed
- CTE SELECT allowed
- DELETE blocked
- UPDATE blocked
- INSERT blocked
- DROP blocked
- multiple statements blocked

Normal benchmark remained:

```text
8/8 = 100%
```

---

# Week 7 — Hybrid Retrieval

Week 7 combines semantic embeddings with BM25 lexical matching.

Architecture:

```text
Question
   ├── Embedding retrieval
   └── BM25 retrieval
           ↓
     score normalization
           ↓
      weighted fusion
           ↓
      final ranking
```

Current weights:

```text
70% embeddings
30% BM25
```

BM25 tokenization:
- lowercases text,
- removes common question words,
- normalizes simple plurals.

Examples:

```text
customers -> customer
orders    -> order
products  -> product
```

The retriever also prefers populated tables over empty filler tables.

### Hybrid retrieval evaluation

Correct-table instances:

```text
6
```

Results:

```text
Vector Recall@2 = 83.3%
Hybrid Recall@2 = 100%
```

Mean relevant-table rank:

```text
Vector = 1.50
Hybrid = 1.33
```

A useful improvement occurred for:

```text
Which customer spent the most in total?
```

where `ord_txn` improved from rank 3 to rank 2.

CLI flag:

```bash
--hybrid
```

---

# Week 7 — Calibrated Abstention

The system should refuse unsupported or unrelated questions.

Examples:

```text
What is the weather today?
Who is the Prime Minister of India?
Tell me a joke.
Show me the best ones.
What should I eat for dinner?
```

The current abstention signal is the raw embedding distance of the best populated schema match.

Interpretation:

```text
lower distance = stronger schema match
higher distance = weaker / out-of-domain match
```

Calibration data showed:

```text
Answerable questions: 0.633 to 0.797
OOD questions:        0.828 to 0.910
```

Current calibrated development threshold:

```text
0.81
```

Rule:

```text
distance <= 0.81 → answer
distance >  0.81 → abstain
```

This is a calibrated threshold for the current database and embedding model, not a universal constant.

### Abstention calibration

```text
Clear questions answered: 5/5
OOD questions abstained: 5/5
Total: 10/10
```

Example:

```text
Question: What is the weather today?
best table = cfg_prm
distance   = 0.910
threshold  = 0.810
Decision   = ABSTAIN
```

The system stops before:
- value retrieval,
- LLM SQL generation,
- SQL execution.

CLI flag:

```bash
--abstain
```

---

# Week 8 — Streamlit UI

A Streamlit interface was added in:

```text
app.py
```

Run:

```bash
streamlit run app.py
```

Typical URL:

```text
http://localhost:8501
```

Current UI includes:
- natural-language question input,
- clickable example questions,
- Run Query button,
- generated SQL display,
- result table,
- row count,
- approximate prompt-token count,
- SQL safety indicator,
- feature toggles,
- abstention warning,
- database connection status,
- expandable Agent Trace.

Sidebar toggles:
- Schema Retrieval
- Value Retrieval
- Self-Correction
- SQL Safety
- Hybrid BM25
- Calibrated Abstention

## Agent Trace

`ask()` now supports:

```python
ask(
    question,
    conn,
    return_trace=True,
)
```

Trace metadata includes:
- confidence distance,
- abstention reason,
- retrieved tables,
- retrieved values,
- self-correction retry count.

Example for delivered orders:

```text
Confidence distance: 0.667
Retrieved table: ord_txn
Retrieved value: ord_txn.stat_cd = 3
Meaning: delivered
Retries: 0
```

For an out-of-domain query, the Agent Trace shows the low-confidence reason and no SQL is generated.

---

# Full Current Pipeline

```text
Natural-language question
        ↓
Calibrated abstention check
        ↓
Unsupported?
   ├── Yes → ABSTAIN
   └── No
        ↓
Schema retrieval
        ↓
Hybrid vector + BM25 retrieval
        ↓
Relevant table selection
        ↓
Value-level retrieval
        ↓
Focused prompt
        ↓
LLM SQL generation
        ↓
SQL safety validation
        ↓
SQLite query-only protection
        ↓
Execution
        ↓
Execution error?
   ├── No → result
   └── Yes
        ↓
Self-correction
        ↓
Safe retry
        ↓
Final result
```

---

# Current Repository Structure

```text
sqlrag/
├── app.py
├── config.py
├── setup_db.py
├── skeleton.py
├── make_big_db.py
├── indexer.py
├── week2.py
├── value_mappings.py
├── eval_set.py
├── eval_set_small.py
├── run_eval.py
├── llm.py
├── choose_llm.py
├── test_week5.py
├── eval_week5.py
├── test_week6.py
├── test_week7_retrieval.py
├── test_week7_abstention.py
├── requirements.txt
├── .gitignore
└── README.md
```

Generated/runtime folders:

```text
data/
index/
cache/
logs/
venv/
```

Local-only files may include:

```text
.env
llm_choice.json
```

---

# 0. Requirements

| Requirement | Check | If missing |
|---|---|---|
| Python 3.10+ | `python --version` | Install Python 3.12 |
| pip | `pip --version` | Comes with Python |
| LLM API key | Provider dashboard | See API section |
| Project folder | Check files above | Copy repository |

Recommended:

```text
Python 3.12
```

macOS users may initially need:

```bash
python3.12
```

Windows users should enable:

```text
Add python.exe to PATH
```

during Python installation.

---

# 1. Copy the Project

Copy the whole project folder to the new computer.

You usually do not need to copy:

```text
venv/
data/
index/
cache/
logs/
.env
llm_choice.json
```

Do not commit API keys.

---

# 2. Open a Terminal

```bash
cd path/to/sqlrag
```

Run all commands from this folder.

---

# 3. Create and Activate a Virtual Environment

Create:

```bash
python -m venv venv
```

macOS/Linux:

```bash
source venv/bin/activate
```

Windows Command Prompt:

```bat
venv\Scripts\activate
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

---

# 4. Install Dependencies

```bash
pip install -r requirements.txt
```

Important libraries include:

```text
chromadb
sentence-transformers
rank-bm25
sqlglot
streamlit
pandas
matplotlib
python-dotenv
```

Dependency check:

```bash
python -c "import chromadb, sentence_transformers, sqlglot, streamlit; from rank_bm25 import BM25Okapi; print('all packages OK')"
```

Expected:

```text
all packages OK
```

---

# 5. Add an LLM API Key

Create:

```text
.env
```

Example NVIDIA:

```env
NVIDIA_API_KEY=nvapi-your-key-here
```

Gemini:

```env
GEMINI_API_KEY=your-key-here
```

OpenAI:

```env
OPENAI_API_KEY=your-key-here
```

The adapter also supports other configured providers such as DeepSeek, Groq, OpenRouter, and Ollama.

Never commit `.env`.

---

# 6. Choose the LLM Provider

Example:

```bash
python choose_llm.py nvidia
```

Interactive:

```bash
python choose_llm.py
```

Show current:

```bash
python choose_llm.py --show
```

---

# 7. Build Databases

Run in order:

```bash
python setup_db.py
python make_big_db.py
```

The small database contains core populated tables such as:
- `cust_mst`
- `ord_txn`
- `prod_mst`
- `emp_rec`

The large database contains approximately:

```text
63 tables
```

and is used as the main retrieval test bed.

---

# 8. Build Search Indexes

```bash
python indexer.py
```

This builds:
- schema index,
- value index.

Stored under:

```text
./index
```

The first run downloads `all-MiniLM-L6-v2`.

A Hugging Face unauthenticated warning is harmless for this project.

---

# 9. Run Questions from the CLI

Basic:

```bash
python week2.py "How many customers do we have?"
```

Value retrieval:

```bash
python week2.py --values "How many delivered orders are there?"
```

Current complete pipeline:

```bash
python week2.py --values --self-correct --safety --hybrid --abstain "How many delivered orders are there?"
```

Expected answer:

```text
5
```

Abstention test:

```bash
python week2.py --values --self-correct --safety --hybrid --abstain "What is the weather today?"
```

Expected behavior:

```text
I am not confident enough that this question can be answered from the database.
```

No SQL should be generated.

---

# 10. Compare Full Schema vs Retrieval

```bash
python week2.py --compare
```

This compares the approximate prompt size for:
- full-schema prompting,
- retrieved-schema prompting.

Use the values from the current run in the final report because token counts can change as prompts evolve.

---

# 11. Run Evaluation

Baseline-style:

```bash
python run_eval.py --small
```

With value retrieval:

```bash
python run_eval.py --small --values
```

Add self-correction:

```bash
python run_eval.py --small --values --self-correct
```

Add safety:

```bash
python run_eval.py --small --values --self-correct --safety
```

Add hybrid retrieval:

```bash
python run_eval.py --small --values --self-correct --safety --hybrid
```

Current complete evaluation:

```bash
python run_eval.py --small --values --self-correct --safety --hybrid --abstain
```

Current result:

```text
8/8 = 100%
```

Full 20-question run:

```bash
python run_eval.py --values --self-correct --safety --hybrid --abstain
```

---

# 12. Evaluation Logs

Every run writes:

```text
logs/runs.csv
```

Save important runs because the next evaluation may overwrite it.

macOS/Linux:

```bash
cp logs/runs.csv logs/week7_all_features.csv
```

Windows:

```bat
copy logs\runs.csv logs\week7_all_features.csv
```

Useful experiment files may include:

```text
week4_values_off.csv
week4_values_on.csv
week5_values_selfcorrect_on.csv
week6_all_features.csv
week7_all_features.csv
```

---

# 13. Controlled Tests

## Self-correction

```bash
python test_week5.py
python eval_week5.py
```

Expected controlled comparison:

```text
OFF: 0/2
ON : 2/2
```

## SQL safety

```bash
python test_week6.py
```

Expected:

```text
7/7
```

## Hybrid retrieval

```bash
python test_week7_retrieval.py
```

Current summary:

```text
Vector Recall@2 = 83.3%
Hybrid Recall@2 = 100%

Vector mean rank = 1.50
Hybrid mean rank = 1.33
```

## Abstention

```bash
python test_week7_abstention.py
```

Current summary:

```text
5/5 clear questions answered
5/5 OOD questions abstained
10/10 total
```

---

# 14. Run the Streamlit UI

```bash
streamlit run app.py
```

Suggested demo questions:

```text
How many customers do we have?
List all customers from Maharashtra.
How many delivered orders are there?
Which customer spent the most in total?
```

Abstention demo:

```text
What is the weather today?
```

---

# 15. Current Important Configuration

Representative settings in `config.py`:

```python
CONFIG = {
    "use_schema_retrieval": False,
    "use_value_retrieval": False,
    "use_self_correction": False,
    "use_safety_check": False,
    "use_abstention": False,
    "use_hybrid_bm25": False,

    "top_k_tables": 8,
    "max_retries": 3,
    "value_cardinality_limit": 500,

    "abstain_threshold": 0.81,
    "abstain_margin": 0.02,

    "llm_provider": "nvidia",
    "llm_model": "nvidia/nemotron-3-ultra-550b-a55b",

    "embedding_model": "all-MiniLM-L6-v2",

    "call_delay": 1,

    "db_path": "data/demo.db",
    "index_path": "./index",
    "log_path": "logs/runs.csv",

    "cache_llm": True,
    "verbose": True,
}
```

Feature flags default to OFF so each component can be tested independently.

---

# 16. What Each Main File Does

| File | Run? | Purpose |
|---|---:|---|
| `config.py` | No | Central configuration and feature flags |
| `setup_db.py` | Once | Creates the small demo DB |
| `make_big_db.py` | Once | Creates the large enterprise-style DB |
| `indexer.py` | When rebuilding | Builds schema and value indexes |
| `value_mappings.py` | No | Aliases for encoded DB values |
| `week2.py` | Yes | Main agentic SQL pipeline |
| `run_eval.py` | Yes | Main execution-accuracy evaluator |
| `eval_set.py` | Rarely | Full gold evaluation set |
| `eval_set_small.py` | Rarely | Fast 8-question subset |
| `llm.py` | No | Provider-independent LLM adapter |
| `choose_llm.py` | Yes | Selects active LLM provider |
| `app.py` | Yes | Streamlit UI |
| `test_week5.py` | Yes | Self-correction controlled test |
| `eval_week5.py` | Yes | Self-correction stress test |
| `test_week6.py` | Yes | SQL safety test |
| `test_week7_retrieval.py` | Yes | Vector vs hybrid retrieval test |
| `test_week7_abstention.py` | Yes | Abstention calibration test |
| `skeleton.py` | Reference | Week 1 historical implementation |

---

# 17. LLM Adapter and Cache

The rest of the project calls:

```python
call_llm(prompt)
```

instead of provider-specific code.

Benefits:
- easy model/provider switching,
- lower coupling,
- reusable caching,
- easier experiments.

The LLM cache reduces:
- repeated API calls,
- evaluation cost,
- rerun time.

Deterministic generation is preferred, typically using temperature 0 where supported.

---

# 18. Core Demo Schema

## `cust_mst`

```text
cust_id
cust_nm
st_cd
city_nm
crtd_dt
```

## `ord_txn`

```text
ord_id
cust_id
prod_id
qty
amt
ord_dt
stat_cd
```

## `prod_mst`

```text
prod_id
prod_nm
cat_cd
unit_prc
```

## `emp_rec`

```text
emp_id
emp_nm
dept_cd
sal
join_dt
```

Example encoded meanings:

```text
cust_mst.st_cd:
MH = Maharashtra
KA = Karnataka
TN = Tamil Nadu
DL = Delhi
```

```text
ord_txn.stat_cd:
1 = pending
2 = processing
3 = delivered
4 = cancelled
```

---

# 19. Troubleshooting

## `ModuleNotFoundError`

Activate the virtual environment and reinstall:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Windows:

```bat
venv\Scripts\activate
pip install -r requirements.txt
```

## Missing BM25

```bash
pip install rank-bm25
```

## Missing sqlglot

```bash
pip install sqlglot
```

## Missing Streamlit

```bash
pip install streamlit pandas
```

## API key missing

Check `.env`:
- filename must be exactly `.env`,
- not `.env.txt`,
- variable name must match the selected provider,
- no accidental spaces.

## `data/big.db missing`

```bash
python setup_db.py
python make_big_db.py
```

## Index missing

```bash
python indexer.py
```

## Hugging Face warning

A message about unauthenticated HF Hub requests is harmless. The model can still load.

## API rate limit / 503

Possible actions:
1. rerun the command,
2. rely on cached successful calls,
3. increase `call_delay`,
4. switch provider.

## Valid question unexpectedly abstains

The `0.81` threshold is calibrated for the current setup. If the schema or embedding model changes, recalibrate using:

```bash
python test_week7_abstention.py
```

---

# 20. Rebuild After Schema/Data Changes

If schema, descriptions, or value mappings change:

```bash
python indexer.py
```

For a complete reset:

```bash
python setup_db.py
python make_big_db.py
python indexer.py
```

Then rerun controlled tests and the main evaluator.

---

# 21. Recommended Regression Test Sequence

Syntax:

```bash
python -m py_compile week2.py
python -m py_compile run_eval.py
python -m py_compile app.py
```

Controlled tests:

```bash
python test_week6.py
python test_week7_abstention.py
python test_week7_retrieval.py
```

Final benchmark:

```bash
python run_eval.py --small --values --self-correct --safety --hybrid --abstain
```

Target:

```text
8/8 = 100%
```

---

# 22. Fresh Machine — Full Setup

## macOS / Linux

```bash
cd sqlrag

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

# create .env

python choose_llm.py nvidia

python setup_db.py
python make_big_db.py
python indexer.py

python run_eval.py --small --values --self-correct --safety --hybrid --abstain

streamlit run app.py
```

## Windows

```bat
cd sqlrag

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

REM create .env

python choose_llm.py nvidia

python setup_db.py
python make_big_db.py
python indexer.py

python run_eval.py --small --values --self-correct --safety --hybrid --abstain

streamlit run app.py
```

---

# 23. Daily Workflow

```bash
cd path/to/sqlrag
source venv/bin/activate
```

Windows:

```bat
venv\Scripts\activate
```

Then use one of:

```bash
streamlit run app.py
```

```bash
python week2.py --values --self-correct --safety --hybrid --abstain "your question"
```

```bash
python run_eval.py --small --values --self-correct --safety --hybrid --abstain
```

---

# 24. Current Experimental Evidence

| Experiment | Without | With | Result |
|---|---:|---:|---|
| Value retrieval | 6/8 | 8/8 | +25 percentage points |
| Self-correction stress test | 0/2 | 2/2 | execution errors repaired |
| SQL safety | — | 7/7 | unsafe SQL correctly blocked |
| Hybrid Recall@2 | 83.3% | 100% | better table retrieval |
| Mean relevant-table rank | 1.50 | 1.33 | lower is better |
| Abstention calibration | — | 10/10 | clear/OOD separated |
| Full-feature small benchmark | — | 8/8 | 100% |

---

# 25. Key Contributions Demonstrated

## 1. Value-Level Retrieval
Maps natural-language concepts to exact stored DB values.

## 2. Execution-Feedback Self-Correction
Uses SQLite errors to repair failed SQL.

## 3. Read-Only SQL Safety
Uses parser-level and database-level protection.

## 4. Hybrid Schema Retrieval
Combines embedding similarity with BM25 lexical relevance.

## 5. Calibrated Abstention
Rejects unsupported questions before LLM SQL generation.

## 6. Transparent Agent Trace
Shows confidence, retrieved tables, values, and retries in the UI.

---

# 26. Evaluation Interpretation

The small benchmark reached 100% after value retrieval, so later components should not be evaluated only using overall benchmark accuracy.

Use separate evidence:

```text
Value retrieval:
main benchmark improvement

Self-correction:
execution-error stress test

Safety:
unsafe-query test suite

Hybrid retrieval:
Recall@2 + mean rank

Abstention:
clear-vs-OOD calibration
```

This avoids overstating improvements on an already saturated 8-question benchmark.

---

# 27. Next — Week 9

Week 9 will formalize the full ablation study.

Planned comparisons:

```text
schema retrieval only
+ value retrieval
+ self-correction
+ safety
+ hybrid BM25
+ abstention
```

Metrics:
- execution accuracy,
- Recall@k,
- mean table rank,
- correction success rate,
- safety accuracy,
- abstention accuracy,
- prompt-token usage.

Saved CSV logs from earlier weeks should be preserved for this stage.

---

# 28. Final Goal

The completed system demonstrates that enterprise Text-to-SQL can be made more reliable by combining:

```text
schema-aware retrieval
+
value-level grounding
+
hybrid vector/BM25 retrieval
+
execution-driven correction
+
SQL safety
+
confidence-based abstention
+
transparent UI traces
```

rather than depending on a single LLM prompt over the full database schema.

---

# Quick Reference

Full-feature CLI:

```bash
python week2.py --values --self-correct --safety --hybrid --abstain "How many delivered orders are there?"
```

Full-feature small evaluation:

```bash
python run_eval.py --small --values --self-correct --safety --hybrid --abstain
```

Web UI:

```bash
streamlit run app.py
```

Current verified small-benchmark accuracy:

```text
8/8 = 100%
```
