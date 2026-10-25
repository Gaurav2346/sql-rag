"""Lookup for the project's fixed, fast demo question set."""

import json
import os
import re
from pathlib import Path


CACHE_PATH = Path(__file__).resolve().parent / "data" / "demo_qa.json"


def normalize_question(question):
    """Normalize case and punctuation while retaining meaningful words."""
    return " ".join(re.findall(r"[a-z0-9]+", question.casefold()))


def load_demo_answers():
    with CACHE_PATH.open(encoding="utf-8") as cache_file:
        entries = json.load(cache_file)
    return {
        normalize_question(entry["question"]): entry
        for entry in entries
    }


def get_demo_questions():
    """Return the curated questions in display order."""
    return [entry["question"] for entry in load_demo_answers().values()]


def get_demo_answer(question):
    """Return a precomputed answer for an exact normalized match."""
    return load_demo_answers().get(normalize_question(question))


def refresh_demo_answers(conn):
    """Recalculate saved answers after CRUD changes to the demo database."""
    with CACHE_PATH.open(encoding="utf-8") as cache_file:
        entries = json.load(cache_file)

    for entry in entries:
        cursor = conn.execute(entry["sql"])
        entry["columns"] = [column[0] for column in cursor.description]
        entry["rows"] = [list(row) for row in cursor.fetchall()]

    temporary_path = CACHE_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, CACHE_PATH)
