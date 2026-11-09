import json
import tempfile
import unittest
from pathlib import Path

from stemed_jobs import stemedplus_disciplines as shared

LABELS = [
    "Agriculture", "Bioscience", "Chemistry", "Earth Science", "Engineering",
    "Health Education", "Learning Science", "Mathematics", "Physics", "Science Education",
]


class SharedDisciplineTests(unittest.TestCase):
    def test_stored_copy_is_valid_and_in_order(self):
        self.assertEqual([label for label, _ in shared.rules()], LABELS)

    def test_acronyms_match_only_in_capitals(self):
        physics = dict(shared.rules())["Physics"]
        self.assertTrue(physics.search("a PER postdoc"))
        self.assertFalse(physics.search("$60,000 per year"))

    def test_refresh_keeps_the_copy_when_download_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.json"
            path.write_text(shared.VENDORED.read_text())
            message = shared.refresh(url=Path(tmp, "missing.json").as_uri(), path=path)
            self.assertIn("kept", message)
            self.assertEqual(path.read_text(), shared.VENDORED.read_text())

    def test_refresh_rejects_an_invalid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"disciplines": [{"id": "x", "label": "X", "definition": "d", "match": {"terms": "("}}]}))
            path = Path(tmp) / "d.json"
            path.write_text(shared.VENDORED.read_text())
            self.assertIn("kept", shared.refresh(url=bad.as_uri(), path=path))
            self.assertEqual(path.read_text(), shared.VENDORED.read_text())

    def test_refresh_updates_from_a_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = json.loads(shared.VENDORED.read_text())
            doc["version"] = 99
            good = Path(tmp) / "good.json"
            good.write_text(json.dumps(doc))
            path = Path(tmp) / "d.json"
            path.write_text(shared.VENDORED.read_text())
            self.assertIn("updated", shared.refresh(url=good.as_uri(), path=path))
            self.assertEqual(json.loads(path.read_text())["version"], 99)


if __name__ == "__main__":
    unittest.main()
