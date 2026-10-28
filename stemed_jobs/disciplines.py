import re
from typing import List, Tuple


DISCIPLINE_RULES: Tuple[Tuple[str, re.Pattern], ...] = (
    ("Agriculture", re.compile(r"\bagricultur(?:e|al|a)?\b|\bagri[- ]?science\b|\bag ed\b", re.IGNORECASE)),
    (
        "Bioscience",
        re.compile(
            r"\bbio(?:logy|logical|science|medical|medical|engineering)?\b"
            r"|\blife sciences?\b|\bmolecular biology\b|\bgenetics\b|\becology\b"
            r"|\bmicrobiology\b|\banatomy\b|\bphysiology\b",
            re.IGNORECASE,
        ),
    ),
    ("Chemistry", re.compile(r"\bchemistr(?:y|ies)\b|\bchemical sciences?\b|\bchemical education\b", re.IGNORECASE)),
    (
        "Earth Science",
        re.compile(
            r"\bearth sciences?\b|\bgeosciences?\b|\bgeology\b|\bclimate\b"
            r"|\benvironmental sciences?\b|\bmeteorology\b|\boceanography\b",
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
    ("Mathematics", re.compile(r"\bmathematics\b|\bmath(?:ematics)? education\b|\bstatistics\b", re.IGNORECASE)),
    (
        "Physics",
        re.compile(
            r"\bphysics\b|\bphysicist\b|\bphysics education\b|\bphysical sciences?\b"
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


def classify_disciplines(title: str, summary: str) -> List[str]:
    text = "{} {}".format(title, summary)
    matches = [name for name, pattern in DISCIPLINE_RULES if pattern.search(text)]
    return matches or ["Other"]
