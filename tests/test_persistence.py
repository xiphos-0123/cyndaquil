import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from project.persistence import PersistenceError, read_json, write_json


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sessions.json"

    def test_save_keeps_previous_records_and_unknown_fields(self):
        records = [{"id": "old", "completion_note": "日本語", "custom": {"x": 1}}]
        write_json(self.path, records)
        write_json(self.path, records + [{"id": "new"}])
        self.assertEqual(read_json(self.path.with_name("sessions.json.bak"), []), records)
        self.assertEqual(read_json(self.path, [])[:1], records)

    def test_corrupt_records_are_not_overwritten(self):
        for contents in (b"{bad", b"{}", b"[null]"):
            self.path.write_bytes(contents)
            with self.assertRaises(PersistenceError):
                read_json(self.path, [])
            with self.assertRaises(PersistenceError):
                write_json(self.path, [])
            self.assertEqual(self.path.read_bytes(), contents)

    def test_failed_replace_preserves_original_and_cleans_temporary_files(self):
        write_json(self.path, [{"id": "saved"}])
        original = self.path.read_bytes()
        replace = __import__("os").replace

        def fail_primary(source, destination):
            if Path(destination) == self.path:
                raise OSError("simulated full disk")
            return replace(source, destination)

        with patch("project.persistence.os.replace", side_effect=fail_primary):
            with self.assertRaises(PersistenceError):
                write_json(self.path, [{"id": "new"}])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def test_missing_file_returns_independent_default(self):
        fallback = []
        result = read_json(self.path, fallback)
        result.append({})
        self.assertEqual(fallback, [])


if __name__ == "__main__":
    unittest.main()
