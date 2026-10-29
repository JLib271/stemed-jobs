import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

from stemed_jobs.academic_year import DEFAULT_GRACE_DAYS, academic_year_start, filter_current, parse_day
from stemed_jobs.carryover import (
    DEFAULT_MAX_STALE_DAYS,
    STATUS_FILE,
    Previous,
    apply_carryover,
    load_previous,
    write_status,
)
from stemed_jobs.dedup import dedupe_jobs
from stemed_jobs.feed_sources.config import load_feeds
from stemed_jobs.feed_sources.boards import load_job_boards
from stemed_jobs.importers.rss import fetch_all
from stemed_jobs.storage.html_store import write_audience_html, write_index_html
from stemed_jobs.storage.json_store import write_jobs
from stemed_jobs.storage.rss_store import AUDIENCES, write_rss_feeds


def _report_feed_error(message: str) -> None:
    print("Feed error: {}".format(message), file=sys.stderr)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        # A GitHub Actions warning annotation: shown on the run page even when
        # the run succeeds, so a skipped feed is not silent.
        escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print("::warning title=Feed skipped::{}".format(escaped))


def main() -> int:
    parser = argparse.ArgumentParser(description="Import jobs from configured RSS feeds.")
    parser.add_argument("--feeds", type=Path, default=Path("config/feeds.json"))
    parser.add_argument("--boards", type=Path, default=Path("config/job_boards.json"))
    parser.add_argument("--output", type=Path, default=Path("output/jobs.json"))
    parser.add_argument("--feed-output", type=Path, default=Path("output/feeds"))
    parser.add_argument("--html-output", type=Path, default=Path("output"))
    parser.add_argument(
        "--feed-base-url",
        default="/feeds",
        help="Public URL prefix where --feed-output will be hosted (default: /feeds).",
    )
    parser.add_argument(
        "--allow-feed-errors",
        action="store_true",
        help="Exit successfully when some feeds fail, as long as at least one feed "
        "was imported. Failures are still reported. Without this flag any failed "
        "feed makes the command exit nonzero.",
    )
    parser.add_argument(
        "--previous",
        metavar="URL_OR_DIR",
        help="Where the previous output lives: the published site's base URL or a local "
        "directory containing jobs.json and feed_status.json. When a feed fails, its "
        "jobs from there are kept instead of disappearing, and feeds with retain_days "
        "keep the older postings they no longer list.",
    )
    parser.add_argument(
        "--max-stale-days",
        type=int,
        default=DEFAULT_MAX_STALE_DAYS,
        help="Keep a failing feed's previous jobs for at most this many days after its "
        "last successful fetch (default: {}).".format(DEFAULT_MAX_STALE_DAYS),
    )
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help="For advertisements that state no application deadline, only keep those posted "
        "on or after this date. Default: the start of the current academic hiring year "
        "(the most recent May 1). Jobs with no posting date are kept.",
    )
    parser.add_argument(
        "--deadline-grace-days",
        type=int,
        default=DEFAULT_GRACE_DAYS,
        help="Keep an advertisement with a stated application deadline until this many days "
        "after it (default: {}).".format(DEFAULT_GRACE_DAYS),
    )
    args = parser.parse_args()

    notes = []
    try:
        feeds = load_feeds(args.feeds)
        boards = load_job_boards(args.boards)
        if not feeds:
            raise ValueError("No feeds configured in {}.".format(args.feeds))
        results = fetch_all(feeds)
        errors = [result.error for result in results if result.error]
        if len(errors) == len(feeds):
            # Every feed failed (for example a network outage). Writing now
            # would replace the existing output with an empty site.
            for error in errors:
                _report_feed_error(error)
            print("Error: every feed failed; existing output was left untouched.", file=sys.stderr)
            return 1

        previous = Previous([], {})
        if args.previous:
            previous = load_previous(args.previous)
            if previous.note:
                notes.append(
                    previous.note + "; older postings from earlier runs cannot be kept and any failed feed has no fallback."
                )
        carried = apply_carryover(results, previous, datetime.now(timezone.utc), args.max_stale_days)
        notes.extend(carried.notes)

        now = datetime.now(timezone.utc)
        since = parse_day(args.since) if args.since else academic_year_start(now.date())
        all_jobs = dedupe_jobs([job for result in carried.results for job in result.jobs])
        jobs = filter_current(all_jobs, now.date(), since, args.deadline_grace_days)
        with_deadline = sum(1 for job in jobs if job.deadline)
        notes.append(
            "Left out {} advertisement(s): more than {} days past their application deadline, or "
            "(with no stated deadline) posted before {}. {} of the {} kept state a deadline.".format(
                len(all_jobs) - len(jobs), args.deadline_grace_days, since, with_deadline, len(jobs)
            )
        )
        write_jobs(jobs, args.output)
        write_status(carried.status, args.html_output / STATUS_FILE)
        feed_count = write_rss_feeds(jobs, args.feed_output)
        write_index_html(args.html_output / "index.html")
        for audience in AUDIENCES:
            output_path = args.html_output / "{}-jobs.html".format(audience)
            write_audience_html(jobs, audience, boards, output_path, args.feed_base_url)
    except (OSError, ValueError) as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 2

    print("Wrote {} jobs from {} feed(s) to {}.".format(len(jobs), len(feeds) - len(errors), args.output))
    print("Wrote {} audience/discipline RSS feeds to {}.".format(feed_count, args.feed_output))
    print("Wrote Pages index and audience HTML sections for {} to {}.".format(", ".join(AUDIENCES), args.html_output))
    for entry in carried.status.values():
        if "items" in entry:
            window = ", {} to {}".format(entry["oldest"], entry["newest"]) if "oldest" in entry else ""
            kept = ", plus {} kept from earlier runs".format(entry["retained"]) if entry.get("retained") else ""
            print("Feed {}: {} item(s){}{}".format(entry["name"], entry["items"], window, kept))
    for error in errors:
        _report_feed_error(error)
    for note in notes:
        print("Note: {}".format(note))
    if errors:
        print("Skipped {} of {} feed(s) because they failed.".format(len(errors), len(feeds)))
        return 0 if args.allow_feed_errors else 1
    return 0
