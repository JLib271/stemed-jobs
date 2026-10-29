"""Find an application deadline stated in a posting's own text.

Feeds rarely give the deadline as a field, so it is read from phrases such as
"application deadline is January 8, 2027" or "submit your application by
23 November 2026". Only a date that follows a deadline phrase counts, and
"review of applications begins ..." is not a deadline. When no deadline can be
read the result is None; nothing is guessed.
"""

import re
from datetime import date, datetime
from typing import Optional

_MONTHS = {
    name: number
    for number, names in enumerate(
        (
            ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
            ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
            ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"), ("december", "dec"),
        ),
        start=1,
    )
    for name in names
}
_MONTH = r"(?P<month>{})\.?".format("|".join(sorted(_MONTHS, key=len, reverse=True)))

# A deadline phrase, then (within a short stretch) a date.
_TRIGGER = (
    r"(?:application\s+)?deadline|deadline\s+(?:for\s+applications?|to\s+apply)"
    r"|applications?\s+(?:are\s+|is\s+|must\s+be\s+(?:received|submitted)\s+)?(?:due|close[sd]?)"
    r"|(?:apply|applications?\s+(?:accepted|received)|submit\s+(?:your\s+)?applications?)\s+(?:by|before|until|through)"
    r"|(?:closing|close)\s+date|closes?\s+(?:on)?|due\s+(?:on|by)?|must\s+be\s+received\s+by"
)
_DATE_FORMS = (
    r"{month}\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(?P<year>\d{{4}}))?".format(month=_MONTH),
    r"(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{month}(?:,?\s+(?P<year>\d{{4}}))?".format(month=_MONTH),
)
_NUMERIC = re.compile(r"(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})|(?P<m2>\d{1,2})/(?P<d2>\d{1,2})/(?P<y2>\d{4})")
_REVIEW = re.compile(r"review|consider|begin|start|screen", re.IGNORECASE)
_PATTERNS = [
    re.compile(r"(?P<trigger>{})\W{{0,40}}?(?:is\s+|are\s+|:\s*)?(?:on\s+)?(?:(?:mon|tues?|wednes|thurs?|fri|satur|sun)day,?\s+)?{}".format(_TRIGGER, form), re.IGNORECASE)
    for form in _DATE_FORMS
]
_NUMERIC_PATTERN = re.compile(r"(?P<trigger>{})\W{{0,40}}?(?:is\s+|are\s+|:\s*)?{}".format(_TRIGGER, _NUMERIC.pattern), re.IGNORECASE)


def _build(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extract_deadline(text: str, posted: Optional[date] = None) -> Optional[date]:
    """The latest deadline-like date in ``text``, or None.

    A date with no year takes the posting date's year, or the next year when that
    would fall well before the posting. Without a posting date such dates are
    skipped.
    """
    found = []
    for pattern in _PATTERNS:
        for match in pattern.finditer(text or ""):
            if _REVIEW.search(match.group("trigger")) or _REVIEW.search(text[max(0, match.start() - 40):match.start()]):
                continue
            month = _MONTHS[match.group("month").lower()]
            day = int(match.group("day"))
            if match.group("year"):
                result = _build(int(match.group("year")), month, day)
            elif posted:
                result = _build(posted.year, month, day)
                if result and (posted - result).days > 7:
                    result = _build(posted.year + 1, month, day)
            else:
                result = None
            if result:
                found.append(result)
    for match in _NUMERIC_PATTERN.finditer(text or ""):
        if _REVIEW.search(text[max(0, match.start() - 40):match.start()]):
            continue
        if match.group("y"):
            result = _build(int(match.group("y")), int(match.group("m")), int(match.group("d")))
        else:
            result = _build(int(match.group("y2")), int(match.group("m2")), int(match.group("d2")))
        if result:
            found.append(result)
    return max(found) if found else None


def parse_day(value: str) -> Optional[date]:
    try:
        return datetime.strptime((value or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
