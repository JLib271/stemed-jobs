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
    (
        "staff",
        re.compile(
            r"\b(?:instructional|learning|educational|education|curriculum|academic|faculty|course|e-?learning"
            r"|online learning|learning experience|digital learning|teaching and learning)\s+"
            r"(?:designers?|developers?|technologists?|design(?:\s+(?:specialist|consultant|manager|lead|coordinator))?"
            r"|development(?:\s+(?:specialist|consultant|manager|coordinator))?|specialists?|consultants?)\b"
            r"|\bcurriculum\s+(?:writers?|coordinators?)\b"
            r"|\b(?:educational|education|instructional|learning|academic)\s+technology\s+(?:specialist|consultant|manager|coordinator|designer|support)\b|\bacademic\s+technologists?\b|\binstructional\s+(?:design|technolog\w*)\b|\blearning\s+technolog\w*\s+(?:specialist|consultant|manager)\b",
            re.IGNORECASE,
        ),
    ),
)

# Titles that name a professor, lecturer or instructor are faculty even when they
# also name design or development work.
_FACULTY_RANK = re.compile(r"\bprofessors?(?:ships?)?\b|\blecturer\b|\binstructor\b|\btenure[ -]?track\b|\btenured\b", re.IGNORECASE)

_FUNCTION_RULES = (
    ("research", re.compile(r"\bresearch\b|\bscholarship\b|\binvestigat(?:e|ion|ing)\b", re.IGNORECASE)),
    ("teaching", re.compile(r"\bteach(?:er|ers|ing)?\b|\binstruction(?:al)?\b|\beducator\b", re.IGNORECASE)),
)


# Curriculum specialist, writer, coordinator, developer and designer roles are staff jobs unless the
# title makes them a graduate, postdoctoral or faculty position.
_CURRICULUM_ROLE = re.compile(r"\bcurriculum\s+(?:specialists?|writers?|coordinators?|developers?|designers?|development|design)\b", re.IGNORECASE)


def classify_job(title: str, summary: str) -> Tuple[List[str], List[str]]:
    """Return evidenced audience categories and work functions for a posting."""
    categories = [category for category, pattern in _CATEGORY_RULES if pattern.search(title)]
    if _CURRICULUM_ROLE.search(title):
        academic = [c for c in categories if c in ("graduates", "postdocs")]
        if _FACULTY_RANK.search(title):
            academic.append("faculty")
        categories = academic or ["staff"]
    if "staff" in categories:
        if _FACULTY_RANK.search(title):
            # "Assistant Professor of Instructional Design" is a faculty post.
            categories.remove("staff")
        elif "faculty" in categories:
            # "Faculty Developer" is a staff role in a teaching center, not a faculty post.
            categories.remove("faculty")
    searchable_text = "{} {}".format(title, summary)
    functions = [function for function, pattern in _FUNCTION_RULES if pattern.search(searchable_text)]
    return categories, functions


# Teaching-focused positions: a fifth, overlapping audience ("teaching") for people who want a career
# centered on teaching. A job can be both, for example "faculty" and "teaching". Evidence must be in the
# title or the hiring institution's name, so research-focused posts that merely mention teaching duties
# are not included.
_TEACHING_TITLE = re.compile(
    r"\bteaching[- ](?:professors?|faculty|track|stream|postdoc\w*|fellow\w*|scholars?|associates?|specialists?)\b"
    r"|\bprofessors?\s+of\s+(?:the\s+)?(?:teaching|practice|instruction)\b"
    r"|\b(?:professors?|faculty)\s*,?\s*\(?(?:teaching|instructional)[- ](?:track|stream|line)\)?"
    r"|\b(?:senior\s+|principal\s+|associate\s+)?lecturers?\b"
    r"|\b(?:clinical\s+)?instructors?\b"
    r"|\bpost[ -]?doctoral\s+(?:teaching|education(?:al)?)\s+(?:fellows?|scholars?|associates?|fellowships?)\b"
    r"|\bpostdoc\w*\s+in\s+(?:teaching|stem education|science education|biology education)\b"
    r"|\bIRACDA\b"
    r"|\bgraduate\s+teaching\s+(?:assistant|assistantship|fellow)s?\b|\bteaching\s+assistantships?\b",
    re.IGNORECASE,
)
_TEACHING_INSTITUTION = re.compile(
    r"\bcommunity\s+college\b|\btechnical\s+(?:and\s+community\s+)?college\b|\btwo[- ]year\s+college\b"
    r"|\bjunior\s+college\b|\bstate\s+technical\b",
    re.IGNORECASE,
)
_ACADEMIC = ("graduates", "postdocs", "faculty")


def is_teaching_focused(title: str, company: str = "", categories=()) -> bool:
    """True when the title names a teaching-focused role, or the employer is a two-year college,
    for graduate, postdoctoral, or faculty positions."""
    if categories and not any(c in _ACADEMIC for c in categories):
        return False
    if _TEACHING_TITLE.search(title or ""):
        return True
    return bool(_TEACHING_INSTITUTION.search("{} {}".format(title or "", company or "")))


def with_teaching(categories: List[str], title: str, company: str = "") -> List[str]:
    """Add the overlapping "teaching" audience when the job is teaching-focused."""
    categories = [c for c in categories if c != "teaching"]
    if is_teaching_focused(title, company, categories):
        categories.append("teaching")
    return categories
