import unittest

from stemed_jobs.disciplines import classify_disciplines
from stemed_jobs.models import Job
from stemed_jobs.relevance import is_stem_education_relevant


class AcronymMatchingTests(unittest.TestCase):
    def test_ordinary_words_do_not_trigger_acronym_disciplines(self):
        disciplines = classify_disciplines(
            "Assistant Professor of Teaching, Biology",
            "Salary is $90,000 per year. Teaches three courses per term; hourly rate $40 per hour.",
        )
        self.assertEqual(disciplines, ["Bioscience"])

    def test_uppercase_acronyms_still_match(self):
        self.assertIn("Physics", classify_disciplines("PER Postdoctoral Fellow", ""))
        self.assertIn("Chemistry", classify_disciplines("CER Faculty", ""))
        self.assertIn("Earth Science", classify_disciplines("GER Graduate Fellow", ""))
        self.assertIn("Bioscience", classify_disciplines("BER Postdoctoral Fellow", ""))

    def test_lowercase_per_in_title_does_not_qualify_as_physics_education(self):
        job = Job(
            id="1",
            title="Postdoctoral Scholar, 40 hours per week",
            company="",
            location="",
            url="https://jobs.example/1",
            published="",
            summary="",
            source="Board",
            source_url="",
            categories=["postdocs"],
            functions=[],
            disciplines=["Physics"],
        )
        self.assertFalse(is_stem_education_relevant(job, "Physics"))


if __name__ == "__main__":
    unittest.main()
