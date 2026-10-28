"""Cross-source duplicate detection for normalized jobs.

The same posting is often syndicated to several boards under different URLs.
Two jobs are treated as duplicates when either:

* their canonical URLs match (tracking parameters, fragments, host case and
  trailing slashes are ignored), or
* they have the same normalized title *and* the same normalized, non-empty
  company. Jobs without a company never match on title alone, because generic
  titles such as "Postdoctoral Researcher" would otherwise merge unrelated ads.

The first job seen wins, so feed order in ``config/feeds.json`` acts as source
priority.
"""

import re
from typing import Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from stemed_jobs.models import Job


_TRACKING_PARAMS = re.compile(r"^(?:utm_.*|gclid|fbclid|mc_cid|mc_eid)$", re.IGNORECASE)
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def canonical_url(url: str) -> str:
    """Return a comparison form of ``url``; the job's stored URL is left unchanged."""
    parts = urlsplit(url.strip())
    query = urlencode(
        [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING_PARAMS.match(key)]
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def _normalize(text: str) -> str:
    return _NON_WORD.sub(" ", text.casefold()).strip()


def content_key(job: Job) -> Optional[Tuple[str, str]]:
    """Return (title, company) for matching across boards, or None if company is unknown."""
    title, company = _normalize(job.title), _normalize(job.company)
    if not title or not company:
        return None
    return title, company


def dedupe_jobs(jobs: Iterable[Job]) -> List[Job]:
    seen_urls = set()
    seen_content = set()
    unique = []
    for job in jobs:
        url_key = canonical_url(job.url)
        key = content_key(job)
        if url_key in seen_urls or (key is not None and key in seen_content):
            continue
        seen_urls.add(url_key)
        if key is not None:
            seen_content.add(key)
        unique.append(job)
    return unique
