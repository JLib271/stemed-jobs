import unittest

from stemed_jobs.classification import classify_job, is_teaching_focused, with_teaching


def audiences(title, company=""):
    return with_teaching(classify_job(title, "")[0], title, company)


class TeachingFocusedTests(unittest.TestCase):
    def test_teaching_titles(self):
        for title in ("Assistant Teaching Professor of Chemistry", "Lecturer in Mathematics",
                      "Senior Lecturer, Physics Education", "Instructor of Biology",
                      "Professor of Practice in Engineering Education",
                      "Assistant Professor (Teaching Track), Computer Science",
                      "Postdoctoral Teaching Fellow in Biology", "IRACDA Postdoctoral Fellow",
                      "Graduate Teaching Assistantship in Chemistry Education"):
            self.assertIn("teaching", audiences(title), title)

    def test_two_year_colleges(self):
        self.assertIn("teaching", audiences("Assistant Professor of Biology", "Tacoma Community College"))
        self.assertIn("teaching", audiences("Faculty, Chemistry - Valencia Community College"))

    def test_research_posts_are_not_teaching_focused(self):
        for title in ("Assistant Professor of Science Education", "Postdoctoral Researcher in Physics Education",
                      "PhD Student Position in Engineering Education Research"):
            self.assertNotIn("teaching", audiences(title), title)

    def test_staff_roles_are_not_teaching_focused(self):
        # An instructional designer is staff, and "teaching" needs an academic audience.
        self.assertFalse(is_teaching_focused("Instructional Designer", "", ["staff"]))
        self.assertNotIn("teaching", audiences("Teaching and Learning Specialist"))

    def test_teaching_is_added_once_and_keeps_other_audiences(self):
        cats = with_teaching(["faculty", "teaching"], "Lecturer in Physics")
        self.assertEqual(cats, ["faculty", "teaching"])


if __name__ == "__main__":
    unittest.main()
