"""Prompt-template loader.

Templates live as .md files next to this module. ``render(name, **kw)`` loads a
template and substitutes ``{placeholder}`` tokens. We use ``str.replace`` rather
than ``str.format`` so JSON braces inside templates don't need escaping.
"""

from __future__ import annotations

import os
from functools import lru_cache

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompt_templates")


@lru_cache(maxsize=None)
def _load(name: str) -> str:
    path = os.path.join(_PROMPT_DIR, name)
    if not path.endswith(".md"):
        path += ".md"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def render(name: str, **kw: str) -> str:
    text = _load(name)
    for key, value in kw.items():
        text = text.replace("{" + key + "}", str(value))
    return text
