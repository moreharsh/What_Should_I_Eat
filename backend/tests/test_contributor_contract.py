"""Keep developer setup documentation aligned with the live API and secret policy."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


class ContributorContractTests(unittest.TestCase):
    def test_documented_public_routes_match_live_fastapi_app(self):
        source = (BACKEND / "main.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        routes = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for deco in node.decorator_list:
                    if (isinstance(deco, ast.Call)
                            and isinstance(deco.func, ast.Attribute)
                            and isinstance(deco.func.value, ast.Name)
                            and deco.func.value.id == "app"
                            and deco.args
                            and isinstance(deco.args[0], ast.Constant)):
                        routes.add((deco.func.attr.upper(), deco.args[0].value))

        expected = {
            ("GET", "/api/health"), ("POST", "/api/session"),
            ("GET", "/api/session"), ("DELETE", "/api/session"),
            ("POST", "/api/menu"), ("POST", "/api/recipe"),
            ("POST", "/api/menu-dashboard"), ("POST", "/api/recipe-action"),
        }
        self.assertTrue(expected.issubset(routes))
        readme = (ROOT / "ReadMe.md").read_text(encoding="utf-8")
        for method, route in expected:
            with self.subTest(method=method, route=route):
                self.assertIn(f"{method} {route}", readme)

    def test_environment_templates_cover_read_environment_variables(self):
        backend = (BACKEND / ".env.example").read_text(encoding="utf-8")
        frontend = (FRONTEND / ".env.example").read_text(encoding="utf-8")
        expected_backend = {
            "GEMINI_API_KEY", "REDIS_URL", "YOUTUBE_API_KEY",
            "SPOONACULAR_API_KEY", "DATABRICKS_SERVER_HOSTNAME",
            "DATABRICKS_HTTP_PATH", "DATABRICKS_PERSONAL_ACCESS_TOKEN",
            "OLLAMA_BASE_URL", "OLLAMA_MODEL", "OLLAMA_TIMEOUT_SECONDS",
            "ADMIN_PASSWORD",
        }
        for name in expected_backend:
            with self.subTest(name=name):
                self.assertRegex(backend, rf"(?m)^{name}=")
        self.assertRegex(frontend, r"(?m)^VITE_API_URL=")
        # Do not accidentally template a secret into browser-exposed variables.
        for name in expected_backend:
            self.assertNotIn(f"VITE_{name}=", frontend)

    def test_example_files_are_sanitized_and_real_env_is_gitignored(self):
        backend = (BACKEND / ".env.example").read_text(encoding="utf-8")
        for line in backend.splitlines():
            if not line or line.lstrip().startswith("#"):
                continue
            key, sep, value = line.partition("=")
            self.assertEqual(sep, "=", line)
            self.assertTrue(re.fullmatch(r"[A-Z][A-Z0-9_]*", key))
            self.assertTrue(not value or key == "OLLAMA_TIMEOUT_SECONDS")
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("backend/.env", gitignore)
        self.assertIn("frontend/.env.local", gitignore)
        self.assertIn("backend/.venv/", gitignore)


if __name__ == "__main__":
    unittest.main()
