import re
from typing import Pattern

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

_TITLE_RELEVANCE: Pattern[str] = re.compile(
    r"\beducation\b|\blearning\b|\bDBER\b|\bSoTL\b"
    r"|\bhuman dimensions\b|\bcognitive science\b"
    r"|\bteaching\b|\bteacher\b|\blecturer\b|\binstructor\b",
    re.IGNORECASE,
)
_MACHINE_LEARNING_TITLE: Pattern[str] = re.compile(r"\bmachine learning\b", re.IGNORECASE)
_CLEAR_EDUCATION_TITLE: Pattern[str] = re.compile(
    r"\beducation\b|\bDBER\b|\bSoTL\b|\bscholarship of teaching and learning\b"
    r"|\bhuman dimensions\b|\bcognitive science\b|\blearning sciences?\b"
    r"|\bteaching\b|\bteacher\b|\blecturer\b|\binstructor\b",
    re.IGNORECASE,
)
_EDUCATION_RESEARCH: Pattern[str] = re.compile(
    r"\beducation(?:al)? research\b"
    r"|\b(?:discipline[- ]based education research|DBER|PER|CER)\b"
    r"|\b(?:SoTL|scholarship of teaching and learning)\b"
    r"|\b(?:STEM|science|physics|chemistry|biology|bioscience|engineering|"
    r"mathematics|math|earth science|geoscience|agricultural) education research\b",
    re.IGNORECASE,
)
_HUMAN_DIMENSIONS: Pattern[str] = re.compile(r"\bhuman dimensions\b", re.IGNORECASE)
_COGNITIVE_SCIENCE: Pattern[str] = re.compile(r"\bcognitive science\b|\bcognitive scientist\b", re.IGNORECASE)
_STEM_EDUCATION: Pattern[str] = re.compile(
    r"\b(?:STEM|science|physics|chemistry|biology|bioscience|engineering|"
    r"mathematics|math|earth science|geoscience|agricultural) education\b"
    r"|\b(?:STEM|science|physics|chemistry|biology|bioscience|engineering|"
    r"mathematics|math|earth science|geoscience) teaching\b",
    re.IGNORECASE,
)
_TEACHING_ROLE: Pattern[str] = re.compile(
    r"\bteaching\b|\binstruction(?:al)?\b|\bteacher\b|\blecturer\b|\binstructor\b",
    re.IGNORECASE,
)


def is_stem_education_relevant(job: Job) -> bool:
    """Keep STEM jobs whose title signals education, learning, or teaching relevance."""
    if not _STEM_DISCIPLINES.intersection(job.disciplines):
        return False

    if not _TITLE_RELEVANCE.search(job.title):
        return False
    if _MACHINE_LEARNING_TITLE.search(job.title) and not _CLEAR_EDUCATION_TITLE.search(job.title):
        return False

    text = "{} {}".format(job.title, job.summary)
    if (
        _EDUCATION_RESEARCH.search(text)
        or _HUMAN_DIMENSIONS.search(text)
        or _COGNITIVE_SCIENCE.search(text)
        or _STEM_EDUCATION.search(text)
    ):
        return True

    return bool(_TEACHING_ROLE.search(job.title))
