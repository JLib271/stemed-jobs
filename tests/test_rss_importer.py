import json
import gzip
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from stemed_jobs.disciplines import DISCIPLINES
from stemed_jobs.feed_sources.config import load_feeds
from stemed_jobs.feed_sources.boards import load_job_boards
from stemed_jobs.importers.rss import fetch_feed, ingest_feeds, parse_feed
from stemed_jobs.models import Feed
from stemed_jobs.models import Job
from stemed_jobs.relevance import is_stem_education_relevant, requires_education_doctorate
from stemed_jobs.storage.html_store import render_audience_html, render_index_html, write_index_html
from stemed_jobs.storage.json_store import write_jobs
from stemed_jobs.storage.rss_store import NO_POSTINGS_TITLE, render_rss, write_rss_feeds


RSS_ONE = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Feed One</title>
  <item><guid>job-1</guid><title><![CDATA[Research <b>Scientist</b>]]></title>
    <link>https://jobs.example/1</link><description>First &amp; best</description>
    <pubDate>Mon, 26 Oct 2026 12:00:00 GMT</pubDate><author>Example Lab</author>
  </item>
</channel></rss>"""

RSS_TWO = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Feed Two</title>
  <item><guid>job-2</guid><title>STEM Teacher</title>
    <link>https://jobs.example/2</link><description>Teach science</description>
  </item>
</channel></rss>"""


class _Response:
    def __init__(self, content, headers=None):
        self.content = content
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return self.content


def _job_titles(root):
    """Titles of the real jobs in a rendered feed, leaving out the empty-feed placeholder."""
    return [
        title
        for title in (item.findtext("title") for item in root.findall("./channel/item"))
        if title != NO_POSTINGS_TITLE
    ]


class RssImporterTests(unittest.TestCase):
    def test_relevance_filter_keeps_stem_education_and_related_roles(self):
        examples = [
            ("Physics Education Research Faculty", "Physics", ["faculty"], True),
            ("PER Postdoctoral Fellow", "Physics", ["postdocs"], True),
            ("Quantum Education Research Assistant", "Physics", ["graduates"], True),
            ("Physics Research with Education Students", "Physics", ["faculty"], False),
            ("Condensed Matter Theory Faculty", "Physics", ["faculty"], False),
            ("Postdoctoral Scholar in Theoretical Condensed Matter Physics", "Physics", ["postdocs"], False),
            ("PhD Position in Condensed Matter Theory and Quantum Computing", "Physics", ["graduates"], False),
            ("Chemistry Education Research Faculty", "Chemistry", ["faculty"], True),
            ("CER Postdoctoral Fellow", "Chemistry", ["postdocs"], True),
            ("Chemistry Teaching Lecturer", "Chemistry", ["faculty"], True),
            ("Chemistry Lecturer", "Chemistry", ["faculty"], False),
            ("GER Graduate Fellow", "Earth Science", ["graduates"], True),
            ("Earth Science Education Researcher", "Earth Science", ["postdocs"], True),
            ("Geoscience Education Faculty", "Earth Science", ["faculty"], True),
            ("Environmental Education Postdoc", "Earth Science", ["postdocs"], True),
            ("Environmental Science Education Fellow", "Earth Science", ["graduates"], True),
            ("BER Postdoctoral Fellow", "Bioscience", ["postdocs"], True),
            ("Bioscience Education Researcher", "Bioscience", ["faculty"], True),
            ("Biology Education Graduate Fellow", "Bioscience", ["graduates"], True),
            ("Genetics Education Researcher", "Bioscience", ["postdocs"], True),
            ("Genetics Research Fellow", "Bioscience", ["postdocs"], False),
            ("Physics Teaching Professor", "Physics", ["faculty"], True),
            ("Physics SoTL Faculty", "Physics", ["faculty"], True),
            ("Physics Instructor", "Physics", ["faculty"], True),
            ("Physics Teaching Postdoctoral Fellow", "Physics", ["postdocs"], False),
        ]
        for index, (title, discipline, categories, expected) in enumerate(examples):
            with self.subTest(title=title):
                job = Job(
                    id=str(index),
                    title=title,
                    company="",
                    location="",
                    url="https://jobs.example/{}".format(index),
                    published="",
                    summary="The description says education research and teaching, but must not affect title filtering.",
                    source="Test",
                    source_url="https://feeds.example/test",
                    categories=categories,
                    functions=[],
                    disciplines=[discipline],
                )
                self.assertEqual(is_stem_education_relevant(job, discipline), expected)

    def test_faculty_doctorate_in_education_is_an_inclusion_exception(self):
        cases = [
            (
                "Assistant Professor of Biology",
                "Minimum qualifications: Ph.D. in science education required.",
                ["faculty"],
                ["Bioscience"],
                True,
            ),
            (
                "Engineering Education Faculty",
                "Applicants must have an Ed.D. in learning sciences.",
                ["faculty"],
                ["Engineering"],
                True,
            ),
            (
                "Assistant Professor of Biology",
                "A Ph.D. in molecular biology is required.",
                ["faculty"],
                ["Bioscience"],
                False,
            ),
            (
                "Assistant Professor of Biology",
                "A Ph.D. in education is preferred, not required.",
                ["faculty"],
                ["Bioscience"],
                False,
            ),
            (
                "Full Professorship (W3) for Pure Mathematics",
                "Participation in academic self-governance and contributions to teaching are required. "
                "Prerequisites include a university degree, an outstanding doctorate, successful teaching "
                "experience, and a habilitation under the Higher Education Law.",
                ["faculty"],
                ["Mathematics"],
                False,
            ),
            (
                "Postdoctoral Fellow in Biology Education",
                "A Ph.D. in science education is required.",
                ["postdocs"],
                ["Bioscience"],
                False,
            ),
        ]
        for index, (title, summary, categories, disciplines, expected) in enumerate(cases):
            with self.subTest(title=title, summary=summary):
                job = Job(
                    id=str(index),
                    title=title,
                    company="",
                    location="",
                    url="https://jobs.example/degree-{}".format(index),
                    published="",
                    summary=summary,
                    source="Test",
                    source_url="https://feeds.example/test",
                    categories=categories,
                    functions=[],
                    disciplines=disciplines,
                )
                self.assertEqual(requires_education_doctorate(job), expected)

    def test_generates_pages_index_with_audience_and_feed_links(self):
        html = render_index_html()

        self.assertIn('<a href="faculty-jobs.html">Faculty</a>', html)
        self.assertIn('<a href="postdocs-jobs.html">Postdocs</a>', html)
        self.assertIn('<a href="graduates-jobs.html">Graduates</a>', html)
        self.assertIn('<a href="feeds/faculty/physics.xml">Physics, Faculty</a>', html)
        self.assertTrue(html.startswith("<!doctype html>"))

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "output" / "index.html"
            write_index_html(path)
            self.assertEqual(path.read_text(encoding="utf-8"), html)

    def test_ingests_multiple_feeds_and_writes_one_json_file(self):
        feeds = [Feed("Lab", "https://feeds.example/lab"), Feed("Schools", "https://feeds.example/schools")]

        def fake_urlopen(request, timeout):
            content = RSS_ONE if request.full_url.endswith("lab") else RSS_TWO
            return _Response(content)

        with patch("stemed_jobs.importers.rss.urlopen", side_effect=fake_urlopen):
            jobs, errors = ingest_feeds(feeds)

        self.assertEqual(errors, [])
        self.assertEqual([job.title for job in jobs], ["Research Scientist", "STEM Teacher"])
        self.assertEqual(jobs[0].company, "Example Lab")
        self.assertEqual(jobs[0].summary, "First & best")
        self.assertTrue(jobs[0].published.startswith("2026-10-26T"))
        self.assertEqual(jobs[0].categories, [])

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "output" / "jobs.json"
            write_jobs(jobs, output_path)
            saved_jobs = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(len(saved_jobs), 2)
        self.assertEqual(saved_jobs[1]["source"], "Schools")
        self.assertEqual(saved_jobs[1]["categories"], [])
        self.assertEqual(saved_jobs[1]["disciplines"], ["Science Education"])

    def test_classifies_categories_and_research_teaching_functions(self):
        xml = b"""<rss version="2.0"><channel>
          <item><title>Graduate Research Assistantship in Science Education</title>
            <link>https://jobs.example/graduate</link>
            <description>Support teaching and research.</description></item>
          <item><title>Postdoctoral Fellow in STEM Learning</title>
            <link>https://jobs.example/postdoc</link>
            <description>Conduct research on learning.</description></item>
          <item><title>Assistant Professor of STEM Education</title>
            <link>https://jobs.example/faculty</link>
            <description>Research and teaching responsibilities.</description></item>
          <item><title>Undergraduate Research Opportunity</title>
            <link>https://jobs.example/undergrad</link>
            <description>Join a laboratory research project.</description></item>
          <item><title>Physics Faculty Position</title>
            <link>https://jobs.example/faculty-students</link>
            <description>Teach undergraduate students and conduct research.</description></item>
          <item><title>Three DBER Graduate Assistantships</title>
            <link>https://jobs.example/graduate-assistantship</link></item>
          <item><title>TT in Physics Education Research</title>
            <link>https://jobs.example/tenure-track</link></item>
          <item><title>PhD Position in Science Education</title>
            <link>https://jobs.example/phd</link></item>
        </channel></rss>"""
        jobs = parse_feed(xml, Feed("Test", "https://feeds.example/test"))

        self.assertEqual(jobs[0].categories, ["graduates"])
        self.assertEqual(jobs[0].functions, ["research", "teaching"])
        self.assertEqual(jobs[1].categories, ["postdocs"])
        self.assertEqual(jobs[2].categories, ["faculty"])
        self.assertEqual(jobs[2].functions, ["research", "teaching"])
        self.assertEqual(jobs[3].categories, ["undergraduates"])
        self.assertEqual(jobs[4].categories, ["faculty"])
        self.assertEqual(jobs[5].categories, ["graduates"])
        self.assertEqual(jobs[6].categories, ["faculty"])
        self.assertEqual(jobs[7].categories, ["graduates"])

    def test_renders_audience_html_with_board_links_and_feed_links(self):
        xml = b"""<rss version="2.0"><channel>
          <item><title>Assistant Professor of Physics Education Research</title>
            <link>https://jobs.example/physics</link><description>Research and teaching.</description></item>
          <item><title>Postdoctoral Fellow in Biology Education Research</title>
            <link>https://jobs.example/postdoc</link></item>
          <item><title>Graduate Research Assistantship in Chemistry Education Research</title>
            <link>https://jobs.example/graduate</link></item>
          <item><title>PhD position in Condensed Matter Theory</title>
            <link>https://jobs.example/unrelated-graduate</link></item>
          <item><title>Three DBER Graduate Assistantships</title>
            <link>https://jobs.example/dber</link></item>
        </channel></rss>"""
        jobs = parse_feed(xml, Feed("Test & Feed", "https://feeds.example/test"))
        boards = load_job_boards(Path("config/job_boards.json"))

        html = render_audience_html(jobs, "faculty", boards, "https://feeds.example/output")

        self.assertIn('href="#discipline-physics"', html)
        self.assertIn('<h2 id="discipline-physics">Physics</h2>', html)
        self.assertIn("Assistant Professor of Physics Education Research", html)
        self.assertNotIn("Postdoctoral Fellow in Biology Education Research", html)
        self.assertNotIn("Graduate Research Assistantship in Chemistry Education Research", html)
        self.assertNotIn("PhD position in Condensed Matter Theory", html)
        self.assertNotIn("Three DBER Graduate Assistantships", html)
        self.assertIn('href="https://feeds.example/output/faculty/physics.xml"', html)
        self.assertIn('href="https://careers.aapt.org/"', html)
        self.assertIn('href="https://perjobs.blogspot.com/"', html)

    def test_dber_posting_is_cross_listed_using_description_disciplines(self):
        jobs = parse_feed(
            b"""<rss version="2.0"><channel>
              <item><title>Three DBER Graduate Assistantships, Auburn AL</title>
                <link>https://jobs.example/dber</link>
                <description>Graduate fellowships in physics, engineering, biological sciences,
                  geosciences, mathematics and chemistry education research.</description></item>
            </channel></rss>""",
            Feed("PER Jobs", "https://feeds.example/per"),
        )
        self.assertEqual(
            set(jobs[0].disciplines),
            {
                "Bioscience",
                "Chemistry",
                "Earth Science",
                "Engineering",
                "Mathematics",
                "Physics",
                "Science Education",
            },
        )
        boards = []

        for audience in ("graduates", "postdocs", "faculty"):
            html = render_audience_html(jobs, audience, boards)
            for discipline in (
                "agriculture",
                "bioscience",
                "chemistry",
                "earth-science",
                "engineering",
                "learning-science",
                "mathematics",
                "physics",
                "science-education",
            ):
                with self.subTest(audience=audience, discipline=discipline):
                    section = html.split('<h2 id="discipline-{}">'.format(discipline), 1)[1]
                    section = section.split("</section>", 1)[0]
                    if audience == "graduates" and discipline in {
                        "bioscience",
                        "chemistry",
                        "earth-science",
                        "engineering",
                        "mathematics",
                        "physics",
                        "science-education",
                    }:
                        self.assertIn("Three DBER Graduate Assistantships", section)
                    else:
                        self.assertNotIn("Three DBER Graduate Assistantships", section)

    def test_dber_posting_uses_description_disciplines_only_within_its_audience(self):
        jobs = parse_feed(
            b"""<rss version="2.0"><channel>
              <item><title>Three DBER Graduate Assistantships</title>
                <link>https://jobs.example/dber</link>
                <description>Fellowships in physics and engineering education research.</description></item>
            </channel></rss>""",
            Feed("PER Jobs", "https://feeds.example/per"),
        )

        for audience in ("graduates", "postdocs", "faculty"):
            for discipline in (
                "Agriculture",
                "Bioscience",
                "Chemistry",
                "Earth Science",
                "Engineering",
                "Learning Science",
                "Mathematics",
                "Physics",
                "Science Education",
            ):
                root = ElementTree.fromstring(render_rss(jobs, audience, discipline))
                has_dber = _job_titles(root) != []
                with self.subTest(audience=audience, discipline=discipline):
                    self.assertEqual(
                        has_dber,
                        audience == "graduates" and discipline in ("Physics", "Engineering", "Science Education"),
                    )

    def test_renders_rss_for_an_audience_and_discipline(self):
        xml = b"""<rss version="2.0"><channel>
          <item><title>Postdoctoral Fellow in Biology Education Research</title>
            <link>https://jobs.example/postdoc</link></item>
          <item><title>Assistant Professor of Physics Education Research</title>
            <link>https://jobs.example/faculty</link></item>
          <item><title>Three DBER Graduate Assistantships</title>
            <link>https://jobs.example/dber</link></item>
          <item><title>Postdoctoral Scholar in Theoretical Condensed Matter Physics</title>
            <link>https://jobs.example/condensed-matter</link></item>
        </channel></rss>"""
        jobs = parse_feed(xml, Feed("Test", "https://feeds.example/test"))
        graduate_root = ElementTree.fromstring(render_rss(jobs, "graduates", "Science Education"))
        postdoc_root = ElementTree.fromstring(render_rss(jobs, "postdocs", "Bioscience"))
        faculty_root = ElementTree.fromstring(render_rss(jobs, "faculty", "Bioscience"))

        self.assertEqual(postdoc_root.findtext("./channel/title"), "STEMEd Jobs: Bioscience jobs — Postdocs")
        self.assertEqual(postdoc_root.findtext("./channel/item/title"), "Postdoctoral Fellow in Biology Education Research")
        self.assertIsNone(postdoc_root.find("./channel/item[2]"))
        self.assertEqual(
            graduate_root.findtext("./channel/item/title"),
            "Three DBER Graduate Assistantships",
        )
        self.assertEqual(_job_titles(faculty_root), [])

    def test_writes_rss_files_for_three_audiences_and_all_disciplines(self):
        jobs = parse_feed(
            b"""<rss version="2.0"><channel>
              <item><title>Graduate Research Assistantship in Chemistry Education Research</title>
                <link>https://jobs.example/graduate</link></item>
              <item><title>Three DBER Graduate Assistantships</title>
                <link>https://jobs.example/dber</link></item>
            </channel></rss>""",
            Feed("Test", "https://feeds.example/test"),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            feed_directory = Path(temporary_directory) / "feeds"
            count = write_rss_feeds(jobs, feed_directory)
            graduate_feed = ElementTree.parse(feed_directory / "graduates" / "chemistry.xml")
            faculty_feed = ElementTree.parse(feed_directory / "faculty" / "chemistry.xml")
            postdoc_feed = ElementTree.parse(feed_directory / "postdocs" / "physics.xml")

        self.assertEqual(count, 40)
        self.assertEqual(len(graduate_feed.findall("./channel/item")), 1)
        self.assertEqual(_job_titles(faculty_feed), [])
        self.assertEqual(_job_titles(postdoc_feed), [])
        # An empty feed holds one placeholder item instead of nothing, so feed
        # readers and WordPress widgets do not report an error.
        self.assertEqual(
            [item.findtext("title") for item in faculty_feed.findall("./channel/item")], ["No current postings"]
        )

    def test_deduplicates_jobs_by_url(self):
        feeds = [Feed("First", "https://feeds.example/1"), Feed("Second", "https://feeds.example/2")]
        with patch("stemed_jobs.importers.rss.urlopen", return_value=_Response(RSS_ONE)):
            jobs, errors = ingest_feeds(feeds)

        self.assertEqual(errors, [])
        self.assertEqual(len(jobs), 1)

    def test_reads_gzip_compressed_rss(self):
        response = _Response(gzip.compress(RSS_ONE), {"Content-Encoding": "gzip"})
        with patch("stemed_jobs.importers.rss.urlopen", return_value=response):
            jobs = fetch_feed(Feed("Lab", "https://feeds.example/lab"))

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Research Scientist")

    def test_loads_feed_configuration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "feeds.json"
            config_path.write_text(
                '{"feeds":[{"name":"Lab","url":"https://feeds.example/lab"}]}',
                encoding="utf-8",
            )
            self.assertEqual(load_feeds(config_path), [Feed("Lab", "https://feeds.example/lab")])

    def test_technology_and_other_are_not_disciplines(self):
        self.assertEqual(
            DISCIPLINES,
            (
                "Agriculture",
                "Bioscience",
                "Chemistry",
                "Earth Science",
                "Engineering",
                "Health Education",
                "Learning Science",
                "Mathematics",
                "Physics",
                "Science Education",
            ),
        )
        for board in load_job_boards(Path("config/job_boards.json")):
            self.assertNotIn("Technology", board.disciplines)
            self.assertNotIn("Other", board.disciplines)

    def test_job_with_no_discipline_evidence_appears_in_no_discipline_list(self):
        jobs = parse_feed(
            b"""<rss version="2.0"><channel>
              <item><title>Teaching Assistant Professor in German Studies</title>
                <link>https://jobs.example/german</link>
                <description>Teach courses in German language and literature.</description></item>
            </channel></rss>""",
            Feed("Test", "https://feeds.example/test"),
        )
        self.assertEqual(jobs[0].disciplines, [])
        html = render_audience_html(jobs, "faculty", [])
        self.assertNotIn("German Studies", html)

    def test_feed_default_discipline_is_used_when_posting_names_none(self):
        content = b"""<rss version="2.0"><channel>
          <item><title>Chern Instructor</title><link>https://jobs.example/chern</link>
            <description>Applications are invited for a three-year position.</description></item>
        </channel></rss>"""
        with_default = parse_feed(content, Feed("MathJobs", "https://feeds.example/m", ("Mathematics",)))
        without_default = parse_feed(content, Feed("Other board", "https://feeds.example/o"))
        self.assertEqual(with_default[0].disciplines, ["Mathematics"])
        self.assertEqual(without_default[0].disciplines, [])

    def test_loads_feed_default_disciplines_and_rejects_unknown_ones(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "feeds.json"
            config_path.write_text(
                '{"feeds":[{"name":"MathJobs","url":"https://feeds.example/m","disciplines":["Mathematics"]}]}',
                encoding="utf-8",
            )
            self.assertEqual(
                load_feeds(config_path),
                [Feed("MathJobs", "https://feeds.example/m", ("Mathematics",))],
            )
            config_path.write_text(
                '{"feeds":[{"name":"X","url":"https://feeds.example/x","disciplines":["Technology"]}]}',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_feeds(config_path)

    def test_loads_retain_days_and_rejects_bad_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "feeds.json"
            config_path.write_text(
                '{"feeds":[{"name":"A","url":"https://feeds.example/a","retain_days":90},'
                '{"name":"B","url":"https://feeds.example/b"}]}',
                encoding="utf-8",
            )
            feeds = load_feeds(config_path)
            self.assertEqual([feed.retain_days for feed in feeds], [90, 0])
            for bad in ("-1", '"90"', "true", "1.5"):
                config_path.write_text(
                    '{"feeds":[{"name":"A","url":"https://feeds.example/a","retain_days":%s}]}' % bad,
                    encoding="utf-8",
                )
                with self.assertRaises(ValueError):
                    load_feeds(config_path)

    def test_loads_disciplined_job_board_registry(self):
        boards = load_job_boards(Path("config/job_boards.json"))
        self.assertEqual(len(boards), 23)
        self.assertIn("Physics", next(board for board in boards if board.name == "AAPT Career Center").disciplines)


class EmptyFeedTests(unittest.TestCase):
    def test_a_feed_with_no_jobs_holds_one_placeholder_with_a_link(self):
        root = ElementTree.fromstring(render_rss([], "faculty", "Physics"))
        items = root.findall("./channel/item")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].findtext("title"), "No current postings")
        self.assertIn("faculty", items[0].findtext("description"))
        self.assertIn("Physics", items[0].findtext("description"))
        self.assertTrue(items[0].findtext("link").startswith("https://"))
        self.assertEqual(items[0].findtext("guid"), "no-current-postings-faculty-physics")

    def test_the_placeholder_disappears_when_there_are_jobs(self):
        job = Job(
            id="1", title="Assistant Teaching Professor of Physics", company="", location="",
            url="https://jobs.example/1", published="", summary="", source="s", source_url="u",
            categories=["faculty"], functions=[], disciplines=["Physics"],
        )
        titles = [i.findtext("title") for i in ElementTree.fromstring(render_rss([job], "faculty", "Physics")).findall("./channel/item")]
        self.assertEqual(titles, ["Assistant Teaching Professor of Physics"])


if __name__ == "__main__":
    unittest.main()
