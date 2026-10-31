import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from xml.etree import ElementTree

from stemed_jobs.carryover import Previous, apply_carryover, load_previous
from stemed_jobs.feed_sources.config import load_feeds
from stemed_jobs.importers.rss import parse_feed
from stemed_jobs.models import Feed, FeedResult
from stemed_jobs.relevance import is_stem_education_relevant
from stemed_jobs.storage.rss_store import NO_POSTINGS_TITLE, render_rss


HUB = Feed("Seekers' Hub", "https://hub.example/category/positions/feed/", curated=True)
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)

# A real post from the Seekers' Hub feed (WordPress 7.0, one test post), unedited.
SAMPLE = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"
	xmlns:content="http://purl.org/rss/1.0/modules/content/"
	xmlns:dc="http://purl.org/dc/elements/1.1/"
	xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
	<title>Positions &#8211; The Seekers Hub</title>
	<item>
		<title>Test</title>
		<link>https://theseekershub.stemedplus.org/2026/10/31/test/</link>
		<dc:creator><![CDATA[Julie C Libarkin]]></dc:creator>
		<pubDate>Sat, 31 Oct 2026 12:50:05 +0000</pubDate>
				<category><![CDATA[Bioscience]]></category>
		<category><![CDATA[Engineering]]></category>
		<category><![CDATA[Faculty]]></category>
		<category><![CDATA[Positions]]></category>
		<category><![CDATA[Postdoc]]></category>
		<guid isPermaLink="false">https://theseekershub.stemedplus.org/?p=249</guid>
		<description><![CDATA[Title: assoc of things Institution: msu Location: here Application deadline: rolling Review of applications begins: {field:review_date} Link to the official posting:&#160;stemedplus.org This is a test]]></description>
		<content:encoded><![CDATA[
<p class="wp-block-paragraph">Title: assoc of things</p>

<p class="wp-block-paragraph">Institution: msu</p>

<p class="wp-block-paragraph">Location: here</p>

<p class="wp-block-paragraph">Application deadline: rolling</p>

<p class="wp-block-paragraph">Review of applications begins: {field:review_date}</p>

<p class="wp-block-paragraph">Link to the official posting:&nbsp;stemedplus.org</p>

<p class="wp-block-paragraph">This is a test</p>
]]></content:encoded>
	</item>
</channel>
</rss>
""".encode("utf-8")


def _post(title="Postdoctoral Researcher", categories=("Positions",), body="", creator="A. Poster"):
    tags = "".join("<category><![CDATA[{}]]></category>".format(name) for name in categories)
    return (
        '<?xml version="1.0"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item><title>{}</title>'
        "<link>https://hub.example/post/</link><dc:creator><![CDATA[{}]]></dc:creator>"
        "<pubDate>Sat, 31 Oct 2026 12:50:05 +0000</pubDate>{}<guid>https://hub.example/?p=1</guid>"
        "<description><![CDATA[ignored when content is present]]></description>"
        "<content:encoded><![CDATA[{}]]></content:encoded></item></channel></rss>".format(title, creator, tags, body)
    ).encode("utf-8")


def _paragraphs(*lines):
    return "".join('<p class="wp-block-paragraph">{}</p>\n\n'.format(line) for line in lines)


class CuratedParsingTests(unittest.TestCase):
    def setUp(self):
        self.job = parse_feed(SAMPLE, HUB)[0]

    def test_categories_set_the_audiences_and_disciplines(self):
        self.assertEqual(self.job.categories, ["faculty", "postdocs"])
        self.assertEqual(self.job.disciplines, ["Bioscience", "Engineering"])
        self.assertTrue(self.job.curated)

    def test_labeled_lines_fill_in_institution_and_location(self):
        self.assertEqual((self.job.company, self.job.location), ("msu", "here"))

    def test_the_posters_name_is_never_used(self):
        self.assertNotIn("Libarkin", json.dumps(self.job.to_dict()))

    def test_the_summary_is_the_description_without_the_labeled_lines(self):
        self.assertEqual(self.job.summary, "This is a test")

    def test_rolling_and_an_unfilled_review_tag_give_no_dates(self):
        self.assertEqual((self.job.deadline, self.job.review_date), ("", ""))

    def test_the_link_is_the_post_and_the_post_date_is_kept(self):
        self.assertEqual(self.job.url, "https://theseekershub.stemedplus.org/2026/10/31/test/")
        self.assertEqual(self.job.published, "2026-10-31T12:50:05Z")


class CuratedFieldTests(unittest.TestCase):
    def _parse(self, **kwargs):
        return parse_feed(_post(**kwargs), HUB)[0]

    def test_a_written_out_deadline_and_review_date_are_read(self):
        body = _paragraphs(
            "Institution: State University",
            "Application deadline: December 1, 2026",
            "Review of applications begins: November 15, 2026",
            "Teach and research.",
        )
        job = self._parse(body=body)
        self.assertEqual((job.deadline, job.review_date), ("2026-12-01", "2026-11-15"))

    def test_numeric_and_abbreviated_deadlines_are_read(self):
        self.assertEqual(self._parse(body=_paragraphs("Application deadline: 12/1/2026")).deadline, "2026-12-01")
        self.assertEqual(self._parse(body=_paragraphs("Application deadline: Dec. 1, 2026")).deadline, "2026-12-01")

    def test_a_review_line_just_before_the_deadline_does_not_hide_it(self):
        body = _paragraphs("Review of applications begins: November 1, 2026", "Application deadline: December 1, 2026")
        job = self._parse(body=body)
        self.assertEqual((job.deadline, job.review_date), ("2026-12-01", "2026-11-01"))

    def test_all_audience_names_are_recognised(self):
        cases = {
            "Graduate Student": "graduates",
            "Postdoc": "postdocs",
            "Faculty": "faculty",
            "Professional Staff": "staff",
        }
        for name, audience in cases.items():
            self.assertEqual(self._parse(categories=("Positions", name)).categories, [audience], name)

    def test_category_names_ignore_case_and_extra_spaces(self):
        job = self._parse(categories=("Positions", "  graduate   student ", "earth science"))
        self.assertEqual((job.categories, job.disciplines), (["graduates"], ["Earth Science"]))

    def test_without_chosen_categories_the_usual_keyword_sorting_applies(self):
        job = self._parse(
            title="Assistant Teaching Faculty in Mathematics", body=_paragraphs("Teach calculus.")
        )
        self.assertEqual(job.categories, ["faculty"])
        self.assertEqual(job.disciplines, ["Mathematics"])

    def test_a_chosen_audience_replaces_the_keyword_guess(self):
        job = self._parse(title="Assistant Teaching Faculty in Mathematics", categories=("Positions", "Postdoc"))
        self.assertEqual(job.categories, ["postdocs"])

    def test_nothing_under_the_reviewer_heading_is_published(self):
        body = _paragraphs(
            "Institution: State University",
            "A good job.",
            "--- For the reviewer (do not publish) ---",
            "Contact: someone@example.edu",
        )
        job = self._parse(body=body)
        self.assertEqual(job.summary, "A good job.")
        self.assertNotIn("someone@example.edu", json.dumps(job.to_dict()))

    def test_unfilled_form_tags_never_appear(self):
        job = self._parse(body=_paragraphs("Institution: {field:institution}", "Fine job {field:oops}."))
        self.assertEqual((job.company, job.summary), ("", "Fine job ."))

    def test_line_breaks_inside_a_paragraph_also_separate_lines(self):
        job = self._parse(body="<p>Institution: State U<br>Location: Lansing, MI</p>")
        self.assertEqual((job.company, job.location), ("State U", "Lansing, MI"))

    def test_a_feed_that_is_not_curated_is_unchanged(self):
        job = parse_feed(_post(body=_paragraphs("Institution: Elsewhere")), Feed("Plain", "https://plain.example"))[0]
        self.assertFalse(job.curated)
        self.assertEqual(job.company, "A. Poster")  # the ordinary importer still uses the author

    def test_a_post_with_only_a_flattened_description_still_imports(self):
        xml = (
            b'<?xml version="1.0"?><rss version="2.0"><channel><item><title>Postdoc</title>'
            b"<link>https://hub.example/p/</link><category>Faculty</category>"
            b"<description>Institution: X Location: Y</description></item></channel></rss>"
        )
        job = parse_feed(xml, HUB)[0]
        self.assertEqual(job.categories, ["faculty"])
        self.assertEqual(job.summary, "Institution: X Location: Y")


class CuratedFeedOutputTests(unittest.TestCase):
    def setUp(self):
        self.jobs = parse_feed(SAMPLE, HUB)

    def _titles(self, audience, discipline):
        root = ElementTree.fromstring(render_rss(self.jobs, audience, discipline))
        return [item.findtext("title") for item in root.iter("item")]

    def test_the_post_appears_in_each_chosen_audience_and_discipline_feed(self):
        for audience in ("faculty", "postdocs"):
            for discipline in ("Bioscience", "Engineering"):
                self.assertEqual(self._titles(audience, discipline), ["Test"], (audience, discipline))

    def test_it_is_not_in_other_feeds(self):
        self.assertEqual(self._titles("graduates", "Bioscience"), [NO_POSTINGS_TITLE])
        self.assertEqual(self._titles("faculty", "Physics"), [NO_POSTINGS_TITLE])

    def test_an_approved_post_skips_the_keyword_screening(self):
        # "Test" has no education wording at all; only the editor's approval lets it through.
        self.assertTrue(is_stem_education_relevant(self.jobs[0], "Bioscience"))
        plain = parse_feed(SAMPLE, Feed("Plain", "https://plain.example"))[0]
        self.assertFalse(is_stem_education_relevant(plain, "Bioscience"))

    def test_a_curated_job_is_still_limited_to_its_chosen_disciplines(self):
        self.assertFalse(is_stem_education_relevant(self.jobs[0], "Physics"))


class CuratedCarryOverTests(unittest.TestCase):
    def test_a_failed_feed_keeps_the_editors_categories_not_keyword_guesses(self):
        job = parse_feed(SAMPLE, HUB)[0]
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "jobs.json").write_text(json.dumps([job.to_dict()]), encoding="utf-8")
            previous = load_previous(directory)
        carried = apply_carryover([FeedResult(HUB, [], "down")], previous, NOW)
        kept = carried.results[0].jobs[0]
        self.assertEqual((kept.categories, kept.disciplines), (["faculty", "postdocs"], ["Bioscience", "Engineering"]))
        self.assertTrue(kept.curated)


class CuratedConfigTests(unittest.TestCase):
    def _load(self, feed):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feeds.json"
            path.write_text(json.dumps({"feeds": [feed]}), encoding="utf-8")
            return load_feeds(path)

    def test_curated_is_read_and_defaults_to_false(self):
        self.assertTrue(self._load({"name": "Hub", "url": "https://hub.example/feed/", "curated": True})[0].curated)
        self.assertFalse(self._load({"name": "Hub", "url": "https://hub.example/feed/"})[0].curated)

    def test_curated_must_be_true_or_false(self):
        with self.assertRaises(ValueError):
            self._load({"name": "Hub", "url": "https://hub.example/feed/", "curated": "yes"})


if __name__ == "__main__":
    unittest.main()
