import unittest
from datetime import date

from stemed_jobs.deadlines import extract_deadline, extract_review_start

POSTED = date(2026, 10, 12)


class ExtractDeadlineTests(unittest.TestCase):
    def check(self, text, expected):
        self.assertEqual(extract_deadline(text, POSTED), expected, text)

    def test_reads_common_phrasings(self):
        self.check("The application deadline is January 8, 2027 (15:00 CET).", date(2027, 1, 8))
        self.check("Please submit your application by 23 November 2026.", date(2026, 11, 23))
        self.check("Applications due December 1, 2026", date(2026, 12, 1))
        self.check("application deadline 12/1/2026", date(2026, 12, 1))
        self.check("Deadline: 2026-11-15", date(2026, 11, 15))
        self.check("Applications close on 5th January", date(2027, 1, 5))

    def test_a_date_without_a_year_follows_the_posting_date(self):
        self.check("applications are due Dec. 1", date(2026, 12, 1))

    def test_a_date_without_a_year_is_skipped_when_the_posting_date_is_unknown(self):
        self.assertIsNone(extract_deadline("applications are due Dec. 1", None))

    def test_review_start_dates_and_other_dates_are_not_deadlines(self):
        self.check("Review of applications will begin December 1 and continue until filled", None)
        self.check("We begin reviewing applications on November 1, 2026", None)
        self.check("Posting date: October 27, 2026", None)
        self.check("Position starts August 2 - August 6, 2027.", None)

    def test_no_text_means_no_deadline(self):
        self.assertIsNone(extract_deadline("", POSTED))


class ExtractReviewStartTests(unittest.TestCase):
    def check(self, text, expected):
        self.assertEqual(extract_review_start(text, POSTED), expected, text)

    def test_reads_common_phrasings(self):
        self.check("Review of applications will begin December 1 and continue until filled", date(2026, 12, 1))
        self.check("Review of applications begins on November 15, 2026.", date(2026, 11, 15))
        self.check("We will begin reviewing applications on 3 January 2027", date(2027, 1, 3))
        self.check("applications will be reviewed beginning Jan. 5, 2027", date(2027, 1, 5))
        self.check("Review of applications will begin 12/01/2026", date(2026, 12, 1))

    def test_other_dates_are_not_review_starts(self):
        self.check("The application deadline is January 8, 2027", None)
        self.check("Posting date: October 27, 2026", None)

    def test_a_review_start_is_not_read_as_a_deadline(self):
        self.assertIsNone(extract_deadline("Review of applications will begin December 1", POSTED))


if __name__ == "__main__":
    unittest.main()
