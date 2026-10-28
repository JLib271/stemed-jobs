"""Keep a failed feed's last good jobs instead of dropping them from the site.

Every run rebuilds the output from scratch, so a feed that is down for a day
would otherwise remove its listings for that day. The previous deployment
(``jobs.json`` and ``feed_status.json`` on the published site, or in a local
directory) is the record of the last good copy, so nothing extra has to be
stored between runs.

A failed feed's previous jobs are reused for at most ``max_stale_days`` after
its last successful fetch, so postings that have really expired at the source
do not linger indefinitely.

The same record also lets boards that only list their newest postings build up
a longer history: a feed with ``retain_days`` keeps postings seen in earlier
runs for that many days after they were posted, even once the board has pushed
them out of its window.
"""

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import Request, urlopen

from stemed_jobs.classification import classify_job
from stemed_jobs.dedup import canonical_url
from stemed_jobs.disciplines import classify_disciplines
from stemed_jobs.models import Feed, FeedResult, Job


JOBS_FILE = "jobs.json"
STATUS_FILE = "feed_status.json"
DEFAULT_MAX_STALE_DAYS = 7
_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class Previous:
    jobs: List[Job]
    status: Dict[str, dict]
    note: Optional[str] = None


@dataclass(frozen=True)
class CarryOver:
    results: List[FeedResult]
    status: Dict[str, dict]
    notes: List[str]


def _read(location: str, name: str) -> str:
    if location.startswith(("http://", "https://")):
        request = Request(location.rstrip("/") + "/" + name, headers={"User-Agent": "STEMEd-Jobs/0.1"})
        with urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8")
    return (Path(location) / name).read_text(encoding="utf-8")


def _text(item: dict, key: str) -> str:
    value = item.get(key)
    return value if isinstance(value, str) else ""


def _job_from_dict(item: object) -> Optional[Job]:
    if not isinstance(item, dict):
        return None
    title, url, source_url = _text(item, "title"), _text(item, "url"), _text(item, "source_url")
    if not title or not url or not source_url:
        return None
    return Job(
        id=_text(item, "id") or url,
        title=title,
        company=_text(item, "company"),
        location=_text(item, "location"),
        url=url,
        published=_text(item, "published"),
        summary=_text(item, "summary"),
        source=_text(item, "source"),
        source_url=source_url,
        categories=[],
        functions=[],
        disciplines=[],
    )


def load_previous(location: str) -> Previous:
    """Read the previous output from a published site URL or a local directory.

    Never raises: if nothing usable is there, the result is empty and ``note``
    says why, so a missing first deployment just means no fallback exists yet.
    """
    try:
        data = json.loads(_read(location, JOBS_FILE))
        if not isinstance(data, list):
            raise ValueError("{} is not a list".format(JOBS_FILE))
        jobs = [job for job in (_job_from_dict(item) for item in data) if job is not None]
    except Exception as error:  # noqa: BLE001 - any problem just means no fallback
        return Previous([], {}, "no previous {} available ({}: {})".format(JOBS_FILE, type(error).__name__, error))

    try:
        raw = json.loads(_read(location, STATUS_FILE))
        status = raw.get("feeds", {}) if isinstance(raw, dict) else {}
        status = {url: entry for url, entry in status.items() if isinstance(entry, dict)}
    except Exception:  # noqa: BLE001 - a missing status file is normal on the first run
        status = {}
    return Previous(jobs, status)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(_TIME_FORMAT)


def _parse_time(value: object) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, _TIME_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _reclassify(job: Job, feed: Feed) -> Job:
    """Re-sort a stored job with the current rules, which may have changed."""
    categories, functions = classify_job(job.title, job.summary)
    disciplines = classify_disciplines(job.title, job.summary, feed.disciplines)
    return replace(job, categories=categories, functions=functions, disciplines=disciplines)


def _published_date(job: Job) -> Optional[datetime]:
    try:
        return datetime.strptime((job.published or "")[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _retained_jobs(feed: Feed, fresh: List[Job], stored: List[Job], now: datetime) -> List[Job]:
    """Earlier-seen jobs a working feed no longer lists, kept for ``feed.retain_days``.

    Boards that show only their newest postings drop older ones even though they
    may still be open. Postings are kept for ``retain_days`` after their posting
    date, so running daily builds up the ones the board has pushed out of its
    window. A job still listed by the feed is replaced by the fresh copy, and a
    job with no posting date cannot be aged, so it is not kept.
    """
    if feed.retain_days <= 0 or not stored:
        return []
    fresh_urls = {canonical_url(job.url) for job in fresh}
    kept = []
    for job in stored:
        posted = _published_date(job)
        if posted is None or (now.date() - posted.date()).days > feed.retain_days:
            continue
        if canonical_url(job.url) in fresh_urls:
            continue
        kept.append(_reclassify(job, feed))
    return kept


def _success_status(feed: Feed, jobs: List[Job], now: datetime) -> dict:
    """Status for a feed that loaded, including how far back its items reach.

    A feed that only lists its most recent postings cannot show older ones, so
    the item count and date range show whether a board's window is too short.
    """
    entry = {"name": feed.name, "last_success": _iso(now), "items": len(jobs)}
    dates = sorted(job.published[:10] for job in jobs if job.published)
    if dates:
        entry["oldest"], entry["newest"] = dates[0], dates[-1]
    return entry


def apply_carryover(
    results: List[FeedResult],
    previous: Previous,
    now: datetime,
    max_stale_days: int = DEFAULT_MAX_STALE_DAYS,
) -> CarryOver:
    """Fill in failed feeds from the previous output and build the new status.

    Returns the results (failed feeds now carrying their last good jobs when
    those are recent enough), the per-feed status to publish, and
    human-readable notes about what was kept or dropped.
    """
    previous_by_source: Dict[str, List[Job]] = {}
    for job in previous.jobs:
        previous_by_source.setdefault(job.source_url, []).append(job)

    updated: List[FeedResult] = []
    status: Dict[str, dict] = {}
    notes: List[str] = []

    for result in results:
        feed = result.feed
        if result.error is None:
            retained = _retained_jobs(feed, result.jobs, previous_by_source.get(feed.url, []), now)
            status[feed.url] = _success_status(feed, result.jobs, now)
            if retained:
                status[feed.url]["retained"] = len(retained)
                result = replace(result, jobs=result.jobs + retained)
            updated.append(result)
            continue

        # Unknown last success (first failure since this feature was added):
        # start the staleness clock now.
        last_success = _parse_time(previous.status.get(feed.url, {}).get("last_success")) or now
        status[feed.url] = {"name": feed.name, "last_success": _iso(last_success), "last_error": result.error}

        stored = previous_by_source.get(feed.url, [])
        if not stored:
            updated.append(result)
        elif now - last_success > timedelta(days=max_stale_days):
            notes.append(
                "Dropped {} stored job(s) from {}: it has been failing since {}, "
                "longer than {} days.".format(len(stored), feed.name, _iso(last_success), max_stale_days)
            )
            updated.append(result)
        else:
            notes.append(
                "Kept {} job(s) from the last good copy of {} (last fetched {}).".format(
                    len(stored), feed.name, _iso(last_success)
                )
            )
            updated.append(replace(result, jobs=[_reclassify(job, feed) for job in stored]))

    return CarryOver(updated, status, notes)


def write_status(status: Dict[str, dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump({"feeds": status}, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")
