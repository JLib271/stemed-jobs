import argparse
import os
from pathlib import Path
import sys

from stemed_jobs.feed_sources.config import load_feeds
from stemed_jobs.feed_sources.boards import load_job_boards
from stemed_jobs.importers.rss import ingest_feeds
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
    args = parser.parse_args()

    try:
        feeds = load_feeds(args.feeds)
        boards = load_job_boards(args.boards)
        if not feeds:
            raise ValueError("No feeds configured in {}.".format(args.feeds))
        jobs, errors = ingest_feeds(feeds)
        if len(errors) == len(feeds):
            # Every feed failed (for example a network outage). Writing now
            # would replace the existing output with an empty site.
            for error in errors:
                _report_feed_error(error)
            print("Error: every feed failed; existing output was left untouched.", file=sys.stderr)
            return 1
        write_jobs(jobs, args.output)
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
    for error in errors:
        _report_feed_error(error)
    if errors:
        print("Skipped {} of {} feed(s) because they failed.".format(len(errors), len(feeds)))
        return 0 if args.allow_feed_errors else 1
    return 0
