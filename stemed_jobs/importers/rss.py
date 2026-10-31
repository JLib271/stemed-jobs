from html.parser import HTMLParser
import gzip
import re
import time
from typing import List, Tuple
from urllib.request import Request, urlopen

import feedparser

from stemed_jobs.classification import classify_job
from stemed_jobs.dedup import dedupe_jobs
from stemed_jobs.deadlines import extract_deadline, extract_review_start, parse_day
from stemed_jobs.disciplines import DISCIPLINES, classify_disciplines
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


# --- Curated feeds (editor-reviewed posts) -----------------------------------
#
# A post's categories choose its audience and disciplines, and its body is a few
# labeled lines followed by the description:
#
#   Institution: ...            Application deadline: ...
#   Location: ...               Review of applications begins: ...
#   Link to the official posting: ...
#
# Anything under a "do not publish" heading is never part of a post, and the
# poster's name (dc:creator) is never used.

_AUDIENCE_TAGS = {
    "graduate student": "graduates",
    "graduate students": "graduates",
    "graduate": "graduates",
    "graduates": "graduates",
    "grad student": "graduates",
    "grad students": "graduates",
    "postdoc": "postdocs",
    "postdocs": "postdocs",
    "postdoctoral": "postdocs",
    "postdoctoral researcher": "postdocs",
    "postdoctoral researchers": "postdocs",
    "faculty": "faculty",
    "professional staff": "staff",
    "staff": "staff",
}
_DISCIPLINE_TAGS = {name.lower(): name for name in DISCIPLINES}
_LABELS = {
    "title",
    "institution",
    "location",
    "application deadline",
    "review of applications begins",
    "link to the official posting",
}
_LABELED_LINE = re.compile(r"^([A-Za-z][A-Za-z ]{1,40}?)\s*:\s*(.*)$")
_REVIEWER_ONLY = re.compile(r"for the reviewer|do not publish", re.IGNORECASE)
_MERGE_TAG = re.compile(r"\{field:[^}]*\}")  # a form field the editor never filled in
_BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}


class _LineExtractor(HTMLParser):
    """Plain text with a line break at every paragraph, list item or <br>."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _body_lines(html: str) -> List[str]:
    parser = _LineExtractor()
    parser.feed(html or "")
    text = _MERGE_TAG.sub("", "".join(parser.parts)).replace("\xa0", " ")
    return [" ".join(line.split()) for line in text.split("\n") if line.strip()]


def _split_labeled(lines: List[str]) -> Tuple[dict, List[str]]:
    """The labeled lines (by lowercase label) and the remaining description lines."""
    fields, description = {}, []
    for line in lines:
        match = _LABELED_LINE.match(line)
        label = match.group(1).strip().lower() if match else ""
        if label in _LABELS:
            fields.setdefault(label, match.group(2).strip())
        else:
            description.append(line)
    return fields, description


def _tag_terms(entry) -> List[str]:
    return [" ".join((tag.get("term") or "").split()) for tag in entry.get("tags", []) or []]


def _curated_job(entry, feed: Feed, title: str, url: str, identifier: str, published: str) -> Job:
    body = "".join(part.get("value", "") for part in entry.get("content", []) or []) or entry.get("summary", "")
    lines = _body_lines(body)
    for index, line in enumerate(lines):
        if _REVIEWER_ONLY.search(line):  # never publish anything an editor pasted under this heading
            lines = lines[:index]
            break
    if entry.get("content"):
        fields, description = _split_labeled(lines)
    else:
        # A summary-only feed has run the lines together, so the labels cannot be told apart.
        fields, description = {}, lines
    summary = " ".join(description)

    posted = parse_day(published)
    deadline_text = fields.get("application deadline")
    deadline = extract_deadline(
        "Application deadline: " + deadline_text if deadline_text else title + ".\n" + "\n".join(lines), posted
    )
    review_text = fields.get("review of applications begins")
    review_start = extract_review_start(
        "Review of applications begins: " + review_text if review_text else title + ".\n" + "\n".join(lines), posted
    )

    terms = [term.lower() for term in _tag_terms(entry)]
    audiences = list(dict.fromkeys(_AUDIENCE_TAGS[term] for term in terms if term in _AUDIENCE_TAGS))
    disciplines = list(dict.fromkeys(_DISCIPLINE_TAGS[term] for term in terms if term in _DISCIPLINE_TAGS))

    # Without a chosen audience or discipline, fall back to the usual keyword sorting.
    categories, functions = classify_job(title, summary)
    if audiences:
        categories = audiences
    if not disciplines:
        disciplines = classify_disciplines(title, summary, feed.disciplines)

    return Job(
        id=identifier,
        title=title,
        company=fields.get("institution", ""),
        location=fields.get("location", ""),
        url=url,
        published=published,
        summary=summary,
        source=feed.name,
        source_url=feed.url,
        categories=categories,
        functions=functions,
        disciplines=disciplines,
        deadline=deadline.isoformat() if deadline else "",
        review_date=review_start.isoformat() if review_start else "",
        curated=True,
    )


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
        if feed.curated:
            jobs.append(_curated_job(entry, feed, title, url, identifier, _published(entry)))
            continue
        summary = _plain_text(entry.get("summary", ""))
        categories, functions = classify_job(title, summary)
        # The full text (content:encoded) often has the deadline the short summary cuts off.
        full_text = " ".join(_plain_text(part.get("value", "")) for part in entry.get("content", []) or [])
        published = _published(entry)
        searchable = title + ". " + summary + " " + full_text
        deadline = extract_deadline(searchable, parse_day(published))
        review_start = extract_review_start(searchable, parse_day(published))
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
                published=published,
                summary=summary,
                source=feed.name,
                source_url=feed.url,
                categories=categories,
                functions=functions,
                disciplines=disciplines,
                deadline=deadline.isoformat() if deadline else "",
                review_date=review_start.isoformat() if review_start else "",
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
