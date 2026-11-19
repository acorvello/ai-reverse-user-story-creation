import tempfile
import unittest
from pathlib import Path

from ai_reverse_user_story.models import BusinessRule, Evidence, Feature, UserStory
from ai_reverse_user_story.scanner import ScanConfig, line_count, read_lines, scan_repository
from ai_reverse_user_story.verify import verify_evidence


def write(root: Path, rel: str, content: str = "x = 1\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def feature_with(file: str, start: int, end: int) -> Feature:
    return Feature(
        name="Login",
        module="Auth",
        user_story=UserStory(actor="a user", goal="to sign in", benefit="I can use my account"),
        rules=[BusinessRule(statement="Invalid credentials are rejected.", evidence=[Evidence(file=file, start_line=start, end_line=end)])],
    )


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_lists_source_files_in_stable_order(self):
        write(self.root, "routes/login.ts")
        write(self.root, "routes/basket.ts")
        write(self.root, "README.md")
        paths = [f.path for f in scan_repository(self.root)]
        self.assertEqual(paths, ["routes/basket.ts", "routes/login.ts"])

    def test_skips_dependency_and_build_folders(self):
        write(self.root, "src/app.ts")
        write(self.root, "node_modules/lib/index.js")
        write(self.root, "dist/app.js")
        write(self.root, ".git/hooks/pre-commit.js")
        self.assertEqual([f.path for f in scan_repository(self.root)], ["src/app.ts"])

    def test_skips_sensitive_files(self):
        write(self.root, "src/app.ts")
        write(self.root, ".env", "TOKEN=abc\n")
        write(self.root, "keys/server.key.js")  # extension is allowed, name is not special
        write(self.root, "keys/server.pem")
        paths = [f.path for f in scan_repository(self.root)]
        self.assertNotIn(".env", paths)
        self.assertNotIn("keys/server.pem", paths)
        self.assertIn("src/app.ts", paths)

    def test_skips_large_files(self):
        write(self.root, "src/small.ts", "a\n")
        write(self.root, "src/big.ts", "a" * 500)
        paths = [f.path for f in scan_repository(self.root, ScanConfig(max_file_bytes=100))]
        self.assertEqual(paths, ["src/small.ts"])

    def test_missing_directory_raises(self):
        with self.assertRaises(NotADirectoryError):
            scan_repository(self.root / "does-not-exist")

    def test_read_lines_returns_numbered_range(self):
        write(self.root, "src/a.ts", "one\ntwo\nthree\nfour\n")
        self.assertEqual(read_lines(self.root, "src/a.ts", 2, 3), [(2, "two"), (3, "three")])

    def test_read_lines_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            read_lines(self.root, "../outside.ts")

    def test_line_count(self):
        write(self.root, "src/a.ts", "one\ntwo\nthree\n")
        self.assertEqual(line_count(self.root, "src/a.ts"), 3)


class VerifyEvidenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        write(self.root, "routes/login.ts", "\n".join(f"line {i}" for i in range(1, 31)) + "\n")

    def test_valid_evidence_has_no_problems(self):
        self.assertEqual(verify_evidence(self.root, feature_with("routes/login.ts", 5, 20)), [])

    def test_missing_file_is_reported(self):
        problems = verify_evidence(self.root, feature_with("routes/missing.ts", 1, 5))
        self.assertEqual(problems, ["Evidence file not found: routes/missing.ts"])

    def test_out_of_range_lines_are_reported(self):
        problems = verify_evidence(self.root, feature_with("routes/login.ts", 10, 80))
        self.assertEqual(len(problems), 1)
        self.assertIn("exceeds the 30 lines", problems[0])

    def test_path_outside_repository_is_reported(self):
        problems = verify_evidence(self.root, feature_with("../secret.ts", 1, 2))
        self.assertEqual(problems, ["Evidence path is outside the repository: ../secret.ts"])


if __name__ == "__main__":
    unittest.main()
