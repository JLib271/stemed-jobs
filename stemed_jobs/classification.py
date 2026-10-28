import re
from typing import List, Tuple


_CATEGORY_RULES = (
    (
        "undergraduates",
        re.compile(
            r"\bundergraduate(?:s)?\b|\bbachelor(?:'s)?\s+(?:student|degree)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "graduates",
        re.compile(
            r"\bgraduate\s+(?:(?:research|teaching)\s+)?"
            r"(?:students?|assistantships?|assistants?|fellowships?|fellows?|positions?)\b"
            r"|\b(?:ph\.?d\.?|doctoral)\s+(?:(?:research|teaching)\s+)?"
            r"(?:students?|fellowships?|fellows?|assistantships?|assistants?|positions?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "postdocs",
        re.compile(
            r"\bpost[ -]?doctoral\b|\bpostdoc(?:toral)?s?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "faculty",
        re.compile(
            r"\bfaculty\b|\bprofessors?(?:ships?)?\b|\blecturer\b|\binstructor\b"
            r"|\b(?:teaching|research)\s+faculty\b|\btenure[ -]?track\b"
            r"|\btenured\b|\btt(?:/t)?\b",
            re.IGNORECASE,
        ),
    ),
)

_FUNCTION_RULES = (
    ("research", re.compile(r"\bresearch\b|\bscholarship\b|\binvestigat(?:e|ion|ing)\b", re.IGNORECASE)),
    ("teaching", re.compile(r"\bteach(?:er|ers|ing)?\b|\binstruction(?:al)?\b|\beducator\b", re.IGNORECASE)),
)


def classify_job(title: str, summary: str) -> Tuple[List[str], List[str]]:
    """Return evidenced audience categories and work functions for a posting."""
    categories = [category for category, pattern in _CATEGORY_RULES if pattern.search(title)]
    searchable_text = "{} {}".format(title, summary)
    functions = [function for function, pattern in _FUNCTION_RULES if pattern.search(searchable_text)]
    return categories, functions
