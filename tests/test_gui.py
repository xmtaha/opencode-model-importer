"""Drives the real window offscreen: fetch -> select -> save -> re-add (duplicate).

Run with:  python tests/test_gui.py
"""

import json
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock
from http.server import HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from config import jsonc  # noqa: E402
from services import openrouter  # noqa: E402
from tests.test_core import Handler  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.model_dialog import ModelDialog, split_variant  # noqa: E402
from utils import i18n  # noqa: E402

CONFIG = """{
  // Benim ayarlarım
  "$schema": "https://opencode.ai/config.json",
  "model": "openrouter/x/y",
  "providers": {
    "openrouter": {
      "models": {
        "x/y": { "options": { "provider": { "order": ["baseten"] } } },
      },
    },
  },
}
"""


def wait(window, timeout_ms=10000):
    app = QApplication.instance()
    worker = window.worker
    deadline = 0
    while worker is not None and worker.isRunning() and deadline < timeout_ms:
        app.processEvents()
        worker.wait(50)
        deadline += 50
    app.processEvents()


class GuiFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "opencode.jsonc"
        self.path.write_text(CONFIG, encoding="utf-8")
        QApplication.instance() or QApplication([])
        i18n.set_language("tr")
        self.addCleanup(i18n.set_language, "tr")
        self.dialogs = mock.patch("ui.main_window.QMessageBox").start()
        self.addCleanup(mock.patch.stopall)
        self.window = MainWindow()
        self.window._load_config(self.path)
        self.window.base_url.setText(self.base + "/open/")
        self.window.name.setText("Example Provider")
        self.window.provider_id.setText("example")
        self.window.all_button.click()

    def tearDown(self):
        self.window.close()
        self.dir.cleanup()

    def _fetch(self):
        self.window.fetch_models()
        wait(self.window)
        return [self.window.table.item(r, 1).data(Qt.UserRole) for r in range(self.window.table.rowCount())]

    def save_and_return_text(self):
        with_unchecked = self.window._selected()
        self.assertTrue(with_unchecked)
        self.window.save()
        wait(self.window)
        return self.path.read_text(encoding="utf-8")

    def test_fetch_select_save_and_duplicate(self):
        self.assertEqual(self._fetch(), ["a", "b"])
        rows = self.window.table.rowCount()
        self.window.all_button.click()
        self.assertEqual(len(self.window._selected()), rows)

        text = self.save_and_return_text()
        self.assertIn("// Benim ayarlarım", text)
        self.assertIn("baseten", text)
        data = json.loads(jsonc.strip_jsonc(text))
        self.assertEqual(data["model"], "openrouter/x/y")
        self.assertEqual(data["providers"]["openrouter"], {"models": {"x/y": {"options": {"provider": {"order": ["baseten"]}}}}})
        self.assertEqual(
            data["providers"]["example"],
            {
                "name": "Example Provider",
                "package": "@opencode/ai/providers/openai-compatible",
                "settings": {"baseURL": self.base + "/open"},
                "models": {"a": {}, "b": {"name": "Bee"}},
            },
        )
        backups = list(Path(self.dir.name).glob("opencode.jsonc.bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), CONFIG)

        # Same models again: nothing added, file untouched.
        before = (text, self.path.stat().st_mtime_ns)
        self.window.save()
        wait(self.window)
        self.assertEqual(before, (self.path.read_text(encoding="utf-8"), self.path.stat().st_mtime_ns))

    def test_filter_select(self):
        self._fetch()
        self.assertEqual(self.window.count_label.text(), "2 / 2 model")
        self.window.none_button.click()
        self.window.search.setText("bee")
        self.assertEqual(self.window.count_label.text(), "1 / 2 model")
        self.window.all_button.click()
        self.assertEqual([m[0] for m in self.window._selected()], ["b"])

    def _pick(self, provider_id):
        index = self.window.provider_combo.findData(provider_id)
        self.assertGreaterEqual(index, 0, f"{provider_id} listede yok")
        self.window.provider_combo.setCurrentIndex(index)

    def _row(self, model_id):
        for row in range(self.window.table.rowCount()):
            if self.window.table.item(row, 1).data(Qt.UserRole) == model_id:
                return row
        self.fail(f"{model_id} tabloda yok")

    def test_edit_existing_provider_and_remove_models(self):
        self._fetch()
        self.window.all_button.click()
        self.save_and_return_text()  # add provider "example" with a and b

        self._pick("example")
        self.assertEqual(self.window.name.text(), "Example Provider")
        self.assertEqual(self.window.base_url.text(), self.base + "/open")
        self.assertFalse(self.window.provider_id.isEnabled())
        self.assertEqual(self.window.table.rowCount(), 2)
        self.assertEqual(len(self.window._selected()), 2)  # registered models start checked

        # Uncheck "a" -> removed; rename + change URL -> rewritten in place.
        self.window.table.item(self._row("a"), 0).setCheckState(Qt.CheckState.Unchecked)
        self.window.name.setText("Renamed")
        self.window.base_url.setText(self.base + "/open/v1")
        self.window.save()
        wait(self.window)

        text = self.path.read_text(encoding="utf-8")
        self.assertIn("// Benim ayarlarım", text)
        data = json.loads(jsonc.strip_jsonc(text))
        provider = data["providers"]["example"]
        self.assertEqual(provider["name"], "Renamed")
        self.assertEqual(provider["settings"]["baseURL"], self.base + "/open/v1")
        self.assertEqual(provider["models"], {"b": {"name": "Bee"}})
        self.assertEqual(data["providers"]["openrouter"]["models"]["x/y"]["options"], {"provider": {"order": ["baseten"]}})

        # The table now reflects the file: only "b", checked, so saving again is a no-op.
        self.assertEqual([m[0] for m in self.window._selected()], ["b"])
        before = (text, self.path.stat().st_mtime_ns)
        self.window.save()
        wait(self.window)
        self.assertEqual(before, (self.path.read_text(encoding="utf-8"), self.path.stat().st_mtime_ns))

    def test_delete_provider(self):
        self._fetch()
        self.window.all_button.click()
        self.save_and_return_text()
        self._pick("example")
        self.dialogs.question.return_value = self.dialogs.Yes
        self.window.delete_provider()

        data = json.loads(jsonc.strip_jsonc(self.path.read_text(encoding="utf-8")))
        self.assertNotIn("example", data["providers"])
        self.assertIn("openrouter", data["providers"])
        self.assertEqual(data["model"], "openrouter/x/y")
        self.assertIn("// Benim ayarlarım", self.path.read_text(encoding="utf-8"))
        self.assertIsNone(self.window.editing)
        self.assertEqual(self.window.provider_combo.currentData(), "")

    def test_model_settings_dialog_sets_variant_and_order(self):
        self._fetch()
        self.window.all_button.click()
        self.save_and_return_text()
        self._pick("example")
        self.window.table.selectRow(self._row("a"))
        self.assertTrue(self.window.model_button.isEnabled())

        dialog = mock.MagicMock()
        dialog.return_value.exec.return_value = QDialog.Accepted
        dialog.return_value.result_settings.return_value = (
            "a:floor",
            {
                "provider": {"order": ["particle-ai/us/flex"], "allow_fallbacks": False},
                "service_tier": "flex",
                "max_completion_tokens": 131072,
            },
        )
        with mock.patch("ui.main_window.ModelDialog", dialog):
            self.window.edit_model()

        data = json.loads(jsonc.strip_jsonc(self.path.read_text(encoding="utf-8")))
        self.assertEqual(
            data["providers"]["example"]["models"],
            {
                "a:floor": {
                    "body": {
                        "provider": {"order": ["particle-ai/us/flex"], "allow_fallbacks": False},
                        "service_tier": "flex",
                        "max_completion_tokens": 131072,
                    }
                },
                "b": {"name": "Bee"},
            },
        )

    def test_model_dialog_builds_options(self):
        self.assertEqual(split_variant("x-ai/grok:floor"), ("x-ai/grok", ":floor"))
        self.assertEqual(split_variant("absolutereality:free"), ("absolutereality", ":free"))
        self.assertEqual(split_variant("plain/model"), ("plain/model", ""))
        self.assertEqual(split_variant("a/b:c/d"), ("a/b:c/d", ""))

        dialog = ModelDialog("x-ai/grok:floor", {"provider": {"order": ["baseten"]}})
        dialog.order.setText("particle-ai/us/flex, baseten")
        dialog.fallback.setCurrentIndex(2)  # izin verme
        model_id, options = dialog.result_settings()
        self.assertEqual(model_id, "x-ai/grok:floor")
        self.assertEqual(
            options,
            {
                "provider": {"order": ["particle-ai/us/flex", "baseten"], "allow_fallbacks": False},
                "service_tier": "flex",
            },
        )

        dialog.order.setText("")
        dialog.fallback.setCurrentIndex(0)
        dialog.variant.setCurrentText("floor")
        model_id, options = dialog.result_settings()
        self.assertEqual(model_id, "x-ai/grok:floor")
        self.assertEqual(options, {})

    def test_model_dialog_picks_openrouter_providers(self):
        dialog = ModelDialog("x-ai/grok:floor", {})
        dialog.show_providers(
            [
                openrouter.Endpoint("particle-ai/us/flex", "Particle", "Giriş $0.50/M"),
                openrouter.Endpoint("baseten", "Baseten", ""),
            ]
        )
        self.assertTrue(dialog.provider_list.isVisibleTo(dialog))
        self.assertEqual(dialog.provider_list.count(), 2)

        dialog.provider_list.item(1).setCheckState(Qt.Checked)
        _, options = dialog.result_settings()
        self.assertEqual(options, {"provider": {"order": ["baseten"]}})

        dialog.provider_list.item(0).setCheckState(Qt.Checked)
        _, options = dialog.result_settings()
        self.assertEqual(
            options,
            {
                "provider": {"order": ["baseten", "particle-ai/us/flex"]},
                "service_tier": "flex",
            },
        )

        dialog.provider_list.item(1).setCheckState(Qt.Unchecked)
        dialog.order.setText("particle-ai/us/flex, elle/yazilan")
        self.assertEqual(dialog.provider_list.item(0).checkState(), Qt.Checked)
        self.assertEqual(dialog.provider_list.item(1).checkState(), Qt.Unchecked)

        dialog.show_providers([openrouter.Endpoint("particle-ai/us/flex", "Particle", "")])
        self.assertEqual(dialog.provider_list.count(), 2)  # the hand-typed slug stays visible
        self.assertIn("elle/yazilan", dialog.provider_list.item(1).text())
        self.assertEqual(dialog.provider_list.item(1).checkState(), Qt.Checked)

    def test_model_dialog_caps_output_to_the_selected_provider(self):
        dialog = ModelDialog("x-ai/grok", {})
        dialog.show_providers(
            [
                openrouter.Endpoint("particle-ai/us/flex", "Particle", "", max_output=131072),
                openrouter.Endpoint("baseten", "Baseten", "", max_output=262144),
            ]
        )
        dialog.order.setText("particle-ai/us/flex, baseten")
        _, options = dialog.result_settings()
        self.assertEqual(options["service_tier"], "flex")
        self.assertEqual(options["max_completion_tokens"], 131072)

        dialog.order.setText("baseten")
        _, options = dialog.result_settings()
        self.assertNotIn("service_tier", options)
        self.assertEqual(options["max_completion_tokens"], 262144)

        dialog.order.setText("elle/yazilan")
        _, options = dialog.result_settings()
        self.assertNotIn("max_completion_tokens", options)

    def test_picking_a_provider_fills_and_clears_the_form(self):
        self.assertEqual(self.window.provider_combo.currentData(), "")
        self.assertTrue(self.window.provider_id.isEnabled())

        self._pick("openrouter")
        self.assertFalse(self.window.provider_id.isEnabled())
        self.assertEqual(self.window.provider_id.text(), "openrouter")
        self.assertEqual([m[0] for m in self.window._selected()], ["x/y"])

        self.window.provider_combo.setCurrentIndex(0)
        self.assertTrue(self.window.provider_id.isEnabled())
        self.assertEqual(self.window.name.text(), "")
        self.assertEqual(self.window.table.rowCount(), 0)

    def test_language_switch_updates_the_ui(self):
        combo = self.window.language_combo
        with mock.patch("ui.main_window.QSettings"):
            combo.setCurrentIndex(combo.findData("en"))
            self.assertEqual(self.window.tabs.tabText(0), "Provider")
            self.assertEqual(self.window.fetch_button.text(), "Fetch models")
            self.assertEqual(self.window.save_button.text(), "Add to configuration")
            self.assertEqual(ModelDialog("x-ai/grok", {}).windowTitle(), "Model settings")
            self.assertEqual(self.window.config_hint.text()[:1], "A")

            combo.setCurrentIndex(combo.findData("tr"))
        self.assertEqual(self.window.tabs.tabText(0), "Sağlayıcı")
        self.assertEqual(self.window.fetch_button.text(), "Modelleri Getir")


if __name__ == "__main__":
    unittest.main()
