import unittest

from stemed_jobs.dedup import canonical_url, dedupe_jobs
from stemed_jobs.models import Job


def _job(title, url, company="", source="Board"):
    return Job(
        id=url,
        title=title,
        company=company,
        location="",
        url=url,
        published="",
        summary="",
        source=source,
        source_url="",
        categories=[],
        functions=[],
        disciplines=[],
    )


class DedupTests(unittest.TestCase):
    def test_canonical_url_ignores_tracking_fragment_case_and_trailing_slash(self):
        self.assertEqual(
            canonical_url("HTTPS://Jobs.Example/job/1/?utm_source=x&id=7&gclid=abc#apply"),
            canonical_url("https://jobs.example/job/1?id=7"),
        )

    def test_canonical_url_keeps_identifying_query_parameters(self):
        self.assertNotEqual(canonical_url("https://jobs.example/view?id=1"), canonical_url("https://jobs.example/view?id=2"))

    def test_same_url_with_tracking_parameters_is_a_duplicate(self):
        jobs = [_job("A", "https://jobs.example/1"), _job("A", "https://jobs.example/1?utm_campaign=rss")]
        self.assertEqual(len(dedupe_jobs(jobs)), 1)

    def test_same_title_and_company_on_different_boards_is_a_duplicate(self):
        jobs = [
            _job("Assistant Professor of Teaching, Physics", "https://a.example/1", "Michigan State University", "First"),
            _job("Assistant Professor of Teaching - Physics", "https://b.example/9", "michigan state university", "Second"),
        ]
        unique = dedupe_jobs(jobs)
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0].source, "First")

    def test_same_title_with_different_company_is_kept(self):
        jobs = [
            _job("Postdoctoral Researcher", "https://a.example/1", "University A"),
            _job("Postdoctoral Researcher", "https://b.example/2", "University B"),
        ]
        self.assertEqual(len(dedupe_jobs(jobs)), 2)

    def test_same_title_without_company_is_not_merged(self):
        jobs = [_job("Postdoctoral Researcher", "https://a.example/1"), _job("Postdoctoral Researcher", "https://b.example/2")]
        self.assertEqual(len(dedupe_jobs(jobs)), 2)


if __name__ == "__main__":
    unittest.main()
