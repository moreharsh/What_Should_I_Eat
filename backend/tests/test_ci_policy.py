"""Guard essential CI policy from YAML regressions without live integrations.

These checks run inside the existing mocked backend test job. We deliberately
preserve GitHub-required check names and the separate dietary regression job.
"""
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
REQUIRED_JOBS = {
    "quality.yml": {
        "frontend": "Frontend lint, types, build",
        "backend": "Backend syntax, lint, tests",
        "spelling": "Spelling (CSpell)",
        "hygiene": "Git whitespace and conflict markers",
    },
    "dietary-cache-tests.yml": {"dietary-cache-tests": "dietary-cache-tests"},
    "dependency-security.yml": {
        "npm-audit": "Frontend dependency vulnerability scan",
        "python-audit": "Backend dependency vulnerability scan",
    },
}


def read_yaml(path):
    # BaseLoader preserves the literal GitHub Actions 'on' key: standard YAML
    # 1.1 loaders mistakenly convert it into the boolean True.
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


class WorkflowPolicyTests(unittest.TestCase):
    def test_all_workflows_and_repository_policy_yaml_parse(self):
        paths = sorted(WORKFLOWS.glob("*.yml"))
        paths += sorted((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))
        paths.append(ROOT / ".github" / "dependabot.yml")
        self.assertGreaterEqual(len(paths), 7)
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                doc = read_yaml(path)
                self.assertIsInstance(doc, dict)
                self.assertTrue(doc)

    def test_all_pr_jobs_keep_required_status_names_and_read_only_permissions(self):
        for workflow_file, jobs in REQUIRED_JOBS.items():
            with self.subTest(workflow=workflow_file):
                doc = read_yaml(WORKFLOWS / workflow_file)
                self.assertIn("pull_request", doc["on"])
                self.assertEqual(doc.get("permissions"), {"contents": "read"})
                self.assertNotIn("pull_request_target", doc["on"])
                for key, expected_name in jobs.items():
                    self.assertIn(key, doc["jobs"])
                    job = doc["jobs"][key]
                    self.assertEqual(job.get("name", key), expected_name)
                    self.assertTrue(int(job["timeout-minutes"]) > 0)
                    for step in job["steps"]:
                        if step.get("uses", "").startswith("actions/checkout@"):
                            self.assertEqual(
                                step.get("with", {}).get("persist-credentials"),
                                "false",
                            )

    def test_required_jobs_are_not_skipped_by_path_filters(self):
        for workflow_file in REQUIRED_JOBS:
            doc = read_yaml(WORKFLOWS / workflow_file)
            trigger = doc["on"]["pull_request"]
            # All required jobs must run on every PR (including docs-only).
            self.assertNotIsInstance(trigger, dict)
            for job_name in REQUIRED_JOBS[workflow_file]:
                self.assertNotIn("if", doc["jobs"][job_name])

    def test_spelling_covers_documentation_and_backend_sources(self):
        doc = read_yaml(WORKFLOWS / "quality.yml")
        steps = doc["jobs"]["spelling"]["steps"]
        spell_command = next(step["run"] for step in steps if "cspell@" in step.get("run", ""))
        for path in (
            "ReadMe.md", "CONTRIBUTING.md", "SECURITY.md",
            ".github/*.md", "frontend/README.md", "backend/**/*.md",
            "frontend/src/**/*.{js,jsx,css}", "backend/**/*.py",
        ):
            self.assertIn(path, spell_command)

    def test_dependabot_tracks_all_three_ecosystems_with_bounded_prs(self):
        doc = read_yaml(ROOT / ".github" / "dependabot.yml")
        self.assertEqual(doc["version"], "2")
        updates = doc["updates"]
        self.assertEqual(
            {part["package-ecosystem"] for part in updates},
            {"npm", "pip", "github-actions"},
        )
        for part in updates:
            self.assertLessEqual(int(part["open-pull-requests-limit"]), 5)
            self.assertEqual(part["schedule"]["interval"], "weekly")

    def test_main_only_jobs_do_not_expose_deployment_secrets_to_prs(self):
        for workflow_name in ("deployment-smoke.yml", "redis-heartbeat.yml"):
            doc = read_yaml(WORKFLOWS / workflow_name)
            self.assertNotIn("pull_request", doc["on"])
            self.assertNotIn("pull_request_target", doc["on"])
            self.assertEqual(doc["permissions"], {"contents": "read"})


if __name__ == "__main__":
    unittest.main()
