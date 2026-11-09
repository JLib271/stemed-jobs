"""Computing counts as Engineering (the shared STEMEd+ discipline list)."""
import unittest

from stemed_jobs.disciplines import classify_disciplines
from stemed_jobs.models import Job
from stemed_jobs.relevance import is_stem_education_relevant


def relevant(title, discipline, categories=("faculty",)):
    job = Job(
        id=title, title=title, company="", location="", url="https://jobs.example/x", published="",
        summary="", source="s", source_url="u", categories=list(categories), functions=[],
        disciplines=classify_disciplines(title, ""),
    )
    return is_stem_education_relevant(job, discipline)


class ComputingTests(unittest.TestCase):
    def test_computer_science_is_engineering(self):
        self.assertEqual(classify_disciplines("Assistant Teaching Professor of Computer Science", ""), ["Engineering"])
        self.assertEqual(classify_disciplines("Postdoc in Computer Science Education", ""), ["Engineering"])

    def test_math_and_computer_science_is_both(self):
        self.assertEqual(
            classify_disciplines("Math and Computer Science Learning Specialist", ""), ["Engineering", "Mathematics"]
        )

    def test_teaching_and_education_research_roles_are_listed(self):
        self.assertTrue(relevant("Assistant Teaching Professor of Computer Science", "Engineering"))
        self.assertTrue(relevant("Postdoc in Computing Education Research", "Engineering", ("postdocs",)))

    def test_computer_science_research_roles_are_not(self):
        self.assertFalse(relevant("Assistant Professor of Computer Science", "Engineering"))
