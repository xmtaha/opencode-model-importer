"""End-to-end checks for discovery, credentials and config editing.

Run with:  python -m unittest discover -s tests -v
"""

import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from config.opencode_config import ConfigFile
from config import jsonc
from config.schema import model_entry
from config.writer import delete_provider, edit_model, sync_provider
from services import credentials, discovery, openrouter
from utils import i18n
from utils.errors import DiscoveryError
from utils.i18n import tr


class Handler(BaseHTTPRequestHandler):
    seen_auth: list = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        Handler.seen_auth.append(self.headers.get("Authorization"))
        key = self.headers.get("Authorization", "")
        if self.path == "/open/v1/models":
            self._json(200, {"data": [{"id": "a"}, {"id": "b", "name": "Bee"}]})
        elif self.path == "/secret/v1/models":
            self._json(200, {"data": [{"id": "s"}]}) if key == "Bearer real-key" else self._json(401, {})
        elif self.path == "/forbidden/v1/models":
            self._json(403, {})
        elif self.path == "/broken/v1/models":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<html>not json</html>")
        else:
            self._json(404, {"error": "not found"})

    def _json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class DiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_no_key(self):
        Handler.seen_auth.clear()
        models = discovery.fetch_models(self.base + "/open", None)
        self.assertEqual([m.id for m in models], ["a", "b"])
        self.assertEqual(Handler.seen_auth[-1], None)

    def test_direct_key(self):
        with mock.patch.dict(os.environ, {"MY_PROVIDER_KEY": "real-key"}):
            key = credentials.resolve("real-key")
            self.assertEqual(key.secret, "real-key")
            self.assertEqual(key.env_name, "")
            discovery.fetch_models(self.base + "/secret", key.secret)
            self.assertEqual(Handler.seen_auth[-1], "Bearer real-key")

    def test_env_var_is_resolved_not_sent(self):
        with mock.patch.dict(os.environ, {"MY_PROVIDER_KEY": "real-key"}):
            key = credentials.resolve("MY_PROVIDER_KEY")
            self.assertEqual(key.secret, "real-key")
            self.assertEqual(key.env_name, "MY_PROVIDER_KEY")
            discovery.fetch_models(self.base + "/secret", key.secret)
            self.assertEqual(Handler.seen_auth[-1], "Bearer real-key")

    def test_undefined_env_var(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(DiscoveryError, "MY_PROVIDER_KEY"):
                credentials.resolve("MY_PROVIDER_KEY")

    def test_401_and_403(self):
        with self.assertRaisesRegex(DiscoveryError, "401"):
            discovery.fetch_models(self.base + "/secret", "wrong")
        with self.assertRaisesRegex(DiscoveryError, "403"):
            discovery.fetch_models(self.base + "/forbidden", None)

    def test_models_not_supported(self):
        with self.assertRaisesRegex(DiscoveryError, "desteklemiyor"):
            discovery.fetch_models(self.base + "/nothing-here", None)

    def test_bad_json(self):
        with self.assertRaises(DiscoveryError):
            discovery.fetch_models(self.base + "/broken", None)

    def test_url_normalization(self):
        self.assertEqual(discovery._models_endpoint("https://x.ai/v1/"), "https://x.ai/v1/models")
        self.assertEqual(discovery._models_endpoint("https://x.ai/v1/models"), "https://x.ai/v1/models")
        self.assertEqual(discovery._models_endpoint("https://x.ai"), "https://x.ai/v1/models")
        with self.assertRaises(DiscoveryError):
            discovery.normalized_base_url("ftp://x")


class OpenRouterTests(unittest.TestCase):
    payload = {
        "data": {
            "id": "x-ai/grok",
            "endpoints": [
                {
                    "provider_name": "Particle",
                    "tag": "particle-ai/us/flex",
                    "context_length": 131072,
                    "max_completion_tokens": 16384,
                    "quantization": "unknown",
                    "pricing": {"prompt": "0.0000005", "completion": "0.000001"},
                },
                {"provider_name": "Baseten", "tag": "baseten", "pricing": {"prompt": "-1"}},
                {"tag": "baseten"},  # a duplicate tag is kept once
                {"provider_name": "No tag"},
            ],
        }
    }

    def test_endpoint_url_strips_the_variant(self):
        self.assertEqual(
            openrouter.endpoint_url("x-ai/grok:floor"),
            "https://openrouter.ai/api/v1/models/x-ai/grok/endpoints",
        )

    def test_endpoint_url_needs_an_author_slash_model_id(self):
        with self.assertRaisesRegex(DiscoveryError, "yazar/model"):
            openrouter.endpoint_url("glm-5.3-flash")

    def test_parse_endpoints(self):
        endpoints = openrouter.parse_endpoints(self.payload)
        self.assertEqual([endpoint.tag for endpoint in endpoints], ["particle-ai/us/flex", "baseten"])
        self.assertEqual(endpoints[0].name, "Particle")
        self.assertIn("Giriş $0.50/M", endpoints[0].detail)
        self.assertIn("131,072 bağlam", endpoints[0].detail)
        self.assertIn("16,384 çıkış", endpoints[0].detail)
        self.assertNotIn("Giriş", endpoints[1].detail)  # negative price means "variable", not shown

    def test_parse_endpoints_rejects_a_missing_list(self):
        with self.assertRaisesRegex(DiscoveryError, "sağlayıcı listesi"):
            openrouter.parse_endpoints({"data": {}})


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "opencode.json"

    def tearDown(self):
        self.dir.cleanup()

    def _config(self, text):
        self.path.write_text(text, encoding="utf-8")
        return ConfigFile.load(self.path)

    def _sync(self, config, provider_id="ex", models=(), remove=(), name="Example",
              base_url="https://api.example.com/v1", api_kind="openai-compatible", env_name="EXAMPLE_API_KEY"):
        return sync_provider(config, provider_id, name, base_url, api_kind, env_name, list(models), list(remove))

    def test_add_to_empty(self):
        config = self._config('{"$schema": "https://opencode.ai/config.json"}\n')
        result = self._sync(config, models=[("m1", "M One"), ("m2", "m2")])
        self.assertEqual(result.added, ["m1", "m2"])
        data = json.loads(result.text)
        self.assertEqual(data["$schema"], "https://opencode.ai/config.json")
        self.assertEqual(
            data["providers"]["ex"],
            {
                "name": "Example",
                "package": "@opencode/ai/providers/openai-compatible",
                "env": ["EXAMPLE_API_KEY"],
                "settings": {"baseURL": "https://api.example.com/v1"},
                "models": {"m1": {"name": "M One"}, "m2": {}},
            },
        )

    def test_existing_content_and_comments_preserved(self):
        original = (
            "{\n"
            "  // keep me\n"
            '  "$schema": "https://opencode.ai/config.json",\n'
            '  "providers": {\n'
            '    "other": {\n'
            '      "name": "Other", // trailing comment\n'
            '      "models": {"x": {"name": "X"}},\n'
            "    },\n"
            "  },\n"
            '  "model": "other/x",\n'
            "}\n"
        )
        config = self._config(original)
        text = self._sync(config, models=[("m1", "M1")]).text
        self.assertIn("// keep me", text)
        self.assertIn("// trailing comment", text)
        data = json.loads(jsonc.strip_jsonc(text))
        self.assertEqual(data["providers"]["other"], {"name": "Other", "models": {"x": {"name": "X"}}})
        self.assertEqual(data["model"], "other/x")
        self.assertEqual(data["providers"]["ex"]["models"], {"m1": {"name": "M1"}})

    def test_existing_provider_gets_models_without_overwrite(self):
        config = self._config(
            '{"providers": {"ex": {"name": "Mine", "package": "p", "settings": {"baseURL": "https://old/v1"},'
            ' "models": {"m1": {"name": "Custom", "limit": {"context": 1}}}, "headers": {"A": "B"}}}}'
        )
        result = self._sync(
            config, models=[("m1", "M1"), ("m2", "M2")], name="Mine",
            base_url="https://old/v1", api_kind="", env_name="",
        )
        self.assertEqual(result.added, ["m2"])
        self.assertEqual(result.skipped, ["m1"])
        data = json.loads(result.text)
        self.assertEqual(data["providers"]["ex"]["name"], "Mine")
        self.assertEqual(data["providers"]["ex"]["package"], "p")
        self.assertEqual(data["providers"]["ex"]["settings"]["baseURL"], "https://old/v1")
        self.assertEqual(data["providers"]["ex"]["models"]["m1"], {"name": "Custom", "limit": {"context": 1}})
        self.assertEqual(data["providers"]["ex"]["headers"], {"A": "B"})

    def test_second_add_is_a_no_op(self):
        config = self._config("{}")
        text = self._sync(config, models=[("m1", "M1")]).text
        config.save(text)
        again = ConfigFile.load(self.path)
        result = self._sync(again, models=[("m1", "M1")])
        self.assertEqual((result.added, result.skipped, result.changed), ([], ["m1"], False))
        self.assertEqual(result.text, again.text)

    def test_remove_models_keeps_comments_and_commas_valid(self):
        original = (
            "{\n"
            "  // üstte\n"
            '  "providers": {\n'
            '    "ex": {\n'
            '      "name": "Example",\n'
            '      "models": {\n'
            '        "keep": {}, // kalsın\n'
            '        "drop": {},\n'
            '        "drop2": {},\n'
            "      },\n"
            "    },\n"
            "  },\n"
            "}\n"
        )
        config = self._config(original)
        result = self._sync(config, models=[("keep", "keep")], remove=["drop", "drop2"])
        self.assertTrue(result.changed)
        self.assertEqual(result.removed, ["drop", "drop2"])
        text = result.text
        self.assertIn("// üstte", text)
        self.assertIn("// kalsın", text)  # the kept model's trailing comment survives
        data = json.loads(jsonc.strip_jsonc(text))
        self.assertEqual(data["providers"]["ex"]["models"], {"keep": {}})

    def test_removed_run_leaves_strict_json(self):
        config = self._config(
            '{\n  "providers": {\n    "ex": {\n      "models": {\n'
            '        "a": {},\n        "b": {},\n        "c": {}\n      }\n    }\n  }\n}\n'
        )
        text = self._sync(config, models=[("a", "a")], remove=["b", "c"]).text
        json.loads(text)  # strict JSON: the comma before the removed run is gone
        self.assertEqual(json.loads(text)["providers"]["ex"]["models"], {"a": {}})

    def test_removing_the_last_model_leaves_an_empty_object(self):
        config = self._config('{"providers": {"ex": {"models": {"only": {}}}}}')
        result = self._sync(config, remove=["only"])
        data = json.loads(result.text)
        self.assertEqual(data["providers"]["ex"]["models"], {})
        self.assertEqual(result.removed, ["only"])

    def test_fields_are_updated_in_place(self):
        original = (
            "{\n"
            '  "providers": {\n'
            '    "ex": {\n'
            '      "name": "Eski Ad", // isim\n'
            '      "package": "@opencode/ai/providers/openai-compatible",\n'
            '      "env": ["OLD_KEY"],\n'
            '      "settings": { "baseURL": "https://old/v1" },\n'
            '      "models": {"m1": {}},\n'
            "    },\n"
            "  },\n"
            "}\n"
        )
        config = self._config(original)
        result = self._sync(
            config, models=[("m1", "m1")], name="Yeni Ad", base_url="https://new/v1", env_name="NEW_KEY"
        )
        data = json.loads(jsonc.strip_jsonc(result.text))
        self.assertEqual(data["providers"]["ex"]["name"], "Yeni Ad")
        self.assertEqual(data["providers"]["ex"]["env"], ["NEW_KEY"])
        self.assertEqual(data["providers"]["ex"]["settings"]["baseURL"], "https://new/v1")
        self.assertEqual(data["providers"]["ex"]["models"], {"m1": {}})
        self.assertIn("// isim", result.text)

    def test_base_url_change_keeps_other_settings(self):
        original = (
            '{\n  "providers": {\n    "ex": {\n'
            '      "name": "X",\n'
            '      "settings": {\n'
            '        "baseURL": "https://old/v1",\n'
            '        "apiKey": "env://OLD_KEY"\n'
            "      },\n"
            '      "models": {"m1": {}}\n'
            "    }\n  }\n}\n"
        )
        config = self._config(original)
        details = config.provider_details("ex")
        self.assertTrue(details["settings_key"])
        result = self._sync(config, models=[("m1", "m1")], name="X", base_url="https://new/v1", env_name="")
        data = json.loads(result.text)
        self.assertEqual(data["providers"]["ex"]["settings"], {"baseURL": "https://new/v1", "apiKey": "env://OLD_KEY"})

    def test_empty_env_name_removes_the_env_field(self):
        config = self._config('{"providers": {"ex": {"env": ["OLD_KEY"], "models": {"m1": {}}}}}')
        result = self._sync(config, models=[("m1", "m1")], env_name="")
        self.assertNotIn("env", json.loads(result.text)["providers"]["ex"])

    def test_unknown_package_is_preserved(self):
        config = self._config('{"providers": {"ex": {"package": "custom/pkg", "models": {"m1": {}}}}}')
        result = self._sync(config, models=[("m1", "m1")], api_kind="")
        self.assertEqual(json.loads(result.text)["providers"]["ex"]["package"], "custom/pkg")

    def test_missing_models_object_is_created(self):
        config = self._config('{"providers": {"ex": {"name": "X", "settings": {"baseURL": "https://old/v1"}}}}')
        result = self._sync(config, models=[("m1", "M1")], name="X", base_url="https://old/v1", env_name="")
        data = json.loads(result.text)
        self.assertEqual(data["providers"]["ex"]["models"], {"m1": {"name": "M1"}})
        self.assertEqual(data["providers"]["ex"]["settings"]["baseURL"], "https://old/v1")

    def test_delete_provider_keeps_the_others(self):
        config = self._config(
            '{\n  "providers": {\n'
            '    "a": {"models": {"x": {}}},\n'
            '    "b": {"name": "B", "models": {"y": {}}},\n'
            '    "c": {"models": {"z": {}}}\n'
            "  },\n"
            '  "model": "b/y"\n'
            "}\n"
        )
        text, models = delete_provider(config, "b")
        self.assertEqual(models, ["y"])
        data = json.loads(text)
        self.assertEqual(list(data["providers"]), ["a", "c"])
        self.assertEqual(data["model"], "b/y")
        self.assertNotIn("B", text)

    def test_delete_last_provider_leaves_an_empty_object(self):
        config = self._config('{"providers": {"only": {"models": {"x": {}}}}}')
        text, _ = delete_provider(config, "only")
        self.assertEqual(json.loads(text)["providers"], {})

    def test_delete_unknown_provider_is_rejected(self):
        config = self._config('{"providers": {"a": {}}}')
        with self.assertRaisesRegex(DiscoveryError, "bulunamadı"):
            delete_provider(config, "yok")

    def test_model_variant_rename_keeps_the_value(self):
        config = self._config(
            '{"providers": {"ex": {"models": {"x-ai/grok": {"name": "Grok", "limit": {"context": 1}}}}}}'
        )
        text = edit_model(
            config,
            "ex",
            "x-ai/grok",
            "x-ai/grok:floor",
            {"provider": {"order": ["particle-ai/us/flex"], "allow_fallbacks": False}},
        )
        data = json.loads(text)
        self.assertEqual(
            data["providers"]["ex"]["models"],
            {
                "x-ai/grok:floor": {
                    "name": "Grok",
                    "limit": {"context": 1},
                    "body": {"provider": {"order": ["particle-ai/us/flex"], "allow_fallbacks": False}},
                }
            },
        )

    def test_clearing_model_options_removes_routing_but_keeps_other_body_fields(self):
        config = self._config(
            '{"providers": {"ex": {"models": {"m": {"name": "M", "body": '
            '{"temperature": 0.2, "service_tier": "flex", "max_completion_tokens": 131072, '
            '"provider": {"order": ["a"]}}}}}}}'
        )
        text = edit_model(config, "ex", "m", "m", {})
        self.assertEqual(
            json.loads(text)["providers"]["ex"]["models"],
            {"m": {"name": "M", "body": {"temperature": 0.2}}},
        )

    def test_model_extras_are_written_to_body(self):
        config = self._config(
            '{"providers": {"ex": {"models": {"m": {"name": "M", "body": {"temperature": 0.2}}}}}}'
        )
        options = {
            "provider": {"order": ["particle-ai/us/flex"], "allow_fallbacks": False},
            "service_tier": "flex",
            "max_completion_tokens": 131072,
        }
        text = edit_model(config, "ex", "m", "m", options)
        self.assertEqual(
            json.loads(text)["providers"]["ex"]["models"]["m"]["body"],
            {"temperature": 0.2, **options},
        )

    def test_switching_away_from_a_tier_removes_extras(self):
        config = self._config(
            '{"providers": {"ex": {"models": {"m": {"body": {"service_tier": "flex", '
            '"max_completion_tokens": 131072, "provider": {"order": ["a"]}}}}}}}'
        )
        text = edit_model(config, "ex", "m", "m", {"provider": {"order": ["baseten"]}})
        self.assertEqual(
            json.loads(text)["providers"]["ex"]["models"],
            {"m": {"body": {"provider": {"order": ["baseten"]}}}},
        )

    def test_model_details_include_extras(self):
        config = self._config(
            '{"providers": {"ex": {"models": {"m": {"body": {"service_tier": "flex", '
            '"max_completion_tokens": 131072, "provider": {"order": ["a"]}}}}}}}'
        )
        self.assertEqual(
            config.model_details("ex", "m")["options"],
            {"provider": {"order": ["a"]}, "service_tier": "flex", "max_completion_tokens": 131072},
        )

    def test_clearing_the_last_body_field_removes_body(self):
        config = self._config(
            '{"providers": {"ex": {"models": {"m": {"name": "M", "body": {"provider": {"order": ["a"]}}}}}}}'
        )
        text = edit_model(config, "ex", "m", "m", {})
        self.assertEqual(json.loads(text)["providers"]["ex"]["models"], {"m": {"name": "M"}})

    def test_legacy_options_are_migrated_to_body(self):
        config = self._config(
            '{"providers": {"ex": {"models": {"m": {"options": {"provider": {"order": ["a"]}}}}}}}'
        )
        text = edit_model(config, "ex", "m", "m", {"provider": {"order": ["a"]}})
        self.assertEqual(
            json.loads(text)["providers"]["ex"]["models"],
            {"m": {"body": {"provider": {"order": ["a"]}}}},
        )

    def test_legacy_options_with_other_keys_are_kept(self):
        config = self._config(
            '{"providers": {"ex": {"models": {"m": {"options": '
            '{"provider": {"order": ["a"]}, "reasoning": true}}}}}}'
        )
        text = edit_model(config, "ex", "m", "m", {"provider": {"order": ["b"]}})
        self.assertEqual(
            json.loads(text)["providers"]["ex"]["models"],
            {"m": {"options": {"reasoning": True}, "body": {"provider": {"order": ["b"]}}}},
        )

    def test_edit_model_without_changes_returns_none(self):
        config = self._config(
            '{"providers": {"ex": {"models": {"m": {"body": {"provider": {"order": ["a"]}}}}}}}'
        )
        self.assertIsNone(edit_model(config, "ex", "m", "m", {"provider": {"order": ["a"]}}))

    def test_edit_model_rejects_a_taken_id(self):
        config = self._config('{"providers": {"ex": {"models": {"m": {}, "n": {}}}}}')
        with self.assertRaisesRegex(DiscoveryError, "zaten kayıtlı"):
            edit_model(config, "ex", "m", "n", {})

    def test_details_round_trip(self):
        config = self._config("{}")
        config.save(self._sync(config, models=[("m1", "M1")]).text)
        again = ConfigFile.load(self.path)
        self.assertIsNone(again.provider_details("yok"))
        details = again.provider_details("ex")
        self.assertEqual(details["name"], "Example")
        self.assertEqual(details["api_kind"], "openai-compatible")
        self.assertEqual(details["base_url"], "https://api.example.com/v1")
        self.assertEqual(details["env"], "EXAMPLE_API_KEY")

    def test_invalid_json_rejected(self):
        with self.assertRaises(DiscoveryError):
            self._config('{"providers": }')
        with self.assertRaises(DiscoveryError):
            self._config("[1, 2]")

    def test_save_backs_up(self):
        config = self._config('{"a": 1}\n')
        text = self._sync(config, models=[("m1", "M1")]).text
        backup = config.save(text)
        self.assertEqual(backup.read_text(encoding="utf-8"), '{"a": 1}\n')
        self.assertIn("ex", json.loads(self.path.read_text(encoding="utf-8"))["providers"])

    def test_model_entry(self):
        self.assertEqual(model_entry("m", "m"), "{}")
        self.assertEqual(model_entry("m", ""), "{}")


class I18nTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("tr")

    def test_turkish_is_the_default(self):
        self.assertEqual(i18n.current_language(), "tr")
        self.assertEqual(tr("Sağlayıcıyı sil"), "Sağlayıcıyı sil")

    def test_english_translation(self):
        i18n.set_language("en")
        self.assertEqual(tr("Sağlayıcıyı sil"), "Delete provider")
        self.assertEqual(tr("bilinmeyen metin"), "bilinmeyen metin")


if __name__ == "__main__":
    unittest.main()
