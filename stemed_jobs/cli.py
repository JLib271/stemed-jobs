import argparse
from pathlib import Path
import sys

from stemed_jobs.feed_sources.config import load_feeds
from stemed_jobs.feed_sources.boards import load_job_boards
from stemed_jobs.importers.rss import ingest_feeds
from stemed_jobs.storage.html_store import write_audience_html
from stemed_jobs.storage.json_store import write_jobs
from stemed_jobs.storage.rss_store import AUDIENCES, write_rss_feeds


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
    args = parser.parse_args()

    try:
        feeds = load_feeds(args.feeds)
        boards = load_job_boards(args.boards)
        if not feeds:
            raise ValueError("No feeds configured in {}.".format(args.feeds))
        jobs, errors = ingest_feeds(feeds)
        write_jobs(jobs, args.output)
        feed_count = write_rss_feeds(jobs, args.feed_output)
        for audience in AUDIENCES:
            output_path = args.html_output / "{}-jobs.html".format(audience)
            write_audience_html(jobs, audience, boards, output_path, args.feed_base_url)
    except (OSError, ValueError) as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 2

    print("Wrote {} jobs from {} feed(s) to {}.".format(len(jobs), len(feeds), args.output))
    print("Wrote {} audience/discipline RSS feeds to {}.".format(feed_count, args.feed_output))
    print("Wrote audience HTML sections for {} to {}.".format(", ".join(AUDIENCES), args.html_output))
    for error in errors:
        print("Feed error: {}".format(error), file=sys.stderr)
    return 1 if errors else 0
