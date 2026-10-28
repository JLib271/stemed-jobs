import re
from typing import Iterable, List, Sequence, Set, Tuple


# Acronyms such as PER, CER, GER and BER are wrapped in (?-i:...) so they only
# match when written in capitals; otherwise "per year" or "per hour" in a
# description would tag a job as Physics.
DISCIPLINE_RULES: Tuple[Tuple[str, re.Pattern], ...] = (
    ("Agriculture", re.compile(r"\bagricultur(?:e|al|a)?\b|\bagri[- ]?science\b|\bag ed\b", re.IGNORECASE)),
    (
        "Bioscience",
        re.compile(
            r"\bbio(?:logy|logical|science|engineering)?\b"
            r"|\blife sciences?\b|\bmolecular biology\b|\bgenetics\b|\becology\b"
            r"|\bmicrobiology\b|\banatomy\b|\bphysiology\b|\b(?-i:BER)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Chemistry",
        re.compile(
            r"\bchemistr(?:y|ies)\b|\bchemical sciences?\b|\bchemical education\b|\b(?-i:CER)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Earth Science",
        re.compile(
            r"\bearth sciences?\b|\bgeosciences?\b|\bgeology\b|\bclimate\b"
            r"|\benvironmental sciences?\b|\benvironmental education\b|\bmeteorology\b"
            r"|\boceanography\b|\b(?-i:GER)\b",
            re.IGNORECASE,
        ),
    ),
    ("Engineering", re.compile(r"\bengineering\b|\bengineer(?:s|ing)?\b", re.IGNORECASE)),
    (
        "Learning Science",
        re.compile(
            r"\blearning sciences?\b|\bcognitive sciences?\b|\bcognition\b"
            r"|\beducational psychology\b|\blearning analytics\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Mathematics",
        re.compile(
            r"\bmathematics\b|\bmath(?:ematics)? education\b|\bmathematical sciences?\b|\bstatistics\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Physics",
        re.compile(
            r"\bphysics\b|\bphysicist\b|\bphysics education\b|\bphysical sciences?\b|\b(?-i:PER)\b"
            r"|\bquantum\b|\bastrophysics\b|\bastronomy\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Science Education",
        re.compile(
            r"\bscience education\b|\bscience teaching\b|\bscience teacher education\b"
            r"|\bscience teachers?\b|\bstem education\b|\bstem teaching\b|\bstem teachers?\b"
            r"|\bdiscipline[- ]based education research\b"
            r"|\bdber\b",
            re.IGNORECASE,
        ),
    ),
)

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


def _matching_disciplines(text: str) -> List[str]:
    return [name for name, pattern in DISCIPLINE_RULES if pattern.search(text)]


def _first_unit_disciplines(patterns: Iterable[re.Pattern], text: str) -> List[str]:
    """Disciplines of the earliest unit named in the text that names any.

    The hiring unit is nearly always named before collaborators, parent
    colleges and other units, so later units are ignored.
    """
    hits = sorted((match.start(), match.group("name")) for pattern in patterns for match in pattern.finditer(text))
    for _, name in hits:
        found = _matching_disciplines(name)
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


def classify_disciplines(title: str, summary: str, default: Sequence[str] = ()) -> List[str]:
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
        return _ordered(set(_matching_disciplines("{} {}".format(title, summary))))

    text = "{}. {}".format(title, summary)
    found = set(_matching_disciplines(title)) | set(_first_unit_disciplines(_NARROW_UNIT, text))
    if not found:
        found = {name for name in default if name in DISCIPLINES}
    if not found:
        found = set(_first_unit_disciplines(_BROAD_UNIT, text))
    if not found:
        found = set(_dominant_disciplines(summary))
    return _ordered(found)
