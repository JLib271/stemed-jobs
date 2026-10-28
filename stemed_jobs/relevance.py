import re
from typing import Dict, Pattern

from stemed_jobs.models import Job


_STEM_DISCIPLINES = {
    "Agriculture",
    "Bioscience",
    "Chemistry",
    "Earth Science",
    "Engineering",
    "Mathematics",
    "Physics",
    "Technology",
}

_DISCIPLINE_SIGNALS: Dict[str, Pattern[str]] = {
    "Physics": re.compile(
        r"\bphysics education\b|\bPER\b"
        r"|\b(?:quantum|astronomy|astrophysics|particle|nuclear|optics|mechanics|"
        r"thermodynamics|electromagnetism|acoustics) education\b",
        re.IGNORECASE,
    ),
    "Chemistry": re.compile(r"\bchemistry education\b|\bCER\b", re.IGNORECASE),
    "Earth Science": re.compile(
        r"\bGER\b|\bearth science education\b|\bgeoscience education\b"
        r"|\benvironmental education\b|\benvironmental science education\b",
        re.IGNORECASE,
    ),
    "Bioscience": re.compile(
        r"\bBER\b|\bbioscience education\b|\bbiology education\b"
        r"|\b(?:genetics|ecology|evolution|microbiology|molecular biology|"
        r"cell biology|anatomy|physiology) education\b",
        re.IGNORECASE,
    ),
    "Engineering": re.compile(r"\bengineering education\b|\bEER\b", re.IGNORECASE),
    "Mathematics": re.compile(r"\bmathematics education\b|\bmath education\b", re.IGNORECASE),
    "Agriculture": re.compile(r"\bagricultural education\b|\bagriculture education\b", re.IGNORECASE),
    "Science Education": re.compile(r"\bSTEM education\b|\bscience education\b|\bDBER\b", re.IGNORECASE),
    "Learning Science": re.compile(r"\bcognitive science\b|\blearning science\b", re.IGNORECASE),
}

_FACULTY_INCLUDE: Pattern[str] = re.compile(
    r"\bteaching\b|\bSoTL\b|\binstructor\b",
    re.IGNORECASE,
)
_DBER: Pattern[str] = re.compile(r"\bDBER\b", re.IGNORECASE)
_DOCTORAL_DEGREE: Pattern[str] = re.compile(
    r"\b(?:Ph\.?\s?D\.?|Ed\.?\s?D\.?|doctorate|doctoral degree)\b",
    re.IGNORECASE,
)
_EDUCATION_FIELD: Pattern[str] = re.compile(
    r"\beducation(?:al)?\b|\blearning sciences?\b|\bDBER\b|\bSoTL\b"
    r"|\bscholarship of teaching and learning\b",
    re.IGNORECASE,
)
_REQUIRED_QUALIFICATION: Pattern[str] = re.compile(
    r"\brequired\b|\bmust\b|\bminimum qualifications?\b|\bis a requirement\b",
    re.IGNORECASE,
)


def is_dber_title(title: str) -> bool:
    return bool(_DBER.search(title))


def requires_education_doctorate(job: Job) -> bool:
    if "faculty" not in job.categories or not _STEM_DISCIPLINES.intersection(job.disciplines):
        return False

    clauses = re.split(r"(?<=[.!?;])\s+|\n|•", job.summary)
    windows = clauses + [
        "{} {}".format(first, second)
        for first, second in zip(clauses, clauses[1:])
    ]
    for window in windows:
        requirement_text = re.sub(
            r"\bnot\s+(?:necessarily\s+)?required\b|\bnot\s+(?:a\s+)?requirement\b",
            "",
            window,
            flags=re.IGNORECASE,
        )
        if (
            _DOCTORAL_DEGREE.search(window)
            and _EDUCATION_FIELD.search(window)
            and _REQUIRED_QUALIFICATION.search(requirement_text)
        ):
            return True
    return False


def is_stem_education_relevant(job: Job, discipline: str) -> bool:
    """Include education-research title signals or explicitly requested faculty teaching roles."""
    title = job.title
    if is_dber_title(title):
        return True
    if requires_education_doctorate(job):
        return discipline in job.disciplines
    if "faculty" in job.categories and _FACULTY_INCLUDE.search(title):
        return discipline in job.disciplines

    pattern = _DISCIPLINE_SIGNALS.get(discipline)
    return bool(pattern and pattern.search(title))
