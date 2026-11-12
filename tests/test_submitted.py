import datetime as dt
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from stemed_jobs import submitted
from stemed_jobs.carryover import Previous, apply_carryover
from stemed_jobs.academic_year import filter_current

TODAY = dt.date(2026, 11, 12)
EMAIL = "\n".join([
    "New submission: Seekers' Hub job form", "",
    "Position title: Assistant Professor of Chemistry Education",
    "Institution or organization: Example State University",
    "Location: Springfield, Illinois",
    "Who is this position for?",
    "Faculty",
    "Postdoc",
    "Disciplines: Chemistry, Science Education",
    "Link to the official posting: https://jobs.example.edu/12345",
    "Application deadline: January 15, 2027",
    "Review of applications begins:",
    "Description:",
    "We seek a chemistry education researcher.",
    "Start date August 2027.",
    "Your name and email (for the reviewer only): Pat Poster, pat@example.edu",
])


class SubmittedTest(unittest.TestCase):
    def test_reads_email(self):
        p, problems = submitted.from_email(EMAIL, TODAY)
        self.assertEqual(problems, [])
        self.assertEqual(p["title"], "Assistant Professor of Chemistry Education")
        self.assertEqual(p["audiences"], ["Postdoc", "Faculty"])
        self.assertEqual(p["disciplines"], [d for d in submitted.DISCIPLINES if d in ("Chemistry", "Science Education")])
        self.assertEqual(p["description"], "We seek a chemistry education researcher.\nStart date August 2027.")
        self.assertNotIn("pat@example.edu", json.dumps(p))

    def test_problems(self):
        p, problems = submitted.from_email(EMAIL.replace("https://jobs.example.edu/12345", "jobs.example.edu"), TODAY)
        self.assertTrue(any("web address" in x for x in problems))
        _, problems = submitted.from_email("Position title: X", TODAY)
        self.assertTrue(any("Institution" in x for x in problems))

    def test_issue_to_job_and_site(self):
        body = f"### {submitted.PASTE_LABEL}\n\n```text\n{EMAIL}\n```"
        with tempfile.TemporaryDirectory() as tmp:
            changed, pid, reply = submitted.handle_issue(body, TODAY, Path(tmp))
            self.assertTrue(changed, reply)
            again, _, reply2 = submitted.handle_issue(body, TODAY + dt.timedelta(days=3), Path(tmp))
            self.assertIn("Updated", reply2)
            self.assertEqual(json.loads((Path(tmp) / f"{pid}.json").read_text())["approved"], TODAY.isoformat())
            result = submitted.load(Path(tmp))
            self.assertIsNone(result.error)
            job = result.jobs[0]
            self.assertEqual((job.company, job.deadline, job.curated), ("Example State University", "2027-01-15", True))
            self.assertEqual(sorted(job.categories), ["faculty", "postdocs"])
            carried = apply_carryover([result], Previous([], {}), datetime.now(timezone.utc), 30)
            kept = filter_current([j for r in carried.results for j in r.jobs], TODAY, dt.date(2026, 5, 1), 14, 6)
            self.assertEqual(len(kept), 1)

    def test_bad_paste_not_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            changed, _, reply = submitted.handle_issue("### x\n\nnothing", TODAY, Path(tmp))
            self.assertFalse(changed)
            self.assertIn("Missing", reply)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_spec_and_template_up_to_date(self):
        self.assertEqual(submitted.SPEC.read_text(encoding="utf-8"), submitted.spec())
        self.assertEqual(submitted.TEMPLATE.read_text(encoding="utf-8"), submitted.issue_template())


if __name__ == "__main__":
    unittest.main()
