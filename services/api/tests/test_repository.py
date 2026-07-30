from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.repository import Repository, new_ulid


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        test_root = Path('data')
        test_root.mkdir(parents=True, exist_ok=True)
        self.tmp = TemporaryDirectory(dir=test_root)
        self.repository = Repository(Path(self.tmp.name) / "test.db")
        self.repository.migrate()
        self.repository.seed_demo_data()

    def tearDown(self):
        self.tmp.cleanup()

    def test_seed_contains_ten_distinct_objects(self):
        objects = self.repository.list_objects()
        self.assertGreaterEqual(len(objects), 10)
        self.assertEqual(len({item.object_id for item in objects}), len(objects))

    def test_rename_preserves_id_and_aliases(self):
        item = self.repository.list_objects()[0]
        updated = self.repository.rename_object(item.object_id, "娴嬭瘯鐗╁搧", ["娴嬭瘯鍒悕"])
        self.assertEqual(updated.object_id, item.object_id)
        self.assertEqual(updated.aliases, ["娴嬭瘯鍒悕"])

    def test_duplicate_name_is_rejected(self):
        first, second = self.repository.list_objects()[:2]
        with self.assertRaises(ValueError):
            self.repository.rename_object(second.object_id, first.name, None)

    def test_ulid_is_stable_length(self):
        self.assertEqual(len(new_ulid(datetime.now(UTC))), 26)
