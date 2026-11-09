import re
from typing import Iterable, List, Sequence, Set, Tuple

from stemed_jobs import stemedplus_disciplines as shared


# The disciplines and the words that match them come from the STEMEd+ discipline
# list shared across STEMEd+ Commons (see stemedplus_disciplines.py). The term
# alternations below are also used by relevance.py, which looks for
# "<name> education" in titles.
EARTH_TERMS = shared.terms("earth_science")
CHEMISTRY_TERMS = shared.terms("chemistry")
BIOSCIENCE_TERMS = shared.terms("bioscience")
PHYSICS_TERMS = shared.terms("physics")
HEALTH_TERMS = shared.terms("health_education")

# Acronyms such as PER, CER, GER and BER match only when written in capitals;
# otherwise "per year" or "per hour" in a description would tag a job as Physics.
DISCIPLINE_RULES: Tuple[Tuple[str, re.Pattern], ...] = shared.rules()

DISCIPLINES = tuple(name for name, _ in DISCIPLINE_RULES)

_DBER_TITLE = re.compile(r"\bDBER\b", re.IGNORECASE)

# A unit name is a run of capitalized words, optionally joined by "and", "&",
# "of" or "the", e.g. "Mechanical & Industrial Engineering". Words such as
# College or University end the name, so "Department of Physics and the Grainger
# College of Engineering" names Physics only.
_UNIT_STOP = r"(?!(?:College|School|Faculty|Institute|University|Department|Dept|Program|Programme)\b)"
_NAME_TOKEN = r"(?:" + _UNIT_STOP + r"[A-Z][\w'’-]*|and|&|of|the)"
_UNIT_NAME = _NAME_TOKEN + r"(?:,?\s+" + _NAME_TOKEN + r"){0,6}"

# The hiring department or program: "Department of Physics", "Computer
# Engineering Department", "Systems Engineering Program".
_NARROW_UNIT = (
    re.compile(
        r"\b(?:Departments?|Dept\.?|Programs?|Programmes?)\s+(?:of|in)\s+(?:the\s+)?(?P<name>" + _UNIT_NAME + ")"
    ),
    re.compile(
        r"\b(?P<name>" + _UNIT_NAME + r")\s+(?:Departments?|Dept\.?|Programs?|Programmes?)\b(?!\s+(?:of|in)\b)"
    ),
)

# A school, college or institute. It is the hiring unit at some universities
# ("School of Electrical and Computer Engineering") and only the parent of the
# department at others ("Grainger College of Engineering"), so it is weaker
# evidence than a department or program.
_BROAD_UNIT = (
    re.compile(
        r"\b(?:Colleges?|Schools?|Faculty|Faculties|Institutes?)\s+of\s+(?:the\s+)?(?P<name>" + _UNIT_NAME + ")"
    ),
)


def matching_disciplines(text: str) -> List[str]:
    return [name for name, pattern in DISCIPLINE_RULES if pattern.search(text)]


def _first_unit_disciplines(patterns: Iterable[re.Pattern], text: str) -> List[str]:
    """Disciplines of the earliest unit named in the text that names any.

    The hiring unit is nearly always named before collaborators, parent
    colleges and other units, so later units are ignored.
    """
    hits = sorted((match.start(), match.group("name")) for pattern in patterns for match in pattern.finditer(text))
    for _, name in hits:
        found = matching_disciplines(name)
        if found:
            return found
    return []


def _dominant_disciplines(text: str) -> List[str]:
    """Disciplines mentioned at least twice and more than half as often as the top one."""
    counts = {name: sum(1 for _ in pattern.finditer(text)) for name, pattern in DISCIPLINE_RULES}
    top = max(counts.values())
    if top < 2:
        return []
    return [name for name, count in counts.items() if count >= 2 and count * 2 > top]


def _ordered(found: Set[str]) -> List[str]:
    return [name for name, _ in DISCIPLINE_RULES if name in found]


# Curriculum specialist, writer, coordinator, developer and designer roles (K-12 or
# higher education).
# They are listed only when they are STEM or in a followed discipline: under the
# discipline the title names ("Biology Curriculum Specialist"), under every
# discipline when the title says STEM in general ("STEM Curriculum Writer"), and
# otherwise under disciplines the posting itself gives evidence for. The phrase
# "curriculum ..." alone never counts as Learning Science.
CURRICULUM_ROLE = re.compile(r"\bcurriculum\s+(?:specialists?|writers?|coordinators?|developers?|designers?|development|design)\b", re.IGNORECASE)
_CURRICULUM_PHRASE = re.compile(r"\bcurricul(?:um|a|ar)\b(?:\s+(?:and\s+)?(?:design|development|developers?|specialists?|writers?|coordinators?|writing))*", re.IGNORECASE)
_GENERAL_STEM = re.compile(r"\b(?-i:STEM|STEAM|STEMM)\b", re.IGNORECASE)
# Short subject words common in curriculum titles but not discipline terms themselves.
_CURRICULUM_SUBJECTS = (
    ("Mathematics", re.compile(r"\bmaths?\b", re.IGNORECASE)),
    ("Engineering", re.compile(r"\bcomputer science\b|\bcomputing\b|\bcoding\b", re.IGNORECASE)),
)
_GENERAL_SCIENCE = re.compile(r"\bsciences?\b", re.IGNORECASE)
_NOT_SCIENCE = re.compile(
    r"\b(?:social|political|library|information|behaviou?ral|family and consumer|consumer|exercise|sport|data)\s+sciences?\b"
    r"|\barts,?\s+(?:and|&)\s+sciences?\b",
    re.IGNORECASE,
)


def is_curriculum_role(title: str) -> bool:
    return bool(CURRICULUM_ROLE.search(title))


def _curriculum_disciplines(title: str, summary: str, default: Sequence[str]) -> List[str]:
    plain_title = _CURRICULUM_PHRASE.sub(" ", title)
    found = set(matching_disciplines(plain_title))
    found |= {name for name, pattern in _CURRICULUM_SUBJECTS if pattern.search(plain_title)}
    if found:
        return _ordered(found)
    if _GENERAL_STEM.search(title):
        return list(DISCIPLINES)
    if _GENERAL_SCIENCE.search(_NOT_SCIENCE.sub(" ", plain_title)):
        return ["Science Education"]
    return _classify(plain_title, _CURRICULUM_PHRASE.sub(" ", summary), default)


def classify_disciplines(title: str, summary: str, default: Sequence[str] = ()) -> List[str]:
    if is_curriculum_role(title):
        return _curriculum_disciplines(title, summary, default)
    return _classify(title, summary, default)


def _classify(title: str, summary: str, default: Sequence[str] = ()) -> List[str]:
    """Assign disciplines from the strongest evidence available.

    The first of these that finds a discipline decides:

    1. DBER titles are cross-listed under every discipline found in the title
       or description, because those postings are explicitly multi-discipline.
    2. The title, plus the first department or program named in the posting
       ("Department of Physics", "Systems Engineering Program").
    3. ``default``: the disciplines of the feed the job came from, for boards
       devoted to one field such as MathJobs.
    4. The first school, college or institute named in the posting.
    5. Disciplines the description mentions at least twice and more than half as
       often as the most-mentioned one.

    A passing mention of a discipline in the description never qualifies a
    posting when better evidence exists. A posting with no evidence at all gets
    no discipline and so appears in no discipline list.
    """
    if _DBER_TITLE.search(title):
        return _ordered(set(matching_disciplines("{} {}".format(title, summary))))

    text = "{}. {}".format(title, summary)
    found = set(matching_disciplines(title)) | set(_first_unit_disciplines(_NARROW_UNIT, text))
    if not found:
        found = {name for name in default if name in DISCIPLINES}
    if not found:
        found = set(_first_unit_disciplines(_BROAD_UNIT, text))
    if not found:
        found = set(_dominant_disciplines(summary))
    return _ordered(found)
