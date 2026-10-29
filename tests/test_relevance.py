import unittest

from stemed_jobs.models import Job
from stemed_jobs.relevance import is_stem_education_relevant


def _job(title, summary="", disciplines=("Learning Science",), categories=()):
    return Job(
        id=title, title=title, company="", location="", url="https://jobs.example/" + title.replace(" ", "-"),
        published="", summary=summary, source="s", source_url="u", categories=list(categories),
        functions=[], disciplines=list(disciplines),
    )


class LearningScienceRelevanceTests(unittest.TestCase):
    def relevant(self, job):
        return is_stem_education_relevant(job, "Learning Science")

    def test_the_three_field_names_count_in_the_title(self):
        for title in (
            "Postdoc in the Learning Sciences",
            "Assistant Professor of Cognitive Science",
            "Lecturer in Educational Psychology",
            "PhD position, learning science",
        ):
            self.assertTrue(self.relevant(_job(title)), title)

    def test_they_also_count_when_only_the_description_names_the_field(self):
        job = _job("Research Associate", "The lab studies cognitive science of how students learn algebra.")
        self.assertTrue(self.relevant(job))

    def test_an_unrelated_job_is_not_relevant(self):
        self.assertFalse(self.relevant(_job("Research Associate", "Studies of mouse behavior.")))

    def test_the_description_rule_needs_the_learning_science_discipline(self):
        job = _job("Research Associate", "Uses cognitive science methods.", disciplines=("Physics",))
        self.assertFalse(is_stem_education_relevant(job, "Learning Science"))


class SubfieldEducationTests(unittest.TestCase):
    def test_subfield_education_titles_are_relevant_to_their_discipline(self):
        for title, discipline in (
            ("Postdoc in Geology Education Research", "Earth Science"),
            ("Hydrology Education Postdoctoral Fellow", "Earth Science"),
            ("Biochemistry Education Research Postdoc", "Chemistry"),
            ("Entomology Education Postdoc", "Bioscience"),
            ("Animal Science Education Postdoc", "Bioscience"),
            ("Astronomy Education Research Postdoc", "Physics"),
            ("Space Science Education Postdoc", "Physics"),
            ("Environmental Education Postdoc", "Earth Science"),
            ("Chemical Education Postdoc", "Chemistry"),
        ):
            self.assertTrue(is_stem_education_relevant(_job(title, disciplines=(discipline,)), discipline), title)

    def test_a_plain_subfield_title_without_education_is_not_enough(self):
        self.assertFalse(is_stem_education_relevant(_job("Postdoc in Geophysics", disciplines=("Earth Science",)), "Earth Science"))


if __name__ == "__main__":
    unittest.main()
