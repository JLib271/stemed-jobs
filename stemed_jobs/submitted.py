"""Positions submitted through the Seekers' Hub form, without a blog post in between.

How it works:

1. Someone fills in the job form on the Seekers' Hub, which emails the submission to the editor.
2. The editor pastes that email into the GitHub issue template "Add a submitted position (editors)"
   and adds the "approved" label.
3. .github/workflows/add-position.yml runs `python -m stemed_jobs.submitted --issue`, which reads the
   email by its field names and saves the position as `submitted/<id>.json`, then republishes the site.
4. Every run of the site reads `submitted/` as one more feed ("STEMEd+ submissions"). Positions leave the
   site on the same rules as any other (a stated deadline, or the academic hiring year).

    python -m stemed_jobs.submitted --write-spec     # rewrite docs/seekers-hub-form.md and the issue form
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from stemed_jobs.classification import classify_job
from stemed_jobs.deadlines import extract_deadline, extract_review_start
from stemed_jobs.disciplines import DISCIPLINES, classify_disciplines
from stemed_jobs.models import Feed, FeedResult, Job

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "submitted"
SPEC = ROOT / "docs" / "seekers-hub-form.md"
TEMPLATE = ROOT / ".github" / "ISSUE_TEMPLATE" / "add-submitted-position.yml"
FEED = Feed(name="STEMEd+ submissions", url="https://theseekershub.stemedplus.org/", curated=True)

# Field key -> the field's name on the Seekers' Hub form (the email shows these names).
LABELS: Dict[str, str] = {
    "title": "Position title",
    "institution": "Institution or organization",
    "location": "Location",
    "audiences": "Who is this position for?",
    "disciplines": "Disciplines",
    "url": "Link to the official posting",
    "deadline": "Application deadline",
    "review": "Review of applications begins",
    "description": "Description",
    "contact": "Your name and email (for the reviewer only)",
}
REQUIRED = ("title", "institution", "location", "audiences", "url", "description")
AUDIENCES = {"Graduate Student": "graduates", "Postdoc": "postdocs", "Faculty": "faculty",
             "Professional Staff": "staff"}
DESCRIPTION_MAX = 2000
PASTE_LABEL = "The form email, pasted whole"


def _norm(text: str) -> str:
    text = re.sub(r"\([^)]*\)", "", text or "")
    text = re.sub(r"[*:?]+\s*$", "", text.strip())
    return " ".join(text.lower().split())


_KEYS = {_norm(v): k for k, v in LABELS.items()}
_KEYS.update({"title": "title", "job title": "title", "institution": "institution", "organization": "institution",
              "audience": "audiences", "position type": "audiences", "discipline": "disciplines",
              "link": "url", "official posting": "url", "deadline": "deadline", "review begins": "review",
              "your name and email": "contact", "for the reviewer": "contact"})


def sections(text: str) -> Dict[str, str]:
    """The email's answers by field: a field starts at a line that is one of the form's field names,
    alone or followed by ":" and its answer."""
    out, key, buf = {}, None, []
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        found, rest = _KEYS.get(_norm(line)), ""
        if not found and ":" in line:
            left, right = line.split(":", 1)
            found, rest = _KEYS.get(_norm(left)), right
        if found:
            if key:
                out[key] = "\n".join(buf).strip()
            key, buf = found, ([rest.strip()] if rest.strip() else [])
        elif key:
            buf.append(line)
    if key:
        out[key] = "\n".join(buf).strip()
    return out


def _chosen(text: str, options: List[str]) -> List[str]:
    hay = " ".join((text or "").lower().split())
    found = []
    for option in sorted(options, key=len, reverse=True):
        needle = option.lower()
        if needle in hay:
            found.append(option)
            hay = hay.replace(needle, " | ")
    return [o for o in options if o in found]


def _slug(title: str, institution: str, url: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", f"{institution} {title}".lower()).strip("-")[:60].strip("-")
    return f"{base}-{hashlib.sha1(url.encode()).hexdigest()[:6]}"


def from_email(text: str, today: dt.date) -> Tuple[dict, List[str]]:
    """The position a pasted form email describes, and what is wrong with it (empty when fine)."""
    s = {k: v for k, v in sections(text).items() if k != "contact"}   # the poster's details are never kept
    get = lambda k: " ".join((s.get(k) or "").split())  # noqa: E731
    position = {
        "title": get("title"),
        "institution": get("institution"),
        "location": get("location"),
        "audiences": _chosen(s.get("audiences", ""), list(AUDIENCES)),
        "disciplines": _chosen(s.get("disciplines", ""), list(DISCIPLINES)),
        "url": get("url"),
        "deadline": get("deadline"),
        "review": get("review"),
        "description": "\n".join(line.strip() for line in (s.get("description") or "").split("\n")).strip(),
        "approved": today.isoformat(),
    }
    problems = [f"Missing: {LABELS[k]}" for k in REQUIRED if not position[k]]
    if position["url"] and not re.match(r"^https?://\S+$", position["url"]):
        problems.append("The link to the official posting must be a web address starting with http:// or https://")
    if len(position["description"]) > DESCRIPTION_MAX:
        problems.append(f"The description is longer than {DESCRIPTION_MAX} characters; please shorten it.")
    position["id"] = _slug(position["title"], position["institution"], position["url"] or position["title"])
    return position, problems


def to_job(p: dict) -> Job:
    approved = dt.date.fromisoformat(p["approved"])
    published = f"{p['approved']}T12:00:00Z"
    deadline = None
    if p.get("deadline") and p["deadline"].strip().lower() not in ("rolling", "none", "open until filled"):
        deadline = extract_deadline("Application deadline: " + p["deadline"], approved)
    review = extract_review_start("Review of applications begins: " + p["review"], approved) if p.get("review") else None
    summary = " ".join(p["description"].split())
    categories, functions = classify_job(p["title"], summary)
    audiences = [AUDIENCES[a] for a in p.get("audiences", []) if a in AUDIENCES]
    disciplines = list(p.get("disciplines") or []) or classify_disciplines(p["title"], summary, ())
    return Job(id="submitted:" + p["id"], title=p["title"], company=p["institution"], location=p["location"],
               url=p["url"], published=published, summary=summary, source=FEED.name, source_url=FEED.url,
               categories=audiences or categories, functions=functions, disciplines=disciplines,
               deadline=deadline.isoformat() if deadline else "", review_date=review.isoformat() if review else "",
               curated=True)


def load(folder: Path = FOLDER) -> FeedResult:
    jobs = []
    for path in sorted(Path(folder).glob("*.json")):
        try:
            jobs.append(to_job(json.loads(path.read_text(encoding="utf-8"))))
        except (ValueError, KeyError, TypeError) as exc:
            return FeedResult(feed=FEED, error=f"{FEED.name}: {path.name} could not be read ({exc})")
    return FeedResult(feed=FEED, jobs=jobs)


# ---------- the issue intake ----------

def _issue_paste(body: str) -> str:
    m = re.search(r"###\s*" + re.escape(PASTE_LABEL) + r"\s*\n(.*)", body or "", re.S)
    text = (m.group(1) if m else body or "").strip()
    fence = re.match(r"^```[^\n]*\n(.*?)\n?```\s*$", text, re.S)
    return fence.group(1) if fence else text


def handle_issue(body: str, today: dt.date, folder: Path = FOLDER) -> Tuple[bool, str, str]:
    """(changed, position id, reply for the issue)."""
    position, problems = from_email(_issue_paste(body), today)
    if problems:
        return False, "", ("This position was not added yet. Please edit the issue to fix the following, then add "
                           "the approved label again:\n\n" + "\n".join(f"- {p}" for p in problems))
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{position['id']}.json"
    verb = "Updated" if path.exists() else "Added"
    if path.exists():
        position["approved"] = json.loads(path.read_text(encoding="utf-8")).get("approved", position["approved"])
    path.write_text(json.dumps(position, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    where = ", ".join(position["audiences"]) or "matched by keywords"
    return True, position["id"], (f"{verb} **{position['title']}** at {position['institution']} (for: {where}). "
                                  "It will appear on STEMEd+ Jobs and the Seekers' Hub after the site rebuilds, "
                                  "within a few minutes.")


# ---------- the form spec and the GitHub issue form ----------

def spec() -> str:
    out = ["# The Seekers' Hub job form", "",
           "Generated by `python -m stemed_jobs.submitted --write-spec`. Do not edit by hand.", "",
           "Build these fields on the Seekers' Hub form, in this order, with **exactly** these field names and",
           "choices, and have each submission emailed to the editor with every field and its name. The editor",
           "pastes that email into the GitHub issue template \"Add a submitted position (editors)\" and adds the",
           "approved label; the position then appears on STEMEd+ Jobs. No blog post is needed.", ""]
    rows = [
        ("title", "single line of text", True, "", None),
        ("institution", "single line of text", True, "Its full name, not an abbreviation.", None),
        ("location", "single line of text", True, "City and state or country, or Remote.", None),
        ("audiences", "checkboxes (at least one)", True, "", list(AUDIENCES)),
        ("disciplines", "checkboxes (choose any)", False, "Leave blank if none fit; we will sort it by its text.",
         list(DISCIPLINES)),
        ("url", "website address (URL)", True, "Where applicants read the full ad and apply.", None),
        ("deadline", "date, or the word rolling", False, "e.g. January 15, 2027, or rolling.", None),
        ("review", "date", False, "Only if the ad says when review begins.", None),
        ("description", f"paragraph text, up to {DESCRIPTION_MAX} characters", True,
         "A short summary of the position.", None),
        ("contact", "single line of text", True,
         "Only the editor sees this; it is never published.", None),
    ]
    for n, (key, kind, required, note, options) in enumerate(rows, 1):
        out += [f"## {n}. {LABELS[key]}", "", f"- Type: {kind}", f"- Required: {'yes' if required else 'no'}"]
        if note:
            out.append(f"- Help text: {note}")
        if options:
            out.append("- Choices:")
            out += [f"    - {o}" for o in options]
        out.append("")
    out += ["Put the contact field last, so nothing after it is read into the position.", ""]
    return "\n".join(out)


def issue_template() -> str:
    return "\n".join([
        "# Generated by: python -m stemed_jobs.submitted --write-spec",
        "name: Add a submitted position (editors)",
        "description: Paste the email from the Seekers' Hub job form to add the position to STEMEd+ Jobs.",
        'title: "Position: "',
        "labels: [\"position: add\"]",
        "body:",
        "  - type: markdown",
        "    attributes:",
        "      value: >-",
        "        For editors. Paste the whole notification email from the Seekers' Hub job form below, add the",
        "        position title to the issue title, and submit. Then add the **approved** label. The email is",
        "        read by the form's field names (docs/seekers-hub-form.md); the poster's name and email are",
        "        never kept.",
        "  - type: textarea",
        "    id: paste",
        "    attributes:",
        f"      label: {PASTE_LABEL}",
        "      render: text",
        "    validations:",
        "      required: true",
        "",
    ])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write-spec", action="store_true")
    ap.add_argument("--issue", action="store_true", help="read ISSUE_BODY and add the position")
    ap.add_argument("--result", type=Path, help="write the reply for the issue here")
    args = ap.parse_args(argv)
    if args.write_spec:
        SPEC.parent.mkdir(parents=True, exist_ok=True)
        SPEC.write_text(spec(), encoding="utf-8")
        TEMPLATE.write_text(issue_template(), encoding="utf-8")
        print(f"Wrote {SPEC} and {TEMPLATE}")
        return 0
    if args.issue:
        changed, pid, reply = handle_issue(os.environ.get("ISSUE_BODY", ""), dt.date.today())
        if args.result:
            args.result.write_text(reply + "\n", encoding="utf-8")
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(f"changed={'true' if changed else 'false'}\n")
                fh.write(f"position={pid if re.match(r'^[a-z0-9-]+$', pid or '') else 'unknown'}\n")
        print(reply)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
