# Agentic SQL RAG — Setup & Run Guide

A natural-language-to-SQL system. Ask a database questions in plain English;
it retrieves the relevant tables, writes SQL, runs it, and returns the answer.

This guide takes you from a **fresh computer** to a **working system** with a
measured accuracy score. Follow it top to bottom. It assumes no prior setup.

**Progress so far:** Weeks 1–3 complete. Current baseline: **6/8 (75%)**.

---

## 0. What you need before starting

| Requirement | How to check | If missing |
|---|---|---|
| Python 3.10 or newer | `python --version` | Install Python 3.12 from python.org |
| pip | `pip --version` | Comes with Python |
| An LLM API key | — | Get one (see Step 4) |
| The project files | — | Copy the whole folder |

> **macOS note:** the built-in Python is 3.9, which is too old. Install 3.12
> from python.org and use `python3.12` where this guide says `python`.
>
> **Windows note:** when installing Python, **tick "Add python.exe to PATH"**
> on the first screen, or `python` won't be recognised.

---

## 1. Get the project onto the new machine

Copy the entire project folder (call it `sqlrag`) to the new computer. It must
contain these files:

```
sqlrag/
├── config.py
├── setup_db.py
├── skeleton.py
├── make_big_db.py
├── indexer.py
├── week2.py
├── eval_set.py
├── eval_set_small.py
├── run_eval.py
├── llm.py
├── choose_llm.py
├── requirements.txt
├── .gitignore
└── README.md   (this file)
```

You do **not** need to copy `venv/`, `data/`, `index/`, `cache/`, `logs/`,
`.env`, or `llm_choice.json` — those are all recreated below. (In fact
`.gitignore` deliberately excludes them.)

---

## 2. Open a terminal inside the folder

```bash
cd path/to/sqlrag
```

On Windows use Command Prompt or PowerShell; on Mac/Linux use Terminal.
Everything from here runs from inside this folder.

---

## 3. Create the virtual environment and install packages

A virtual environment keeps this project's packages separate from the rest of
the system. Create it once:

```bash
# create it
python -m venv venv

# activate it  (do this EVERY time you open a new terminal)
source venv/bin/activate        # Mac / Linux
venv\Scripts\activate           # Windows
```

When active, your prompt shows `(venv)` at the start. Now install everything:

```bash
pip install -r requirements.txt
```

This takes a few minutes — `sentence-transformers` pulls in PyTorch, which is
large. That is normal. Confirm it worked:

```bash
python -c "import chromadb, openai, sentence_transformers; print('all packages OK')"
```

---

## 4. Add your API key

The system needs an LLM to write SQL. It supports several providers. Pick one
and get a key:

| Provider | Where to get a key | Cost |
|---|---|---|
| NVIDIA (current default) | build.nvidia.com | free tier |
| Google Gemini | aistudio.google.com/apikey | free tier |
| OpenAI | platform.openai.com/api-keys | ~₹400 |
| Local (Ollama) | ollama.com — no key needed | free, needs 8GB RAM |

Create a file named exactly **`.env`** in the `sqlrag` folder with one line:

```
NVIDIA_API_KEY=nvapi-your-key-here
```

(Use `GEMINI_API_KEY=` or `OPENAI_API_KEY=` instead if you chose those.)

> **Creating .env:**
> - VS Code: File → New File → save as `.env`
> - Mac/Linux terminal: `echo "NVIDIA_API_KEY=your-key" > .env`
> - Windows: in Notepad's Save dialog set "Save as type" to **All Files** so it
>   doesn't become `.env.txt`

---

## 5. Choose which LLM to use

```bash
python choose_llm.py nvidia
```

Or run `python choose_llm.py` with no argument for an interactive menu. It shows
which providers have a key ready. Confirm your choice any time:

```bash
python choose_llm.py --show
```

---

## 6. Build the databases and search index (run once)

These commands create the data the system works on. **Run them in this order.**

```bash
# 1. small toy database (4 tables) — used for early testing
python setup_db.py

# 2. large database (63 tables) — the real test bed
python make_big_db.py

# 3. build the search index over the large database
#    FIRST RUN downloads the embedding model (~80 MB) — be patient
python indexer.py
```

**Expected output:**

```
# setup_db.py
created data/demo.db
  cust_mst     7 rows
  ...

# make_big_db.py
created data/big.db with 63 tables

# indexer.py
indexing data/big.db ...
indexed 63 tables into ./index
example enriched description (cust_mst):
  customer master. customer master table. Stores customer master records.
  Columns: customer id, customer name, ... (7 rows of data).
```

---

## 7. Run the system

Ask it a question directly:

```bash
python week2.py "who are our top customers by total spend?"
```

You'll see the tables it retrieved, the SQL it generated, and the result rows.

See the core benefit — retrieval vs dumping the whole schema:

```bash
python week2.py --compare
```

This prints token counts for both approaches (~807 tokens full schema vs ~132
retrieved), the proof that retrieval scales.

---

## 8. Run the evaluation (the accuracy score)

This is how we measure the system. It runs a set of test questions, compares
each answer against the known-correct answer, and prints a percentage.

```bash
# fast: 8 questions (recommended for free API tiers)
python run_eval.py --small

# full: 20 questions
python run_eval.py
```

**Expected output (current state):**

```
  OK  e01   easy    How many customers do we have?
  OK  e02   easy    List all customers from Maharashtra.
  ...
============================================================
  OVERALL: 6/8 = 75.0%
    easy   : 3/3 = 100%
    medium : 2/3 = 67%
    hard   : 1/2 = 50%
```

Every run is logged to `logs/runs.csv` — open it to see, for each question, the
SQL the system generated versus the correct SQL. That file is how we diagnose
what to improve next.

---

## Quick reference — the whole thing in order

```bash
# ONE TIME on a new machine:
cd sqlrag
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
# create .env with your API key
python choose_llm.py nvidia
python setup_db.py
python make_big_db.py
python indexer.py

# EVERY TIME after that (new terminal):
source venv/bin/activate            # Windows: venv\Scripts\activate
python run_eval.py --small          # or: python week2.py "your question"
```

---

## What each file does

| File | Run it? | What it is |
|---|---|---|
| `config.py` | no (settings) | Central settings and feature flags. Everything reads this. |
| `setup_db.py` | once | Builds the small 4-table toy database. |
| `make_big_db.py` | once | Builds the 63-table database (the real test bed). |
| `indexer.py` | once | Reads the DB schema, builds the searchable vector index. |
| `week2.py` | anytime | The main pipeline. Ask questions with it. |
| `run_eval.py` | anytime | Runs the test set, prints the accuracy score. |
| `eval_set.py` | rarely | The 20 test questions with correct answers. |
| `eval_set_small.py` | rarely | An 8-question subset for fast runs. |
| `llm.py` | no (library) | Talks to the LLM. Used by other files. |
| `choose_llm.py` | when switching | Picks which LLM provider to use. |
| `skeleton.py` | reference | The original Week 1 version. Kept for history. |

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'chromadb'`**
The virtual environment isn't active, or packages aren't installed. Run
`source venv/bin/activate` then `pip install -r requirements.txt`.

**`NVIDIA_API_KEY missing`**
Your `.env` file is missing, misnamed (check it's `.env` not `.env.txt`), or has
the wrong key name for your chosen provider.

**`data/big.db missing` / `index missing`**
You skipped Step 6. Run `python make_big_db.py` then `python indexer.py`.

**`Error code: 503 ResourceExhausted` during evaluation**
The free API tier rate-limited you. Just re-run the same command — cached
answers are kept, so only the failed question re-calls. If it persists, increase
`call_delay` in `config.py`.

**First `indexer.py` run seems frozen**
It's downloading the 80 MB embedding model. Wait — it only happens once, then
it's cached.

**A `Warning: ... HF_TOKEN ...` message**
Harmless. It just means the embedding model downloaded anonymously. Ignore it.

---

## What's built and what's next

**Done (Weeks 1–3):** working pipeline, schema retrieval, evaluation harness,
75% baseline, multi-provider LLM support.

**Next (Week 4):** value retrieval — teaching the system that "Maharashtra"
means `MH` and "delivered" means status code `3`. This targets the two
questions currently failing.

Later weeks add self-correction, a safety layer, a Streamlit web interface, and
a full ablation study.
