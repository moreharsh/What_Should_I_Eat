"""Minimal import-free smoke test for checked-in backend modules."""
import ast
import unittest
from pathlib import Path


class BackendSourceTests(unittest.TestCase):
    def test_all_backend_python_sources_parse(self):
        root = Path(__file__).resolve().parents[1]
        sources = list(root.rglob("*.py"))
        self.assertTrue(sources, "No Python sources found")
        for path in sources:
            with self.subTest(path=path.relative_to(root)):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


if __name__ == "__main__":
    unittest.main()
