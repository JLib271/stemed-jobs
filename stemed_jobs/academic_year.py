"""Decide which advertisements are still current.

A posting that states an application deadline stays until
``deadline_grace_days`` after it (default one month), whenever it was posted.
A posting with no stated deadline falls back to its posting date: it is kept
if posted on or after the start of the current academic hiring year (the most
recent May 1). A posting with neither date is kept, since nothing says it is old.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional

from stemed_jobs.deadlines import parse_day as _day
from stemed_jobs.models import Job

START_MONTH = 5
START_DAY = 1
DEFAULT_GRACE_DAYS = 30


def academic_year_start(today: date) -> date:
    """The most recent May 1 on or before ``today``."""
    start = date(today.year, START_MONTH, START_DAY)
    return start if today >= start else date(today.year - 1, START_MONTH, START_DAY)


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def is_current(job: Job, today: date, since: date, grace_days: int = DEFAULT_GRACE_DAYS) -> bool:
    deadline: Optional[date] = _day(job.deadline)
    if deadline is not None:
        return deadline + timedelta(days=grace_days) >= today
    posted = _day(job.published or "")
    return posted is None or posted >= since


def filter_current(jobs: List[Job], today: date, since: date, grace_days: int = DEFAULT_GRACE_DAYS) -> List[Job]:
    return [job for job in jobs if is_current(job, today, since, grace_days)]
