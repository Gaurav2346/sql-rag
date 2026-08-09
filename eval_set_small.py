"""
WEEK 3 -- small evaluation set (8 questions) for free-tier Gemini.

Same structure as eval_set.py but trimmed so a full run stays well
under the free-tier per-minute request cap. Once cached, re-runs are
free, so you can expand to the full 20 later for final numbers.
"""

from eval_set import EVAL_SET as _FULL

_KEEP = {"e01", "e02", "e03", "m01", "m02", "m06", "h01", "h03"}

EVAL_SET = [i for i in _FULL if i["id"] in _KEEP]


def by_level():
    out = {}
    for item in EVAL_SET:
        out.setdefault(item["level"], []).append(item)
    return out


if __name__ == "__main__":
    for i in EVAL_SET:
        print(i["id"], i["level"], "-", i["q"])