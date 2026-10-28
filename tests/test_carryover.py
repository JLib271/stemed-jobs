import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from stemed_jobs.carryover import Previous, apply_carryover, load_previous, write_status
from stemed_jobs.models import Feed, FeedResult, Job


NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
MATH = Feed("MathJobs", "https://feeds.example/math", ("Mathematics",))
OTHER = Feed("Other board", "https://feeds.example/other")


def _job(identifier, feed, title="Teaching Faculty", summary="", disciplines=()):
    return Job(
        id=identifier,
        title=title,
        company="",
        location="",
        url="https://jobs.example/{}".format(identifier),
        published="",
        summary=summary,
        source=feed.name,
        source_url=feed.url,
        categories=[],
        functions=[],
        disciplines=list(disciplines),
    )


def _failed(feed):
    return FeedResult(feed, [], "{} ({}): down".format(feed.name, feed.url))


class LoadPreviousTests(unittest.TestCase):
    def test_reads_jobs_and_status_from_a_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "jobs.json").write_text(
                json.dumps([_job("1", MATH).to_dict(), {"title": "no url"}, "junk"]), encoding="utf-8"
            )
            (Path(directory) / "feed_status.json").write_text(
                json.dumps({"feeds": {MATH.url: {"last_success": "2026-10-27T00:00:00Z"}}}), encoding="utf-8"
            )
            previous = load_previous(directory)
        self.assertEqual([job.id for job in previous.jobs], ["1"])
        self.assertEqual(previous.status[MATH.url]["last_success"], "2026-10-27T00:00:00Z")
        self.assertIsNone(previous.note)

    def test_missing_files_give_an_empty_result_with_a_note_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = load_previous(directory)
        self.assertEqual(previous.jobs, [])
        self.assertEqual(previous.status, {})
        self.assertIn("no previous jobs.json available", previous.note)

    def test_unreachable_site_gives_an_empty_result_instead_of_raising(self):
        previous = load_previous("http://127.0.0.1:9/nothing")
        self.assertEqual(previous.jobs, [])
        self.assertIsNotNone(previous.note)

    def test_missing_status_file_is_fine(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "jobs.json").write_text(json.dumps([_job("1", MATH).to_dict()]), encoding="utf-8")
            previous = load_previous(directory)
        self.assertEqual(len(previous.jobs), 1)
        self.assertEqual(previous.status, {})


class ApplyCarryOverTests(unittest.TestCase):
    def test_successful_feed_is_untouched_and_gets_a_fresh_timestamp(self):
        result = FeedResult(MATH, [_job("new", MATH)])
        carried = apply_carryover([result], Previous([_job("old", MATH)], {}), NOW)
        self.assertEqual(carried.results, [result])
        self.assertEqual(
            carried.status[MATH.url], {"name": "MathJobs", "last_success": "2026-10-28T12:00:00Z", "items": 1}
        )
        self.assertEqual(carried.notes, [])

    def test_successful_feed_status_records_how_far_back_its_items_reach(self):
        newest = _job("new", MATH)
        oldest = _job("old", MATH)
        mid = _job("mid", MATH)
        newest = Job(**{**newest.__dict__, "published": "2026-10-20T09:00:00Z"})
        oldest = Job(**{**oldest.__dict__, "published": "2026-10-01T09:00:00Z"})
        mid = Job(**{**mid.__dict__, "published": "2026-10-10T09:00:00Z"})
        carried = apply_carryover([FeedResult(MATH, [newest, oldest, mid])], Previous([], {}), NOW)
        entry = carried.status[MATH.url]
        self.assertEqual((entry["items"], entry["oldest"], entry["newest"]), (3, "2026-10-01", "2026-10-20"))

    def test_failed_feed_keeps_only_its_own_previous_jobs(self):
        previous = Previous([_job("math-old", MATH), _job("other-old", OTHER)], {})
        carried = apply_carryover([_failed(MATH)], previous, NOW)
        self.assertEqual([job.id for job in carried.results[0].jobs], ["math-old"])
        self.assertIsNotNone(carried.results[0].error)  # still reported as a failure

    def test_kept_jobs_are_resorted_with_the_current_rules(self):
        stale = _job("old", MATH, title="Assistant Teaching Faculty in Mathematics", disciplines=["Engineering"])
        carried = apply_carryover([_failed(MATH)], Previous([stale], {}), NOW)
        kept = carried.results[0].jobs[0]
        self.assertEqual(kept.disciplines, ["Mathematics"])
        self.assertEqual(kept.categories, ["faculty"])

    def test_the_feed_default_discipline_applies_when_resorting(self):
        stale = _job("old", MATH, title="Chern Instructor", summary="A three-year position.")
        carried = apply_carryover([_failed(MATH)], Previous([stale], {}), NOW)
        self.assertEqual(carried.results[0].jobs[0].disciplines, ["Mathematics"])

    def test_last_success_is_carried_forward_not_reset(self):
        previous = Previous([_job("old", MATH)], {MATH.url: {"last_success": "2026-10-26T12:00:00Z"}})
        carried = apply_carryover([_failed(MATH)], previous, NOW)
        self.assertEqual(carried.status[MATH.url]["last_success"], "2026-10-26T12:00:00Z")
        self.assertEqual(carried.status[MATH.url]["last_error"], "MathJobs (https://feeds.example/math): down")

    def test_jobs_expire_after_the_stale_limit(self):
        previous = Previous([_job("old", MATH)], {MATH.url: {"last_success": "2026-10-20T11:59:00Z"}})
        carried = apply_carryover([_failed(MATH)], previous, NOW, max_stale_days=7)
        self.assertEqual(carried.results[0].jobs, [])
        self.assertIn("Dropped 1 stored job(s) from MathJobs", carried.notes[0])

    def test_jobs_are_kept_right_up_to_the_stale_limit(self):
        previous = Previous([_job("old", MATH)], {MATH.url: {"last_success": "2026-10-21T12:00:00Z"}})
        carried = apply_carryover([_failed(MATH)], previous, NOW, max_stale_days=7)
        self.assertEqual(len(carried.results[0].jobs), 1)

    def test_unknown_last_success_starts_the_clock_now(self):
        carried = apply_carryover([_failed(MATH)], Previous([_job("old", MATH)], {}), NOW)
        self.assertEqual(len(carried.results[0].jobs), 1)
        self.assertEqual(carried.status[MATH.url]["last_success"], "2026-10-28T12:00:00Z")

    def test_garbled_last_success_is_treated_as_unknown(self):
        previous = Previous([_job("old", MATH)], {MATH.url: {"last_success": "yesterday-ish"}})
        carried = apply_carryover([_failed(MATH)], previous, NOW)
        self.assertEqual(len(carried.results[0].jobs), 1)
        self.assertEqual(carried.status[MATH.url]["last_success"], "2026-10-28T12:00:00Z")

    def test_failed_feed_with_nothing_stored_is_just_reported(self):
        carried = apply_carryover([_failed(MATH)], Previous([], {}), NOW)
        self.assertEqual(carried.results[0].jobs, [])
        self.assertEqual(carried.notes, [])


CAPPED = Feed("Capped board", "https://feeds.example/capped", (), 90)


def _posted(job, days_ago):
    return Job(**{**job.__dict__, "published": (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT00:00:00Z")})


class RetentionTests(unittest.TestCase):
    def _apply(self, fresh, stored, feed=CAPPED):
        return apply_carryover([FeedResult(feed, fresh)], Previous(stored, {}), NOW)

    def test_a_posting_the_feed_no_longer_lists_is_kept_within_the_window(self):
        old = _posted(_job("old", CAPPED), 40)
        carried = self._apply([_job("new", CAPPED)], [old])
        self.assertEqual([job.id for job in carried.results[0].jobs], ["new", "old"])
        self.assertEqual(carried.status[CAPPED.url]["retained"], 1)
        self.assertEqual(carried.status[CAPPED.url]["items"], 1)  # items counts only what the feed returned
        self.assertIsNone(carried.results[0].error)

    def test_retained_postings_are_resorted_with_the_current_rules(self):
        stored = _posted(
            _job("old", CAPPED, title="Assistant Teaching Faculty in Mathematics", disciplines=["Engineering"]), 5
        )
        kept = self._apply([], [stored]).results[0].jobs[0]
        self.assertEqual(kept.disciplines, ["Mathematics"])

    def test_a_posting_is_kept_through_the_last_day_of_the_window_and_dropped_after(self):
        on_last_day = _posted(_job("last", CAPPED), 90)
        too_old = _posted(_job("late", CAPPED), 91)
        carried = self._apply([], [on_last_day, too_old])
        self.assertEqual([job.id for job in carried.results[0].jobs], ["last"])

    def test_the_fresh_copy_wins_and_nothing_is_duplicated(self):
        listed = _posted(_job("same", CAPPED), 3)
        carried = self._apply([listed], [_posted(_job("same", CAPPED), 3)])
        self.assertEqual(len(carried.results[0].jobs), 1)
        self.assertNotIn("retained", carried.status[CAPPED.url])

    def test_a_posting_with_no_date_cannot_be_aged_so_it_is_not_kept(self):
        self.assertEqual(self._apply([], [_job("undated", CAPPED)]).results[0].jobs, [])

    def test_only_the_same_feeds_postings_are_kept(self):
        stored = [_posted(_job("mine", CAPPED), 5), _posted(_job("theirs", OTHER), 5)]
        self.assertEqual([job.id for job in self._apply([], stored).results[0].jobs], ["mine"])

    def test_feeds_without_retain_days_keep_nothing_extra(self):
        no_retention = Feed("Deep board", "https://feeds.example/deep")
        stored = [_posted(_job("old", no_retention), 5)]
        self.assertEqual(self._apply([], stored, no_retention).results[0].jobs, [])


class WriteStatusTests(unittest.TestCase):
    def test_writes_the_status_in_the_shape_load_previous_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            write_status({MATH.url: {"name": "MathJobs", "last_success": "2026-10-28T12:00:00Z"}}, Path(directory) / "feed_status.json")
            (Path(directory) / "jobs.json").write_text("[]", encoding="utf-8")
            previous = load_previous(directory)
        self.assertEqual(previous.status[MATH.url]["last_success"], "2026-10-28T12:00:00Z")


if __name__ == "__main__":
    unittest.main()
