import json
import unittest
from datetime import date

from stemed_jobs.academic_year import academic_year_start, filter_current, is_current
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


TODAY = date(2026, 10, 28)
SINCE = date(2026, 5, 1)


def _with(identifier, published="", deadline=""):
    return Job(**{**_job(identifier).__dict__, "published": published, "deadline": deadline})


class IsCurrentTests(unittest.TestCase):
    def test_a_stated_deadline_decides_whatever_the_posting_date(self):
        self.assertTrue(is_current(_with("a", "2026-01-01T00:00:00Z", "2026-12-01"), TODAY, SINCE))
        self.assertFalse(is_current(_with("b", "2026-09-01T00:00:00Z", "2026-09-01"), TODAY, SINCE))

    def test_kept_until_one_month_after_the_deadline(self):
        self.assertTrue(is_current(_with("a", deadline="2026-09-28"), TODAY, SINCE))  # exactly 30 days
        self.assertFalse(is_current(_with("b", deadline="2026-09-27"), TODAY, SINCE))  # 31 days
        self.assertTrue(is_current(_with("c", deadline="2026-09-01"), TODAY, SINCE, grace_days=60))

    def test_without_a_deadline_the_posting_date_and_cutoff_decide(self):
        self.assertFalse(is_current(_with("old", "2026-04-30T23:59:00Z"), TODAY, SINCE))
        self.assertTrue(is_current(_with("first", "2026-05-01T00:00:00Z"), TODAY, SINCE))

    def test_with_neither_date_the_job_is_kept(self):
        self.assertTrue(is_current(_with("undated"), TODAY, SINCE))

    def test_filter_keeps_order(self):
        jobs = [_with("x", "2026-04-01T00:00:00Z"), _with("y", "2026-06-01T00:00:00Z")]
        self.assertEqual([job.id for job in filter_current(jobs, TODAY, SINCE)], ["y"])


class CliSinceTests(_CliHarness, unittest.TestCase):
    def test_since_flag_filters_the_output_and_says_how_many_were_left_out(self):
        results = [FeedResult(GOOD, [_dated("a", "2026-03-01T00:00:00Z"), _dated("b", "2026-09-01T00:00:00Z")]),
                   FeedResult(BROKEN, [])]
        code, stdout, _, saved, _ = self._run(results, "--since", "2026-05-01")
        self.assertEqual(code, 0)
        self.assertEqual([job["id"] for job in saved], ["b"])
        self.assertIn("Left out 1 advertisement(s)", stdout)

    def test_a_long_past_deadline_removes_a_recent_posting(self):
        results = [FeedResult(GOOD, [_with("closed", "2026-09-01T00:00:00Z", "2026-09-10"),
                                     _with("open", "2026-09-01T00:00:00Z", "2099-01-01")]),
                   FeedResult(BROKEN, [])]
        _, _, _, saved, _ = self._run(results, "--since", "2026-05-01")
        self.assertEqual([job["id"] for job in saved], ["open"])

    def test_a_bad_since_date_is_an_error(self):
        code, _, stderr, _, _ = self._run([FeedResult(GOOD, [])], "--since", "May 2026")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
