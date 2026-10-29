import unittest

from stemed_jobs.disciplines import classify_disciplines


class TitleAndDepartmentTests(unittest.TestCase):
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
            "The Department of Mechanical & Industrial Engineering in the Faculty of Applied "
            "Science & Engineering invites applications.",
        )
        self.assertEqual(disciplines, ["Engineering"])

    def test_department_named_with_the_word_department_last(self):
        disciplines = classify_disciplines(
            "Instructor",
            "The Computer Engineering Department in the College of Engineering seeks an instructor.",
        )
        self.assertEqual(disciplines, ["Engineering"])

    def test_program_named_with_the_word_program_last(self):
        disciplines = classify_disciplines(
            "Teaching Professor",
            "The Cornell Systems Engineering Program seeks a teaching professor. Focus areas include "
            "biotechnology and life sciences.",
        )
        self.assertEqual(disciplines, ["Engineering"])

    def test_biomedical_engineering_department_is_engineering_not_bioscience(self):
        disciplines = classify_disciplines(
            "BME Teaching Faculty",
            "The Boston University Department of Biomedical Engineering seeks teaching faculty "
            "in thermodynamics. Neuroscience and photonics centers collaborate.",
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
            "Assistant Professor of Science Education",
            "The Department of Physics and Astronomy seeks a science education researcher.",
        )
        self.assertEqual(disciplines, ["Physics", "Science Education"])

    def test_hiring_department_wins_over_collaborating_department(self):
        disciplines = classify_disciplines(
            "Teaching Faculty",
            "The Department of Physics seeks a lecturer. You will collaborate with the "
            "Department of Chemistry and the Department of Mathematics.",
        )
        self.assertEqual(disciplines, ["Physics"])

    def test_department_of_physics_does_not_absorb_the_parent_college(self):
        disciplines = classify_disciplines(
            "Teaching Faculty",
            "The Department of Physics and the Grainger College of Engineering seek a lecturer.",
        )
        self.assertEqual(disciplines, ["Physics"])


class SchoolAndFeedDefaultTests(unittest.TestCase):
    def test_school_is_the_hiring_unit_when_no_department_is_named(self):
        disciplines = classify_disciplines(
            "Assistant Teaching Professor 2026-27",
            "The School of Electrical and Computer Engineering at Cornell University seeks a "
            "teaching professor for programming, digital logic and embedded systems.",
        )
        self.assertEqual(disciplines, ["Engineering"])

    def test_college_name_is_used_only_when_nothing_better_exists(self):
        disciplines = classify_disciplines(
            "Teaching Professor",
            "Join the School of Engineering as a full-time teaching professor.",
        )
        self.assertEqual(disciplines, ["Engineering"])

    def test_feed_default_beats_a_school_name(self):
        disciplines = classify_disciplines(
            "Open Rank - Fixed Term - Teaching Professor",
            "The School of Science and Engineering invites applications.",
            ("Mathematics",),
        )
        self.assertEqual(disciplines, ["Mathematics"])

    def test_feed_default_applies_when_posting_names_nothing(self):
        disciplines = classify_disciplines(
            "Chern Instructor",
            "Applications are invited for a three-year position.",
            ("Mathematics",),
        )
        self.assertEqual(disciplines, ["Mathematics"])

    def test_feed_default_never_overrides_title_or_department(self):
        self.assertEqual(
            classify_disciplines("Assistant Professor of Physics", "A great job.", ("Mathematics",)),
            ["Physics"],
        )
        self.assertEqual(
            classify_disciplines(
                "Teaching Faculty", "The Department of Chemistry seeks a lecturer.", ("Mathematics",)
            ),
            ["Chemistry"],
        )


class DescriptionFallbackTests(unittest.TestCase):
    def test_most_mentioned_discipline_wins_when_nothing_else_names_one(self):
        disciplines = classify_disciplines(
            "Teaching Faculty",
            "We seek someone to teach chemistry courses and supervise chemistry labs. "
            "Some collaboration with physics is possible.",
        )
        self.assertEqual(disciplines, ["Chemistry"])

    def test_equally_mentioned_disciplines_are_both_kept(self):
        disciplines = classify_disciplines(
            "Teaching Faculty",
            "Teach chemistry and biology. Chemistry labs and biology labs are part of the role.",
        )
        self.assertEqual(disciplines, ["Bioscience", "Chemistry"])

    def test_a_single_passing_mention_is_not_enough(self):
        self.assertEqual(
            classify_disciplines("Teaching Professor", "We value work in climate science."), []
        )

    def test_no_evidence_gives_no_discipline(self):
        self.assertEqual(classify_disciplines("Teaching Professor", "Great benefits."), [])


class DberTests(unittest.TestCase):
    def test_dber_title_is_cross_listed_from_the_description(self):
        disciplines = classify_disciplines(
            "Three DBER Graduate Assistantships, Auburn AL",
            "Fellowships in physics, engineering and mathematics education research.",
        )
        self.assertEqual(
            set(disciplines), {"Engineering", "Mathematics", "Physics", "Science Education"}
        )


class SubfieldTests(unittest.TestCase):
    def check(self, title, expected):
        self.assertEqual(classify_disciplines(title, ""), expected, title)

    def test_earth_subfields_are_earth_science(self):
        for title in (
            "Assistant Professor of Geophysics", "Postdoc in Hydrology", "Lecturer in Atmospheric Science",
            "Assistant Professor of Paleontology", "Instructor of Oceanography", "Seismology Postdoctoral Fellow",
            "Assistant Professor of Planetary Science", "Lecturer in Soil Science", "Geology Instructor",
        ):
            self.assertIn("Earth Science", classify_disciplines(title, ""), title)

    def test_chemistry_subfields_are_chemistry(self):
        for title in (
            "Assistant Professor of Biochemistry", "Lecturer in Organic Chemistry", "Postdoc in Chemical Biology",
            "Instructor, Analytical Chemistry", "Assistant Professor of Geochemistry",
        ):
            self.assertIn("Chemistry", classify_disciplines(title, ""), title)

    def test_biology_subfields_are_bioscience(self):
        for title in (
            "Assistant Professor of Animal Science", "Lecturer in Entomology", "Postdoc in Genetics",
            "Assistant Professor of Zoology", "Instructor of Botany", "Assistant Professor of Neuroscience",
            "Postdoc in Plant Sciences", "Assistant Professor of Genomics", "Lecturer in Immunology",
        ):
            self.assertIn("Bioscience", classify_disciplines(title, ""), title)

    def test_biochemistry_is_listed_under_chemistry_and_bioscience(self):
        self.check("Assistant Professor of Biochemistry", ["Bioscience", "Chemistry"])

    def test_physics_includes_astronomy_and_space_science(self):
        for title in (
            "Assistant Professor of Astronomy", "Lecturer in Astrophysics", "Postdoc in Space Science",
            "Instructor of Planetary Sciences", "Assistant Professor of Cosmology", "Heliophysics Postdoc",
        ):
            self.assertIn("Physics", classify_disciplines(title, ""), title)

    def test_biomedical_engineering_is_still_not_bioscience(self):
        self.check("Assistant Professor of Biomedical Engineering", ["Engineering"])


class HealthEducationTests(unittest.TestCase):
    def test_medical_nursing_pharmacy_and_related_fields(self):
        for title in (
            "Assistant Professor of Nursing", "Clinical Assistant Professor, College of Pharmacy",
            "Lecturer in Public Health", "Medical Education Postdoc", "Postdoc in Kinesiology",
            "Assistant Professor of Physical Therapy", "Instructor, Dental Hygiene", "Lecturer in Nutrition",
            "Assistant Professor of Epidemiology", "Physician Assistant Program Faculty", "Assistant Professor of Veterinary Medicine",
            "Allied Health Instructor", "Postdoctoral Fellow, Health Professions Education",
        ):
            self.assertIn("Health Education", classify_disciplines(title, ""), title)

    def test_benefits_boilerplate_does_not_make_a_job_health_education(self):
        text = "We offer medical, dental and vision coverage. Medical leave and a 401k are included."
        self.assertEqual(classify_disciplines("Research Associate", text), [])

    def test_biomedical_engineering_is_not_health_education(self):
        self.assertEqual(classify_disciplines("Assistant Professor of Biomedical Engineering", ""), ["Engineering"])

    def test_a_medical_school_unit_in_the_description_is_health_education(self):
        found = classify_disciplines("Assistant Professor", "Department of Nursing, College of Health Sciences")
        self.assertEqual(found, ["Health Education"])


if __name__ == "__main__":
    unittest.main()
