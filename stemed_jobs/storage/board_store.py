"""board.json: the data the STEMEd+ Jobs page (index.html) shows.

Only jobs that pass the same STEM+ education screening as the RSS feeds are listed, each with the
disciplines it passed in. Summaries are shortened so the page loads quickly; the full posting is
one click away.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from stemed_jobs.disciplines import DISCIPLINES, NAMED_ONLY
from stemed_jobs.models import Job, JobBoard
from stemed_jobs.relevance import is_stem_education_relevant
from stemed_jobs.storage.rss_store import AUDIENCES, audience_label, feed_relative_path

SUMMARY_CHARS = 260
REPO_URL = "https://github.com/JLib271/stemed-jobs"
CONTACT_URL = "https://stemedplus.org/contact-us/"


def _short(text: str, limit: int = SUMMARY_CHARS) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:.-–—")
    return cut + "…"


_EMAIL = re.compile(r"\S+@\S+")


def _organization(company: str) -> str:
    """The employer's name, or "" when the feed gave a contact address instead (Blogger feeds such as PER
    Jobs list "noreply@blogger.com (Author)" as the post's author)."""
    return "" if _EMAIL.search(company or "") else (company or "")


def board_entry(job: Job) -> Optional[dict]:
    """The job as the page shows it, or None when it is not listed."""
    audiences = [a for a in AUDIENCES if a in job.categories]
    disciplines = [d for d in DISCIPLINES if d in job.disciplines and is_stem_education_relevant(job, d)]
    if not audiences or not disciplines:
        return None
    return {
        "id": job.id,
        "t": job.title,
        "org": _organization(job.company),
        "loc": job.location,
        "url": job.url,
        "pub": (job.published or "")[:10],
        "dl": job.deadline,
        "rv": job.review_date,
        "aud": audiences,
        "disc": disciplines,
        "src": job.source,
        "sum": _short(job.summary),
        "cur": job.curated,
    }


def build_board(jobs: Iterable[Job], boards: Sequence[JobBoard], now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    items: List[dict] = [entry for entry in (board_entry(job) for job in jobs) if entry]
    items.sort(key=lambda i: (i["pub"], i["t"]), reverse=True)
    return {
        "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "today": now.date().isoformat(),
        "repo_url": REPO_URL,
        "contact_url": CONTACT_URL,
        "audiences": [{"key": a, "label": audience_label(a)} for a in AUDIENCES],
        "disciplines": list(DISCIPLINES),
        "named_only": list(NAMED_ONLY),
        "feeds": {a: {d: feed_relative_path(a, d) for d in DISCIPLINES} for a in AUDIENCES},
        "boards": [{"name": b.name, "url": b.url, "disciplines": list(b.disciplines)} for b in boards],
        "items": items,
    }


def write_board(jobs: Iterable[Job], boards: Sequence[JobBoard], path: Path, now: Optional[datetime] = None) -> int:
    data = build_board(jobs, boards, now)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return len(data["items"])
