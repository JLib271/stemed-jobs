"""The STEMEd+ disciplines, shared across STEMEd+ Commons through HuMeta.

The disciplines (ids, labels, definitions, and the words that match them) are
kept in one file in HuMeta, standard/humeta/stemedplus_disciplines.json. This
site keeps a copy next to this module and builds from it, so it always works
offline. Run ``python -m <package>.stemedplus_disciplines --refresh [path]``
(the build workflow does) to replace the copy with the current HuMeta version; if
the download fails or the new file is not valid, the copy is left as it was.

This module is identical in every STEMEd+ site. Change it in all of them.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SOURCE_URL = (
    "https://raw.githubusercontent.com/JLib271/HuMeta/main/standard/humeta/stemedplus_disciplines.json"
)
VENDORED = Path(__file__).with_name("stemedplus_disciplines.json")
_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_ACRONYM = re.compile(r"^[A-Z][A-Z0-9]*$")


def validate(doc: dict) -> List[dict]:
    """Return the disciplines in ``doc``, or raise ValueError if it is not usable."""
    if not isinstance(doc, dict) or not isinstance(doc.get("disciplines"), list) or not doc["disciplines"]:
        raise ValueError("no disciplines list")
    ids, labels = set(), set()
    for d in doc["disciplines"]:
        for key in ("id", "label", "definition", "match"):
            if key not in d:
                raise ValueError(f"discipline missing {key}: {d!r}")
        if not _ID.match(d["id"]) or d["id"] in ids:
            raise ValueError(f"bad or repeated id {d['id']!r}")
        if not d["label"] or d["label"] in labels:
            raise ValueError(f"bad or repeated label {d['label']!r}")
        ids.add(d["id"])
        labels.add(d["label"])
        if d.get("scope", "education") not in ("education", "field"):
            raise ValueError(f"bad scope for {d['id']}")
        acronyms = d["match"].get("acronyms", [])
        if not d["match"].get("terms") or any(not _ACRONYM.match(a) for a in acronyms):
            raise ValueError(f"bad match for {d['id']}")
        compile_rule(d)  # raises re.error, a ValueError, if a pattern is broken
    return doc["disciplines"]


def compile_rule(discipline: dict) -> re.Pattern:
    """Whole-word, case-insensitive terms; acronyms match only in capitals."""
    match = discipline["match"]
    pattern = r"\b(?:" + match["terms"] + r")\b"
    pattern += "".join(r"|\b(?-i:" + a + r")\b" for a in match.get("acronyms", []))
    return re.compile(pattern, re.IGNORECASE)


def load(path: Path = VENDORED) -> List[dict]:
    return validate(json.loads(Path(path).read_text(encoding="utf-8")))


def rules(path: Path = VENDORED) -> Tuple[Tuple[str, re.Pattern], ...]:
    """(label, pattern) pairs, in the shared order."""
    return tuple((d["label"], compile_rule(d)) for d in load(path))


def labels_by_id(path: Path = VENDORED) -> Dict[str, str]:
    return {d["id"]: d["label"] for d in load(path)}


def field_labels(path: Path = VENDORED) -> Tuple[str, ...]:
    """Labels of disciplines that include the field itself, not only education in it."""
    return tuple(d["label"] for d in load(path) if d.get("scope") == "field")


def terms(discipline_id: str, path: Path = VENDORED) -> str:
    """The regex alternation of one discipline's terms, without word boundaries."""
    for d in load(path):
        if d["id"] == discipline_id:
            return d["match"]["terms"]
    raise KeyError(discipline_id)


def refresh(url: str = SOURCE_URL, path: Path = VENDORED, timeout: float = 30) -> str:
    """Replace the copy with HuMeta's current file if it downloads and is valid."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        validate(json.loads(raw))
    except Exception as error:  # keep the copy on any failure
        return f"kept the stored disciplines ({type(error).__name__}: {error})"
    if Path(path).exists() and Path(path).read_text(encoding="utf-8") == raw:
        return "stored disciplines are current"
    Path(path).write_text(raw, encoding="utf-8")
    return "updated the stored disciplines from HuMeta"


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[1]) if len(argv) > 1 else VENDORED
    if argv[:1] == ["--refresh"]:
        print(refresh(path=path))
        return 0
    for d in load(Path(argv[0]) if argv else VENDORED):
        print(f"{d['id']}: {d['label']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
