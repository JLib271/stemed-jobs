import re
from typing import List, Tuple


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
    (
        "Technology",
        re.compile(
            r"\btechnology education\b|\beducational technology\b|\bcomputer science\b"
            r"|\bcomputing education\b|\binformatics\b|\bartificial intelligence\b"
            r"|\bmachine learning\b|\bcybersecurity\b|\bdigital learning\b",
            re.IGNORECASE,
        ),
    ),
)

DISCIPLINES = tuple(name for name, _ in DISCIPLINE_RULES) + ("Other",)


_DBER_TITLE = re.compile(r"\bDBER\b", re.IGNORECASE)

# A unit name is a run of capitalized words, optionally joined by "and", "&",
# "of" or "the", e.g. "Mechanical & Industrial Engineering".
_NAME_TOKEN = r"(?:[A-Z][\w'’-]*|and|&|of|the)"
_UNIT_NAME = _NAME_TOKEN + r"(?:,?\s+" + _NAME_TOKEN + r"){0,6}"

# The hiring department or program: "Department of Physics", "Mathematics Program".
_DEPARTMENT_PHRASES = (
    re.compile(r"\b(?:Department|Dept\.?|Program|Programme)\s+of\s+(?:the\s+)?(?P<name>" + _UNIT_NAME + ")"),
    re.compile(r"\b(?P<name>" + _UNIT_NAME + r")\s+(?:Department|Dept\.?|Program|Programme)\b(?!\s+of\b)"),
)

# Broader units: "Grainger College of Engineering", "School of Science and
# Engineering". Many postings name one only to say where the department sits.
_BROAD_UNIT = re.compile(r"\b(?:College|School|Faculty|Institute)\s+of\s+(?P<name>" + _UNIT_NAME + ")")


def _matching_disciplines(text: str) -> List[str]:
    return [name for name, pattern in DISCIPLINE_RULES if pattern.search(text)]


def _dominant_disciplines(text: str) -> List[str]:
    """Disciplines mentioned more than half as often as the most-mentioned one."""
    counts = {
        name: sum(1 for _ in pattern.finditer(text)) for name, pattern in DISCIPLINE_RULES
    }
    top = max(counts.values())
    if top == 0:
        return []
    return [name for name, count in counts.items() if count * 2 > top]


def classify_disciplines(title: str, summary: str) -> List[str]:
    """Assign disciplines from the strongest evidence available.

    1. DBER titles are cross-listed under every discipline found in the title
       or description, because those postings are explicitly multi-discipline.
    2. Otherwise a discipline counts when it appears in the title or names the
       hiring department or program ("Department of Physics").
    3. If that finds nothing, the description is counted, ignoring college and
       school names (a physics department in a College of Engineering is not an
       engineering job), and only the most-mentioned disciplines are kept.
    4. As a last resort, college and school names are counted the same way.

    A passing mention of a discipline in the description never qualifies a
    posting on its own when better evidence exists.
    """
    if _DBER_TITLE.search(title):
        return _matching_disciplines("{} {}".format(title, summary)) or ["Other"]

    found = set(_matching_disciplines(title))
    text = "{}. {}".format(title, summary)
    unit_names = [
        match.group("name") for pattern in _DEPARTMENT_PHRASES for match in pattern.finditer(text)
    ]
    found.update(_matching_disciplines(" ; ".join(unit_names)))

    if not found:
        found.update(_dominant_disciplines(_BROAD_UNIT.sub(" ", summary)))
    if not found:
        found.update(_dominant_disciplines(" ; ".join(m.group("name") for m in _BROAD_UNIT.finditer(summary))))

    ordered = [name for name, _ in DISCIPLINE_RULES if name in found]
    return ordered or ["Other"]
