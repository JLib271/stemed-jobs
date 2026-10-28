import contextlib
import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.error import HTTPError

from stemed_jobs import cli
from stemed_jobs.importers.rss import ingest_feeds
from stemed_jobs.models import Feed, FeedResult, Job


GOOD = Feed("Good feed", "https://feeds.example/good")
BROKEN = Feed("Broken feed", "https://feeds.example/broken")


def _job(identifier: str, source: Feed = GOOD, title: str = "Assistant Professor of Physics Education Research") -> Job:
    return Job(
        id=identifier,
        title=title,
        company="",
        location="",
        url="https://jobs.example/{}".format(identifier),
        published="",
        summary="",
        source=source.name,
        source_url=source.url,
        categories=["faculty"],
        functions=[],
        disciplines=["Physics"],
    )


def _failed(feed: Feed, message: str = "boom") -> FeedResult:
    return FeedResult(feed, [], "{} ({}): {}".format(feed.name, feed.url, message))


class IngestIsolatesBrokenFeedsTests(unittest.TestCase):
    def test_any_kind_of_feed_failure_is_skipped_and_reported(self):
        feeds = [
            Feed("Not found", "https://feeds.example/404"),
            Feed("Cut off", "https://feeds.example/cut"),
            Feed("Bug", "https://feeds.example/bug"),
            Feed("Good", "https://feeds.example/good"),
        ]

        def fake_fetch(feed):
            if feed.name == "Not found":
                raise HTTPError(feed.url, 404, "Not Found", {}, None)
            if feed.name == "Cut off":
                raise http.client.IncompleteRead(b"partial")
            if feed.name == "Bug":
                raise RuntimeError("unexpected")
            return [_job("1")]

        with patch("stemed_jobs.importers.rss.fetch_feed", side_effect=fake_fetch):
            jobs, errors = ingest_feeds(feeds)

        self.assertEqual([job.id for job in jobs], ["1"])
        self.assertEqual(len(errors), 3)
        self.assertIn("Not found (https://feeds.example/404): HTTPError", errors[0])
        self.assertIn("IncompleteRead", errors[1])
        self.assertIn("RuntimeError: unexpected", errors[2])


class _CliHarness:
    """Runs the real command with fetching replaced by canned results."""

    def _run(self, results, *extra_args, environment=None, previous_files=None):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            feeds_path = root / "feeds.json"
            feeds_path.write_text(
                json.dumps({"feeds": [{"name": feed.name, "url": feed.url} for feed in (GOOD, BROKEN)]}),
                encoding="utf-8",
            )
            previous = root / "previous"
            previous.mkdir()
            for name, content in (previous_files or {}).items():
                (previous / name).write_text(json.dumps(content), encoding="utf-8")
            output = root / "output"
            argv = [
                "stemed_jobs",
                "--feeds", str(feeds_path),
                "--boards", "config/job_boards.json",
                "--output", str(output / "jobs.json"),
                "--feed-output", str(output / "feeds"),
                "--html-output", str(output),
                *extra_args,
            ]
            if previous_files is not None:
                argv += ["--previous", str(previous)]
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch("sys.argv", argv), patch("stemed_jobs.cli.fetch_all", return_value=results), patch.dict(
                os.environ, environment or {}, clear=False
            ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cli.main()
            saved = None
            status = None
            if (output / "jobs.json").exists():
                saved = json.loads((output / "jobs.json").read_text(encoding="utf-8"))
            if (output / "feed_status.json").exists():
                status = json.loads((output / "feed_status.json").read_text(encoding="utf-8"))
        return code, stdout.getvalue(), stderr.getvalue(), saved, status


class CliTests(_CliHarness, unittest.TestCase):
    def test_prints_how_many_items_each_working_feed_returned_and_how_far_back(self):
        dated = Job(**{**_job("1").__dict__, "published": "2026-10-01T00:00:00Z"})
        newer = Job(**{**_job("2").__dict__, "published": "2026-10-20T00:00:00Z"})
        _, stdout, _, _, status = self._run(
            [FeedResult(GOOD, [dated, newer]), FeedResult(BROKEN, [_job("3", BROKEN)])]
        )
        self.assertIn("Feed Good feed: 2 item(s), 2026-10-01 to 2026-10-20", stdout)
        self.assertIn("Feed Broken feed: 1 item(s)", stdout)
        self.assertEqual(status["feeds"][GOOD.url]["items"], 2)

    def test_without_the_flag_a_failed_feed_still_exits_nonzero(self):
        code, _, stderr, saved, _ = self._run([FeedResult(GOOD, [_job("1")]), _failed(BROKEN)])
        self.assertEqual(code, 1)
        self.assertIn("Feed error: Broken feed", stderr)
        self.assertEqual(len(saved), 1)

    def test_with_the_flag_a_failed_feed_is_skipped_and_the_run_succeeds(self):
        code, stdout, stderr, saved, _ = self._run(
            [FeedResult(GOOD, [_job("1")]), _failed(BROKEN)], "--allow-feed-errors"
        )
        self.assertEqual(code, 0)
        self.assertEqual(len(saved), 1)
        self.assertIn("Feed error: Broken feed", stderr)
        self.assertIn("Skipped 1 of 2 feed(s)", stdout)

    def test_when_every_feed_fails_the_run_fails_and_writes_nothing(self):
        code, _, stderr, saved, status = self._run([_failed(GOOD, "down"), _failed(BROKEN, "down")], "--allow-feed-errors")
        self.assertEqual(code, 1)
        self.assertIsNone(saved)
        self.assertIsNone(status)
        self.assertIn("every feed failed", stderr)

    def test_github_actions_gets_a_warning_annotation_for_each_skipped_feed(self):
        failed = FeedResult(BROKEN, [], "Broken feed (u): line one\nline two 100%")
        _, stdout, _, _, _ = self._run(
            [FeedResult(GOOD, [_job("1")]), failed], "--allow-feed-errors", environment={"GITHUB_ACTIONS": "true"}
        )
        self.assertIn("::warning title=Feed skipped::Broken feed", stdout)
        self.assertIn("line one%0Aline two 100%25", stdout)

    def test_no_annotation_outside_github_actions(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_ACTIONS", None)
            _, stdout, _, _, _ = self._run(
                [FeedResult(GOOD, [_job("1")]), _failed(BROKEN)], "--allow-feed-errors"
            )
        self.assertNotIn("::warning", stdout)


class CliFallbackTests(_CliHarness, unittest.TestCase):
    def _previous(self, last_success="2099-01-01T00:00:00Z"):
        broken_job = _job("old", BROKEN, "Teaching Faculty in Mathematics").to_dict()
        broken_job["disciplines"] = ["Engineering"]  # sorted wrongly by an older version
        return {
            "jobs.json": [_job("good-old").to_dict(), broken_job],
            "feed_status.json": {
                "feeds": {BROKEN.url: {"name": BROKEN.name, "last_success": last_success}},
            },
        }

    def test_failed_feed_keeps_its_last_good_jobs_and_they_are_resorted(self):
        code, stdout, _, saved, status = self._run(
            [FeedResult(GOOD, [_job("1")]), _failed(BROKEN)], "--allow-feed-errors", previous_files=self._previous()
        )
        self.assertEqual(code, 0)
        by_id = {job["id"]: job for job in saved}
        self.assertEqual(set(by_id), {"1", "old"})  # the good feed's stale copy is not reused
        self.assertEqual(by_id["old"]["disciplines"], ["Mathematics"])
        self.assertIn("Kept 1 job(s) from the last good copy of Broken feed", stdout)
        self.assertEqual(status["feeds"][BROKEN.url]["last_success"], "2099-01-01T00:00:00Z")
        self.assertIn("last_error", status["feeds"][BROKEN.url])
        self.assertNotIn("last_error", status["feeds"][GOOD.url])

    def test_failed_feed_jobs_expire_after_the_stale_limit(self):
        code, stdout, _, saved, _ = self._run(
            [FeedResult(GOOD, [_job("1")]), _failed(BROKEN)],
            "--allow-feed-errors",
            previous_files=self._previous(last_success="2000-01-01T00:00:00Z"),
        )
        self.assertEqual(code, 0)
        self.assertEqual([job["id"] for job in saved], ["1"])
        self.assertIn("Dropped 1 stored job(s) from Broken feed", stdout)

    def test_missing_previous_output_is_not_fatal(self):
        code, stdout, _, saved, _ = self._run(
            [FeedResult(GOOD, [_job("1")]), _failed(BROKEN)], "--allow-feed-errors", previous_files={}
        )
        self.assertEqual(code, 0)
        self.assertEqual([job["id"] for job in saved], ["1"])
        self.assertIn("any failed feed has no fallback", stdout)

    def test_working_feed_with_retain_days_keeps_older_postings_from_the_previous_output(self):
        capped = Feed("Capped", "https://feeds.example/capped", (), 90)
        older = _job("older", capped, "Teaching Faculty in Mathematics")
        older_dict = older.to_dict()
        older_dict["published"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        code, stdout, _, saved, status = self._run(
            [FeedResult(GOOD, [_job("1")]), FeedResult(capped, [_job("2", capped)])],
            previous_files={"jobs.json": [older_dict], "feed_status.json": {"feeds": {}}},
        )
        self.assertEqual(code, 0)
        self.assertEqual({job["id"] for job in saved}, {"1", "2", "older"})
        self.assertEqual(status["feeds"][capped.url]["retained"], 1)
        self.assertIn("plus 1 kept from earlier runs", stdout)
        self.assertNotIn("retained", status["feeds"][GOOD.url])


if __name__ == "__main__":
    unittest.main()
