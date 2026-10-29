import json
import unittest
from datetime import date

from stemed_jobs.academic_year import academic_year_start, filter_since
from stemed_jobs.models import Job
from test_feed_failures import BROKEN, GOOD, FeedResult, _CliHarness, _job


def _dated(identifier, published):
    return Job(**{**_job(identifier).__dict__, "published": published})


class AcademicYearStartTests(unittest.TestCase):
    def test_the_year_starts_on_the_most_recent_may_first(self):
        self.assertEqual(academic_year_start(date(2026, 10, 28)), date(2026, 5, 1))
        self.assertEqual(academic_year_start(date(2026, 5, 1)), date(2026, 5, 1))
        self.assertEqual(academic_year_start(date(2027, 4, 30)), date(2026, 5, 1))
        self.assertEqual(academic_year_start(date(2027, 5, 1)), date(2027, 5, 1))


class FilterSinceTests(unittest.TestCase):
    def test_drops_older_postings_keeps_the_boundary_and_undated_ones(self):
        jobs = [
            _dated("old", "2026-04-30T23:59:00Z"),
            _dated("first", "2026-05-01T00:00:00Z"),
            _dated("new", "2026-10-01T00:00:00Z"),
            _dated("undated", ""),
        ]
        kept = filter_since(jobs, date(2026, 5, 1))
        self.assertEqual([job.id for job in kept], ["first", "new", "undated"])


class CliSinceTests(_CliHarness, unittest.TestCase):
    def test_since_flag_filters_the_output_and_says_how_many_were_left_out(self):
        results = [FeedResult(GOOD, [_dated("a", "2026-03-01T00:00:00Z"), _dated("b", "2026-09-01T00:00:00Z")]),
                   FeedResult(BROKEN, [])]
        code, stdout, _, saved, _ = self._run(results, "--since", "2026-05-01")
        self.assertEqual(code, 0)
        self.assertEqual([job["id"] for job in saved], ["b"])
        self.assertIn("left out 1 older one(s)", stdout)

    def test_a_bad_since_date_is_an_error(self):
        code, _, stderr, _, _ = self._run([FeedResult(GOOD, [])], "--since", "May 2026")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
