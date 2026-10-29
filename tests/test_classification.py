import unittest

from stemed_jobs.classification import classify_job


class StaffAudienceTests(unittest.TestCase):
    def categories(self, title):
        return classify_job(title, "")[0]

    def test_educational_design_and_development_roles_are_staff(self):
        for title in (
            "Instructional Designer", "Educational Designer, College of Nursing", "Learning Experience Designer",
            "Senior Instructional Designer", "Curriculum Developer, STEM", "Educational Developer",
            "Academic Technologist", "Educational Technology Specialist", "Learning Designer",
            "Online Learning Specialist", "Teaching and Learning Consultant",
        ):
            self.assertIn("staff", self.categories(title), title)

    def test_faculty_developer_is_staff_not_faculty(self):
        self.assertEqual(self.categories("Faculty Developer, Center for Teaching and Learning"), ["staff"])

    def test_a_professor_of_instructional_design_is_faculty_not_staff(self):
        self.assertEqual(self.categories("Assistant Professor of Instructional Design"), ["faculty"])

    def test_unrelated_titles_are_not_staff(self):
        for title in ("Software Developer", "Assistant Professor of Physics", "Postdoc in Chemistry Education"):
            self.assertNotIn("staff", self.categories(title), title)


if __name__ == "__main__":
    unittest.main()
