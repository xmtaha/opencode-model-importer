"""Per-model OpenRouter-style settings: variant suffix and provider routing."""

import json
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from services import openrouter
from ui.worker import Worker
from utils.i18n import tr

VARIANTS = ["", ":free", ":nitro", ":floor", ":online", ":thinking", ":extended"]


def split_variant(model_id: str) -> tuple[str, str]:
    """'x-ai/grok:floor' -> ('x-ai/grok', ':floor')."""
    head, sep, tail = model_id.rpartition(":")
    if sep and "/" not in tail and tail:
        return head, ":" + tail
    return model_id, ""


class ModelDialog(QDialog):
    def __init__(self, model_id: str, options: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Model ayarları"))
        self.setMinimumWidth(560)
        self.base, suffix = split_variant(model_id)
        self.options = deepcopy(options)
        self.worker = None
        self.endpoints: dict[str, openrouter.Endpoint] = {}

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.variant = QComboBox()
        self.variant.setEditable(True)
        self.variant.addItems(VARIANTS)
        self.variant.setCurrentText(suffix)
        self.variant.setToolTip(tr(":floor en ucuz sağlayıcıya yönlendirir; :free ücretsiz, :nitro en hızlı."))
        self.variant.currentTextChanged.connect(self._refresh_preview)

        self.order = QLineEdit()
        provider = self.options.get("provider") if isinstance(self.options.get("provider"), dict) else {}
        order = provider.get("order") if isinstance(provider.get("order"), list) else []
        self.order.setText(", ".join(str(item) for item in order))
        self.order.setCursorPosition(0)
        self.order.setPlaceholderText(tr("örn. particle-ai/us/flex, baseten"))
        self.order.setToolTip(tr("OpenRouter sağlayıcı slug'ları; soldan sağa denenir"))
        self.order.textChanged.connect(self._sync_checks)

        self.fetch_button = QPushButton(tr("Sağlayıcıları getir"))
        self.fetch_button.setToolTip(tr("Bu modeli OpenRouter'da hangi sağlayıcıların sunduğunu listeler"))
        self.fetch_button.clicked.connect(self.fetch_providers)
        order_row = QHBoxLayout()
        order_row.setContentsMargins(0, 0, 0, 0)
        order_row.addWidget(self.order, 1)
        order_row.addWidget(self.fetch_button)

        self.provider_note = QLabel("")
        self.provider_note.setObjectName("hint")
        self.provider_note.setWordWrap(True)
        self.provider_list = QListWidget()
        self.provider_list.setMinimumHeight(140)
        self.provider_list.setMaximumHeight(190)
        self.provider_list.setVisible(False)
        self.provider_list.itemChanged.connect(self._toggle_provider)

        self.fallback = QComboBox()
        self.fallback.setToolTip(
            tr("İzin verme: seçili sağlayıcı uygun değilse (bağlam/çıktı limiti, hesap kısıtı) istek başarısız olur")
        )
        self.fallback.addItem(tr("Varsayılan (yazılmaz)"), None)
        self.fallback.addItem(tr("İzin ver"), True)
        self.fallback.addItem(tr("İzin verme"), False)
        current = provider.get("allow_fallbacks")
        self.fallback.setCurrentIndex(1 if current is True else 2 if current is False else 0)
        self.fallback.currentIndexChanged.connect(self._refresh_preview)

        form.addRow("Model", QLabel(model_id))
        form.addRow(tr("Varyant"), self.variant)
        form.addRow(tr("Sağlayıcı sırası"), order_row)
        form.addRow("Fallback", self.fallback)

        self.preview = QLabel()
        self.preview.setObjectName("hint")
        self.preview.setWordWrap(True)
        self.preview.setTextInteractionFlags(Qt.TextSelectableByMouse)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)
        layout.addLayout(form)
        layout.addWidget(self.provider_note)
        layout.addWidget(self.provider_list)
        layout.addWidget(self.preview)
        layout.addWidget(buttons)
        self._refresh_preview()

    def variant_text(self) -> str:
        text = self.variant.currentText().strip()
        if not text:
            return ""
        return text if text.startswith(":") else ":" + text

    def model_id(self) -> str:
        return self.base + self.variant_text()

    def _order_list(self) -> list[str]:
        return [part.strip() for part in self.order.text().split(",") if part.strip()]

    def result_settings(self) -> tuple[str, dict]:
        """(model ID, options object) — empty options are left out entirely."""
        options = deepcopy(self.options)
        provider = options.get("provider")
        if not isinstance(provider, dict):
            provider = {}
        order = self._order_list()
        if order:
            provider["order"] = order
        else:
            provider.pop("order", None)
        fallback = self.fallback.currentData()
        if fallback is None:
            provider.pop("allow_fallbacks", None)
        else:
            provider["allow_fallbacks"] = fallback
        if provider:
            options["provider"] = provider
        else:
            options.pop("provider", None)

        if order:
            tier = next(
                (tag.rsplit("/", 1)[-1] for tag in order if tag.rsplit("/", 1)[-1] in ("flex", "priority")),
                "",
            )
            if tier:
                options["service_tier"] = tier
            else:
                options.pop("service_tier", None)
            cap = self._output_cap(order)
            if cap is not None:
                options["max_completion_tokens"] = cap
        else:
            options.pop("service_tier", None)
            options.pop("max_completion_tokens", None)
        return self.model_id(), options

    def _output_cap(self, order: list[str]) -> int | None:
        """Lowest max output of the selected providers, or None when a slug is unknown."""
        if any(tag not in self.endpoints for tag in order):
            return None
        limits = [self.endpoints[tag].max_output for tag in order]
        if any(limit is None for limit in limits):
            return None
        return min(limits)

    # --- OpenRouter provider picker --------------------------------------

    def fetch_providers(self):
        if self.worker is not None:
            return
        self.fetch_button.setEnabled(False)
        self.provider_note.setText(tr("Sağlayıcılar getiriliyor…"))
        worker = Worker(lambda: openrouter.fetch_endpoints(self.base))
        self.worker = worker
        worker.done.connect(self.show_providers)
        worker.failed.connect(self._providers_failed)
        worker.finished.connect(self._worker_done)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _worker_done(self):
        self.worker = None

    def _providers_failed(self, message: str):
        self.fetch_button.setEnabled(True)
        self.provider_note.setText(message)

    def show_providers(self, endpoints: list):
        self.fetch_button.setEnabled(True)
        self.endpoints = {endpoint.tag: endpoint for endpoint in endpoints}
        selected = set(self._order_list())
        self.provider_list.blockSignals(True)
        self.provider_list.clear()
        for endpoint in endpoints:
            self._add_provider(endpoint.name, endpoint.tag, endpoint.detail, endpoint.tag in selected)
        known = {endpoint.tag for endpoint in endpoints}
        for tag in self._order_list():
            if tag not in known:  # typed by hand or absent from this model's endpoint list
                self._add_provider(tag, tag, tr("Elle yazıldı"), True)
        self.provider_list.blockSignals(False)
        self.provider_list.setVisible(bool(self.provider_list.count()))
        self.provider_note.setText(
            tr("{count} sağlayıcı · işaretledikleriniz sıraya eklenir").format(count=len(endpoints))
        )
        self._refresh_preview()

    def _add_provider(self, name: str, tag: str, detail: str, checked: bool):
        item = QListWidgetItem(f"{name} — {tag}")
        item.setData(Qt.UserRole, tag)
        item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        item.setToolTip(detail or tag)
        self.provider_list.addItem(item)

    def _toggle_provider(self, item: QListWidgetItem):
        tag = item.data(Qt.UserRole)
        order = self._order_list()
        if item.checkState() == Qt.Checked:
            if tag not in order:
                order.append(tag)
        else:
            order = [name for name in order if name != tag]
        self.order.setText(", ".join(order))

    def _sync_checks(self):
        selected = set(self._order_list())
        self.provider_list.blockSignals(True)
        for row in range(self.provider_list.count()):
            item = self.provider_list.item(row)
            item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in selected else Qt.Unchecked)
        self.provider_list.blockSignals(False)
        self._refresh_preview()

    def _refresh_preview(self, *_):
        _, options = self.result_settings()
        self.preview.setText(
            f'"body": {json.dumps(options, ensure_ascii=False)}' if options else tr("Ek ayar yazılmayacak.")
        )
