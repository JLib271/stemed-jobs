from html import escape
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
from urllib.parse import urlparse

from stemed_jobs.disciplines import DISCIPLINES
from stemed_jobs.models import Job, JobBoard
from stemed_jobs.storage.rss_store import feed_relative_path


def render_index_html() -> str:
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>STEMEd Jobs</title>",
        "</head>",
        "<body>",
        "<main>",
        "<h1>STEMEd Jobs</h1>",
        "<p>STEM education research and teaching opportunities, organized by audience and discipline.</p>",
        "<h2>Browse jobs</h2>",
        "<ul>",
    ]
    for audience in ("graduates", "postdocs", "faculty"):
        lines.append(
            '<li><a href="{}-jobs.html">{}</a></li>'.format(
                escape(audience), escape(audience.title())
            )
        )
    lines.extend(
        [
            "</ul>",
            "<h2>Subscribe to RSS feeds</h2>",
            "<p>Choose an audience and discipline for a filtered RSS feed:</p>",
            "<ul>",
        ]
    )
    for audience, discipline in (
        ("graduates", "science-education"),
        ("postdocs", "bioscience"),
        ("faculty", "physics"),
    ):
        relative_url = "feeds/{}/{}.xml".format(audience, discipline)
        lines.append(
            '<li><a href="{}">{}, {}</a></li>'.format(
                escape(relative_url, quote=True),
                escape(discipline.replace("-", " ").title()),
                escape(audience.title()),
            )
        )
    lines.extend(["</ul>", "</main>", "</body>", "</html>", ""])
    return "\n".join(lines)


def write_index_html(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_index_html(), encoding="utf-8")


def _anchor_id(discipline: str) -> str:
    return "discipline-" + "-".join(discipline.lower().split())


def _job_link(job: Job) -> str:
    url = escape(job.url, quote=True)
    if urlparse(job.url).scheme.lower() not in ("http", "https"):
        return escape(job.title)
    return '<a href="{}" rel="noopener noreferrer">{}</a>'.format(url, escape(job.title))


def render_audience_html(
    jobs: Iterable[Job],
    audience: str,
    boards: Sequence[JobBoard],
    feed_base_url: str = "/feeds",
) -> str:
    if audience not in ("graduates", "postdocs", "faculty"):
        raise ValueError("Unsupported audience: {}".format(audience))

    grouped: Dict[str, List[Job]] = {discipline: [] for discipline in DISCIPLINES}
    for job in jobs:
        if audience not in job.categories:
            continue
        disciplines = [name for name in job.disciplines if name in grouped] or ["Other"]
        for discipline in disciplines:
            grouped[discipline].append(job)

    feed_base_url = feed_base_url.rstrip("/")
    lines = [
        '<nav aria-label="{} jobs by discipline">'.format(escape(audience.title())),
        '<div class="wp-block-buttons is-content-justification-center">',
    ]
    for discipline in DISCIPLINES:
        anchor = _anchor_id(discipline)
        lines.append(
            '<div class="wp-block-button"><a class="wp-block-button__link wp-element-button" '
            'href="#{}">{}</a></div>'.format(anchor, escape(discipline))
        )
    lines.extend(["</div>", "</nav>"])

    for discipline in DISCIPLINES:
        lines.append("<section>")
        lines.append('<h2 id="{}">{}</h2>'.format(_anchor_id(discipline), escape(discipline)))
        feed_url = "{}/{}".format(
            escape(feed_base_url, quote=True),
            escape(feed_relative_path(audience, discipline), quote=True),
        )
        lines.append(
            '<p><a href="{}" type="application/rss+xml">RSS feed: {} {}</a></p>'.format(
                feed_url, escape(discipline), escape(audience)
            )
        )

        relevant_boards = [board for board in boards if discipline in board.disciplines]
        if relevant_boards:
            lines.append("<p>Related job boards:</p>")
            lines.append("<ul>")
            for board in relevant_boards:
                lines.append(
                    '<li><a href="{}" rel="noopener noreferrer">{}</a></li>'.format(
                        escape(board.url, quote=True), escape(board.name)
                    )
                )
            lines.append("</ul>")

        if not grouped[discipline]:
            lines.append("<p>No matching {} jobs in the current feed.</p>".format(escape(audience)))
        else:
            lines.append("<ul>")
            for job in grouped[discipline]:
                details = [escape(job.source)]
                if job.location:
                    details.append(escape(job.location))
                if job.published:
                    details.append(escape(job.published[:10]))
                lines.append(
                    "<li>{} <span>({})</span></li>".format(_job_link(job), " · ".join(details))
                )
            lines.append("</ul>")
        lines.append("</section>")

    return "\n".join(lines) + "\n"


def write_audience_html(
    jobs: Iterable[Job],
    audience: str,
    boards: Sequence[JobBoard],
    path: Path,
    feed_base_url: str = "/feeds",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_audience_html(jobs, audience, boards, feed_base_url),
        encoding="utf-8",
    )
