import unittest

from stemed_jobs.models import Job
from stemed_jobs.relevance import _is_named_research_instructorship, is_stem_education_relevant


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


class FieldDisciplineTests(unittest.TestCase):
    """History & Philosophy of Science and Science & Health Communication include
    the fields themselves, not only education in them."""

    HPS = "History & Philosophy of Science"
    SHC = "Science & Health Communication"

    def test_field_jobs_count_when_the_title_names_the_field(self):
        for title, discipline in (
            ("Assistant Professor, History of Science", self.HPS),
            ("Postdoctoral Fellow in Science and Technology Studies", self.HPS),
            ("Lecturer in Philosophy of Biology", self.HPS),
            ("Assistant Professor of Health Communication", self.SHC),
            ("Science Communication Specialist", self.SHC),
            ("Postdoc, Climate Change Communication", self.SHC),
        ):
            job = _job(title, disciplines=(discipline,))
            self.assertTrue(is_stem_education_relevant(job, discipline), title)

    def test_history_of_science_in_the_description_counts(self):
        job = _job("Assistant Professor (Tenure-track)", "AOS: history and philosophy of science.", disciplines=(self.HPS,))
        self.assertTrue(is_stem_education_relevant(job, self.HPS))

    def test_science_communication_skills_in_the_description_do_not_count(self):
        job = _job("Research Scientist", "Strong science communication skills required.", disciplines=(self.SHC,))
        self.assertFalse(is_stem_education_relevant(job, self.SHC))

    def test_human_dimensions_jobs_count_by_title_or_description(self):
        hd = "Human Dimensions"
        job = _job("Assistant Professor, Human Dimensions of Forestry", disciplines=(hd, "Agriculture"))
        self.assertTrue(is_stem_education_relevant(job, hd))
        job = _job("Assistant Professor", "Research on social-ecological systems and conservation social science.", disciplines=(hd,))
        self.assertTrue(is_stem_education_relevant(job, hd))

    def test_the_field_must_be_the_jobs_discipline(self):
        job = _job("Assistant Professor, History of Science", disciplines=("Physics",))
        self.assertFalse(is_stem_education_relevant(job, self.HPS))


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


class HealthEducationRelevanceTests(unittest.TestCase):
    def test_health_education_titles_are_relevant(self):
        for title in (
            "Postdoc in Medical Education Research", "Nursing Education Fellow", "Pharmacy Education Research Postdoc",
            "Health Professions Education Postdoctoral Fellow", "Public Health Education Postdoc",
        ):
            job = _job(title, disciplines=("Health Education",))
            self.assertTrue(is_stem_education_relevant(job, "Health Education"), title)

    def test_a_faculty_teaching_role_is_relevant(self):
        job = _job("Assistant Teaching Professor of Nursing", disciplines=("Health Education",), categories=("faculty",))
        self.assertTrue(is_stem_education_relevant(job, "Health Education"))

    def test_a_plain_clinical_research_title_is_not(self):
        job = _job("Postdoc in Oncology Nursing Research", disciplines=("Health Education",))
        self.assertFalse(is_stem_education_relevant(job, "Health Education"))


class NamedInstructorshipTests(unittest.TestCase):
    def relevant(self, title, discipline="Mathematics", categories=("faculty",)):
        return is_stem_education_relevant(_job(title, disciplines=(discipline,), categories=categories), discipline)

    def test_named_research_instructorships_are_not_teaching_roles(self):
        for title in (
            "Bernoulli Instructor in Probability and Stochastic Analysis", "Courant Instructor",
            "Hermann-Weyl Instructor", "Chern Instructor", "Dickson Instructor",
        ):
            self.assertFalse(self.relevant(title), title)

    def test_ordinary_instructor_and_lecturer_roles_stay(self):
        for title in (
            "Instructor of Mathematics", "Mathematics Instructor", "Visiting Instructor in Mathematics",
            "Online Instructor, Mathematics", "Senior Teaching Lecturer in Mathematics", "Teaching Assistant Professor of Mathematics",
            "Bernoulli Instructor in Mathematics Education",
        ):
            self.assertTrue(self.relevant(title), title)

    def test_a_subject_word_is_not_mistaken_for_a_name(self):
        self.assertTrue(self.relevant("Chemistry Instructor", "Chemistry"))
        self.assertFalse(_is_named_research_instructorship("Physics Lecturer"))
        self.assertFalse(_is_named_research_instructorship("Nursing Instructor"))


class StaffRelevanceTests(unittest.TestCase):
    def test_a_design_role_is_relevant_to_the_disciplines_it_was_sorted_into(self):
        job = _job("Instructional Designer", disciplines=("Learning Science",), categories=("staff",))
        self.assertTrue(is_stem_education_relevant(job, "Learning Science"))
        self.assertFalse(is_stem_education_relevant(job, "Physics"))


if __name__ == "__main__":
    unittest.main()
