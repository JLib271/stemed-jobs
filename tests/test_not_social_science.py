import unittest

from stemed_jobs.disciplines import classify_disciplines
from stemed_jobs.models import Job
from stemed_jobs.relevance import is_stem_education_relevant


def job(title, summary=""):
    return Job(id=title, title=title, company="State University", location="", url="https://example.org/",
               published=None, summary=summary, source="Test", source_url="", categories=["faculty"],
               functions=[], disciplines=classify_disciplines(title, summary))


class NotScienceEducationTests(unittest.TestCase):
    def test_social_science_education_is_not_science_education(self):
        for title in ("Assistant Professor of History/Social Science Education",
                      "Assistant Professor, Social Sciences Education",
                      "Lecturer in Political Science Education"):
            j = job(title, "Prepare future history and social studies teachers.")
            self.assertNotIn("Science Education", j.disciplines, title)
            self.assertFalse(is_stem_education_relevant(j, "Science Education"), title)

    def test_science_education_still_counts(self):
        for title in ("Assistant Professor of Science Education",
                      "Clinical Assistant Professor in Elementary Mathematics and Science Education",
                      "Assistant Professor of Social Studies and Science Education"):
            j = job(title)
            self.assertIn("Science Education", j.disciplines, title)
            self.assertTrue(is_stem_education_relevant(j, "Science Education"), title)


if __name__ == "__main__":
    unittest.main()
