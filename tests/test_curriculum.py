"""Curriculum specialist, writer and coordinator roles."""
import unittest

from stemed_jobs.classification import classify_job
from stemed_jobs.disciplines import DISCIPLINES, classify_disciplines
from stemed_jobs.models import Job
from stemed_jobs.relevance import is_stem_education_relevant


def feeds(title, summary=""):
    categories, functions = classify_job(title, summary)
    disciplines = classify_disciplines(title, summary)
    job = Job(
        id=title, title=title, company="", location="", url="https://jobs.example/x", published="",
        summary=summary, source="s", source_url="u", categories=categories, functions=functions,
        disciplines=disciplines,
    )
    return {(a, d) for a in categories for d in disciplines if is_stem_education_relevant(job, d)}


class CurriculumRoleTests(unittest.TestCase):
    def test_a_named_discipline_lists_the_job_under_that_discipline(self):
        self.assertEqual(feeds("Biology Curriculum Specialist"), {("staff", "Bioscience")})
        self.assertEqual(feeds("Math Curriculum Writer"), {("staff", "Mathematics")})
        self.assertEqual(feeds("Computer Science Curriculum Coordinator"), {("staff", "Engineering")})
        self.assertEqual(feeds("Science Curriculum Writer, Grades 6-8"), {("staff", "Science Education")})

    def test_general_stem_lists_the_job_under_every_discipline(self):
        self.assertEqual(feeds("STEM Curriculum Specialist"), {("staff", d) for d in DISCIPLINES})

    def test_the_posting_can_supply_the_discipline(self):
        self.assertEqual(
            feeds("Curriculum Writer", "Write middle school mathematics units. Mathematics lessons aligned to standards."),
            {("staff", "Mathematics")},
        )
        self.assertEqual(feeds("Curriculum Coordinator, Department of Chemistry"), {("staff", "Chemistry")})

    def test_non_stem_curriculum_jobs_are_left_out(self):
        self.assertEqual(feeds("Curriculum Writer", "Write lessons for high school English."), set())
        self.assertEqual(feeds("Social Studies Curriculum Specialist"), set())
        self.assertEqual(feeds("Political Science Curriculum Writer"), set())
        self.assertEqual(feeds("Harvard University, Faculty of Arts & Sciences: Lab Curriculum Coordinator I"), set())

    def test_curriculum_alone_is_not_learning_science(self):
        self.assertNotIn("Learning Science", classify_disciplines("Physics Curriculum Specialist", ""))
        self.assertEqual(feeds("Biology Curriculum Developer"), {("staff", "Bioscience")})
        self.assertEqual(feeds("Curriculum Development Manager", "Lead curriculum development."), set())
        self.assertEqual(feeds("Instructional Designer"), {("staff", "Learning Science")})

    def test_staff_unless_the_title_says_graduate_postdoc_or_faculty(self):
        self.assertEqual(classify_job("Undergraduate Curriculum Coordinator", "")[0], ["staff"])
        self.assertEqual(classify_job("Postdoctoral Fellow, Physics Curriculum Specialist", "")[0], ["postdocs"])
        self.assertEqual(classify_job("Assistant Professor and Mathematics Curriculum Coordinator", "")[0], ["faculty"])
        self.assertEqual(feeds("Postdoctoral Fellow, Physics Curriculum Specialist"), {("postdocs", "Physics")})


if __name__ == "__main__":
    unittest.main()
