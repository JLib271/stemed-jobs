import json
import gzip
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from stemed_jobs.feed_sources.config import load_feeds
from stemed_jobs.feed_sources.boards import load_job_boards
from stemed_jobs.importers.rss import fetch_feed, ingest_feeds, parse_feed
from stemed_jobs.models import Feed
from stemed_jobs.models import Job
from stemed_jobs.relevance import is_stem_education_relevant
from stemed_jobs.storage.html_store import render_audience_html, render_index_html, write_index_html
from stemed_jobs.storage.json_store import write_jobs
from stemed_jobs.storage.rss_store import render_rss, write_rss_feeds


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


class RssImporterTests(unittest.TestCase):
    def test_relevance_filter_keeps_stem_education_and_related_roles(self):
        examples = [
            ("Assistant Professor of Physics Education Research", "Study physics learning.", ["Physics"], True),
            ("Human Dimensions of Climate Science Fellow", "Research climate impacts.", ["Earth Science"], True),
            ("Postdoctoral Fellow in Cognitive Science of Biology Learning", "Study STEM learners.", ["Bioscience"], True),
            ("Physics Teaching Assistant Professor", "Teach introductory physics.", ["Physics"], True),
            ("Assistant Professor of Physics SoTL", "Study student learning.", ["Physics"], True),
            ("Assistant Professor of Physics", "Education research in introductory physics.", ["Physics"], False),
            ("Cognitive Science Researcher", "Study memory and perception.", ["Learning Science"], False),
            ("Assistant Professor of Machine Learning", "Study machine learning in physics.", ["Physics"], False),
            (
                "Assistant Professor of Machine Learning",
                "Committed to undergraduate education while researching machine learning in physics.",
                ["Physics"],
                False,
            ),
            (
                "Assistant Professor of Machine Learning and STEM Education",
                "Research machine learning for STEM education.",
                ["Physics"],
                True,
            ),
            ("Assistant Professor of Experimental Physics", "Research photonics and quantum materials.", ["Physics"], False),
            ("Graduate Research Assistant in Chemistry", "Synthesize novel catalysts.", ["Chemistry"], False),
        ]
        for index, (title, summary, disciplines, expected) in enumerate(examples):
            with self.subTest(title=title):
                job = Job(
                    id=str(index),
                    title=title,
                    company="",
                    location="",
                    url="https://jobs.example/{}".format(index),
                    published="",
                    summary=summary,
                    source="Test",
                    source_url="https://feeds.example/test",
                    categories=["faculty"],
                    functions=[],
                    disciplines=disciplines,
                )
                self.assertEqual(is_stem_education_relevant(job), expected)

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
        </channel></rss>"""
        jobs = parse_feed(xml, Feed("Test & Feed", "https://feeds.example/test"))
        boards = load_job_boards(Path("config/job_boards.json"))

        html = render_audience_html(jobs, "faculty", boards, "https://feeds.example/output")

        self.assertIn('href="#discipline-physics"', html)
        self.assertIn('<h2 id="discipline-physics">Physics</h2>', html)
        self.assertIn("Assistant Professor of Physics Education Research", html)
        self.assertNotIn("Postdoctoral Fellow in Biology Education Research", html)
        self.assertNotIn("Graduate Research Assistantship in Chemistry Education Research", html)
        self.assertIn('href="https://feeds.example/output/faculty/physics.xml"', html)
        self.assertIn('href="https://careers.aapt.org/"', html)
        self.assertIn('href="https://perjobs.blogspot.com/"', html)

    def test_renders_rss_for_an_audience_and_discipline(self):
        xml = b"""<rss version="2.0"><channel>
          <item><title>Postdoctoral Fellow in Biology Education Research</title>
            <link>https://jobs.example/postdoc</link></item>
          <item><title>Assistant Professor of Physics Education Research</title>
            <link>https://jobs.example/faculty</link></item>
        </channel></rss>"""
        jobs = parse_feed(xml, Feed("Test", "https://feeds.example/test"))
        rss = render_rss(jobs, "postdocs", "Bioscience")
        root = ElementTree.fromstring(rss)

        self.assertEqual(root.findtext("./channel/title"), "STEMEd Jobs: Bioscience jobs — Postdocs")
        self.assertEqual(root.findtext("./channel/item/title"), "Postdoctoral Fellow in Biology Education Research")
        self.assertIsNone(root.find("./channel/item[2]"))

    def test_writes_rss_files_for_three_audiences_and_all_disciplines(self):
        jobs = parse_feed(
            b"""<rss version="2.0"><channel>
              <item><title>Graduate Research Assistantship in Chemistry Education Research</title>
                <link>https://jobs.example/graduate</link></item>
            </channel></rss>""",
            Feed("Test", "https://feeds.example/test"),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            feed_directory = Path(temporary_directory) / "feeds"
            count = write_rss_feeds(jobs, feed_directory)
            graduate_feed = ElementTree.parse(feed_directory / "graduates" / "chemistry.xml")
            faculty_feed = ElementTree.parse(feed_directory / "faculty" / "chemistry.xml")

        self.assertEqual(count, 33)
        self.assertEqual(len(graduate_feed.findall("./channel/item")), 1)
        self.assertEqual(len(faculty_feed.findall("./channel/item")), 0)

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

    def test_loads_disciplined_job_board_registry(self):
        boards = load_job_boards(Path("config/job_boards.json"))
        self.assertEqual(len(boards), 18)
        self.assertIn("Physics", next(board for board in boards if board.name == "AAPT Career Center").disciplines)


if __name__ == "__main__":
    unittest.main()
