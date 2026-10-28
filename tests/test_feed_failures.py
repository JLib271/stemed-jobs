import contextlib
import http.client
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from stemed_jobs import cli
from stemed_jobs.importers.rss import ingest_feeds
from stemed_jobs.models import Feed, Job


def _job(identifier: str) -> Job:
    return Job(
        id=identifier,
        title="Assistant Professor of Physics Education Research",
        company="",
        location="",
        url="https://jobs.example/{}".format(identifier),
        published="",
        summary="",
        source="Good feed",
        source_url="https://feeds.example/good",
        categories=["faculty"],
        functions=[],
        disciplines=["Physics"],
    )


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


class CliExitCodeTests(unittest.TestCase):
    def _run(self, ingest_result, *extra_args, environment=None):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            feeds_path = root / "feeds.json"
            feeds_path.write_text(
                json.dumps(
                    {
                        "feeds": [
                            {"name": "Good feed", "url": "https://feeds.example/good"},
                            {"name": "Broken feed", "url": "https://feeds.example/broken"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
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
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch("sys.argv", argv), patch("stemed_jobs.cli.ingest_feeds", return_value=ingest_result), patch.dict(
                "os.environ", environment or {}, clear=False
            ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cli.main()
            wrote_jobs = (output / "jobs.json").exists()
            saved = json.loads((output / "jobs.json").read_text(encoding="utf-8")) if wrote_jobs else None
        return code, stdout.getvalue(), stderr.getvalue(), saved

    def test_without_the_flag_a_failed_feed_still_exits_nonzero(self):
        code, _, stderr, saved = self._run(([_job("1")], ["Broken feed (https://feeds.example/broken): boom"]))
        self.assertEqual(code, 1)
        self.assertIn("Feed error: Broken feed", stderr)
        self.assertEqual(len(saved), 1)

    def test_with_the_flag_a_failed_feed_is_skipped_and_the_run_succeeds(self):
        code, stdout, stderr, saved = self._run(
            ([_job("1")], ["Broken feed (https://feeds.example/broken): boom"]), "--allow-feed-errors"
        )
        self.assertEqual(code, 0)
        self.assertEqual(len(saved), 1)
        self.assertIn("Feed error: Broken feed", stderr)
        self.assertIn("Skipped 1 of 2 feed(s)", stdout)
        self.assertIn("Wrote 1 jobs from 1 feed(s)", stdout)

    def test_when_every_feed_fails_the_run_fails_and_writes_nothing(self):
        errors = ["Good feed (https://feeds.example/good): down", "Broken feed (https://feeds.example/broken): down"]
        code, _, stderr, saved = self._run(([], errors), "--allow-feed-errors")
        self.assertEqual(code, 1)
        self.assertIsNone(saved)
        self.assertIn("every feed failed", stderr)

    def test_github_actions_gets_a_warning_annotation_for_each_skipped_feed(self):
        _, stdout, _, _ = self._run(
            ([_job("1")], ["Broken feed (https://feeds.example/broken): line one\nline two 100%"]),
            "--allow-feed-errors",
            environment={"GITHUB_ACTIONS": "true"},
        )
        self.assertIn("::warning title=Feed skipped::Broken feed", stdout)
        self.assertIn("line one%0Aline two 100%25", stdout)

    def test_no_annotation_outside_github_actions(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("GITHUB_ACTIONS", None)
            _, stdout, _, _ = self._run(([_job("1")], ["Broken feed (u): x"]), "--allow-feed-errors")
        self.assertNotIn("::warning", stdout)


if __name__ == "__main__":
    unittest.main()
