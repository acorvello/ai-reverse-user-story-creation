import csv
import io
import json
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from unittest.mock import patch

import app as app_module
from app import AppSettings, ApplicationHandler, load_settings, serialize_settings
from scanner import ScanConfig, read_prefix


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        source = self.root / "src" / "app.py"
        source.parent.mkdir()
        source.write_text("print('local')\n", encoding="utf-8")
        self.settings_path = self.root / "conf" / "settings.json"
        default_settings = AppSettings(ScanConfig(), "http://localhost:11434", "")
        settings_patcher = patch.multiple(
            app_module,
            PROJECT_DIR=self.root,
            SETTINGS_PATH=self.settings_path,
            DATASETS_DIR=self.root / "datasets",
            app_settings=default_settings,
        )
        settings_patcher.start()
        self.addCleanup(settings_patcher.stop)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ApplicationHandler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self._stop_server)

    def _stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _post_scan(self, payload):
        return self._request_json("/api/scan", payload)

    def _request_json(self, path, payload, method="POST"):
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method=method,
        )
        return urlopen(request)

    def test_homepage_serves_web_interface(self):
        with urlopen(self.base_url) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("text/html", response.headers["Content-Type"])
            page = response.read()
            self.assertIn(b"AI Reverse User Story Creation", page)
            self.assertIn(b'id="ollama-test"', page)
            self.assertIn(b'id="ollama-status"', page)

    def test_source_prefix_is_bounded_and_stays_inside_repository(self):
        self.assertEqual(read_prefix(self.root, "src/app.py", 5), "print")
        with self.assertRaises(ValueError):
            read_prefix(self.root, "../outside.py", 5)

    def test_scan_returns_compatible_source_files(self):
        with self._post_scan({"root": str(self.root)}) as response:
            result = json.loads(response.read())

        self.assertEqual(result["file_count"], 1)
        self.assertEqual(result["files"][0]["path"], "src/app.py")
        self.assertEqual(result["extensions"], {".py": 1})

    def test_scan_reports_invalid_repository_path(self):
        with self.assertRaises(HTTPError) as error:
            self._post_scan({"root": str(self.root / "missing")})

        self.assertEqual(error.exception.code, 400)
        body = json.loads(error.exception.read())
        self.assertIn("Não foi possível analisar", body["error"])

    def test_scan_requires_a_repository_path(self):
        with self.assertRaises(HTTPError) as error:
            self._post_scan({})

        self.assertEqual(error.exception.code, 400)
        self.assertIn("Informe o caminho", json.loads(error.exception.read())["error"])

    def test_missing_settings_file_is_created_with_scanner_defaults(self):
        settings = load_settings(self.settings_path)

        self.assertTrue(self.settings_path.is_file())
        self.assertEqual(settings, AppSettings(ScanConfig(), "http://localhost:11434", ""))
        self.assertEqual(json.loads(self.settings_path.read_text(encoding="utf-8")), serialize_settings(settings))

    def test_legacy_settings_are_migrated_with_ollama_defaults(self):
        settings = AppSettings(ScanConfig(), "http://localhost:11434", "")
        legacy = serialize_settings(settings)
        legacy.pop("ollama")
        self.settings_path.parent.mkdir(parents=True)
        self.settings_path.write_text(json.dumps(legacy), encoding="utf-8")

        loaded = load_settings(self.settings_path)

        self.assertEqual(loaded, settings)
        self.assertIn("ollama", json.loads(self.settings_path.read_text(encoding="utf-8")))

    def test_settings_are_saved_as_json_and_used_by_scanner(self):
        javascript = self.root / "src" / "client.js"
        javascript.write_text("console.log('local');\n", encoding="utf-8")
        payload = {
            "scan": {
                "max_file_bytes": 100_000,
                "include_extensions": [".js"],
                "ignore_dirs": ["node_modules"],
                "sensitive_patterns": [".env", "*.pem"],
            },
            "ollama": {"base_url": "http://127.0.0.1:11434", "model": "qwen2.5:7b"},
        }

        with self._request_json("/api/settings", payload) as response:
            saved = json.loads(response.read())

        self.assertEqual(saved, payload)
        self.assertEqual(json.loads(self.settings_path.read_text(encoding="utf-8")), payload)

        with self._post_scan({"root": str(self.root)}) as response:
            result = json.loads(response.read())
        self.assertEqual([item["path"] for item in result["files"]], ["src/client.js"])

    def test_invalid_settings_are_rejected(self):
        payload = {
            "scan": {
                "max_file_bytes": 0,
                "include_extensions": [".py"],
                "ignore_dirs": [],
                "sensitive_patterns": [],
            }
        }

        with self.assertRaises(HTTPError) as error:
            self._request_json("/api/settings", payload)

        self.assertEqual(error.exception.code, 400)
        self.assertFalse(self.settings_path.exists())

    def test_ollama_models_endpoint_lists_generation_models(self):
        response_body = {
            "models": [
                {"name": "qwen:latest", "capabilities": ["completion", "tools"]},
                {"name": "nomic-embed-text:latest", "capabilities": ["embedding"]},
                {"name": "legacy-model"},
            ]
        }

        with patch("app.urlopen", return_value=io.BytesIO(json.dumps(response_body).encode("utf-8"))):
            with self._request_json(
                "/api/ollama/models",
                {"base_url": "http://localhost:11434"},
            ) as response:
                result = json.loads(response.read())

        self.assertEqual(result, {"models": ["qwen:latest", "legacy-model"]})

    def test_ollama_models_endpoint_reports_unavailable_service(self):
        with patch("app.urlopen", side_effect=URLError("connection refused")):
            with self.assertRaises(HTTPError) as error:
                self._request_json("/api/ollama/models", {"base_url": "http://localhost:11434"})

        self.assertEqual(error.exception.code, 503)
        self.assertIn("Ollama não está acessível", json.loads(error.exception.read())["error"])

    def test_ollama_models_endpoint_rejects_non_local_url(self):
        with patch("app.urlopen") as request:
            with self.assertRaises(HTTPError) as error:
                self._request_json("/api/ollama/models", {"base_url": "https://example.com"})

        self.assertEqual(error.exception.code, 400)
        self.assertIn("endereço local", json.loads(error.exception.read())["error"])
        request.assert_not_called()

    def test_generate_writes_one_notebook_format_row_per_feature(self):
        response_body = json.dumps(
            {
                "nome_da_feature": "Login",
                "action": "Como usuário, quero entrar para acessar minha conta.",
            }
        )
        ollama_responses = [
            io.BytesIO(json.dumps({"models": [{"name": "local-model"}]}).encode("utf-8")),
            io.BytesIO(json.dumps({"response": f"[{response_body}]"}).encode("utf-8")),
        ]

        with patch("app.urlopen", side_effect=ollama_responses):
            with self._request_json("/api/generate", {"root": str(self.root)}) as response:
                result = json.loads(response.read())

        output_path = self.root / result["output_path"]
        with output_path.open(encoding="utf-8", newline="") as output:
            reader = csv.DictReader(output)
            rows = list(reader)

        self.assertEqual(reader.fieldnames, ["id", "modulo", "nome_da_feature", "action", "registro_padrao"])
        self.assertEqual(result["record_count"], 1)
        self.assertEqual(result["model"], "local-model")
        self.assertRegex(
            result["file_name"],
            rf"^{re.escape(self.root.name)}_\d{{8}}_\d{{6}}(?:_\d+)?\.csv$",
        )
        self.assertTrue(result["output_path"].startswith("datasets/"))
        self.assertEqual(rows[0]["id"], "1")
        self.assertEqual(rows[0]["modulo"], "src")
        self.assertEqual(rows[0]["nome_da_feature"], "Login")
        self.assertEqual(
            rows[0]["registro_padrao"],
            'nome da feature: Login Action:"Como usuário, quero entrar para acessar minha conta."',
        )

    def test_extract_module_features_accepts_single_object_with_schema(self):
        response = {
            "response": json.dumps(
                {
                    "nome_da_feature": "Adicionar produto",
                    "action": "Como cliente, quero adicionar produto ao carrinho.",
                }
            )
        }

        with patch("app.request_ollama_json", return_value=response) as request:
            features = app_module.extract_module_features(
                "http://localhost:11434",
                "local-model",
                "carrinho",
                "def add_item(): pass",
            )

        self.assertEqual(
            features,
            [
                {
                    "nome_da_feature": "Adicionar produto",
                    "action": "Como cliente, quero adicionar produto ao carrinho.",
                }
            ],
        )
        self.assertEqual(request.call_args.args[2]["format"], app_module.FEATURES_JSON_SCHEMA)

    def test_generate_reports_when_ollama_is_unavailable(self):
        with patch("app.urlopen", side_effect=URLError("connection refused")):
            with self.assertRaises(HTTPError) as error:
                self._request_json("/api/generate", {"root": str(self.root)})

        self.assertEqual(error.exception.code, 503)
        self.assertIn("Ollama não está acessível", json.loads(error.exception.read())["error"])


if __name__ == "__main__":
    unittest.main()
