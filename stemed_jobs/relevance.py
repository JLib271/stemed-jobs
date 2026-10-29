import re
from typing import Dict, Pattern

from stemed_jobs.disciplines import BIOSCIENCE_TERMS, CHEMISTRY_TERMS, EARTH_TERMS, HEALTH_TERMS, PHYSICS_TERMS
from stemed_jobs.disciplines import matching_disciplines
from stemed_jobs.models import Job


_STEM_DISCIPLINES = {
    "Agriculture",
    "Bioscience",
    "Chemistry",
    "Earth Science",
    "Engineering",
    "Mathematics",
    "Physics",
}


def _education_in(terms: str) -> str:
    """A subfield name followed by "education", e.g. "geology education"."""
    return r"\b(?:" + terms + r")\s+education\b"


_DISCIPLINE_SIGNALS: Dict[str, Pattern[str]] = {
    "Physics": re.compile(_education_in(PHYSICS_TERMS) + r"|\b(?-i:PER)\b", re.IGNORECASE),
    "Chemistry": re.compile(
        _education_in(CHEMISTRY_TERMS) + r"|\bchemical education\b|\b(?-i:CER)\b", re.IGNORECASE
    ),
    "Earth Science": re.compile(
        _education_in(EARTH_TERMS) + r"|\benvironmental education\b|\b(?-i:GER)\b", re.IGNORECASE
    ),
    "Bioscience": re.compile(_education_in(BIOSCIENCE_TERMS) + r"|\b(?-i:BER)\b", re.IGNORECASE),
    "Health Education": re.compile(
        _education_in(HEALTH_TERMS) + r"|\bhealth education\b|\bhealth ?care education\b|\bmedical education\b"
        r"|\bnursing education\b|\bhealth professions education\b",
        re.IGNORECASE,
    ),
    "Engineering": re.compile(r"\bengineering education\b|\b(?-i:EER)\b", re.IGNORECASE),
    "Mathematics": re.compile(r"\bmathematics education\b|\bmath education\b", re.IGNORECASE),
    "Agriculture": re.compile(r"\bagricultural education\b|\bagriculture education\b", re.IGNORECASE),
    "Science Education": re.compile(r"\bSTEM education\b|\bscience education\b|\bDBER\b", re.IGNORECASE),
    "Learning Science": re.compile(
        r"\bcognitive sciences?\b|\blearning sciences?\b|\beducational psychology\b", re.IGNORECASE
    ),
}

# These field names are specific enough that naming one anywhere in the posting
# (title or description), not just the title, shows the job belongs to the field.
_LEARNING_SCIENCE_TERMS: Pattern[str] = _DISCIPLINE_SIGNALS["Learning Science"]

_FACULTY_INCLUDE: Pattern[str] = re.compile(
    r"\bteaching\b|\bSoTL\b|\binstructor\b",
    re.IGNORECASE,
)
# Named research instructorships ("Bernoulli Instructor", "Courant Instructor",
# "Hermann-Weyl Instructor") are postdoc-style research appointments that happen
# to be called Instructor; they are not teaching-focused roles. The name is a
# single capitalized word right before the rank, so generic ranks are excluded.
_GENERIC_RANK_WORD = (
    r"(?:Visiting|Assistant|Associate|Senior|Junior|Clinical|Adjunct|Teaching|Full-time|Part-time|Temporary"
    r"|Lead|Principal|Research|Faculty|Graduate|Postdoctoral|Open|Tenure-track|Online|Hybrid|Remote|Lab|Laboratory"
    r"|Summer|Fall|Spring|Winter|Interim|Substitute|Contingent|Continuing|Guest|Emeritus|Distinguished|Endowed|Named)"
)
_NAMED_INSTRUCTORSHIP: Pattern[str] = re.compile(
    r"(?-i:\b(?!" + _GENERIC_RANK_WORD + r"\b)(?P<name>[A-Z][\w'’]+(?:-[A-Z][\w'’]+)?)\s+"
    r"(?:Instructor|Lecturer|Assistant Professor)\b)"
)
_TEACHING_IN_TITLE: Pattern[str] = re.compile(r"\bteaching\b|\beducation\b|\bpedagog\w*|\bSoTL\b", re.IGNORECASE)
_DBER: Pattern[str] = re.compile(r"\bDBER\b", re.IGNORECASE)
_EDUCATION_DOCTORATE: Pattern[str] = re.compile(
    r"\b(?:Ph\.?\s?D\.?|Ed\.?\s?D\.?|doctorate|doctoral degree)"
    r"\s+(?:degree\s+)?in\s+"
    r"(?:STEM|science|physics|chemistry|biology|bioscience|earth science|"
    r"geoscience|environmental science|engineering|mathematics|math|"
    r"agricultural)?\s*education\b"
    r"|\b(?:Ph\.?\s?D\.?|Ed\.?\s?D\.?|doctorate|doctoral degree)"
    r"\s+(?:degree\s+)?in\s+(?:learning sciences?|educational psychology|DBER|SoTL)\b",
    re.IGNORECASE,
)
_NEGATED_REQUIRED: Pattern[str] = re.compile(r"\bnot\s+(?:necessarily\s+)?required\b", re.IGNORECASE)
_REQUIRED_BEFORE: Pattern[str] = re.compile(
    r"\b(?:must|minimum qualifications?(?:\s+(?:include|are|require))?|requirement is)\b",
    re.IGNORECASE,
)
_REQUIRED_AFTER: Pattern[str] = re.compile(r"\b(?:is\s+)?required\b|\bis a requirement\b", re.IGNORECASE)
_PREFERRED: Pattern[str] = re.compile(r"\bpreferred\b|\bdesirable\b", re.IGNORECASE)


def _is_named_research_instructorship(title: str) -> bool:
    if _TEACHING_IN_TITLE.search(title):
        return False
    # A subject word ("Mathematics Instructor", "Physics Lecturer") is not a name.
    return any(not matching_disciplines(match.group("name")) for match in _NAMED_INSTRUCTORSHIP.finditer(title))


def is_dber_title(title: str) -> bool:
    return bool(_DBER.search(title))


def requires_education_doctorate(job: Job) -> bool:
    if "faculty" not in job.categories or not _STEM_DISCIPLINES.intersection(job.disciplines):
        return False

    summary = re.sub(r"\bPh\.?\s?D\.?", "PhD", job.summary, flags=re.IGNORECASE)
    summary = re.sub(r"\bEd\.?\s?D\.?", "EdD", summary, flags=re.IGNORECASE)
    clauses = re.split(r"(?<=[.!?;])\s+|\n|•", summary)
    for clause in clauses:
        for degree_match in _EDUCATION_DOCTORATE.finditer(clause):
            before = clause[max(0, degree_match.start() - 80) : degree_match.start()]
            after = clause[degree_match.end() : degree_match.end() + 60]
            if _NEGATED_REQUIRED.search(after):
                continue
            if _REQUIRED_BEFORE.search(before):
                return True
            if _REQUIRED_AFTER.search(after) and not _PREFERRED.search(after):
                return True
    return False


def is_stem_education_relevant(job: Job, discipline: str) -> bool:
    """Include education-research title signals or explicitly requested faculty teaching roles."""
    title = job.title
    if is_dber_title(title):
        return discipline in job.disciplines
    if requires_education_doctorate(job):
        return discipline in job.disciplines
    if _is_named_research_instructorship(title):
        return False
    if "faculty" in job.categories and _FACULTY_INCLUDE.search(title):
        return discipline in job.disciplines

    if discipline == "Learning Science" and discipline in job.disciplines:
        return bool(_LEARNING_SCIENCE_TERMS.search(title) or _LEARNING_SCIENCE_TERMS.search(job.summary))

    pattern = _DISCIPLINE_SIGNALS.get(discipline)
    return bool(pattern and pattern.search(title))
