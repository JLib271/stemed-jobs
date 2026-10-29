"""Limit the output to the current academic hiring year.

Academic hiring years run from May 1 to the next April 30, so in October 2026
only advertisements posted on or after 2026-05-01 are kept, and on 2027-05-01
the cutoff moves to 2027-05-01.
"""

from datetime import date, datetime
from typing import List, Optional

from stemed_jobs.models import Job

START_MONTH = 5
START_DAY = 1


def academic_year_start(today: date) -> date:
    """The most recent May 1 on or before ``today``."""
    start = date(today.year, START_MONTH, START_DAY)
    return start if today >= start else date(today.year - 1, START_MONTH, START_DAY)


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _posted_day(job: Job) -> Optional[date]:
    try:
        return parse_day((job.published or "")[:10])
    except ValueError:
        return None


def filter_since(jobs: List[Job], since: date) -> List[Job]:
    """Drop jobs posted before ``since``.

    A job with no usable posting date cannot be placed in a year, so it is kept
    rather than silently lost.
    """
    return [job for job in jobs if _posted_day(job) is None or _posted_day(job) >= since]
