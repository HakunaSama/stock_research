"""Open-Deep-Research engine — a pure-Python port of the ODR approach.

Multi-agent supervisor + parallel sub-research + reflection + compression +
report writing, with NO LangGraph dependency. Exposed as a ``Researcher`` so it
drops into the existing judge/retry loop in ``research.py``.
"""

from .pipeline import OpenDeepResearcher
from .retriever import Retriever, LLMSubResearcher
from .state import (
    ResearchBrief,
    SubTopic,
    SubFinding,
    CompressedNote,
    ODRResult,
)

__all__ = [
    "OpenDeepResearcher",
    "Retriever",
    "LLMSubResearcher",
    "ResearchBrief",
    "SubTopic",
    "SubFinding",
    "CompressedNote",
    "ODRResult",
]
