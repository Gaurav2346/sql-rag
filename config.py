# """
# Central config. Every feature checks its flag here.

# This file exists from day one because the ablation study in Week 9
# works by flipping these booleans and re-running the evaluation.
# Retrofitting flags later is painful, so we do it now.
# """
# """
# Central config. Every feature checks its flag here.

# This file exists from day one because the ablation study in Week 9
# works by flipping these booleans and re-running the evaluation.
# Retrofitting flags later is painful, so we do it now.
# """

# CONFIG = {
#     # --- ablation flags (Week 9 flips these one at a time) ---
#     "use_schema_retrieval": False,   # Week 2
#     "use_value_retrieval":  False,   # Week 4
#     "use_self_correction":  False,   # Week 5
#     "use_safety_check":     False,   # Week 6
#     "use_abstention":       False,   # Week 7
#     "use_hybrid_bm25":      False,   # Week 7

#     # --- tunables ---
#     "top_k_tables":     8,
#     "max_retries":      3,
#     "value_cardinality_limit": 500,   # under this = categorical, index it
#     "abstain_threshold": 0.81,        # distance above this = not confident
#     "abstain_margin":    0.02,        # top-2 closer than this = ambiguous

#     # --- model ---
#     "llm_model": "gemini-3.6-flash",
#     "embedding_model": "all-MiniLM-L6-v2",

#     # --- paths ---
#     "db_path":    "data/demo.db",
#     "index_path": "./index",
#     "log_path":   "logs/runs.csv",

#     # --- dev ---
#     "cache_llm": True,    # cache responses so re-runs cost nothing
#     "verbose":   True,
# }


"""
Central config. Every feature checks its flag here.

This file exists from day one because the ablation study in Week 9
works by flipping these booleans and re-running the evaluation.
Retrofitting flags later is painful, so we do it now.
"""

CONFIG = {
    # --- ablation flags (Week 9 flips these one at a time) ---
    "use_schema_retrieval": False,   # Week 2
    "use_value_retrieval":  False,   # Week 4
    "use_self_correction":  False,   # Week 5
    "use_safety_check":     False,   # Week 6
    "use_abstention":       False,   # Week 7
    "use_hybrid_bm25":      False,   # Week 7

    # --- tunables ---
    "top_k_tables":     8,
    "max_retries":      3,
    "value_cardinality_limit": 500,   # under this = categorical, index it
    "abstain_threshold": 0.81,        # distance above this = not confident
    "abstain_margin":    0.02,        # top-2 closer than this = ambiguous

    # --- model ---
    "llm_provider":    "nvidia",              # gemini | openai | nvidia
    "llm_model":       "nvidia/nemotron-3-ultra-550b-a55b",
    "embedding_model": "all-MiniLM-L6-v2",
    "call_delay":      1,                     # seconds between API calls

    # --- paths ---
    "db_path":    "data/demo.db",
    "index_path": "./index",
    "log_path":   "logs/runs.csv",

    # --- dev ---
    "cache_llm": True,    # cache responses so re-runs cost nothing
    "verbose":   True,
}
