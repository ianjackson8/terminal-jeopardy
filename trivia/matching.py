"""Forgiving answer checking: ignores "what is", articles, punctuation, accents and small typos."""
from __future__ import annotations

import re
import unicodedata

_QUESTION_PREFIX = re.compile(
    r"^(?:(?:what|who|where|when|which)\s+(?:is|are|was|were)|whats|whos|wheres)\s+"
)
_ARTICLE = re.compile(r"^(?:the|a|an)\s+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = text.replace("&", " and ").replace("-", " ")
    text = re.sub(r"[^a-z0-9 ]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = _QUESTION_PREFIX.sub("", text)
    text = _ARTICLE.sub("", text)
    return text.strip()


def _edit_distance(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _allowed_typos(target: str) -> int:
    if target.replace(" ", "").isdigit():
        return 0
    n = len(target)
    if n <= 4:
        return 0
    if n <= 10:
        return 1
    return 2


def is_correct(response: str, answers: list[str]) -> bool:
    r = normalize(response)
    if not r:
        return False
    for ans in answers:
        target = normalize(ans)
        if not target:
            continue
        if r == target or r.replace(" ", "") == target.replace(" ", ""):
            return True
        if _edit_distance(r, target) <= _allowed_typos(target):
            return True
    return False
