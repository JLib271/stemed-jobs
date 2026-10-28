from html.parser import HTMLParser
import gzip
import time
from typing import List, Tuple
from urllib.request import Request, urlopen

import feedparser

from stemed_jobs.classification import classify_job
from stemed_jobs.dedup import dedupe_jobs
from stemed_jobs.disciplines import classify_disciplines
from stemed_jobs.models import Feed, FeedResult, Job


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())


def _published(entry) -> str:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", parsed)
    return ""


def parse_feed(content: bytes, feed: Feed) -> List[Job]:
    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise ValueError("Could not parse feed: {}".format(parsed.bozo_exception))

    jobs = []
    for entry in parsed.entries:
        title = _plain_text(entry.get("title", ""))
        url = entry.get("link", "").strip()
        if not title or not url:
            continue

        identifier = str(entry.get("id") or url).strip()
        summary = _plain_text(entry.get("summary", ""))
        categories, functions = classify_job(title, summary)
        disciplines = classify_disciplines(title, summary, feed.disciplines)
        jobs.append(
            Job(
                id=identifier,
                title=title,
                # WP Job Manager boards (e.g. jobRxiv) put the employer and place in
                # job_listing:* elements; dc:creator there is only the poster.
                company=_plain_text(entry.get("job_listing_company") or entry.get("author", "")),
                location=_plain_text(entry.get("job_listing_location") or entry.get("location", "")),
                url=url,
                published=_published(entry),
                summary=summary,
                source=feed.name,
                source_url=feed.url,
                categories=categories,
                functions=functions,
                disciplines=disciplines,
            )
        )
    return jobs


def fetch_feed(feed: Feed, timeout: int = 20) -> List[Job]:
    request = Request(feed.url, headers={"User-Agent": "STEMEd-Jobs/0.1"})
    with urlopen(request, timeout=timeout) as response:
        content = response.read()
        if response.headers.get("Content-Encoding", "").lower() == "gzip":
            content = gzip.decompress(content)
        return parse_feed(content, feed)


def fetch_all(feeds: List[Feed]) -> List[FeedResult]:
    """Fetch every feed, recording a failure instead of raising."""
    results = []
    for feed in feeds:
        try:
            results.append(FeedResult(feed, fetch_feed(feed)))
        except Exception as error:  # noqa: BLE001 - one broken feed must never stop the others
            message = "{} ({}): {}: {}".format(feed.name, feed.url, type(error).__name__, error)
            results.append(FeedResult(feed, [], message))
    return results


def ingest_feeds(feeds: List[Feed]) -> Tuple[List[Job], List[str]]:
    results = fetch_all(feeds)
    jobs = [job for result in results for job in result.jobs]
    return dedupe_jobs(jobs), [result.error for result in results if result.error]
