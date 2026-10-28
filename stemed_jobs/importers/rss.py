from html.parser import HTMLParser
import gzip
import time
from typing import List, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

import feedparser

from stemed_jobs.classification import classify_job
from stemed_jobs.dedup import dedupe_jobs
from stemed_jobs.disciplines import classify_disciplines
from stemed_jobs.models import Feed, Job


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
                company=_plain_text(entry.get("author", "")),
                location=_plain_text(entry.get("location", "")),
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


def ingest_feeds(feeds: List[Feed]) -> Tuple[List[Job], List[str]]:
    jobs = []
    errors = []

    for feed in feeds:
        try:
            jobs.extend(fetch_feed(feed))
        except (OSError, TimeoutError, URLError, ValueError) as error:
            errors.append("{} ({}): {}".format(feed.name, feed.url, error))

    return dedupe_jobs(jobs), errors
