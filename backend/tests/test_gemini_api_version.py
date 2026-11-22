"""Prevent regression to the incompatible default Gemini Developer API v1."""
import ast
import unittest
from pathlib import Path


class GeminiClientConfigurationTests(unittest.TestCase):
    def test_genai_client_explicitly_uses_v1beta(self):
        path = Path(__file__).resolve().parents[1] / "agents.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        clients = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "client" for target in node.targets)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "Client"
        ]
        self.assertEqual(len(clients), 1, "Expected one global Gemini client")
        options = next((kw.value for kw in clients[0].keywords if kw.arg == "http_options"), None)
        self.assertIsInstance(options, ast.Call, "Gemini Client must set http_options")
        version = next((kw.value for kw in options.keywords if kw.arg == "api_version"), None)
        self.assertIsInstance(version, ast.Constant)
        self.assertEqual(version.value, "v1beta")


if __name__ == "__main__":
    unittest.main()
