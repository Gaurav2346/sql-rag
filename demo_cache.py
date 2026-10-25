"""Lookup for the project's fixed, fast demo question set."""

import json
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
