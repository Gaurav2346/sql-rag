"""
LLM adapter -- one place to configure the model provider.

Every other file calls llm.call_llm(prompt). Swapping providers means
editing only this file. Supports OpenAI, Gemini and NVIDIA NIM via the
same OpenAI-compatible client.

For text-to-SQL we force:
  - temperature 0    -> deterministic, so evaluation is repeatable
  - thinking OFF     -> we want SQL, not a reasoning essay
  - non-streaming    -> simpler; we need the whole answer anyway

Set the provider in config.py via CONFIG["llm_provider"].
"""

import hashlib
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

from config import CONFIG

load_dotenv()

# If the interactive picker (choose_llm.py) has been run, its choice
# overrides whatever is in config.py. This lets you switch providers
# without editing code.
import json as _json
if os.path.exists("llm_choice.json"):
    _c = _json.load(open("llm_choice.json"))
    CONFIG["llm_provider"] = _c.get("provider", CONFIG["llm_provider"])
    CONFIG["llm_model"] = _c.get("model", CONFIG["llm_model"])

# ---- provider setup ------------------------------------------------

_PROVIDERS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
    },
    "openai": {
        "base_url": None,                       # default OpenAI endpoint
        "key_env": "OPENAI_API_KEY",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_env": "NVIDIA_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "key_env": "DEEPSEEK_API_KEY",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "key_env": "",          # local, no key
    },
}


def _client():
    prov = _PROVIDERS[CONFIG["llm_provider"]]
    if prov["key_env"] == "":            # local model, no key required
        return OpenAI(api_key="ollama", base_url=prov["base_url"])
    key = os.getenv(prov["key_env"])
    if not key:
        raise SystemExit(
            f"{prov['key_env']} missing -- add it to .env, "
            f"or run: python choose_llm.py")
    if prov["base_url"]:
        return OpenAI(api_key=key, base_url=prov["base_url"])
    return OpenAI(api_key=key)


_CLIENT = None


def _get_client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = _client()
    return _CLIENT


# ---- cache ---------------------------------------------------------

def _cache_path(prompt):
    tag = CONFIG["llm_model"]
    key = hashlib.md5((tag + "::" + prompt).encode()).hexdigest()
    return os.path.join("cache", key + ".txt")


# ---- main entry point ---------------------------------------------

def call_llm(prompt):
    if CONFIG["cache_llm"]:
        path = _cache_path(prompt)
        if os.path.exists(path):
            return open(path, encoding="utf-8").read()

    time.sleep(CONFIG["call_delay"])

    kwargs = dict(
        model=CONFIG["llm_model"],
        messages=[{"role": "user", "content": prompt}],
        temperature=0,          # deterministic -- do not change for SQL
    )

    # NVIDIA Nemotron is a reasoning model; explicitly disable thinking
    # so we get SQL directly rather than a chain-of-thought essay.
    if CONFIG["llm_provider"] == "nvidia":
        kwargs["extra_body"] = {
            "chat_template_kwargs": {"enable_thinking": False}
        }
        kwargs["max_tokens"] = 1024

    resp = _get_client().chat.completions.create(**kwargs)
    out = resp.choices[0].message.content.strip()

    if CONFIG["cache_llm"]:
        os.makedirs("cache", exist_ok=True)
        with open(_cache_path(prompt), "w", encoding="utf-8") as f:
            f.write(out)
    return out