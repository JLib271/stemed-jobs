import unittest

from stemed_jobs.disciplines import classify_disciplines


class DisciplineEvidenceTests(unittest.TestCase):
    def test_physics_department_in_engineering_college_is_only_physics(self):
        disciplines = classify_disciplines(
            "FT Teaching Assistant Professor, Urbana-Champaign IL",
            "The Department of Physics in the Grainger College of Engineering invites applications. "
            "A doctorate in physics is required. The college runs an engineering education academy.",
        )
        self.assertEqual(disciplines, ["Physics"])

    def test_math_title_is_not_pulled_into_engineering_by_college_lists(self):
        disciplines = classify_disciplines(
            "Assistant Teaching Faculty in Mathematics",
            "The Mathematics & Statistics Department offers strong programs. The university also "
            "has professional programs in engineering, management, education, and music.",
        )
        self.assertEqual(disciplines, ["Mathematics"])

    def test_generic_title_uses_program_name_not_school_name(self):
        disciplines = classify_disciplines(
            "Professor/Associate Professor/Assistant Professor (Research and Teaching Track)",
            "The Mathematics Program, School of Science and Engineering seeks applicants in "
            "pure and applied mathematics.",
        )
        self.assertEqual(disciplines, ["Mathematics"])

    def test_generic_title_uses_department_name(self):
        disciplines = classify_disciplines(
            "Assistant Professor, Teaching Stream - Advanced Manufacturing & Automation",
            "The Department of Mechanical & Industrial Engineering invites applications.",
        )
        self.assertEqual(disciplines, ["Engineering"])

    def test_list_of_colleges_does_not_add_engineering_to_a_statistics_title(self):
        disciplines = classify_disciplines(
            "Visiting Assistant Professor/Instructor of Statistics",
            "Our colleges are Arts & Sciences, Business, Engineering, and Pharmacy.",
        )
        self.assertEqual(disciplines, ["Mathematics"])

    def test_department_and_title_are_combined(self):
        disciplines = classify_disciplines(
            "Teaching Assistant Professor - Department of Physics",
            "The Department of Physics and Astronomy is in the College of Engineering.",
        )
        self.assertEqual(disciplines, ["Physics"])

    def test_most_mentioned_discipline_wins_when_no_title_or_department(self):
        disciplines = classify_disciplines(
            "Teaching Faculty",
            "We seek someone to teach chemistry courses and supervise chemistry labs. "
            "Some collaboration with physics is possible.",
        )
        self.assertEqual(disciplines, ["Chemistry"])

    def test_equally_mentioned_disciplines_are_both_kept(self):
        disciplines = classify_disciplines(
            "Teaching Faculty",
            "Teach courses in chemistry and in biology.",
        )
        self.assertEqual(disciplines, ["Bioscience", "Chemistry"])

    def test_college_name_is_used_only_as_a_last_resort(self):
        disciplines = classify_disciplines(
            "Teaching Professor",
            "Join the School of Engineering as a full-time teaching professor.",
        )
        self.assertEqual(disciplines, ["Engineering"])

    def test_no_evidence_is_other(self):
        self.assertEqual(classify_disciplines("Teaching Professor", "Great benefits."), ["Other"])

    def test_dber_title_is_cross_listed_from_the_description(self):
        disciplines = classify_disciplines(
            "Three DBER Graduate Assistantships, Auburn AL",
            "Fellowships in physics, engineering and mathematics education research.",
        )
        self.assertEqual(
            set(disciplines), {"Engineering", "Mathematics", "Physics", "Science Education"}
        )


if __name__ == "__main__":
    unittest.main()
