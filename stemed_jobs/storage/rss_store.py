from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from typing import Iterable, List
from xml.etree import ElementTree

from stemed_jobs.disciplines import DISCIPLINES
from stemed_jobs.models import Job
from stemed_jobs.relevance import is_dber_title, is_stem_education_relevant


AUDIENCES = ("graduates", "postdocs", "faculty")


def _slug(value: str) -> str:
    return "-".join(value.lower().split())


def feed_relative_path(audience: str, discipline: str) -> str:
    return "{}/{}.xml".format(_slug(audience), _slug(discipline))


def render_rss(jobs: Iterable[Job], audience: str, discipline: str) -> bytes:
    root = ElementTree.Element("rss", {"version": "2.0"})
    channel = ElementTree.SubElement(root, "channel")
    title = "{} jobs — {}".format(discipline, audience.title())
    ElementTree.SubElement(channel, "title").text = "STEMEd Jobs: " + title
    ElementTree.SubElement(channel, "description").text = (
        "{} opportunities in {} across STEM education research and teaching. "
        "Listings are screened for STEM education research, STEM teaching, human dimensions, or cognitive science.".format(
            audience.title(), discipline
        )
    )
    ElementTree.SubElement(channel, "link").text = "https://theseekershub.stemedplus.org/"
    ElementTree.SubElement(channel, "language").text = "en"

    for job in jobs:
        is_global_dber = is_dber_title(job.title)
        if audience not in job.categories:
            continue
        if not is_global_dber and (
            discipline not in job.disciplines
            or not is_stem_education_relevant(job, discipline)
        ):
            continue
        item = ElementTree.SubElement(channel, "item")
        ElementTree.SubElement(item, "title").text = job.title
        ElementTree.SubElement(item, "link").text = job.url
        ElementTree.SubElement(item, "guid", {"isPermaLink": "false"}).text = job.id
        if job.summary:
            ElementTree.SubElement(item, "description").text = job.summary
        if job.published:
            try:
                date = datetime.fromisoformat(job.published.replace("Z", "+00:00"))
                ElementTree.SubElement(item, "pubDate").text = format_datetime(date)
            except ValueError:
                pass
        ElementTree.SubElement(item, "category").text = discipline
        for function in job.functions:
            ElementTree.SubElement(item, "category").text = function.title()
        ElementTree.SubElement(item, "source", {"url": job.source_url}).text = job.source

    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def write_rss_feeds(jobs: Iterable[Job], directory: Path) -> int:
    jobs = list(jobs)
    written = 0
    for audience in AUDIENCES:
        for discipline in DISCIPLINES:
            path = directory / feed_relative_path(audience, discipline)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(render_rss(jobs, audience, discipline))
            written += 1
    return written
