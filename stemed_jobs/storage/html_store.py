from html import escape
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
from urllib.parse import urlparse

from stemed_jobs.disciplines import DISCIPLINES
from stemed_jobs.models import Job, JobBoard
from stemed_jobs.relevance import is_stem_education_relevant
from stemed_jobs.storage.rss_store import AUDIENCES, audience_label, feed_relative_path


COMMONS_URL = "https://stemedplus.hcommons.org/"
# The other STEMEd+ Commons sites, linked from the bottom of the index page.
RELATED_SITES = (
    ("STEMEd+ Conferences", "https://jlib271.github.io/stemed-conferences/",
     "meetings, proposal deadlines, and travel support for STEM+ education"),
    ("STEMEd+ Digest", "https://jlib271.github.io/STEMEd-Digest/", "new journal articles, preprints, and dissertations"),
    ("STEMEd+ Funding", "https://jlib271.github.io/stemed-funding/", "open calls and deadlines for STEM+ education"),
    ("STEM+ Education Research Graduate Programs", "https://jlib271.github.io/stem-ed-research-programs/",
     "where to study STEM+ education research"),
    ("STEMEd+ Professional Learning", "https://jlib271.github.io/stemed-professional-learning/",
     "national programs for K-12 teachers and informal educators"),
    ("STEMEd+ Faculty Development", "https://jlib271.github.io/stemed-faculty-development/",
     "teaching professional development for college faculty, instructors, graduate students, and postdocs"),
)


def _external_link(url: str, text: str) -> str:
    return '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>'.format(escape(url, quote=True), escape(text))


COLLECTION_URL = "https://works.hcommons.org/collections/humetainstrumentlibrary/"
STEMEDPLUS_COLLECTION_URL = "https://works.hcommons.org/collections/stemedplus/"
KC_JOIN_URL = "https://support.hcommons.org/profiles/login-and-registration/"


def _join_box(where: str) -> str:
    """The STEMEd+ Commons invitation shown at the top and bottom of the page."""
    return (
        '<div class="join join-{}" role="note"><p><strong>STEMEd+ Jobs is part of STEMEd+ Commons.</strong> '
        "Join free to deposit instruments in the {}, share your work in the {}, follow new work, and connect with "
        "STEM+ education researchers. You can sign in with GitHub, Google, ORCID, or your institution.</p>"
        "<p>{} · {}</p></div>"
    ).format(
        where,
        _external_link(COLLECTION_URL, "HuMeta Instrument Library collection"),
        _external_link(STEMEDPLUS_COLLECTION_URL, "STEMEd+ collection"),
        _external_link(COMMONS_URL, "Visit STEMEd+ Commons"),
        _external_link(KC_JOIN_URL, "How to join"),
    )


LOGO_FILE = Path(__file__).with_name("stemedplus-commons-logo.png")
THEME_FILES = ("stemedplus-commons-logo-white.png", "stemedplus-theme.css", "manrope.woff")
# The green STEMEd+ Commons band shared by all STEMEd+ sites (HuMeta standard/stemedplus_theme/).
STEMEDPLUS_BAR = '<div class="sp-bar"><div class="sp-in"><a class="sp-logo" href="https://stemedplus.org/"><img src="stemedplus-commons-logo-white.png" alt="STEMEd+ Commons home" width="263" height="91"></a><input type="checkbox" id="sp-menu-toggle" class="sp-toggle"><label for="sp-menu-toggle" class="sp-burger"><span class="sp-burger-icon" aria-hidden="true"></span>Menu</label><nav class="sp-nav" aria-label="STEMEd+ Commons"><ul class="sp-top"><li class="sp-has"><a href="https://stemedplus.org/stemed-features/">Features</a><svg class="sp-chev" width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M1.5 4L6 8L10.5 4" stroke="currentColor" stroke-width="1.5"/></svg><ul class="sp-sub"><li><a href="https://works.hcommons.org/collections/stemedplus/records?q=&amp;l=list&amp;p=1&amp;s=10&amp;sort=newest">STEMEd+ Library</a></li><li><a href="https://stemedplus.org/sites/">STEMEd+ Sites</a></li><li><a href="https://stemedplus.profile.hcommons.org/members/">STEMEd+ Members</a></li><li><a href="https://stemedplus.org/stemed-groups/">STEMEd+ Groups</a></li></ul></li><li class="sp-has"><a href="https://stemedplus.org/stemed-resources/">Resources</a><svg class="sp-chev" width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M1.5 4L6 8L10.5 4" stroke="currentColor" stroke-width="1.5"/></svg><ul class="sp-sub"><li><a href="https://theseekershub.stemedplus.org/">The Seekers’ Hub: A Job Board</a></li><li><a href="https://stemedplus.org/stemed-collaborators/">Find Collaborators</a></li><li><a href="https://jlib271.github.io/stemed-funding/">Find Funding</a></li><li><a href="https://jlib271.github.io/STEMEd-Digest/">STEMEd+ Digest</a></li><li><a href="https://jlib271.github.io/stem-ed-research-programs/">STEMEd+ Graduate Programs</a></li><li><a href="https://jlib271.github.io/stemed-conferences/">STEMEd+ Conferences</a></li><li><a href="https://jlib271.github.io/stemed-professional-learning/">STEMEd+ Professional Learning</a></li><li><a href="https://jlib271.github.io/stemed-faculty-development/">STEMEd+ Faculty Development</a></li></ul></li><li class="sp-has"><a href="https://stemedplus.org/about/">Learn More</a><svg class="sp-chev" width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="M1.5 4L6 8L10.5 4" stroke="currentColor" stroke-width="1.5"/></svg><ul class="sp-sub"><li><a href="https://stemedplus.org/about/">About</a></li><li><a href="https://stemedplus.org/learn-more/">Governance</a></li><li><a href="https://stemedplus.org/vision-research/">Vision &amp; Research</a></li><li><a href="https://support.hcommons.org/">Help &amp; Support</a></li></ul></li><li><a href="https://stemedplus.org/collaborate/">Partner with Us</a></li><li><a href="https://stemedplus.org/contact-us/">Contact Us</a></li><li><a href="https://stemedplus.org/join-stemed/">Join STEMEd+</a></li><li><a href="https://stemedplus.org/stemed-commons-frequently-asked-questions/">Get Started &amp; FAQs</a></li></ul></nav><a class="sp-login" href="https://stemedplus.org/wp-login.php">Log in</a></div></div>'


def render_index_html() -> str:
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>STEMEd Jobs</title>",
        "<style>body { margin: 0; font: 16px/1.55 system-ui, sans-serif; color: #1d2433; background: #f7f8fa; } "
        "main { max-width: 1100px; margin: 0 auto; padding: 20px 20px 40px; } "
        ".join { border: 1px solid; border-radius: 8px; padding: 10px 14px; margin: 14px 0; } .join p { margin: 4px 0; } "
        "ul { padding-left: 20px; } li { margin: 4px 0; }</style>",
        '<link rel="stylesheet" href="stemedplus-theme.css">',
        "</head>",
        "<body>",
        STEMEDPLUS_BAR,
        "<main>",
        _join_box("top"),
        "<h1>STEMEd Jobs</h1>",
        "<p>STEM education research and teaching opportunities, organized by audience and discipline.</p>",
        "<h2>Browse jobs</h2>",
        "<ul>",
    ]
    for audience in AUDIENCES:
        lines.append(
            '<li><a href="{}-jobs.html">{}</a></li>'.format(
                escape(audience), escape(audience_label(audience))
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
        ("staff", "learning-science"),
    ):
        relative_url = "feeds/{}/{}.xml".format(audience, discipline)
        lines.append(
            '<li><a href="{}">{}, {}</a></li>'.format(
                escape(relative_url, quote=True),
                escape(discipline.replace("-", " ").title()),
                escape(audience_label(audience)),
            )
        )
    lines.extend(["</ul>", _join_box("bottom"), "<h2>{}</h2>".format(_external_link(COMMONS_URL, "More from STEMEd+ Commons")), "<ul>"])
    for name, url, about in RELATED_SITES:
        lines.append("<li>{}: {}</li>".format(_external_link(url, name), escape(about)))
    lines.extend(["</ul>", "</main>", "</body>", "</html>", ""])
    return "\n".join(lines)


def write_index_html(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_index_html(), encoding="utf-8")
    shutil.copyfile(LOGO_FILE, path.parent / LOGO_FILE.name)
    for name in THEME_FILES:
        shutil.copyfile(LOGO_FILE.with_name(name), path.parent / name)


def _anchor_id(discipline: str) -> str:
    return "discipline-" + "-".join(discipline.lower().replace("&", " and ").split())


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
    if audience not in AUDIENCES:
        raise ValueError("Unsupported audience: {}".format(audience))

    grouped: Dict[str, List[Job]] = {discipline: [] for discipline in DISCIPLINES}
    for job in jobs:
        if audience not in job.categories:
            continue
        for discipline in DISCIPLINES:
            if (
                discipline in job.disciplines
                and is_stem_education_relevant(job, discipline)
            ):
                grouped[discipline].append(job)

    feed_base_url = feed_base_url.rstrip("/")
    lines = [
        '<nav aria-label="{} jobs by discipline">'.format(escape(audience_label(audience))),
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
                feed_url, escape(discipline), escape(audience_label(audience))
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
            lines.append("<p>No matching {} jobs in the current feed.</p>".format(escape(audience_label(audience).lower())))
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
